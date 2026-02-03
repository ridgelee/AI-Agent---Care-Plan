# Care Plan Generator MVP

最小可行产品 - 前端 + 后端 + PostgreSQL + LLM

## 项目结构

```
careplan-mvp/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── careplan/
│       ├── models.py
│       ├── views.py
│       └── urls.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        └── App.jsx
```

## 快速启动

### 1. 设置环境变量

创建 `.env` 文件或导出环境变量：

```bash
export OPENAI_API_KEY=your-openai-api-key-here
```

### 2. 启动所有服务

```bash
cd careplan-mvp
docker-compose up --build
```

### 3. 访问应用

- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8000/api/

## API 端点

| Method | Endpoint | 描述 |
|--------|----------|------|
| POST | `/api/orders/` | 创建订单并生成 Care Plan |
| GET | `/api/orders/{order_id}/` | 获取订单状态和 Care Plan |
| GET | `/api/orders/{order_id}/download` | 下载 Care Plan 文件 |

## 状态流转

```
pending → processing → completed
                   ↓
                 failed
```

## 数据库

PostgreSQL 数据库包含以下表：
- `patients` - 患者信息
- `providers` - 医生/Provider 信息
- `orders` - 订单（关联患者、Provider、药物信息）
- `care_plans` - 生成的 Care Plan

## 技术栈

- **前端**: React 18 + Vite
- **后端**: Python 3.11 + Django 4.2 + DRF
- **数据库**: PostgreSQL 15
- **LLM**: OpenAI GPT-4o-mini
- **容器化**: Docker + Docker Compose

## 注意事项

这是一个 MVP 版本，为了简化：
- 同步处理（用户等待 LLM 生成完成）
- 没有身份验证
- 没有输入验证
- 没有重复检测
- 没有错误处理优化
- 没有测试

后续可以逐步添加：
- 异步处理 (Celery + Redis)
- WebSocket 实时更新
- 输入验证和错误处理
- 重复检测逻辑
- 测试用例
