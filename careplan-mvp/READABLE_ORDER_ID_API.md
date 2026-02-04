# 可读订单ID功能文档

## 📋 功能概述

我们已经为Order模型添加了可读的10位订单ID（由大写字母和数字组成），并创建了一个新的API端点来通过这个可读ID查询订单。

---

## 🔧 实现的更改

### 1. 数据库模型更改
**文件**: `backend/careplan/models.py`

- 添加了 `generate_readable_order_id()` 函数，用于生成唯一的10位可读ID
- 在 `Order` 模型中添加了 `readable_order_id` 字段：
  ```python
  readable_order_id = models.CharField(
      max_length=10,
      unique=True,
      default=generate_readable_order_id,
      editable=False
  )
  ```

**示例ID**: `A3K9L2M7P4`, `9X2Y5B8Q1T`, `T6H4N8R3W1`

### 2. 数据库迁移
**文件**: `backend/careplan/migrations/0002_order_readable_order_id.py`

需要运行以下命令来应用迁移：
```bash
python manage.py migrate careplan
```

### 3. 新增API视图
**文件**: `backend/careplan/views.py`

创建了 `OrderByReadableIdView` 类，处理通过可读ID查询订单的请求。

### 4. URL路由配置
**文件**: `backend/careplan/urls.py`

添加了新的路由：
```python
path('orders/by-code/<str:readable_order_id>/', OrderByReadableIdView.as_view(), name='order-by-readable-id')
```

---

## 🚀 API使用说明

### 新增API端点

**端点**: `GET /api/orders/by-code/<readable_order_id>/`

**描述**: 通过10位可读订单ID获取订单详细信息

**请求方法**: GET

**URL参数**:
- `readable_order_id` (必需): 10位可读订单ID（大小写不敏感，会自动转换为大写）

---

## 📊 API响应示例

### 成功响应 (200 OK)

#### 订单处理中
```json
{
  "order_id": "123e4567-e89b-12d3-a456-426614174000",
  "readable_order_id": "A3K9L2M7P4",
  "status": "processing",
  "message": "Care Plan is being generated, please wait...",
  "patient": {
    "name": "John Doe",
    "mrn": "123456",
    "dob": "1980-01-15"
  },
  "provider": {
    "name": "Dr. Jane Smith",
    "npi": "1234567890"
  },
  "medication": {
    "name": "Humira",
    "primary_diagnosis": "J45.50",
    "additional_diagnoses": ["E11.9"],
    "medication_history": ["Metformin", "Atorvastatin"]
  },
  "patient_records": "Patient has history of...",
  "created_at": "2024-02-04T10:30:00Z",
  "updated_at": "2024-02-04T10:35:00Z"
}
```

#### 订单已完成
```json
{
  "order_id": "123e4567-e89b-12d3-a456-426614174000",
  "readable_order_id": "A3K9L2M7P4",
  "status": "completed",
  "message": "Care Plan generated successfully",
  "patient": {
    "name": "John Doe",
    "mrn": "123456",
    "dob": "1980-01-15"
  },
  "provider": {
    "name": "Dr. Jane Smith",
    "npi": "1234567890"
  },
  "medication": {
    "name": "Humira",
    "primary_diagnosis": "J45.50",
    "additional_diagnoses": ["E11.9"],
    "medication_history": ["Metformin", "Atorvastatin"]
  },
  "patient_records": "Patient has history of...",
  "created_at": "2024-02-04T10:30:00Z",
  "updated_at": "2024-02-04T10:35:00Z",
  "completed_at": "2024-02-04T10:35:30Z",
  "care_plan": {
    "content": "## Problem List / Drug Therapy Problems...",
    "generated_at": "2024-02-04T10:35:30Z",
    "llm_model": "claude-sonnet-4-20250514",
    "download_url": "/api/orders/123e4567-e89b-12d3-a456-426614174000/download"
  }
}
```

### 错误响应 (404 Not Found)
```json
{
  "status": "error",
  "message": "Order not found",
  "readable_order_id": "INVALID123"
}
```

---

## 🧪 测试示例

### 使用curl测试

```bash
# 示例1: 查询订单（假设订单ID为 A3K9L2M7P4）
curl -X GET http://localhost:8000/api/orders/by-code/A3K9L2M7P4/

# 示例2: 小写也可以（会自动转换为大写）
curl -X GET http://localhost:8000/api/orders/by-code/a3k9l2m7p4/

# 示例3: 查询不存在的订单
curl -X GET http://localhost:8000/api/orders/by-code/INVALID123/
```

### 使用Python requests测试

```python
import requests

# 设置API基础URL
BASE_URL = "http://localhost:8000/api"

# 可读订单ID
readable_order_id = "A3K9L2M7P4"

# 发送GET请求
response = requests.get(f"{BASE_URL}/orders/by-code/{readable_order_id}/")

# 检查响应
if response.status_code == 200:
    data = response.json()
    print(f"订单状态: {data['status']}")
    print(f"患者姓名: {data['patient']['name']}")
    print(f"药物: {data['medication']['name']}")

    if data['status'] == 'completed':
        print(f"Care Plan已生成")
        print(f"下载链接: {data['care_plan']['download_url']}")
elif response.status_code == 404:
    print("订单未找到")
else:
    print(f"请求失败: {response.status_code}")
```

### 使用JavaScript/Fetch测试

```javascript
const readableOrderId = 'A3K9L2M7P4';

fetch(`http://localhost:8000/api/orders/by-code/${readableOrderId}/`)
  .then(response => {
    if (response.ok) {
      return response.json();
    } else if (response.status === 404) {
      throw new Error('订单未找到');
    } else {
      throw new Error('请求失败');
    }
  })
  .then(data => {
    console.log('订单状态:', data.status);
    console.log('患者姓名:', data.patient.name);
    console.log('药物:', data.medication.name);

    if (data.status === 'completed') {
      console.log('Care Plan已生成');
      console.log('Care Plan内容:', data.care_plan.content);
    }
  })
  .catch(error => {
    console.error('错误:', error);
  });
```

---

## 🔄 与现有API的对比

### 旧API（通过UUID查询）
```
GET /api/orders/123e4567-e89b-12d3-a456-426614174000/
```
- ✅ 适合内部系统使用
- ❌ UUID太长，不便于用户记忆和输入

### 新API（通过可读ID查询）
```
GET /api/orders/by-code/A3K9L2M7P4/
```
- ✅ 短小易记（10位）
- ✅ 便于用户通过电话、邮件等方式传递
- ✅ 更友好的用户体验

---

## ⚙️ 部署步骤

1. **应用数据库迁移**
   ```bash
   cd backend
   python manage.py migrate careplan
   ```

2. **重启Django服务器**
   ```bash
   python manage.py runserver
   ```

3. **验证功能**
   - 创建一个新订单
   - 在返回的响应中找到 `readable_order_id`
   - 使用新的API端点查询该订单

---

## 🎯 使用场景

1. **客户服务**：客服人员可以要求用户提供简短的订单码，快速查询订单状态
2. **邮件通知**：在邮件中提供可读的订单ID，用户可以方便地输入查询
3. **电话沟通**：通过电话传达订单ID更加准确和高效
4. **打印文档**：在纸质文档上打印简短的订单码

---

## 🔐 注意事项

1. **唯一性保证**：`generate_readable_order_id()` 函数会检查数据库，确保生成的ID是唯一的
2. **大小写不敏感**：API会自动将输入的ID转换为大写进行查询
3. **只读字段**：`readable_order_id` 字段设置为 `editable=False`，只能在创建时自动生成
4. **向后兼容**：现有的UUID查询API仍然可用，不影响现有功能

---

## 📚 相关文件

- `backend/careplan/models.py` - Order模型和ID生成函数
- `backend/careplan/views.py` - OrderByReadableIdView视图
- `backend/careplan/urls.py` - URL路由配置
- `backend/careplan/migrations/0002_order_readable_order_id.py` - 数据库迁移文件

---

## 🐛 常见问题

**Q: 如何获取订单的可读ID？**
A: 在创建订单时，响应中会自动包含 `readable_order_id` 字段。你也可以通过UUID查询订单时获取。

**Q: 如果输入小写的订单ID会怎样？**
A: API会自动将输入转换为大写进行查询，所以大小写不敏感。

**Q: 可读ID会重复吗？**
A: 不会。生成函数会检查数据库，确保每个ID都是唯一的。

**Q: 我可以手动修改订单的可读ID吗？**
A: 不可以。该字段设置为 `editable=False`，只能在创建时自动生成。

---

## ✅ 完成检查清单

- [x] 在Order模型添加readable_order_id字段
- [x] 创建generate_readable_order_id()函数
- [x] 创建数据库迁移文件
- [x] 创建OrderByReadableIdView视图
- [x] 配置URL路由
- [ ] 运行数据库迁移 (`python manage.py migrate`)
- [ ] 测试新API端点
- [ ] 更新前端以显示可读订单ID
- [ ] 更新API文档

---

生成日期: 2024-02-04
