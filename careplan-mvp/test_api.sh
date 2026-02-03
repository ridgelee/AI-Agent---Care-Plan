#!/bin/bash

# Care Plan API 测试脚本
# 用法: ./test_api.sh

BASE_URL="http://localhost:8000/api"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "========================================"
echo "   Care Plan API 测试 Walkthrough"
echo "========================================"
echo ""

# ============================================
# 测试 1: 创建订单 (POST /api/orders/)
# ============================================
echo -e "${BLUE}[步骤 1] 创建订单 - POST /api/orders/${NC}"
echo "发送病人信息，获取 order_id..."
echo ""

RESPONSE=$(curl -s -X POST "$BASE_URL/orders/" \
  -H "Content-Type: application/json" \
  -d '{
    "patient": {
      "first_name": "张",
      "last_name": "三",
      "dob": "1985-06-15",
      "mrn": "100001"
    },
    "provider": {
      "name": "李医生",
      "npi": "1234567890"
    },
    "medication": {
      "name": "Rituximab",
      "primary_diagnosis": "C83.30",
      "additional_diagnoses": ["I10"],
      "medication_history": ["Prednisone 10mg"]
    },
    "patient_records": "患者既往有高血压病史"
  }')

echo "响应:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# 提取 order_id
ORDER_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('order_id', ''))" 2>/dev/null)

if [ -z "$ORDER_ID" ]; then
    echo -e "${RED}错误: 无法获取 order_id${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 订单创建成功！Order ID: $ORDER_ID${NC}"
echo ""

# ============================================
# 测试 2: 立即查询状态 (GET /api/orders/{id}/)
# ============================================
echo -e "${BLUE}[步骤 2] 立即查询状态 - GET /api/orders/$ORDER_ID/${NC}"
echo "预期状态: pending 或 processing"
echo ""

RESPONSE=$(curl -s "$BASE_URL/orders/$ORDER_ID/")
STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)

echo "响应:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""
echo -e "${YELLOW}当前状态: $STATUS${NC}"
echo ""

# ============================================
# 测试 3: 轮询等待完成
# ============================================
echo -e "${BLUE}[步骤 3] 轮询等待 Care Plan 生成完成...${NC}"
echo "(每5秒检查一次，最多等待2分钟)"
echo ""

MAX_WAIT=120
WAITED=0
INTERVAL=5

while [ "$STATUS" != "completed" ] && [ "$STATUS" != "failed" ] && [ $WAITED -lt $MAX_WAIT ]; do
    sleep $INTERVAL
    WAITED=$((WAITED + INTERVAL))

    RESPONSE=$(curl -s "$BASE_URL/orders/$ORDER_ID/")
    STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)

    echo "  [$WAITED 秒] 状态: $STATUS"
done

echo ""

# ============================================
# 测试 4: 查看最终结果
# ============================================
echo -e "${BLUE}[步骤 4] 查看最终结果${NC}"
echo ""

if [ "$STATUS" == "completed" ]; then
    echo -e "${GREEN}✓ Care Plan 生成成功！${NC}"
    echo ""
    echo "完整响应:"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo ""

    # 提取 Care Plan 内容预览
    echo -e "${BLUE}[Care Plan 内容预览]${NC}"
    echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'care_plan' in data and 'content' in data['care_plan']:
    content = data['care_plan']['content']
    # 显示前500个字符
    print(content[:500] + '...' if len(content) > 500 else content)
" 2>/dev/null
    echo ""

elif [ "$STATUS" == "failed" ]; then
    echo -e "${RED}✗ Care Plan 生成失败${NC}"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    echo -e "${YELLOW}⚠ 超时，当前状态: $STATUS${NC}"
fi

echo ""

# ============================================
# 测试 5: 下载 Care Plan
# ============================================
if [ "$STATUS" == "completed" ]; then
    echo -e "${BLUE}[步骤 5] 下载 Care Plan${NC}"
    echo "下载地址: $BASE_URL/orders/$ORDER_ID/download"
    echo ""

    # 下载并显示文件名
    FILENAME="careplan_$ORDER_ID.txt"
    curl -s "$BASE_URL/orders/$ORDER_ID/download" -o "$FILENAME"

    if [ -f "$FILENAME" ]; then
        echo -e "${GREEN}✓ 文件已下载: $FILENAME${NC}"
        echo "文件大小: $(wc -c < "$FILENAME") bytes"
    fi
fi

echo ""
echo "========================================"
echo "   测试完成！"
echo "========================================"
echo ""
echo "测试摘要:"
echo "  - Order ID: $ORDER_ID"
echo "  - 最终状态: $STATUS"
echo ""
echo "手动测试命令:"
echo "  curl $BASE_URL/orders/$ORDER_ID/"
echo ""
