"""
Lambda 2: generate_careplan
Trigger: SQS (careplan-queue)
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
    logger.info("[generate_careplan] start order_id=%s", order_id)

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("[generate_careplan] order %s not found, skipping", order_id)
        return

    order.status = 'processing'
    order.save(update_fields=['status', 'updated_at'])

    prompt = build_prompt(order)
    logger.info("[generate_careplan] prompt built, length=%d", len(prompt))

    llm = get_llm_service()
    llm_start = time.time()

    response = llm.complete(SYSTEM_PROMPT, prompt)
    content, model = response.content, response.model

    logger.info(
        "[generate_careplan] LLM done model=%s duration=%.2fs",
        model, time.time() - llm_start
    )

    CarePlan.objects.filter(order=order).delete()
    CarePlan.objects.create(
        order=order,
        content=content,
        llm_model=model,
        llm_prompt_version='1.0',
    )

    order.status = 'completed'
    order.completed_at = timezone.now()
    order.save(update_fields=['status', 'completed_at', 'updated_at'])

    logger.info("[generate_careplan] order_id=%s completed", order_id)


def handler(event, context):
    records = event.get('Records', [])
    logger.info("[generate_careplan] received %d SQS messages", len(records))

    batch_item_failures = []

    for record in records:
        message_id = record.get('messageId', 'unknown')
        try:
            body = json.loads(record['body'])
            order_id = body['order_id']
            _process_single_order(order_id)

        except Exception as exc:
            logger.error("[generate_careplan] failed messageId=%s: %s", message_id, str(exc))
            batch_item_failures.append({'itemIdentifier': message_id})

            try:
                order_id = json.loads(record['body'])['order_id']
                order = Order.objects.get(id=order_id)
                order.status = 'failed'
                order.error_message = str(exc)
                order.save(update_fields=['status', 'error_message', 'updated_at'])
            except Exception:
                pass

    return {'batchItemFailures': batch_item_failures}
