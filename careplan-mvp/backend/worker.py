# backend/worker.py
import os
import sys
import django

# 告诉 Django 用哪个 settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 初始化 Django ORM（这样才能用 models）
django.setup()

import redis
from careplan.models import Order, CarePlan
from careplan.views import build_prompt, call_llm
from django.utils import timezone


def get_redis_client():
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    return redis.from_url(redis_url)

def process_order(order_id):
    print(f"[DEBUG] Worker开始处理当前order的order_id={order_id}")
    try:
        # 1. 获取order信息
        order = Order.objects.get(id=order_id)
        
        # 2. order的status改为processing
        order.status = 'processing'
        order.save()

        # 3. 创建prompt信息
        prompt = build_prompt(order)

        # 4. 调用LLM API
        content, model = call_llm(prompt)

        # 5. 创建care plan记录
        CarePlan.objects.create(
            order=order,
            content=content,
            llm_model=model,
            llm_prompt_version='1.0'
        )

        # 6. 更新order状态
        order.status = 'completed'
        order.completed_at = timezone.now()
        order.save()

    except Exception as e:
        print(f"ERROR")
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'failed'
            order.error_message = str(e)
            order.save()
        except:
            pass

def main():
    r = get_redis_client()
    print(f"Worker started. Waiting for Task...")

    while True:
        # Redis的brpop: b = blocking, rpop = right pop
        # 返会key-val pair, 队列名 + order_id
        _, order_id = r.brpop('careplan_queue', timeout=0)
        order_id = order_id.decode('utf-8')
        queue_len = r.llen('careplan_queue')
        print(f"[DEBUG]正在处理order={order_id}, queue剩余={queue_len}")
        process_order(order_id)

if __name__ == '__main__':
    main()