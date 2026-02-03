# Care Plan 自动生成系统 - 设计文档

**版本**: 1.1
**日期**: 2026-02-02
**状态**: 草稿

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.1 | 2026-02-02 | • 明确医疗工作人员输入字段说明<br>• 重新设计核心 API（POST 创建订单 + GET 查询状态）<br>• 详细说明异步处理流程和状态流转<br>• 更新数据库 Schema（添加订单状态字段） |
| 1.0 | 2026-02-01 | 初始版本 |

---

## 1. 项目概述

### 1.1 背景

CVS Specialty Pharmacy 的药剂师目前需要手动为每位患者创建 Care Plan，每份耗时 20-40 分钟。由于 Medicare 报销和制药公司合规要求，这是必须完成的任务。当前人手不足导致任务积压严重。

### 1.2 目标

构建一个自动化的 Care Plan 生成系统，通过 LLM 技术将 Care Plan 创建时间从 20-40 分钟缩短至 2-3 分钟。

### 1.3 用户

| 角色 | 描述 | 系统交互 |
|------|------|----------|
| 医疗助理 (Medical Assistant) | CVS 医疗工作者 | 输入患者信息，下载 Care Plan |
| 药剂师 (Pharmacist) | 审核 Care Plan | 查看、下载、打印 |
| 患者 | 接收打印的 Care Plan | **不直接使用系统** |

---

## 2. 核心概念

### 2.1 关键实体关系

```
┌─────────────┐     1:N     ┌─────────────┐     1:1     ┌─────────────┐
│   Patient   │ ──────────> │    Order    │ ──────────> │  Care Plan  │
│   (患者)    │             │   (订单)    │             │             │
└─────────────┘             └─────────────┘             └─────────────┘
                                   │
                                   │ N:1
                                   ▼
                            ┌─────────────┐
                            │  Provider   │
                            │  (医生)     │
                            └─────────────┘
```

### 2.2 核心业务规则

- **一个 Care Plan 对应一个订单（一种药物）**
- 同一患者可以有多个订单（不同药物）
- 同一 Provider 可以关联多个订单
- Provider 通过 NPI 唯一标识

---

## 3. 功能需求

### 3.1 必须功能 (MVP)

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 患者/订单重复检测 | P0 | 不能打乱现有工作流 |
| Care Plan 生成 | P0 | 核心价值 |
| Provider 重复检测 | P0 | 影响 pharma 报告准确性 |
| 导出报告 | P0 | pharma 报告需要 |
| Care Plan 下载 | P0 | 用户需要上传到他们的系统 |

### 3.2 后续功能 (Future)

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 多数据源支持 | P1 | Adapter 模式处理 |
| 批量处理 | P1 | 提高效率 |
| Care Plan 编辑 | P2 | 用户微调 |

---

## 4. 数据模型

### 4.1 输入字段

**医疗工作人员需要输入以下信息**：

| 字段 | 类型 | 必填 | 验证规则 | 说明 |
|------|------|------|----------|------|
| Patient First Name | string | ✅ | 非空 | 患者名字 |
| Patient Last Name | string | ✅ | 非空 | 患者姓氏 |
| Patient DOB | date | ✅ | 有效日期，不能是未来 | 患者出生日期 |
| Patient MRN | string | ✅ | 6位数字，唯一 | 医疗记录号 (Medical Record Number) |
| Referring Provider | string | ✅ | 非空 | 转诊医生姓名 |
| Referring Provider NPI | string | ✅ | 10位数字 | 国家医生标识号 (National Provider Identifier) |
| Primary Diagnosis | string | ✅ | 有效 ICD-10 格式 | 主要诊断（ICD-10编码） |
| Medication Name | string | ✅ | 非空 | 药物名称 |
| Additional Diagnosis | list[string] | ❌ | 有效 ICD-10 格式 | 其他诊断 |
| Medication History | list[string] | ❌ | - | 用药史 |
| Patient Records | string/file | ❌ | 文本或 PDF | 患者病历 |

### 4.2 数据库 Schema (简化)

```sql
-- 患者表
CREATE TABLE patients (
    id UUID PRIMARY KEY,
    mrn VARCHAR(6) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Provider 表
CREATE TABLE providers (
    id UUID PRIMARY KEY,
    npi VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 订单表
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    provider_id UUID REFERENCES providers(id),
    medication_name VARCHAR(200) NOT NULL,
    primary_diagnosis VARCHAR(20) NOT NULL,
    additional_diagnoses JSONB,
    medication_history JSONB,
    patient_records TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,  -- 记录失败原因
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP  -- Care Plan 完成时间
);

-- Care Plan 表
CREATE TABLE care_plans (
    id UUID PRIMARY KEY,
    order_id UUID UNIQUE REFERENCES orders(id),
    content TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT NOW(),
    llm_model VARCHAR(50),
    llm_prompt_version VARCHAR(20)
);
```

---

## 5. 重复检测规则

### 5.1 规则矩阵

| 场景 | 处理方式 | 原因 |
|------|----------|------|
| 同一患者 + 同一药物 + 同一天 | ❌ **ERROR** - 必须阻止 | 肯定是重复提交 |
| 同一患者 + 同一药物 + 不同天 | ⚠️ **WARNING** - 可确认继续 | 可能是续方 |
| MRN 相同 + 名字或DOB不同 | ⚠️ **WARNING** - 可确认继续 | 可能是录入错误 |
| 名字+DOB相同 + MRN不同 | ⚠️ **WARNING** - 可确认继续 | 可能是同一人 |
| NPI 相同 + Provider名字不同 | ❌ **ERROR** - 必须修正 | NPI 是唯一标识 |

### 5.2 处理流程

```
┌─────────────────┐
│   用户提交表单   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   重复检测引擎   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│ ERROR │ │WARNING│
└───┬───┘ └───┬───┘
    │         │
    ▼         ▼
┌───────┐ ┌─────────────┐
│ 阻止  │ │ 显示警告     │
│ 提交  │ │ 用户确认后   │
└───────┘ │ 可继续提交   │
          └─────────────┘
```

---

## 6. Care Plan 输出规范

### 6.1 必须包含的 Section

| Section | 中文 | 内容要点 |
|---------|------|----------|
| **Problem List / Drug Therapy Problems** | 问题清单 | 列出与药物相关的治疗问题，如不良反应风险、药物相互作用等 |
| **Goals (SMART)** | 治疗目标 | Specific, Measurable, Achievable, Relevant, Time-bound 的目标 |
| **Pharmacist Interventions / Plan** | 药师干预计划 | 给药方案、预处理、输注速率、水化保护等具体措施 |
| **Monitoring Plan & Lab Schedule** | 监测计划 | 治疗前、中、后的监测指标和时间安排 |

### 6.2 输出示例结构

```markdown
# Care Plan - [Patient Name] - [Medication]

## Problem List / Drug Therapy Problems (DTPs)
- [问题1]: [描述]
- [问题2]: [描述]
...

## Goals (SMART)
- **Primary Goal**: [具体目标，包含时间框架]
- **Safety Goal**: [安全相关目标]
- **Process Goal**: [过程目标]

## Pharmacist Interventions / Plan
### Dosing & Administration
- [给药方案详情]

### Premedication
- [预处理用药]

### Infusion Protocol
- [输注方案]

### Adverse Event Management
- [不良反应处理]

## Monitoring Plan & Lab Schedule
| 时间点 | 监测项目 |
|--------|----------|
| 治疗前 | [项目列表] |
| 治疗中 | [项目列表] |
| 治疗后 | [项目列表] |
```

### 6.3 输出格式

- **主要格式**: 纯文本 (.txt)
- **用途**: 用户下载后打印交给患者

---

## 7. 系统架构

### 7.1 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 前端 | React, JavaScript | 用户界面 |
| 后端 | Python, Django, DRF | Web 框架、API |
| 数据库 | PostgreSQL | 数据存储 |
| 异步任务 (本地) | Celery, Redis | 后台任务处理 |
| 异步任务 (AWS) | SQS, Lambda | 生产环境后台任务 |
| AI/LLM | Claude API / OpenAI API | Care Plan 生成 |
| 容器化 | Docker, Docker Compose | 本地开发 + 部署 |
| 云部署 | AWS (EC2, Lambda, RDS, SQS, S3) | 生产环境 |
| 基础设施 | Terraform | 基础设施即代码 |
| 监控 | Prometheus, Grafana | 指标收集、可视化 |
| 测试 | pytest | 单元测试、集成测试 |

### 7.2 架构图

```
                                    ┌─────────────────┐
                                    │   CloudFront    │
                                    └────────┬────────┘
                                             │
┌─────────────────────────────────────────────────────────────────────┐
│                              AWS VPC                                 │
│                                                                      │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │    React     │      │    Django    │      │  PostgreSQL  │      │
│  │   (S3/CF)    │ ───> │   (EC2/ECS)  │ ───> │    (RDS)     │      │
│  └──────────────┘      └──────┬───────┘      └──────────────┘      │
│                               │                                     │
│                               │ async                               │
│                               ▼                                     │
│                        ┌──────────────┐      ┌──────────────┐      │
│                        │     SQS      │ ───> │   Lambda     │      │
│                        │   (Queue)    │      │ (LLM Worker) │      │
│                        └──────────────┘      └──────┬───────┘      │
│                                                     │               │
└─────────────────────────────────────────────────────│───────────────┘
                                                      │
                                                      ▼
                                              ┌──────────────┐
                                              │  Claude API  │
                                              │  / OpenAI    │
                                              └──────────────┘
```

### 7.3 异步处理流程

```
┌───────────────────────────────────────────────────────────────┐
│ 步骤 1: 用户提交表单                                            │
│         POST /api/orders/                                     │
└─────────────────────────┬─────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ 步骤 2: Django 后端                                            │
│   - 验证输入（必填字段、格式校验）                              │
│   - 重复检测（患者、订单、Provider）                           │
│   - 创建 Order 记录 (status: "pending")                       │
│   - 返回 order_id 给前端                                       │
└─────────────────────────┬─────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ 步骤 3: 更新状态为 "processing"                                │
│         发送消息到 SQS 队列                                     │
└─────────────────────────┬─────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ 步骤 4: Lambda 函数消费 SQS 消息                               │
│   - 读取订单数据                                               │
│   - 构建 LLM Prompt                                           │
│   - 调用 Claude/OpenAI API                                    │
└─────────────────────────┬─────────────────────────────────────┘
                          │
                    成功  │  失败
              ┌───────────┴───────────┐
              ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│ 步骤 5a: 成功            │  │ 步骤 5b: 失败            │
│ - 保存 Care Plan 内容   │  │ - 记录错误日志           │
│ - 更新 Order 状态:      │  │ - 更新 Order 状态:      │
│   status = "completed"  │  │   status = "failed"     │
└─────────────────────────┘  └─────────────────────────┘
              │                       │
              └───────────┬───────────┘
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ 步骤 6: 前端轮询或用户刷新页面                                  │
│         GET /api/orders/{order_id}                            │
│   - status = "completed" → 显示 Care Plan                    │
│   - status = "processing" → 继续等待                         │
│   - status = "failed" → 显示错误和重试按钮                    │
└───────────────────────────────────────────────────────────────┘
```

**关键点**:
- 订单创建和 Care Plan 生成是**异步分离**的
- 用户立即收到 `order_id`，无需等待 LLM 完成
- 前端通过**轮询** `GET /api/orders/{order_id}` 获取最新状态
- 生成时间预计 30-90 秒

---

## 8. API 设计

### 8.1 核心 API 工作流程

系统围绕两个核心 API 构建：

```
步骤 1: 提交订单
┌────────────────────────────────────────────────────────┐
│ 用户填写表单，点击提交                                   │
│ ↓                                                      │
│ POST /api/orders/                                      │
│ 发送患者信息（姓名、MRN、Provider、NPI、诊断、药物等）   │
│ ↓                                                      │
│ 后端返回: {"order_id": "123", "status": "pending"}    │
└────────────────────────────────────────────────────────┘

步骤 2: 查询状态（第一次）
┌────────────────────────────────────────────────────────┐
│ 用户想知道 care plan 是否生成完毕                       │
│ ↓                                                      │
│ GET /api/orders/123                                    │
│ ↓                                                      │
│ 后端返回: {"order_id": "123", "status": "processing"} │
└────────────────────────────────────────────────────────┘

步骤 3: 查询状态（第二次）
┌────────────────────────────────────────────────────────┐
│ 过一会儿再次查询                                        │
│ ↓                                                      │
│ GET /api/orders/123                                    │
│ ↓                                                      │
│ 后端返回: {                                            │
│   "order_id": "123",                                   │
│   "status": "completed",                               │
│   "care_plan": {                                       │
│     "content": "Care Plan 完整内容...",                │
│     "download_url": "/api/orders/123/download"        │
│   }                                                    │
│ }                                                      │
└────────────────────────────────────────────────────────┘
```

### 8.2 API 详细规范

#### API 1: 创建订单（提交患者信息）

**Endpoint**: `POST /api/orders/`

**用途**: 接收患者信息，创建订单，触发 Care Plan 异步生成

**请求体**:
```json
{
  "patient": {
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1980-05-15",
    "mrn": "123456"
  },
  "provider": {
    "name": "Dr. Jane Smith",
    "npi": "1234567890"
  },
  "medication": {
    "name": "IVIG",
    "primary_diagnosis": "G70.00",
    "additional_diagnoses": ["I10", "K21.9"],
    "medication_history": ["Pyridostigmine 60mg", "Prednisone 10mg"]
  },
  "patient_records": "患者病历文本或文件..."
}
```

**成功响应** (HTTP 201):
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "订单已创建，Care Plan 正在生成中",
  "created_at": "2026-02-02T10:30:00Z"
}
```

**重复检测警告响应** (HTTP 200):
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "warning",
  "warnings": [
    {
      "type": "potential_duplicate_order",
      "message": "该患者在 2026-01-15 有相同药物的订单，可能是续方",
      "existing_order_id": "uuid-xxx",
      "can_override": true
    }
  ],
  "message": "订单已创建，但检测到潜在重复"
}
```

**重复检测错误响应** (HTTP 400):
```json
{
  "status": "error",
  "errors": [
    {
      "type": "duplicate_order",
      "message": "今天已存在相同患者+相同药物的订单，无法重复提交",
      "existing_order_id": "uuid-xxx"
    }
  ]
}
```

---

#### API 2: 查询订单状态和 Care Plan

**Endpoint**: `GET /api/orders/{order_id}`

**用途**: 根据 order_id 查询 Care Plan 生成状态和结果

**路径参数**:
- `order_id`: 订单 UUID

**响应 1 - 正在处理** (HTTP 200):
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Care Plan 正在生成中，请稍后刷新",
  "progress": {
    "current_step": "调用 LLM 生成中",
    "estimated_time_remaining": "30-60秒"
  },
  "created_at": "2026-02-02T10:30:00Z",
  "updated_at": "2026-02-02T10:30:15Z"
}
```

**响应 2 - 生成完成** (HTTP 200):
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "Care Plan 已生成完毕",
  "patient": {
    "name": "John Doe",
    "mrn": "123456"
  },
  "medication": "IVIG",
  "care_plan": {
    "content": "# Care Plan - John Doe - IVIG\n\n## Problem List...",
    "generated_at": "2026-02-02T10:31:00Z",
    "llm_model": "claude-3-sonnet-20240229",
    "download_url": "/api/orders/550e8400-e29b-41d4-a716-446655440000/download"
  },
  "created_at": "2026-02-02T10:30:00Z",
  "completed_at": "2026-02-02T10:31:00Z"
}
```

**响应 3 - 生成失败** (HTTP 200):
```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "message": "Care Plan 生成失败",
  "error": {
    "code": "LLM_API_ERROR",
    "message": "LLM API 调用超时，请重试",
    "retry_allowed": true
  },
  "created_at": "2026-02-02T10:30:00Z",
  "failed_at": "2026-02-02T10:32:00Z"
}
```

**订单不存在** (HTTP 404):
```json
{
  "status": "error",
  "message": "订单不存在",
  "order_id": "invalid-uuid"
}
```

---

### 8.3 订单状态流转

```
pending → processing → completed
                ↓
              failed (可重试)
```

| 状态 | 描述 | 前端处理 |
|------|------|----------|
| `pending` | 订单已创建，等待处理 | 显示"正在排队" |
| `processing` | LLM 正在生成 Care Plan | 显示"生成中"，轮询或等待 |
| `completed` | Care Plan 已生成 | 显示 Care Plan 内容和下载按钮 |
| `failed` | 生成失败 | 显示错误信息和重试按钮 |

---

### 8.4 其他辅助 Endpoints

| Method | Endpoint | 描述 |
|--------|----------|------|
| GET | `/api/orders/{order_id}/download` | 下载 Care Plan 为 .txt 文件 |
| POST | `/api/orders/{order_id}/retry` | 重新生成失败的 Care Plan |
| GET | `/api/patients/` | 患者列表 |
| GET | `/api/patients/{mrn}/` | 按 MRN 查询患者 |
| GET | `/api/providers/` | Provider 列表 |
| POST | `/api/reports/export/` | 导出报告 (CSV) |

---

## 9. LLM 集成

### 9.1 Prompt 设计原则

- 提供清晰的角色定义（专业药剂师）
- 明确输出格式要求（4个必须Section）
- 包含患者具体信息作为上下文
- 要求基于循证医学

### 9.2 错误处理

| 场景 | 处理方式 |
|------|----------|
| LLM API 超时 | 重试 3 次，指数退避 |
| LLM API 返回错误 | 记录日志，通知用户重试 |
| 生成内容格式不符 | 解析失败时重新生成 |
| Rate Limit | 队列等待，用户看到 "生成中" 状态 |

### 9.3 质量保证

- Prompt 版本化管理
- 记录每次生成使用的 prompt 版本
- 定期审核生成质量

---

## 10. 导出报告

### 10.1 报告用途

用于向制药公司 (Pharma) 提交合规报告，证明已为患者提供 Care Plan。

### 10.2 导出字段 (待确认)

| 字段 | 描述 |
|------|------|
| Patient MRN | 患者唯一标识 |
| Patient Name | 患者姓名 |
| Medication | 药物名称 |
| Provider NPI | 医生 NPI |
| Care Plan Date | Care Plan 生成日期 |
| Order ID | 订单 ID |

### 10.3 导出格式

- **CSV** (主要)
- 支持日期范围筛选

---

## 11. 待确认事项

| # | 问题 | 状态 | 答案 |
|---|------|------|------|
| 1 | MRN 格式是 6 位还是 8 位？ | ❓待确认 | |
| 2 | 是否需要调用外部 API 验证 NPI 真实性？ | ❓待确认 | |
| 3 | PDF 格式的 Patient Records 是否需要 OCR？ | ❓待确认 | |
| 4 | 导出报告的具体字段要求？ | ❓待确认 | |
| 5 | 多数据源具体指哪些？格式是什么？ | ❓待确认 | |
| 6 | 预期并发用户数和日处理量？ | ❓待确认 | |
| 7 | Care Plan 生成的可接受等待时间？ | ❓待确认 | |

---

## 12. 里程碑

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| **Phase 1: MVP** | 基础表单、重复检测、Care Plan 生成、下载 | TBD |
| **Phase 2: 报告** | 导出功能、Provider 管理 | TBD |
| **Phase 3: 部署** | Docker 化、AWS 部署、Terraform | TBD |
| **Phase 4: 监控** | Prometheus + Grafana | TBD |

---

## 附录

### A. 示例数据

**输入示例**
```
Name: A.B. (Fictional)
MRN: 00012345 (fictional)
DOB: 1979-06-08 (Age 46)
Sex: Female
Weight: 72 kg
Allergies: None known
Medication: IVIG
Primary diagnosis: Generalized myasthenia gravis (AChR antibody positive)
Secondary diagnoses: Hypertension, GERD
Home meds: Pyridostigmine 60mg, Prednisone 10mg, Lisinopril 10mg, Omeprazole 20mg
```

### B. 相关文档

- 原始需求文档
- API 详细设计 (待创建)
- 数据库设计 (待创建)
- LLM Prompt 设计 (待创建)
