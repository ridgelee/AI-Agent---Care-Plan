import json


def parse_order_request(request):
    """Parse JSON body from request into dict."""
    data = json.loads(request.body)
    print(f"[DEBUG][serializers.py][parse_order_request] bytes → dict, keys={list(data.keys())}")
    return data


def serialize_order_created(order):
    """Serialize order for 201 creation response."""
    result = {
        'order_id': str(order.id),
        'status': 'pending',
        'message': 'Order received. Care Plan generation queued.',
        'created_at': order.created_at.isoformat()
    }
    print(f"[DEBUG][serializers.py][serialize_order_created] Order ORM → dict, order_id={result['order_id']}")
    return result


def serialize_order_detail(order):
    """Serialize order detail with status-dependent fields."""
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

    return response


def serialize_order_not_found(order_id):
    """Serialize 404 response for order not found."""
    return {
        'status': 'error',
        'message': 'Order not found',
        'order_id': str(order_id)
    }


def serialize_search_results(orders):
    """Serialize search results list."""
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

    return {
        'count': len(results),
        'orders': results
    }
