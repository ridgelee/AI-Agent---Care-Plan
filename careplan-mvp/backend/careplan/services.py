import os
from datetime import date
from django.utils import timezone
from django.db.models import Q
import anthropic

from .models import Patient, Provider, Order, CarePlan
from .exceptions import BlockError, WarningError, ValidationError


def check_provider_duplicate(provider_data):
    """
    Provider 重复检测。
    - NPI 相同 + 名字相同 → 返回现有 provider
    - NPI 相同 + 名字不同 → 阻止 (409)
    - 不存在 → 返回 None
    """
    npi = provider_data['npi']
    name = provider_data['name']

    try:
        existing = Provider.objects.get(npi=npi)
    except Provider.DoesNotExist:
        return None

    if existing.name == name:
        return existing

    raise BlockError(
        message=f"NPI {npi} 已注册给 '{existing.name}'，不能用于 '{name}'。NPI 是国家唯一执照号，请核实。",
        code='NPI_CONFLICT',
        detail={'npi': npi, 'existing_name': existing.name, 'submitted_name': name},
    )


def check_patient_duplicate(patient_data):
    """
    Patient 重复检测。返回 (patient_or_None, warnings_list)。
    - MRN 相同 + 名字和DOB都相同 → 复用现有
    - MRN 相同 + 名字或DOB不同 → 收集警告
    - 名字+DOB 相同 + MRN 不同 → 收集警告
    """
    mrn = patient_data['mrn']
    first_name = patient_data['first_name']
    last_name = patient_data['last_name']
    dob = patient_data['dob']
    if isinstance(dob, str):
        dob = date.fromisoformat(dob)

    warnings = []

    try:
        existing = Patient.objects.get(mrn=mrn)
        name_match = (existing.first_name == first_name and existing.last_name == last_name)
        dob_match = (existing.dob == dob)

        if name_match and dob_match:
            return existing, warnings

        diffs = []
        if not name_match:
            diffs.append(f"姓名: 库中='{existing.first_name} {existing.last_name}', 提交='{first_name} {last_name}'")
        if not dob_match:
            diffs.append(f"DOB: 库中='{existing.dob}', 提交='{dob}'")
        warnings.append({
            'code': 'MRN_INFO_MISMATCH',
            'message': f"MRN {mrn} 已存在但信息不一致: {'; '.join(diffs)}。将复用现有患者记录。",
        })
        return existing, warnings

    except Patient.DoesNotExist:
        pass

    name_dob_matches = Patient.objects.filter(
        first_name=first_name,
        last_name=last_name,
        dob=dob,
    )
    if name_dob_matches.exists():
        matched = name_dob_matches.first()
        warnings.append({
            'code': 'POSSIBLE_DUPLICATE_PATIENT',
            'message': (
                f"患者 '{first_name} {last_name}' (DOB: {dob}) 已存在，MRN={matched.mrn}，"
                f"但本次提交 MRN={mrn}。将创建新患者记录。"
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

    existing_orders = Order.objects.filter(
        patient=patient,
        medication_name=medication_name,
    )

    if not existing_orders.exists():
        return warnings

    same_day = existing_orders.filter(created_at__date=today)
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
    print(f"[DEBUG][build_prompt] 进入 build_prompt()")

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
Medication History: {', '.join(order.medication_history) if order.medication_history else 'None'}
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

    print(f"[DEBUG][build_prompt] prompt 构建完成，长度 = {len(prompt)}")
    return prompt


def call_llm(prompt):
    """Call Anthropic API to generate care plan"""
    print(f"[DEBUG][call_llm] 进入 call_llm()")

    api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY not set")

    print(f"[DEBUG][call_llm] API key 已获取")

    client = anthropic.Anthropic(api_key=api_key)

    print(f"[DEBUG][call_llm] 发送请求到 Anthropic API...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system="You are an expert clinical pharmacist specializing in specialty pharmacy care plans.",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    print(f"[DEBUG][call_llm] 收到 API 响应")

    return response.content[0].text, "claude-sonnet-4-20250514"


def create_order(data):
    """
    Create patient, provider, order and submit Celery task.
    Returns order.
    Raises BlockError / WarningError — View 层不需要处理，exception_handler 统一兜底。
    """
    print("\n" + "="*60)
    print(f"[DEBUG][create_order] 进入 create_order()")

    warnings = []

    # --- Provider 重复检测（BlockError on conflict）---
    provider_data = data['provider']
    provider = check_provider_duplicate(provider_data)
    if provider is None:
        provider = Provider.objects.create(
            npi=provider_data['npi'],
            name=provider_data['name'],
        )
    print(f"[DEBUG][create_order] Provider 完成，provider.id = {provider.id}, provider.npi = {provider.npi}")

    # --- Patient 重复检测 ---
    patient_data = data['patient']
    patient, patient_warnings = check_patient_duplicate(patient_data)
    warnings.extend(patient_warnings)
    if patient is None:
        patient = Patient.objects.create(
            mrn=patient_data['mrn'],
            first_name=patient_data['first_name'],
            last_name=patient_data['last_name'],
            dob=patient_data['dob'],
        )
    print(f"[DEBUG][create_order] Patient 完成，patient.id = {patient.id}, patient.mrn = {patient.mrn}")

    # --- Order 重复检测（BlockError on same-day）---
    medication = data['medication']
    confirm = data.get('confirm', False)
    order_warnings = check_order_duplicate(patient, medication['name'], confirm=confirm)
    warnings.extend(order_warnings)

    # 有警告且用户未确认 → 抛 WarningError，让 exception_handler 统一返回
    if warnings and not confirm:
        raise WarningError(
            message='检测到潜在重复，请确认后重新提交（传 confirm=true）。',
            detail={'warnings': warnings},
        )

    # Create order
    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication_name=medication['name'],
        primary_diagnosis=medication['primary_diagnosis'],
        additional_diagnoses=medication.get('additional_diagnoses', []),
        medication_history=medication.get('medication_history', []),
        patient_records=data.get('patient_records', ''),
        status='pending'
    )
    print(f"[DEBUG][create_order] Order 创建完成，order.id = {order.id}, order.status = {order.status}")

    # 通过 Celery 异步分发任务
    from careplan.tasks import generate_care_plan
    print(f"[DEBUG][create_order] 将 order_id 提交给 Celery...")
    generate_care_plan.delay(str(order.id))
    print(f"[DEBUG][create_order] 已提交 Celery 任务")
    print("="*60 + "\n")

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
    order = get_order_detail(order_id)  # reuse, raises 404

    if order.status != 'completed':
        raise ValidationError(
            message='Care plan not ready yet',
            code='CAREPLAN_NOT_READY',
            detail={'order_id': str(order_id), 'current_status': order.status},
        )

    return order


def search_orders(query):
    """Search orders by query string. Returns queryset."""
    orders = Order.objects.filter(
        Q(id__icontains=query) |
        Q(medication_name__icontains=query) |
        Q(patient__mrn__icontains=query) |
        Q(patient__first_name__icontains=query) |
        Q(patient__last_name__icontains=query)
    ).select_related('patient').order_by('-created_at')[:20]

    return orders
