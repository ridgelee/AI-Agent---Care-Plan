import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,   # 初始重试延迟（秒），指数退避会乘以 2^retry_count
    acks_late=True,           # 任务执行完才 ack，防止 worker 崩溃时任务丢失
    reject_on_worker_lost=True,
)
def generate_care_plan(self, order_id: str):
    """
    异步生成 Care Plan。

    重试策略：
      - 最多重试 3 次
      - 指数退避：10s → 20s → 40s
      - 超出次数后将 order 标记为 failed
    """
    from careplan.models import Order, CarePlan
    from careplan.views import build_prompt, call_llm

    logger.info("[Celery][generate_care_plan] 开始处理 order_id=%s (attempt %d/%d)",
                order_id, self.request.retries + 1, self.max_retries + 1)

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error("[Celery] Order %s 不存在，跳过", order_id)
        return  # 不重试，直接结束

    # 标记为处理中
    order.status = 'processing'
    order.save(update_fields=['status', 'updated_at'])

    try:
        # 1. 构建 Prompt
        prompt = build_prompt(order)
        logger.info("[Celery] Prompt 构建完成，长度=%d", len(prompt))

        # 2. 调用 LLM
        content, model = call_llm(prompt)
        logger.info("[Celery] LLM 返回成功，内容前100字符: %s", content[:100])

        # 3. 写入 CarePlan（已存在则先删除，避免 OneToOne 冲突）
        CarePlan.objects.filter(order=order).delete()
        CarePlan.objects.create(
            order=order,
            content=content,
            llm_model=model,
            llm_prompt_version='1.0',
        )

        # 4. 更新 order 状态
        order.status = 'completed'
        order.completed_at = timezone.now()
        order.save(update_fields=['status', 'completed_at', 'updated_at'])

        logger.info("[Celery] order_id=%s 处理完成", order_id)

    except Exception as exc:
        logger.warning(
            "[Celery] order_id=%s 处理失败 (attempt %d): %s",
            order_id, self.request.retries + 1, str(exc)
        )

        if self.request.retries < self.max_retries:
            # 指数退避：countdown = 10 * 2^retries → 10s, 20s, 40s
            countdown = self.default_retry_delay * (2 ** self.request.retries)
            logger.info(
                "[Celery] 将在 %ds 后重试 (第 %d 次)...",
                countdown, self.request.retries + 1
            )
            # 把 order 重置回 pending，等重试
            order.status = 'pending'
            order.save(update_fields=['status', 'updated_at'])
            raise self.retry(exc=exc, countdown=countdown)
        else:
            # 全部重试耗尽，标记失败
            logger.error("[Celery] order_id=%s 已达最大重试次数，标记为 failed", order_id)
            order.status = 'failed'
            order.error_message = f"[重试 {self.max_retries} 次后仍失败] {str(exc)}"
            order.save(update_fields=['status', 'error_message', 'updated_at'])
