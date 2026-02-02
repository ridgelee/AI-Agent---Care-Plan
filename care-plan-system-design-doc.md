# Care Plan 自动生成系统 - 设计文档

**版本**: 1.0
**日期**: 2026-02-01
**状态**: 草稿

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

| 字段 | 类型 | 必填 | 验证规则 |
|------|------|------|----------|
| Patient First Name | string | ✅ | 非空 |
| Patient Last Name | string | ✅ | 非空 |
| Patient DOB | date | ✅ | 有效日期，不能是未来 |
| Patient MRN | string | ✅ | 6位数字，唯一 |
| Referring Provider | string | ✅ | 非空 |
| Referring Provider NPI | string | ✅ | 10位数字 |
| Primary Diagnosis | string | ✅ | 有效 ICD-10 格式 |
| Medication Name | string | ✅ | 非空 |
| Additional Diagnosis | list[string] | ❌ | 有效 ICD-10 格式 |
| Medication History | list[string] | ❌ | - |
| Patient Records | string/file | ❌ | 文本或 PDF |

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
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
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
1. 用户提交订单
       │
       ▼
2. Django 验证输入 + 重复检测
       │
       ▼
3. 创建 Order 记录 (status: pending)
       │
       ▼
4. 发送消息到 SQS
       │
       ▼
5. Lambda 消费消息
       │
       ▼
6. 调用 LLM 生成 Care Plan
       │
       ▼
7. 保存 Care Plan，更新 Order (status: completed)
       │
       ▼
8. 用户刷新页面看到结果 / 通知用户
```

---

## 8. API 设计

### 8.1 核心 Endpoints

| Method | Endpoint | 描述 |
|--------|----------|------|
| POST | `/api/orders/` | 创建订单，触发 Care Plan 生成 |
| GET | `/api/orders/{id}/` | 获取订单详情（含 Care Plan 状态） |
| GET | `/api/orders/{id}/care-plan/` | 获取 Care Plan 内容 |
| GET | `/api/orders/{id}/care-plan/download/` | 下载 Care Plan 文件 |
| GET | `/api/patients/` | 患者列表 |
| GET | `/api/patients/{mrn}/` | 按 MRN 查询患者 |
| GET | `/api/providers/` | Provider 列表 |
| POST | `/api/reports/export/` | 导出报告 |

### 8.2 重复检测 Response 示例

**WARNING 响应 (HTTP 200, 需要确认)**
```json
{
  "status": "warning",
  "warnings": [
    {
      "type": "potential_duplicate_order",
      "message": "该患者在 2026-01-15 有相同药物的订单，可能是续方",
      "existing_order_id": "uuid-xxx",
      "can_override": true
    }
  ],
  "data": { ... }
}
```

**ERROR 响应 (HTTP 400, 阻止提交)**
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
