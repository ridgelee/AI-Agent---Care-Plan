#!/bin/bash
# ============================================================
# Care Plan API 测试命令
# 使用方法: 复制下面的命令到终端执行
# 确保后端服务器正在运行: python manage.py runserver
# ============================================================

# 设置基础 URL (根据你的实际情况修改)
BASE_URL="http://localhost:8000"

# ============================================================
# 测试 1: 创建 Order (POST /api/orders/)
# ============================================================
echo "========== 测试 1: 创建 Order =========="

curl -X POST "${BASE_URL}/api/orders/" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "first_name": "张",
      "last_name": "三",
      "dob": "1985-03-15",
      "mrn": "123456"
    },
    "provider": {
      "name": "Dr. Smith",
      "npi": "1234567890"
    },
    "medication": {
      "name": "Humira",
      "primary_diagnosis": "M06.9",
      "additional_diagnoses": ["E11.9", "I10"],
      "medication_history": ["Methotrexate 15mg", "Prednisone 10mg"]
    },
    "patient_records": "Patient has been on MTX for 6 months with inadequate response. No history of TB or hepatitis."
  }' | python3 -m json.tool

# 注意: 记下返回的 order_id，下面的测试需要用到


# ============================================================
# 测试 2: 查询 Order 状态 (GET /api/orders/{order_id}/)
# 把 YOUR_ORDER_ID 替换成实际的 order_id
# ============================================================
echo ""
echo "========== 测试 2: 查询 Order 状态 =========="

# 替换下面的 ORDER_ID
ORDER_ID="YOUR_ORDER_ID_HERE"

curl -X GET "${BASE_URL}/api/orders/${ORDER_ID}/" | python3 -m json.tool


# ============================================================
# 测试 3: 搜索 Orders (POST /api/orders/search/)
# ============================================================
echo ""
echo "========== 测试 3: 搜索 Orders =========="

# 按患者姓名搜索
curl -X POST "${BASE_URL}/api/orders/search/" \
  -H "Content-Type: application/json" \
  -d '{"query": "张"}' | python3 -m json.tool

# 按 MRN 搜索
curl -X POST "${BASE_URL}/api/orders/search/" \
  -H "Content-Type: application/json" \
  -d '{"query": "123456"}' | python3 -m json.tool

# 按药物名称搜索
curl -X POST "${BASE_URL}/api/orders/search/" \
  -H "Content-Type: application/json" \
  -d '{"query": "Humira"}' | python3 -m json.tool


# ============================================================
# 测试 4: 下载 Care Plan (GET /api/orders/{order_id}/download)
# 只有 status=completed 才能下载
# ============================================================
echo ""
echo "========== 测试 4: 下载 Care Plan =========="

curl -X GET "${BASE_URL}/api/orders/${ORDER_ID}/download" -o careplan_output.txt
echo "Care Plan 已保存到 careplan_output.txt"
