# Lambda 部署指南

## 前置检查
- [x] RDS 已创建：careplan.cv2cuyqoui0j.us-east-2.rds.amazonaws.com
- [ ] SQS 队列已创建
- [ ] 三个 Lambda 函数已创建
- [ ] 环境变量已配置
- [ ] zip 包已上传

---

## 第零步：创建 SQS 队列（在 RDS 之后，Lambda 之前做）

1. AWS 控制台 → SQS → **创建队列**
2. 类型选 **标准队列（Standard）**（不选 FIFO）
3. 名称：`careplan-queue`
4. 其余默认，点创建
5. 创建后，复制队列的 **URL**，格式：
   `https://sqs.us-east-2.amazonaws.com/123456789/careplan-queue`
   → 这个 URL 后面要填到 Lambda 1 的环境变量 SQS_QUEUE_URL

---

## 第一步：在本地打包（在 terminal 里执行）

```bash
cd careplan-mvp/lambdas
bash build.sh
```

完成后会生成：
- `dist/create_order.zip`
- `dist/generate_careplan.zip`
- `dist/get_order.zip`

---

## 第二步：创建三个 Lambda 函数

对每个 Lambda 重复以下操作：

### 控制台操作
1. AWS 控制台 → Lambda → **创建函数**
2. 选 **从头开始创作**
3. 填写：
   | Lambda | 函数名称 | 运行时 | Handler 配置 |
   |--------|---------|--------|------------|
   | Lambda 1 | `create-order` | Python 3.12 | `handler.handler` |
   | Lambda 2 | `generate-careplan` | Python 3.12 | `handler.handler` |
   | Lambda 3 | `get-order` | Python 3.12 | `handler.handler` |

4. 架构选 **x86_64**
5. 执行角色：选 **创建新角色**（先用默认，后面加权限）
6. 点 **创建函数**

### 上传代码
1. 进入函数页面 → **代码** 选项卡
2. 右上角点 **上传自** → **.zip 文件**
3. 上传对应的 zip 文件

### 调整超时时间
Lambda 2（generate-careplan）需要等 LLM 响应，默认 3 秒太短：
1. **配置** → **常规配置** → **编辑**
2. 超时改为 **5 分钟（300 秒）**
3. 内存改为 **512 MB**

Lambda 1 和 3：超时 30 秒，内存 256 MB 即可

---

## 第三步：配置环境变量

对每个 Lambda → **配置** → **环境变量** → **编辑** → **添加环境变量**：

### Lambda 1（create-order）需要的变量
```
DATABASE_URL    = postgresql://careplan:<你的密码>@careplan.cv2cuyqoui0j.us-east-2.rds.amazonaws.com:5432/careplan
SQS_QUEUE_URL   = https://sqs.us-east-2.amazonaws.com/<你的账号ID>/careplan-queue
AWS_REGION      = us-east-2
```

### Lambda 2（generate-careplan）需要的变量
```
DATABASE_URL        = postgresql://careplan:<你的密码>@careplan.cv2cuyqoui0j.us-east-2.rds.amazonaws.com:5432/careplan
LLM_PROVIDER        = anthropic
ANTHROPIC_API_KEY   = sk-ant-...（你的 Anthropic key）
AWS_REGION          = us-east-2
```

### Lambda 3（get-order）需要的变量
```
DATABASE_URL    = postgresql://careplan:<你的密码>@careplan.cv2cuyqoui0j.us-east-2.rds.amazonaws.com:5432/careplan
```

---

## 第四步：给 Lambda 加 SQS 权限

Lambda 1 需要「发消息到 SQS」的权限，Lambda 2 需要「读 SQS 消息」的权限。

### 给 Lambda 1 加 SQS 发消息权限
1. Lambda 1 页面 → **配置** → **权限**
2. 点击执行角色名称（会跳到 IAM）
3. **添加权限** → **附加策略**
4. 搜索 `AmazonSQSFullAccess`，勾选，**添加权限**

（生产环境应该用最小权限原则，但学习阶段用 FullAccess 省事）

### 给 Lambda 2 加 SQS 触发器
1. Lambda 2 页面 → **配置** → **触发器** → **添加触发器**
2. 选择 **SQS**
3. SQS 队列选 `careplan-queue`
4. 批处理大小：**1**（每次处理 1 条消息，适合学习）
5. 点 **添加**

---

## 第五步：运行数据库迁移

RDS 是新数据库，还没有表。需要先建表：

```bash
# 在本地 terminal 执行，把迁移命令跑到 RDS
cd careplan-mvp/backend
DATABASE_URL="postgresql://careplan:<密码>@careplan.cv2cuyqoui0j.us-east-2.rds.amazonaws.com:5432/careplan" \
python manage.py migrate
```

---

## 第六步：创建 API Gateway（让 Lambda 1 和 3 有 HTTP 入口）

1. AWS 控制台 → API Gateway → **创建 API**
2. 选 **HTTP API**（更简单，够用）
3. 集成 → Lambda → 选 `create-order`
4. 配置路由：
   - `POST /orders` → `create-order`
   - `GET /orders/{order_id}` → `get-order`
5. 部署阶段名称：`prod`
6. 完成后拿到 API 的 Invoke URL

---

## 第七步：端到端测试

```bash
# 测试 Lambda 1（创建订单）
curl -X POST https://<你的API-GW-URL>/orders \
  -H "Content-Type: application/json" \
  -H "X-Order-Source: clinic_b" \
  -d '{
    "patient": {
      "first_name": "John",
      "last_name": "Doe",
      "dob": "1980-01-01",
      "mrn": "MRN001"
    },
    "provider": {
      "name": "Dr. Smith",
      "npi": "1234567890"
    },
    "medication": {
      "name": "Humira",
      "primary_diagnosis": "M06.9"
    }
  }'

# 拿到 order_id 后，等 30 秒让 Lambda 2 跑完，再查询
curl https://<你的API-GW-URL>/orders/<order_id>
```

---

## 常见问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `cannot import psycopg2` | 打包时用了 Mac 版本 | 重新跑 `build.sh`，确认用了 `--platform manylinux2014_x86_64` |
| `connection refused` 连不上 RDS | RDS 安全组没放行 Lambda | RDS 安全组加入站规则：5432 端口，来源 0.0.0.0/0（学习阶段） |
| Lambda 2 没有被触发 | SQS 触发器没配 | 检查 Lambda 2 的触发器设置 |
| `Task timed out` | Lambda 超时太短 | 把 Lambda 2 超时改到 300 秒 |

查日志：AWS 控制台 → CloudWatch → 日志组 → `/aws/lambda/函数名`
