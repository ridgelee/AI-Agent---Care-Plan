# 设计模式学习笔记
**项目：** Careplan MVP Backend
**日期：** 2026-02-21
**技术栈：** Python · Django · Celery · Redis · PostgreSQL

---

## 目录

1. [Adapter Pattern — 多数据源适配](#1-adapter-pattern--多数据源适配)
2. [Abstract Base Class (ABC)](#2-abstract-base-class-abc)
3. [Dataclass — 内部标准格式](#3-dataclass--内部标准格式)
4. [Factory Pattern — 工厂函数](#4-factory-pattern--工厂函数)
5. [Bridge 层是否必要？](#5-bridge-层是否必要)
6. [LLM Service 抽象层](#6-llm-service-抽象层)
7. [Django settings 驱动配置](#7-django-settings-驱动配置)
8. [完整请求流程 Walk-through](#8-完整请求流程-walk-through)
9. [关键设计原则总结](#9-关键设计原则总结)

---

## 1. Adapter Pattern — 多数据源适配

### 问题背景

不同医院/诊所发来的数据格式各不相同：

| 来源 | 格式 | 字段命名 | 特殊处理 |
|------|------|----------|----------|
| ClinicB | JSON | snake_case，嵌套 `pt`/`dx`/`rx` | `npi_num` |
| HospitalA | XML | PascalCase，NPI 是 attribute | ElementTree 解析 |
| Riverside | JSON | `subject`/`ordering_physician` | 日期 `YYYYMMDD` → ISO |
| Summit | JSON | 完全平铺 `SCREAMING_SNAKE_CASE` | `DX_CODE_1/2/3` → 数组 |

### 解决方案：Adapter Pattern

**核心思想：** 把"格式转换"和"业务逻辑"完全隔离。业务代码只认识 `InternalOrder`，永远不知道外部格式长什么样。

```
外部请求 (各种格式)
    │
    ▼
[Adapter] parse() → transform() → validate()
    │
    ▼
InternalOrder (统一内部格式)
    │
    ▼
业务逻辑 create_order(internal_order)
```

### 加入新医院只需 2 步

**第一步：** 新建一个 Adapter 类（继承 `BaseIntakeAdapter`）

```python
class NewHospitalAdapter(BaseIntakeAdapter):
    source = "new_hospital"

    def parse(self):
        self._data = json.loads(self._raw_body)

    def transform(self) -> InternalOrder:
        raw = self._data
        return InternalOrder(
            patient=PatientData(
                mrn=raw["patient_id"],
                first_name=raw["first"],
                last_name=raw["last"],
                dob=raw["birth_date"],
            ),
            # ...
            source=self.source,
            raw_payload=raw,
        )
```

**第二步：** 在 factory 注册表里加一行

```python
def _build_registry():
    return {
        "clinic_b":    ClinicBAdapter,
        "hospital_a":  HospitalAAdapter,
        "riverside":   RiversideAdapter,
        "summit":      SummitAdapter,
        "new_hospital": NewHospitalAdapter,  # ← 加这一行
    }
```

**业务代码 `views.py`、`services.py` 完全不需要改动。**

---

## 2. Abstract Base Class (ABC)

### 为什么用 ABC？

ABC 是"契约"：凡是继承它的子类，**必须**实现指定的方法，否则实例化时直接报错。

```python
from abc import ABC, abstractmethod

class BaseIntakeAdapter(ABC):

    @abstractmethod
    def parse(self) -> Any:
        """解析原始字节/字符串，子类必须实现"""
        ...

    @abstractmethod
    def transform(self) -> InternalOrder:
        """转换成统一内部格式，子类必须实现"""
        ...
```

### ABC 的好处

| 没有 ABC | 有 ABC |
|----------|--------|
| 忘记实现某方法，运行时才发现 | 实例化时立刻报 `TypeError` |
| IDE 无法提示需要实现哪些方法 | IDE 自动提示未实现的抽象方法 |
| 代码规范靠人工约定 | 规范由语言强制执行 |

### `validate()` 不是 abstract

`validate()` 有默认实现（通用的 NPI / MRN / ICD-10 格式校验），子类可选择性覆盖。只有**每个来源都必须自己实现**的方法才用 `@abstractmethod`。

---

## 3. Dataclass — 内部标准格式

### 为什么用 dataclass 而不是 dict？

```python
# ❌ dict：没有类型提示，拼错 key 运行时才报错
order["patient"]["frist_name"]  # typo，但不报错直到运行

# ✅ dataclass：IDE 自动补全，类型检查，属性访问
order.patient.first_name  # 拼错时 IDE 立刻报红
```

### 核心数据结构

```python
@dataclass
class PatientData:
    mrn: str
    first_name: str
    last_name: str
    dob: str          # 统一 ISO 8601: "YYYY-MM-DD"

@dataclass
class ProviderData:
    npi: str
    name: str

@dataclass
class MedicationData:
    name: str
    primary_diagnosis: str
    additional_diagnoses: list[str] = field(default_factory=list)
    medication_history: list[Any]   = field(default_factory=list)

@dataclass
class InternalOrder:
    patient: PatientData
    provider: ProviderData
    medication: MedicationData
    patient_records: str = ""
    confirm: bool        = False
    source: str          = ""
    raw_payload: Any     = field(default=None, repr=False)  # 保留原始数据
```

### `raw_payload` 的价值

每个 `InternalOrder` 都保存了原始请求数据，用于：
- 调试时追溯"收到的原始报文是什么"
- 合规审计（医疗场景必须）
- `repr=False` 避免日志输出时暴露大量原始数据

---

## 4. Factory Pattern — 工厂函数

### 注册表模式 (Registry Pattern)

```python
def _build_registry() -> dict[str, type[BaseIntakeAdapter]]:
    # 延迟导入，避免循环依赖
    from .adapters import ClinicBAdapter, HospitalAAdapter, RiversideAdapter, SummitAdapter
    return {
        "clinic_b":   ClinicBAdapter,
        "hospital_a": HospitalAAdapter,
        "riverside":  RiversideAdapter,
        "summit":     SummitAdapter,
    }

def get_adapter(source: str, raw_body: bytes | str, content_type: str = "") -> BaseIntakeAdapter:
    registry = _build_registry()
    adapter_cls = registry.get(source)
    if adapter_cls is None:
        raise ValidationError(
            message=f"未知的数据来源: {source!r}",
            code="UNKNOWN_SOURCE",
        )
    return adapter_cls(raw_body, content_type)
```

### 为什么 `_build_registry()` 在函数内部？

- **避免循环依赖**：模块加载时不立刻 import 所有 adapter
- **延迟加载**：只在真正需要时才触发 import
- **易于测试**：可以在测试中 mock 注册表

---

## 5. Bridge 层是否必要？

### 最初的错误设计

```
InternalOrder → bridge.py → dict → create_order(dict)
```

`bridge.py` 的作用是把 `InternalOrder` 转成 dict 再传给 `create_order()`。

### 为什么这是多余的？

`create_order()` 完全可以**直接接受 `InternalOrder`**，没有必要来回转换。

**错误设计的信号：**
> 如果一个模块的唯一工作是"把 A 转成 A 的另一种表示形式再传下去"，说明它很可能是多余的。

### 正确设计

```python
# ✅ 直接传 InternalOrder，属性访问清晰
def create_order(internal_order: InternalOrder):
    provider = check_provider_duplicate(internal_order.provider)
    patient, warnings = check_patient_duplicate(internal_order.patient)
    order = Order.objects.create(
        medication_name=internal_order.medication.name,
        primary_diagnosis=internal_order.medication.primary_diagnosis,
        ...
    )
```

**删掉 `bridge.py`，代码反而更清晰。**

---

## 6. LLM Service 抽象层

### 问题：LLM 选择权不应该给调用方

**错误想法：** 在请求体里传 `"llm": "openai"` 让调用方选择用哪个 LLM。

**为什么不对：**
- 调用方（医院系统）不应该关心平台用哪家 LLM
- 安全风险：调用方可以随意切换，无法统一管控成本
- 违反"单一职责"：业务请求不应携带平台配置

**正确做法：** LLM 选择是**平台决策**，由环境变量驱动。

### 架构设计（与 Intake Adapter 完全对称）

```
careplan/llm/
  __init__.py   → 对外只暴露 get_llm_service()
  types.py      → LLMResponse(content, model)
  base.py       → BaseLLMService ABC，定义 complete() 接口
  services.py   → ClaudeService / OpenAIService 具体实现
  factory.py    → get_llm_service() 读取 settings.LLM_PROVIDER
```

### 核心代码

```python
# base.py
class BaseLLMService(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        ...

# services.py
class ClaudeService(BaseLLMService):
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    def complete(self, system_prompt, user_prompt) -> LLMResponse:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(...)
        return LLMResponse(content=response.content[0].text, model=model)

class OpenAIService(BaseLLMService):
    DEFAULT_MODEL = "gpt-4o"
    def complete(self, system_prompt, user_prompt) -> LLMResponse:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(...)
        return LLMResponse(content=response.choices[0].message.content, model=model)

# factory.py
def get_llm_service() -> BaseLLMService:
    provider = getattr(settings, "LLM_PROVIDER", "anthropic")
    registry = {"anthropic": ClaudeService, "openai": OpenAIService}
    return registry[provider]()
```

### tasks.py 调用方式

```python
# 改前（硬编码 Anthropic）
content, model = call_llm(prompt)

# 改后（通过抽象层，不知道具体是哪家 LLM）
llm = get_llm_service()
response = llm.complete(SYSTEM_PROMPT, prompt)
content, model = response.content, response.model
```

---

## 7. Django settings 驱动配置

### 原则：配置不应该硬编码在代码里

```python
# config/settings.py
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'anthropic')  # 默认 Claude
```

```bash
# 切换到 OpenAI，只改环境变量，代码不动
LLM_PROVIDER=openai docker-compose up
```

### 配置的三个层级

```
环境变量 (.env / docker-compose.yml)
    ↓
settings.py (读取环境变量，提供默认值)
    ↓
业务代码 (通过 getattr(settings, "LLM_PROVIDER") 读取)
```

---

## 8. 完整请求流程 Walk-through

以 Summit Health System 发来一个 SCREAMING_SNAKE_CASE 格式的 JSON 为例：

```
POST /api/orders/
Headers: X-Order-Source: summit
Body: {
  "PATIENT_ID": "MRN-9900",
  "FIRST_NAME": "Alice",
  ...
}
```

### Step 1: `views.py` — 路由分发

```python
def post(self, request):
    source = request.headers.get('X-Order-Source', 'clinic_b')  # → "summit"
    adapter = get_adapter(source, request.body, request.content_type)
    internal_order = adapter.process()
    order = create_order(internal_order)
    return JsonResponse(serialize_order_created(order), status=201)
```

### Step 2: `factory.py` — 工厂查找

```
get_adapter("summit", b'{"PATIENT_ID":...}', "application/json")
    ↓ 注册表查找
SummitAdapter(raw_body, content_type)
```

### Step 3: `SummitAdapter.process()` — 三步流水线

```
parse()      → json.loads(raw_body) → self._data = {"PATIENT_ID": ..., "FIRST_NAME": ...}
transform()  → 读 PATIENT_ID/FIRST_NAME/... → 构造 InternalOrder
validate()   → 校验 NPI 格式、MRN 格式、ICD-10 格式
```

### Step 4: `services.py` — 业务逻辑

```
create_order(internal_order)
    ├── check_provider_duplicate()  → NPI 冲突检测
    ├── check_patient_duplicate()   → MRN / 姓名+DOB 重复检测
    ├── check_order_duplicate()     → 同日重复下单检测
    └── Order.objects.create()      → 写入数据库
```

### Step 5: `tasks.py` — 异步生成 Care Plan

```
generate_care_plan.delay(order.id)  # Celery 异步
    ├── build_prompt(order)          → 构造 LLM prompt
    ├── get_llm_service()            → 读 settings.LLM_PROVIDER → ClaudeService
    ├── llm.complete(SYSTEM_PROMPT, prompt) → 调用 Claude API
    └── CarePlan.objects.create()    → 写入生成结果
```

---

## 9. 关键设计原则总结

### 开闭原则 (Open/Closed Principle)

> 对扩展开放，对修改封闭。

加入新医院 = 新增一个 Adapter 类 + 注册表加一行。
**不修改任何已有代码。**

### 单一职责原则 (Single Responsibility Principle)

| 模块 | 职责 |
|------|------|
| `intake/adapters.py` | 把外部格式转成 InternalOrder |
| `services.py` | 业务逻辑（重复检测、创建记录）|
| `tasks.py` | 异步任务编排 |
| `llm/` | LLM API 调用细节 |
| `serializers.py` | ORM 对象 → JSON 响应 |

每个模块只做一件事，改一个需求只影响一个模块。

### 依赖倒置原则 (Dependency Inversion Principle)

```
tasks.py 依赖 BaseLLMService（抽象）
    而不是 ClaudeService / OpenAIService（具体实现）
```

`tasks.py` 不知道（也不关心）底层用的是哪家 LLM。

### "删代码往往比加代码更难"

这次重构中**删掉了**：
- `bridge.py`（整个文件）
- `serializers.py` 里的所有 parse 函数
- `services.py` 里的 `call_llm()`
- `views.py` 里的手动解析逻辑

删代码需要更深的理解，因为你要确定它真的没有被依赖。

---

## 附：文件结构速览

```
backend/careplan/
├── intake/
│   ├── __init__.py      # 对外: get_adapter
│   ├── types.py         # InternalOrder, PatientData, ProviderData, MedicationData
│   ├── base.py          # BaseIntakeAdapter ABC
│   ├── adapters.py      # ClinicBAdapter, HospitalAAdapter, RiversideAdapter, SummitAdapter
│   └── factory.py       # get_adapter() 注册表工厂
├── llm/
│   ├── __init__.py      # 对外: get_llm_service
│   ├── types.py         # LLMResponse
│   ├── base.py          # BaseLLMService ABC
│   ├── services.py      # ClaudeService, OpenAIService
│   └── factory.py       # get_llm_service() 读 settings.LLM_PROVIDER
├── models.py            # Patient, Provider, Order, CarePlan
├── views.py             # HTTP 入口，4 行搞定 OrderCreateView
├── services.py          # 业务逻辑，接受 InternalOrder
├── serializers.py       # ORM → JSON（纯输出，无解析）
├── tasks.py             # Celery 异步任务
└── exceptions.py        # BlockError, WarningError, ValidationError
```
