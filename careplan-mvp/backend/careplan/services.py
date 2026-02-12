import os
from django.utils import timezone
from django.db.models import Q
import anthropic

from .models import Patient, Provider, Order, CarePlan


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
    """Create patient, provider, order and submit Celery task. Returns order."""
    print("\n" + "="*60)
    print(f"[DEBUG][create_order] 进入 create_order()")

    # Get or create patient
    patient_data = data['patient']
    patient, _ = Patient.objects.get_or_create(
        mrn=patient_data['mrn'],
        defaults={
            'first_name': patient_data['first_name'],
            'last_name': patient_data['last_name'],
            'dob': patient_data['dob'],
        }
    )
    print(f"[DEBUG][create_order] Patient 创建/获取完成，patient.id = {patient.id}, patient.mrn = {patient.mrn}")

    # Get or create provider
    provider_data = data['provider']
    provider, _ = Provider.objects.get_or_create(
        npi=provider_data['npi'],
        defaults={'name': provider_data['name']}
    )
    print(f"[DEBUG][create_order] Provider 创建/获取完成，provider.id = {provider.id}, provider.npi = {provider.npi}")

    # Create order with pending status
    medication = data['medication']
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
    """Get order by ID. Returns Order or None."""
    try:
        return Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return None


def get_care_plan_download(order_id):
    """Get order for download. Returns (order, error_msg, status_code) tuple."""
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return None, 'Order not found', 404

    if order.status != 'completed':
        return None, 'Care plan not ready', 400

    return order, None, None


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
