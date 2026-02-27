"""
Lambda 3: get_order
触发方式: API Gateway GET /orders/{order_id}
职责: 从路径参数取 order_id → 查 RDS → 返回订单详情（含 CarePlan）

工作流程:
  API Gateway → handler() → get_order_detail() → serialize_order_detail() → 返回 JSON
  (和本地 Django OrderDetailView 调用的是完全一样的 service 函数)
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
    """
    Lambda 入口函数。

    API Gateway GET /orders/{order_id} 触发时，event 结构：
    {
        "pathParameters": {"order_id": "abc-123-..."},
        "httpMethod": "GET"
    }
    """
    try:
        # 1. 从路径参数里取 order_id
        path_params = event.get('pathParameters') or {}
        order_id = path_params.get('order_id')

        if not order_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing order_id in path'}),
            }

        # 2. 调用 service（和本地 Django OrderDetailView 第 55 行完全一样）
        order = get_order_detail(order_id)   # 找不到会抛 BlockError (404)

        # 3. 序列化并返回
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
