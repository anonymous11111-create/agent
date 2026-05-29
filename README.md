# JChatMind Agent

基于 **FastAPI + LangGraph** 构建的 AI Agent 智能助手后端系统。

## ✨ 功能特性

- **🤖 智能对话** — 基于 LangGraph 的 think-execute 循环，支持多步骤推理与工具调用
- **📚 知识库检索 (RAG)** — 向量检索 + 关键词检索 + RRF 融合排序
- **🌐 联网搜索** — 通过 MCP 集成 Tavily 搜索引擎
- **📧 邮件发送** — SMTP 邮件发送工具
- **🧩 子智能体委派** — 复杂任务自动拆分给子智能体并行执行
- **👥 团队协作** — 多智能体消息通信、广播、队友管理
- **💾 记忆管理** — 长期记忆存储与上下文感知
- **📋 任务管理** — 任务创建、依赖追踪、状态流转
- **🔧 MCP 服务器** — 动态加载外部工具能力
- **📝 技能系统** — 可扩展的 Skill 机制，支持领域专业知识注入
- **🔄 上下文压缩** — 自动压缩对话历史，支持长对话
- **⚡ 后台任务** — 异步任务执行与状态通知
- **📊 工具调用日志** — 记录每次工具调用的状态、耗时、参数，支持 SSE 实时推送
- **🔍 RAG 查询日志** — 向量/关键词检索的召回数、耗时、Top 分数等指标追踪
- **🔐 操作确认** — 敏感工具（发邮件、删任务、数据库查询）执行前需用户确认

## 🏗️ 项目结构

```
agent/
├── app/
│   ├── agent/          # LangGraph Agent 核心（think-execute 循环）
│   │   ├── think_node.py    # 决策节点（意图理解、工具选择）
│   │   └── execute_node.py  # 执行节点（工具调用、确认、日志埋点）
│   ├── api/            # FastAPI 路由层
│   │   ├── confirmation.py      # 敏感操作确认接口
│   │   ├── tool_call_log.py     # 工具调用日志查询接口
│   │   └── rag_query_log.py     # RAG 查询日志与反馈接口
│   ├── background/     # 后台任务管理
│   ├── config.py       # 配置管理（pydantic-settings）
│   ├── context_compact/ # 上下文压缩
│   ├── db/             # 数据库引擎
│   ├── hooks/          # 工具调用钩子
│   ├── llm/            # LLM 模型注册（DeepSeek / 智谱 / Ollama）
│   ├── mcp/            # MCP 客户端与工具路由
│   ├── memory/         # 记忆管理
│   ├── models/         # SQLAlchemy 数据模型
│   │   ├── tool_call_log.py    # 工具调用日志模型
│   │   └── rag_query_log.py    # RAG 查询日志模型
│   ├── rag/            # RAG 检索（向量 + 关键词 + 融合）
│   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── sse_event.py        # SSE 事件模型（含工具/RAG 事件）
│   │   ├── tool_call_log.py    # 工具日志请求/响应 Schema
│   │   └── rag_query_log.py    # RAG 日志请求/响应 Schema
│   ├── services/       # 业务逻辑层
│   │   ├── confirmation_service.py      # 用户确认服务（asyncio.Event）
│   │   ├── tool_call_log_service.py     # 工具日志查询服务
│   │   └── rag_query_log_service.py     # RAG 日志查询服务
│   ├── tasks/          # 任务管理
│   ├── teams/          # 多智能体协作
│   ├── tools/          # 原生工具集
│   │   ├── email.py            # 邮件发送（需用户确认）
│   │   └── knowledge_search.py # 知识库检索（含日志埋点）
│   └── utils/          # 工具函数
├── skills/             # 技能目录
│   └── eap-troubleshooting/  # 半导体设备故障排查技能
├── .env.example        # 环境变量模板
├── init_db.py          # 数据库初始化脚本
├── requirements.txt    # Python 依赖
└── run.py              # 启动入口
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/anonymous11111-create/agent.git
cd agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制模板并填写配置
cp .env.example .env
```

编辑 `.env` 文件，填写以下必要配置：

| 配置项 | 说明 |
|-------|------|
| `DATABASE_URL` | PostgreSQL 数据库连接地址 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `TAVILY_API_KEY` | Tavily 搜索 API 密钥（可选，用于联网搜索） |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | 邮件 SMTP 配置（可选） |

### 3. 初始化数据库

确保 PostgreSQL 已启动并创建好数据库，然后执行：

```bash
python init_db.py
```

### 4. 启动服务

```bash
# Windows（推荐使用 run.py，自动设置 ProactorEventLoop）
python run.py

# Linux/Mac
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

服务启动后访问：
- API 文档：`http://localhost:8080/docs`
- 健康检查：`http://localhost:8080/health`

### 5. 启动前端

前端项目需单独启动（React + Vite）：

```bash
cd ../JChatMind3/ui
npm install
npm run dev
```

前端访问地址：`http://localhost:5173`

## 🔧 支持的 LLM 模型

| 模型 | 配置项 | 说明 |
|------|-------|------|
| DeepSeek Chat | `DEEPSEEK_API_KEY` | 推荐，性价比高 |
| 智谱 GLM | `ZHIPUAI_API_KEY` | 国产模型 |
| Ollama 本地模型 | `OLLAMA_BASE_URL` | 本地部署，用于 Embedding |

## 🌐 MCP 服务器

系统支持通过数据库动态配置 MCP 服务器。配置步骤：

1. 在前端 **MCP 服务器设置** 中添加服务器
2. 在 Agent 的工具配置中启用 `mcpTool`
3. Agent 运行时会自动连接并加载 MCP 工具

### 内置 MCP 服务器（通过 `init_db.py` 初始化）

| 名称 | 说明 | 配置要求 |
|------|------|---------|
| Tavily Search | 联网搜索 | `TAVILY_API_KEY` |

> **Windows 用户注意**：MCP 客户端已兼容 Windows，会自动将 `npx` 命令通过 `cmd /c` 包装执行。

## 📝 技能系统

技能放在 `skills/` 目录下，每个技能是一个子目录 + `SKILL.md` 文件：

```
skills/
  └── my-skill/
        └── SKILL.md
```

SKILL.md 格式：

```markdown
---
name: my-skill
description: 技能描述
---

技能的具体指令内容...
```

Agent 通过 `loadSkill` 工具按需加载技能。

## 🔐 操作确认

对敏感工具启用执行前用户确认，防止误操作。当前受保护的工具：

| 工具 | 说明 |
|------|------|
| `send_email` | 发送邮件 — 防止误发 |
| `task_delete` | 删除任务 — 防止误删 |
| `database_query` | 数据库查询 — 防止危险 SQL |

**流程**：Agent 调用敏感工具 → SSE 推送 `TOOL_CONFIRMATION_REQUIRED` → 前端弹窗 → 用户确认/拒绝 → 继续/中断执行。

**API**：
- `POST /api/tool-confirm/{confirmation_id}` — 提交确认 (approved: true/false)
- 超时默认拒绝，超时时间 120 秒

## 📊 工具调用日志

每次工具调用自动记录到数据库，并通过 SSE 实时推送状态变更。

**记录字段**：
- 会话 ID / Agent ID / 工具名称
- 调用参数（JSON）
- 执行状态：`running` → `success` / `fail` / `timeout` / `blocked` / `rejected`
- 耗时（ms）
- 错误信息 / 结果摘要

**SSE 事件类型**：`TOOL_CALL_UPDATE`

**API**：
- `GET /api/tool-call-logs` — 查询日志（按 session/agent/tool/status 筛选，分页）
- `GET /api/tool-call-logs/stats` — 统计信息（调用次数、成功率、平均耗时等）

## 🔍 RAG 查询日志

每次知识库检索自动记录召回路径和性能指标，支持前端展示检索质量。

**记录字段**：
- 查询文本 / 知识库名称
- 向量召回数 / 关键词召回数 / 最终返回数
- 各阶段耗时：Embedding → 检索 → RRF 融合 → 总耗时
- Top-K 片段的分数、内容摘要、来源文档

**SSE 事件类型**：`RAG_QUERY_UPDATE`

**API**：
- `GET /api/rag-query-logs` — 查询日志
- `GET /api/rag-query-logs/stats` — 统计信息
- `POST /api/rag-query-logs/{log_id}/feedback` — 提交检索质量反馈

## 🔧 Claude Code Hooks

项目包含 Claude Code 钩子配置，用于在工具调用前执行自定义逻辑：

```
.hooks.json          # 钩子注册配置
hooks/
  └── pre_tool_use.py   # 工具执行前拦截脚本
```

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| Agent 框架 | LangGraph |
| LLM 集成 | LangChain |
| 数据库 | PostgreSQL + SQLAlchemy (async) |
| 向量检索 | pgvector |
| Embedding | Ollama (bge-m3) |
| MCP 协议 | JSON-RPC over stdio |
| 前端 | React + Vite + Ant Design |

## 📄 License

MIT
