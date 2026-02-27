"""
Lambda 1: create_order
触发方式: API Gateway POST /orders
职责: 验证请求 → 写入 RDS → 发消息到 SQS → 返回 201

工作流程:
  API Gateway → handler() → get_adapter() → create_order() → SQS.send_message()
  (和本地 Django OrderCreateView 调用的是完全一样的 service 函数)
"""

import os
import sys
import json

# ── 第一步：告诉 Python 去哪找 Django 项目 ────────────────────────────────
# Lambda 打包时，backend/ 目录下的所有文件会被放到 /var/task/
# sys.path 里加上 /var/task 就能 import config.settings / careplan.services 等
sys.path.insert(0, '/var/task')

# ── 第二步：初始化 Django（只激活 ORM，不启动 Web 服务器）────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()   # 这一行让 Order.objects.get() 等 ORM 操作变得可用

# ── 第三步：导入业务逻辑（和 Django View 用的完全一样）──────────────────
from careplan.intake import get_adapter
from careplan.services import create_order
from careplan.exceptions import BaseAppException
from careplan.serializers import serialize_order_created


def handler(event, context):
    """
    Lambda 入口函数，格式固定：handler(event, context)

    event 来自 API Gateway，结构：
    {
        "body": '{"patient": {...}, "medication": {...}}',   ← 字符串！
        "headers": {"X-Order-Source": "clinic_b", "Content-Type": "application/json"},
        "httpMethod": "POST"
    }
    """
    try:
        # 1. 从 event 里取 headers
        headers = event.get('headers') or {}

        # API Gateway 有时把 header key 全转小写，做兼容处理
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

        # 2. 取 body（API Gateway 传来的 body 是字符串，需要转成 bytes）
        body = event.get('body', '')
        if isinstance(body, str):
            body = body.encode('utf-8')

        # 3. 调用 intake adapter（和本地 Django View 第 44-45 行完全一样）
        adapter = get_adapter(source, body, content_type)
        internal_order = adapter.process()   # parse → transform → validate

        # 4. 调用 create_order（写 DB + 发 SQS）
        order = create_order(internal_order)

        # 5. 返回 API Gateway 格式的响应（必须有 statusCode + body）
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(serialize_order_created(order), default=str),
        }

    except BaseAppException as exc:
        # 业务异常（重复订单、NPI 冲突等）→ 返回对应 HTTP 状态码
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
        # 未预期异常 → 500，同时打印到 CloudWatch
        print(f"[create_order] Unexpected error: {exc}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error', 'detail': str(exc)}),
        }
