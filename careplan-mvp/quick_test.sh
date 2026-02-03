#!/bin/bash

# 快速 API 测试命令
# 用法: ./quick_test.sh [order_id]

BASE_URL="http://localhost:8000/api"

if [ -n "$1" ]; then
    # 如果提供了 order_id，直接查询状态
    echo "查询订单状态: $1"
    curl -s "$BASE_URL/orders/$1/" | python3 -m json.tool
else
    # 创建新订单
    echo "创建新订单..."
    RESPONSE=$(curl -s -X POST "$BASE_URL/orders/" \
      -H "Content-Type: application/json" \
      -d '{
        "patient": {"first_name": "Test", "last_name": "User", "dob": "1990-01-01", "mrn": "999999"},
        "provider": {"name": "Dr. Test", "npi": "9999999999"},
        "medication": {"name": "TestDrug", "primary_diagnosis": "A00.0", "additional_diagnoses": [], "medication_history": []},
        "patient_records": ""
      }')

    echo "$RESPONSE" | python3 -m json.tool

    ORDER_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('order_id', ''))" 2>/dev/null)

    echo ""
    echo "----------------------------------------"
    echo "查询状态命令:"
    echo "  ./quick_test.sh $ORDER_ID"
    echo ""
    echo "或者:"
    echo "  curl $BASE_URL/orders/$ORDER_ID/"
fi
