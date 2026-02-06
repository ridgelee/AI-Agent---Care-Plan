import os
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db.models import Q
import json
import anthropic
import redis

from .models import Patient, Provider, Order, CarePlan

# Redis connection
_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(redis_url)
    return _redis_client


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


def generate_care_plan_async(order_id):
    """Background task to generate care plan"""
    print("\n" + "="*60)
    print(f"[DEBUG][generate_care_plan_async] 进入后台线程 generate_care_plan_async()")
    print(f"[DEBUG][generate_care_plan_async] order_id = {order_id}")

    import django
    django.setup()

    from .models import Order, CarePlan

    try:
        order = Order.objects.get(id=order_id)
        print(f"[DEBUG][generate_care_plan_async] 获取 order 成功，order.id = {order.id}")

        # Update to processing
        order.status = 'processing'
        order.save()
        print(f"[DEBUG][generate_care_plan_async] 状态已更新为 processing")

        # Generate care plan
        print(f"[DEBUG][generate_care_plan_async] 准备调用 build_prompt()")
        prompt = build_prompt(order)
        print(f"[DEBUG][generate_care_plan_async] prompt 前200字符 = {prompt[:200]}...")

        print(f"[DEBUG][generate_care_plan_async] 准备调用 call_llm() -> Anthropic API")
        content, model = call_llm(prompt)
        print(f"[DEBUG][generate_care_plan_async] LLM 返回成功")
        print(f"[DEBUG][generate_care_plan_async] 返回内容前100字符 = {content[:100]}...")

        # Create care plan
        CarePlan.objects.create(
            order=order,
            content=content,
            llm_model=model,
            llm_prompt_version='1.0'
        )
        print(f"[DEBUG][generate_care_plan_async] CarePlan 已创建")

        # Update order to completed
        order.status = 'completed'
        order.completed_at = timezone.now()
        order.save()
        print(f"[DEBUG][generate_care_plan_async] 状态已更新为 completed")
        print("="*60 + "\n")

    except Exception as e:
        print(f"[DEBUG][generate_care_plan_async][ERROR] {str(e)}")
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'failed'
            order.error_message = str(e)
            order.save()
        except:
            pass


@method_decorator(csrf_exempt, name='dispatch')
class OrderCreateView(View):
    """POST /api/orders/ - Create order and start async care plan generation"""

    def post(self, request):
        print("\n" + "="*60)
        print(f"[DEBUG][OrderCreateView.post] 进入 OrderCreateView.post()")

        data = json.loads(request.body)
        print(f"[DEBUG][OrderCreateView.post] 收到的原始数据 = {data}")

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
        print(f"[DEBUG][OrderCreateView.post] Patient 创建/获取完成，patient.id = {patient.id}, patient.mrn = {patient.mrn}")

        # Get or create provider
        provider_data = data['provider']
        provider, _ = Provider.objects.get_or_create(
            npi=provider_data['npi'],
            defaults={'name': provider_data['name']}
        )
        print(f"[DEBUG][OrderCreateView.post] Provider 创建/获取完成，provider.id = {provider.id}, provider.npi = {provider.npi}")

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
        print(f"[DEBUG][OrderCreateView.post] Order 创建完成，order.id = {order.id}, order.status = {order.status}")

        # Push order_id to Redis queue for async processing
        print(f"[DEBUG][OrderCreateView.post] 将 order_id 放入 Redis 队列...")
        r = get_redis_client()
        r.lpush('careplan_queue', str(order.id))
        print(f"[DEBUG][OrderCreateView.post] 已放入 Redis 队列 careplan_queue")

        # Return immediately with order_id
        print(f"[DEBUG][OrderCreateView.post] 返回响应给前端")
        print("="*60 + "\n")
        return JsonResponse({
            'order_id': str(order.id),
            'status': 'pending',
            'message': 'Order received. Care Plan generation queued.',
            'created_at': order.created_at.isoformat()
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class OrderDetailView(View):
    """GET /api/orders/<order_id>/ - Get order status and care plan"""

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Order not found',
                'order_id': str(order_id)
            }, status=404)

        response = {
            'order_id': str(order.id),
            'status': order.status,
            'patient': {
                'name': f"{order.patient.first_name} {order.patient.last_name}",
                'mrn': order.patient.mrn
            },
            'medication': order.medication_name,
            'created_at': order.created_at.isoformat(),
            'updated_at': order.updated_at.isoformat(),
        }

        if order.status == 'processing':
            response['message'] = 'Care Plan is being generated, please wait...'
        elif order.status == 'pending':
            response['message'] = 'Order is queued for processing'
        elif order.status == 'completed':
            response['message'] = 'Care Plan generated successfully'
            response['completed_at'] = order.completed_at.isoformat() if order.completed_at else None
            response['care_plan'] = {
                'content': order.care_plan.content,
                'generated_at': order.care_plan.generated_at.isoformat(),
                'llm_model': order.care_plan.llm_model,
                'download_url': f'/api/orders/{order.id}/download'
            }
        elif order.status == 'failed':
            response['message'] = 'Care Plan generation failed'
            response['error'] = {
                'message': order.error_message,
                'retry_allowed': True
            }

        return JsonResponse(response)


@method_decorator(csrf_exempt, name='dispatch')
class OrderDownloadView(View):
    """GET /api/orders/<order_id>/download - Download care plan as text file"""

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)

        if order.status != 'completed':
            return JsonResponse({'error': 'Care plan not ready'}, status=400)

        content = order.care_plan.content
        filename = f"careplan_{order.patient.mrn}_{order.medication_name}_{order.created_at.strftime('%Y%m%d')}.txt"

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class OrderSearchView(View):
    """POST /api/orders/search/ - Search orders"""

    def post(self, request):
        data = json.loads(request.body)
        query = data.get('query', '').strip()

        # Build Q object for OR search
        orders = Order.objects.filter(
            Q(id__icontains=query) |
            Q(medication_name__icontains=query) |
            Q(patient__mrn__icontains=query) |
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query)
        ).select_related('patient').order_by('-created_at')[:20]

        results = []
        for order in orders:
            results.append({
                'order_id': str(order.id),
                'status': order.status,
                'patient_name': f"{order.patient.first_name} {order.patient.last_name}",
                'patient_mrn': order.patient.mrn,
                'medication': order.medication_name,
                'created_at': order.created_at.isoformat()
            })

        return JsonResponse({
            'count': len(results),
            'orders': results
        })
