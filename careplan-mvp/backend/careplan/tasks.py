import logging
import os
import time

from celery import shared_task
from django.utils import timezone
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# ── Prometheus 指标定义 ────────────────────────────────────────────────────
#
# Histogram buckets 按 LLM 延迟特点设计：
#   1s, 5s, 10s, 30s, 60s(警告), 90s, 120s(严重), 180s, 300s
#
LLM_LATENCY = Histogram(
    'llm_api_duration_seconds',
    'LLM API call duration in seconds',
    ['provider', 'model'],
    buckets=[1, 5, 10, 30, 60, 90, 120, 180, 300],
)

LLM_CALLS_TOTAL = Counter(
    'llm_api_calls_total',
    'Total number of LLM API calls',
    ['provider', 'model', 'status'],   # status: success / error
)

LLM_ERRORS_TOTAL = Counter(
    'llm_api_errors_total',
    'LLM API errors by type',
    ['provider', 'error_type'],        # error_type: rate_limit / timeout / network / unknown
)

CARE_PLAN_DURATION = Histogram(
    'care_plan_generation_seconds',
    'Total Care Plan generation time (queue wait + LLM call)',
    buckets=[5, 15, 30, 60, 90, 120, 180, 300],
)


def _classify_llm_error(exc: Exception) -> str:
    """
    根据异常类型判断错误原因：
      rate_limit  — HTTP 429 / API 配额耗尽
      timeout     — 连接或读取超时
      network     — DNS / 连接被拒等网络层错误
      unknown     — 其他
    """
    exc_name = type(exc).__name__
    exc_str  = str(exc).lower()

    rate_limit_signals = ('ratelimit', 'rate_limit', 'quota', '429', 'too many requests')
    timeout_signals    = ('timeout', 'timed out', 'deadline')
    network_signals    = ('connection', 'network', 'dns', 'refused', 'unreachable', 'socket')

    if any(s in exc_name.lower() or s in exc_str for s in rate_limit_signals):
        return 'rate_limit'
    if any(s in exc_name.lower() or s in exc_str for s in timeout_signals):
        return 'timeout'
    if any(s in exc_name.lower() or s in exc_str for s in network_signals):
        return 'network'
    return 'unknown'


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
    from careplan.services import build_prompt, SYSTEM_PROMPT
    from careplan.llm import get_llm_service

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

    task_start = time.time()   # Care Plan 整体计时（含重试等待）

    try:
        # 1. 构建 Prompt
        prompt = build_prompt(order)
        logger.info("[Celery] Prompt 构建完成，长度=%d", len(prompt))

        # 2. 调用 LLM —— 打点计时
        llm = get_llm_service()
        provider = os.getenv('LLM_PROVIDER', 'anthropic')

        llm_start = time.time()
        try:
            response = llm.complete(SYSTEM_PROMPT, prompt)
            llm_duration = time.time() - llm_start
            content, model = response.content, response.model

            # ── 成功打点 ────────────────────────────────────────────────
            LLM_LATENCY.labels(provider=provider, model=model).observe(llm_duration)
            LLM_CALLS_TOTAL.labels(provider=provider, model=model, status='success').inc()
            logger.info("[Celery] LLM 调用成功 provider=%s duration=%.2fs", provider, llm_duration)

        except Exception as llm_exc:
            llm_duration  = time.time() - llm_start
            error_type    = _classify_llm_error(llm_exc)
            model_label   = os.getenv('ANTHROPIC_MODEL', os.getenv('OPENAI_MODEL', 'unknown'))

            # ── 失败打点 ────────────────────────────────────────────────
            LLM_LATENCY.labels(provider=provider, model=model_label).observe(llm_duration)
            LLM_CALLS_TOTAL.labels(provider=provider, model=model_label, status='error').inc()
            LLM_ERRORS_TOTAL.labels(provider=provider, error_type=error_type).inc()
            logger.warning(
                "[Celery] LLM 调用失败 provider=%s error_type=%s duration=%.2fs err=%s",
                provider, error_type, llm_duration, str(llm_exc)
            )
            raise llm_exc   # 继续交给外层 retry 逻辑处理

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

        # ── Care Plan 整体耗时打点 ───────────────────────────────────────
        CARE_PLAN_DURATION.observe(time.time() - task_start)
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
