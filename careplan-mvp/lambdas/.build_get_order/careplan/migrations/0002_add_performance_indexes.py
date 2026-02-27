"""
补充重复检测所需的索引。

services.py 的三个慢查询：

1. check_patient_duplicate — 按姓名+DOB 查重：
   Patient.objects.filter(first_name=..., last_name=..., dob=...)
   → 复合索引 (first_name, last_name, dob)

2. check_order_duplicate — 按患者+药品查重：
   Order.objects.filter(patient=patient, medication_name=medication_name)
   → 复合索引 (patient_id, medication_name)

3. check_order_duplicate — 今天的订单：
   Order.objects.filter(...).filter(created_at__date=today)
   → 索引 (created_at)

4. search_orders — 订单列表按时间排序：
   Order.objects.order_by('-created_at')
   → 同上，(created_at) DESC
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('careplan', '0001_initial'),
    ]

    operations = [
        # patients 表：按姓名+DOB 查重（check_patient_duplicate 第二段查询）
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(
                fields=['first_name', 'last_name', 'dob'],
                name='patient_name_dob_idx',
            ),
        ),

        # orders 表：按患者+药品查重（check_order_duplicate）
        migrations.AddIndex(
            model_name='order',
            index=models.Index(
                fields=['patient', 'medication_name'],
                name='order_patient_medication_idx',
            ),
        ),

        # orders 表：按日期过滤 + 排序（今日重复检测 & search_orders）
        migrations.AddIndex(
            model_name='order',
            index=models.Index(
                fields=['-created_at'],
                name='order_created_at_idx',
            ),
        ),

        # orders 表：状态过滤（按 status 查 pending/processing 订单）
        migrations.AddIndex(
            model_name='order',
            index=models.Index(
                fields=['status'],
                name='order_status_idx',
            ),
        ),
    ]
