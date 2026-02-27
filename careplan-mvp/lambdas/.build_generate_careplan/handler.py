"""
Lambda 2: generate_careplan
触发方式: SQS（careplan-queue 队列有消息时自动触发）
职责: 从 SQS 读 order_id → 调 LLM → 更新 RDS

工作流程:
  SQS → handler() → build_prompt() → llm.complete() → 写 CarePlan 到 RDS

和本地 Celery 的对比:
  本地: @shared_task generate_care_plan(order_id) 被 Redis 触发
  Lambda: handler(event, context) 被 SQS 触发，event['Records'] 就是消息列表
  核心逻辑（build_prompt + llm.complete + 写 DB）完全一样
"""

import os
import sys
import json
import time
import logging

sys.path.insert(0, '/var/task')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.utils import timezone
from careplan.models import Order, CarePlan
from careplan.services import build_prompt, SYSTEM_PROMPT
from careplan.llm import get_llm_service

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _process_single_order(order_id: str):
    """
    处理单条 order 的核心逻辑。
    和 tasks.py 里的 generate_care_plan 做完全一样的事，只是不需要 Celery 装饰器。
    """
    logger.info("[generate_careplan] 开始处理 order_id=%s", order_id)

    # 1. 查 Order（如果不存在就跳过，不重试）
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("[generate_careplan] Order %s 不存在，跳过", order_id)
        return  # 不抛异常，让 SQS 把这条消息标记为成功（避免死循环重试）

    # 2. 标记为处理中
    order.status = 'processing'
    order.save(update_fields=['status', 'updated_at'])

    # 3. 构建 Prompt（直接调 services.py 里的 build_prompt，一行不改）
    prompt = build_prompt(order)
    logger.info("[generate_careplan] Prompt 构建完成，长度=%d", len(prompt))

    # 4. 调用 LLM（直接调 llm/ 目录里的 service，一行不改）
    llm = get_llm_service()
    llm_start = time.time()

    response = llm.complete(SYSTEM_PROMPT, prompt)
    content, model = response.content, response.model

    logger.info(
        "[generate_careplan] LLM 调用成功 model=%s duration=%.2fs",
        model, time.time() - llm_start
    )

    # 5. 写入 CarePlan（同 tasks.py 第 137-143 行）
    CarePlan.objects.filter(order=order).delete()
    CarePlan.objects.create(
        order=order,
        content=content,
        llm_model=model,
        llm_prompt_version='1.0',
    )

    # 6. 更新 Order 状态为 completed
    order.status = 'completed'
    order.completed_at = timezone.now()
    order.save(update_fields=['status', 'completed_at', 'updated_at'])

    logger.info("[generate_careplan] order_id=%s 处理完成", order_id)


def handler(event, context):
    """
    Lambda 入口函数。

    SQS 触发时，event 结构：
    {
        "Records": [
            {
                "body": '{"order_id": "abc-123-..."}',   ← create_order 发的消息
                "messageId": "...",
                "receiptHandle": "..."
            }
        ]
    }

    SQS 可能一次批量发多条消息（BatchSize），所以用 for 循环处理每条。
    如果某条处理失败，把它的 messageId 加入 batchItemFailures，
    SQS 会单独重试这条，不影响其他成功的消息。
    """
    records = event.get('Records', [])
    logger.info("[generate_careplan] 收到 %d 条 SQS 消息", len(records))

    # 用于记录处理失败的消息（SQS 部分失败重试机制）
    batch_item_failures = []

    for record in records:
        message_id = record.get('messageId', 'unknown')

        try:
            # 解析 SQS 消息体（create_order 发来的 JSON）
            body = json.loads(record['body'])
            order_id = body['order_id']

            _process_single_order(order_id)

        except Exception as exc:
            logger.error(
                "[generate_careplan] 处理 messageId=%s 失败: %s",
                message_id, str(exc)
            )
            # 把失败的消息 ID 加入列表，SQS 会重试这条消息
            batch_item_failures.append({'itemIdentifier': message_id})

            # 同时把 Order 标记为 failed（如果能拿到 order_id 的话）
            try:
                order_id = json.loads(record['body'])['order_id']
                order = Order.objects.get(id=order_id)
                order.status = 'failed'
                order.error_message = str(exc)
                order.save(update_fields=['status', 'error_message', 'updated_at'])
            except Exception:
                pass  # 连标记失败都出错了，让 SQS 重试

    # 返回失败列表（为空表示全部成功，SQS 会删除这批消息）
    return {'batchItemFailures': batch_item_failures}
