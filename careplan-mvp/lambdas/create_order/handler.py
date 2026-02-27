"""
Lambda 1: create_order
Trigger: API Gateway POST /orders
"""
import os
import sys
import json

sys.path.insert(0, '/var/task')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from careplan.intake import get_adapter
from careplan.services import create_order
from careplan.exceptions import BaseAppException
from careplan.serializers import serialize_order_created


def handler(event, context):
    try:
        headers = event.get('headers') or {}
        source = (
            headers.get('X-Order-Source')
            or headers.get('x-order-source')
            or 'clinic_b'
        )
        content_type = (
            headers.get('Content-Type')
            or headers.get('content-type')
            or 'application/json'
        )

        body = event.get('body', '')
        if isinstance(body, str):
            body = body.encode('utf-8')

        adapter = get_adapter(source, body, content_type)
        internal_order = adapter.process()
        order = create_order(internal_order)

        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(serialize_order_created(order), default=str),
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
        print(f"[create_order] Unexpected error: {exc}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'detail': str(exc)}),
        }
