"""
Response serializers — ORM 对象 → JSON-able dict。

只负责「输出格式化」，不做任何解析或校验。
输入解析和校验已移至 careplan/intake/ adapter 系统。
"""


def serialize_order_created(order):
    """Serialize order for 201 creation response."""
    return {
        'order_id': str(order.id),
        'status': 'pending',
        'message': 'Order received. Care Plan generation queued.',
        'created_at': order.created_at.isoformat(),
    }


def serialize_order_detail(order):
    """Serialize order detail with status-dependent fields."""
    response = {
        'order_id': str(order.id),
        'status': order.status,
        'patient': {
            'name': f"{order.patient.first_name} {order.patient.last_name}",
            'mrn': order.patient.mrn,
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
            'download_url': f'/api/orders/{order.id}/download',
        }
    elif order.status == 'failed':
        response['message'] = 'Care Plan generation failed'
        response['error'] = {
            'message': order.error_message,
            'retry_allowed': True,
        }

    return response


def serialize_search_results(orders):
    """Serialize search results list."""
    results = [
        {
            'order_id': str(order.id),
            'status': order.status,
            'patient_name': f"{order.patient.first_name} {order.patient.last_name}",
            'patient_mrn': order.patient.mrn,
            'medication': order.medication_name,
            'created_at': order.created_at.isoformat(),
        }
        for order in orders
    ]
    return {
        'count': len(results),
        'orders': results,
    }
