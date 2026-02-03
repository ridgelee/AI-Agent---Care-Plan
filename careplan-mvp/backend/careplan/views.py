import os
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
import json
import anthropic
import threading

from .models import Patient, Provider, Order, CarePlan


def build_prompt(order):
    """Build LLM prompt for care plan generation"""
    return f"""You are an expert clinical pharmacist creating a Care Plan for a specialty pharmacy patient.

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


def call_llm(prompt):
    """Call Anthropic API to generate care plan"""
    api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system="You are an expert clinical pharmacist specializing in specialty pharmacy care plans.",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.content[0].text, "claude-sonnet-4-20250514"


def generate_care_plan_async(order_id):
    """Background task to generate care plan"""
    import django
    django.setup()

    from .models import Order, CarePlan

    try:
        order = Order.objects.get(id=order_id)

        # Update to processing
        order.status = 'processing'
        order.save()

        # Generate care plan
        prompt = build_prompt(order)
        content, model = call_llm(prompt)

        # Create care plan
        CarePlan.objects.create(
            order=order,
            content=content,
            llm_model=model,
            llm_prompt_version='1.0'
        )

        # Update order to completed
        order.status = 'completed'
        order.completed_at = timezone.now()
        order.save()

    except Exception as e:
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
        data = json.loads(request.body)

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

        # Get or create provider
        provider_data = data['provider']
        provider, _ = Provider.objects.get_or_create(
            npi=provider_data['npi'],
            defaults={'name': provider_data['name']}
        )

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

        # Start background thread to generate care plan
        thread = threading.Thread(target=generate_care_plan_async, args=(order.id,))
        thread.daemon = True
        thread.start()

        # Return immediately with order_id
        return JsonResponse({
            'order_id': str(order.id),
            'status': 'pending',
            'message': 'Order created successfully. Care Plan generation started.',
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
