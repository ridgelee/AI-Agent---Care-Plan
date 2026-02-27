"""
Lambda 3: get_order
Trigger: API Gateway GET /orders/{order_id}
"""
import os
import sys
import json

sys.path.insert(0, '/var/task')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from careplan.services import get_order_detail
from careplan.exceptions import BaseAppException
from careplan.serializers import serialize_order_detail


def handler(event, context):
    try:
        path_params = event.get('pathParameters') or {}
        order_id = path_params.get('order_id')

        if not order_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing order_id in path'}),
            }

        order = get_order_detail(order_id)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(serialize_order_detail(order), default=str),
        }

    except BaseAppException as exc:
        body = {
            'type': exc.type,
            'code': exc.code,
            'message': exc.message,
        }
        if exc.detail is not None:
            body['detail'] = exc.detail
        return {
            'statusCode': exc.http_status,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(body),
        }

    except Exception as exc:
        print(f"[get_order] Unexpected error: {exc}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'detail': str(exc)}),
        }
