import time
from datetime import date
from django.db.models import Q
from prometheus_client import Histogram, Counter

from .models import Patient, Provider, Order, CarePlan
from .exceptions import BlockError, WarningError, ValidationError
from .intake.types import InternalOrder, ProviderData, PatientData

SYSTEM_PROMPT = "You are an expert clinical pharmacist specializing in specialty pharmacy care plans."

# ── DB 查询耗时指标 ────────────────────────────────────────────────────────
#
# 打点位置：重复检测三个函数，这是每次下单都会触发的查询
# 500ms = warning 阈值，2000ms = critical 阈值
#
DB_QUERY_DURATION = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],          # operation: check_provider / check_patient_mrn /
                            #            check_patient_name_dob / check_order_history / check_order_same_day
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

DB_SLOW_QUERIES = Counter(
    'db_slow_queries_total',
    'Number of queries exceeding threshold',
    ['operation', 'level'],  # level: warning(>500ms) / critical(>2000ms)
)


def _record_query(operation: str, duration: float):
    """统一打点：记录耗时，并在超阈值时递增慢查询计数器。"""
    DB_QUERY_DURATION.labels(operation=operation).observe(duration)
    if duration > 2.0:
        DB_SLOW_QUERIES.labels(operation=operation, level='critical').inc()
    elif duration > 0.5:
        DB_SLOW_QUERIES.labels(operation=operation, level='warning').inc()


def check_provider_duplicate(provider: ProviderData):
    """
    Provider 重复检测。
    - NPI 相同 + 名字相同 → 返回现有 provider
    - NPI 相同 + 名字不同 → 阻止 (409)
    - 不存在 → 返回 None
    """
    t0 = time.time()
    try:
        existing = Provider.objects.get(npi=provider.npi)
    except Provider.DoesNotExist:
        _record_query('check_provider', time.time() - t0)
        return None
    _record_query('check_provider', time.time() - t0)

    if existing.name == provider.name:
        return existing

    raise BlockError(
        message=f"NPI {provider.npi} 已注册给 '{existing.name}'，不能用于 '{provider.name}'。NPI 是国家唯一执照号，请核实。",
        code='NPI_CONFLICT',
        detail={'npi': provider.npi, 'existing_name': existing.name, 'submitted_name': provider.name},
    )


def check_patient_duplicate(patient: PatientData):
    """
    Patient 重复检测。返回 (patient_or_None, warnings_list)。
    - MRN 相同 + 名字和DOB都相同 → 复用现有
    - MRN 相同 + 名字或DOB不同 → 收集警告
    - 名字+DOB 相同 + MRN 不同 → 收集警告
    """
    dob = date.fromisoformat(patient.dob) if isinstance(patient.dob, str) else patient.dob
    warnings = []

    # 查询 1：按 MRN 查（有 unique 索引，应极快）
    t0 = time.time()
    try:
        existing = Patient.objects.get(mrn=patient.mrn)
        _record_query('check_patient_mrn', time.time() - t0)
        name_match = (existing.first_name == patient.first_name and existing.last_name == patient.last_name)
        dob_match  = (existing.dob == dob)

        if name_match and dob_match:
            return existing, warnings

        diffs = []
        if not name_match:
            diffs.append(f"姓名: 库中='{existing.first_name} {existing.last_name}', 提交='{patient.first_name} {patient.last_name}'")
        if not dob_match:
            diffs.append(f"DOB: 库中='{existing.dob}', 提交='{dob}'")
        warnings.append({
            'code': 'MRN_INFO_MISMATCH',
            'message': f"MRN {patient.mrn} 已存在但信息不一致: {'; '.join(diffs)}。将复用现有患者记录。",
        })
        return existing, warnings

    except Patient.DoesNotExist:
        _record_query('check_patient_mrn', time.time() - t0)

    # 查询 2：按姓名+DOB 查重（现在有复合索引 patient_name_dob_idx）
    t0 = time.time()
    name_dob_matches = Patient.objects.filter(
        first_name=patient.first_name,
        last_name=patient.last_name,
        dob=dob,
    )
    _record_query('check_patient_name_dob', time.time() - t0)
    if name_dob_matches.exists():
        matched = name_dob_matches.first()
        warnings.append({
            'code': 'POSSIBLE_DUPLICATE_PATIENT',
            'message': (
                f"患者 '{patient.first_name} {patient.last_name}' (DOB: {dob}) 已存在，MRN={matched.mrn}，"
                f"但本次提交 MRN={patient.mrn}。将创建新患者记录。"
            ),
        })

    return None, warnings


def check_order_duplicate(patient, medication_name, confirm=False):
    """
    Order 重复检测。
    - 同一患者 + 同一药物 + 同一天 → 阻止 (409)
    - 同一患者 + 同一药物 + 不同天 → 收集警告（confirm=True 跳过）
    """
    warnings = []
    today = date.today()

    # 查询 1：患者历史订单（复合索引 order_patient_medication_idx）
    t0 = time.time()
    existing_orders = Order.objects.filter(
        patient=patient,
        medication_name=medication_name,
    )
    if not existing_orders.exists():
        _record_query('check_order_history', time.time() - t0)
        return warnings

    # 查询 2：今天是否已有订单（created_at 索引）
    same_day = existing_orders.filter(created_at__date=today)
    _record_query('check_order_history', time.time() - t0)

    if same_day.exists():
        order = same_day.first()
        raise BlockError(
            message=(
                f"患者 {patient.first_name} {patient.last_name} (MRN: {patient.mrn}) "
                f"今天已有 '{medication_name}' 的订单，不能重复下单。"
            ),
            code='DUPLICATE_ORDER_SAME_DAY',
            detail={'existing_order_id': str(order.id), 'patient_mrn': patient.mrn},
        )

    if not confirm:
        latest = existing_orders.order_by('-created_at').first()
        warnings.append({
            'code': 'DUPLICATE_ORDER_HISTORY',
            'message': (
                f"患者 {patient.first_name} {patient.last_name} (MRN: {patient.mrn}) "
                f"曾于 {latest.created_at.strftime('%Y-%m-%d')} 下过 '{medication_name}' 的订单。"
                f"如确认需要重复下单，请传 confirm=true。"
            ),
        })

    return warnings


def build_prompt(order):
    """Build LLM prompt for care plan generation"""
    prompt = f"""You are an expert clinical pharmacist creating a Care Plan for a specialty pharmacy patient.

Patient Information:
- Name: {order.patient.first_name} {order.patient.last_name}
- DOB: {order.patient.dob}
- MRN: {order.patient.mrn}

Provider Information:
- Name: {order.provider.name}
- NPI: {order.provider.npi}

Medication: {order.medication_name}
Primary Diagnosis: {order.primary_diagnosis}
Additional Diagnoses: {', '.join(order.additional_diagnoses) if order.additional_diagnoses else 'None'}
Medication History: {', '.join(str(h) for h in order.medication_history) if order.medication_history else 'None'}
Patient Records: {order.patient_records or 'Not provided'}

Please generate a comprehensive Care Plan with the following sections:

1. **Problem List / Drug Therapy Problems (DTPs)**
   - List potential drug therapy problems related to this medication
   - Consider adverse reactions, drug interactions, contraindications

2. **Goals (SMART)**
   - Primary therapeutic goal with specific timeframe
   - Safety goals
   - Process goals for medication adherence

3. **Pharmacist Interventions / Plan**
   - Dosing & Administration details
   - Premedication requirements if applicable
   - Infusion protocol if applicable
   - Adverse event management strategies

4. **Monitoring Plan & Lab Schedule**
   - Pre-treatment monitoring
   - During-treatment monitoring
   - Post-treatment monitoring
   - Specific lab values to track

Format the output in clear markdown with headers."""

    return prompt



def create_order(internal_order: InternalOrder):
    """
    Create patient, provider, order and submit Celery task.
    Accepts InternalOrder directly — no dict conversion needed.
    Raises BlockError / WarningError — View 层不需要处理，exception_handler 统一兜底。
    """
    warnings = []

    # --- Provider 重复检测（BlockError on conflict）---
    provider = check_provider_duplicate(internal_order.provider)
    if provider is None:
        provider = Provider.objects.create(
            npi=internal_order.provider.npi,
            name=internal_order.provider.name,
        )

    # --- Patient 重复检测 ---
    patient, patient_warnings = check_patient_duplicate(internal_order.patient)
    warnings.extend(patient_warnings)
    if patient is None:
        patient = Patient.objects.create(
            mrn=internal_order.patient.mrn,
            first_name=internal_order.patient.first_name,
            last_name=internal_order.patient.last_name,
            dob=internal_order.patient.dob,
        )

    # --- Order 重复检测（BlockError on same-day）---
    order_warnings = check_order_duplicate(
        patient,
        internal_order.medication.name,
        confirm=internal_order.confirm,
    )
    warnings.extend(order_warnings)

    # 有警告且用户未确认 → 抛 WarningError，让 exception_handler 统一返回
    if warnings and not internal_order.confirm:
        raise WarningError(
            message='检测到潜在重复，请确认后重新提交（传 confirm=true）。',
            detail={'warnings': warnings},
        )

    # Create order
    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication_name=internal_order.medication.name,
        primary_diagnosis=internal_order.medication.primary_diagnosis,
        additional_diagnoses=internal_order.medication.additional_diagnoses,
        medication_history=internal_order.medication.medication_history,
        patient_records=internal_order.patient_records,
        status='pending',
    )

    # 通过 Celery 异步分发任务
    from careplan.tasks import generate_care_plan
    generate_care_plan.delay(str(order.id))

    return order


def get_order_detail(order_id):
    """Get order by ID. Raises BlockError if not found."""
    try:
        return Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        raise BlockError(
            message='Order not found',
            code='ORDER_NOT_FOUND',
            detail={'order_id': str(order_id)},
            http_status=404,
        )


def get_care_plan_download(order_id):
    """Get order for download. Raises on not found or not ready."""
    order = get_order_detail(order_id)

    if order.status != 'completed':
        raise ValidationError(
            message='Care plan not ready yet',
            code='CAREPLAN_NOT_READY',
            detail={'order_id': str(order_id), 'current_status': order.status},
        )

    return order


def search_orders(query):
    """Search orders by query string. Returns queryset."""
    return Order.objects.filter(
        Q(id__icontains=query) |
        Q(medication_name__icontains=query) |
        Q(patient__mrn__icontains=query) |
        Q(patient__first_name__icontains=query) |
        Q(patient__last_name__icontains=query)
    ).select_related('patient').order_by('-created_at')[:20]
