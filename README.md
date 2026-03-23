# 千岁回响 (Echoing Through Millennia)

历史文物情感疗愈 AI 对话平台。基于智能对话框架，融合 pgvector 文物知识库与 LLM 情感分析，以文物灵魂的视角提供沉浸式情感陪伴。

用户倾诉心事时，系统自动分析情感状态，从 52 件历史文物中语义匹配最契合的故事，将其注入角色扮演上下文——让千年前的文物用自己的经历，疗愈当下的人。

## 技术栈

| 层级 | 技术 |
|------|------|
| 核心框架 | Python 3.11+ / FastAPI / EchoBot |
| 对话编排 | Decision-Roleplay-Agent 三层架构 |
| 文物知识库 | PostgreSQL 16 + pgvector (语义向量检索) |
| 情感分析 | LLM 驱动的多维情感识别 |
| LLM | OpenAI 兼容接口 (Qwen / DeepSeek / OpenAI 可切换) |
| TTS / ASR | Edge TTS + Kokoro / SenseVoice (sherpa-onnx) |
| 前端 | 原生 JS + Live2D Cubism 4 + PixiJS |
| 多渠道 | Web Console / QQ / Telegram / CLI |
| 部署 | Docker Compose (PostgreSQL) + Python venv |

## 核心功能

### 文物疗愈体系

- **多维情感分析** — LLM 识别主情感/次情感/强度/心理需求/关键词，判断对话阶段
- **文物语义匹配** — pgvector 向量检索 + 关键词检索，从 52 件文物中找到最契合的故事
- **四阶段引导对话** — 倾听 → 共鸣 → 引导 → 升华，渐进式情感疗愈
- **文物卡片展示** — 聊天流中实时展示匹配到的文物信息和情感标签

### 完整能力

- **Agent 工具系统** — 文件/Shell/Web/Memory/Cron 等工具链
- **Decision Engine** — 意图路由，自动区分闲聊与需要 Agent 处理的任务
- **角色卡系统** — 支持多角色切换，内置"文物疗愈师"角色
- **Live2D 形象** — 可交互的 2D 角色，支持舞台背景/光影/粒子效果
- **语音交互** — WebSocket 实时 ASR + 流式 TTS
- **长期记忆** — ReMe 长期记忆系统
- **定时任务** — Cron 调度 + Heartbeat 心跳
- **Agent Traces** — 完整的工具调用追踪可视化

## 快速开始

### 前置条件

- Python 3.11+
- Docker (用于 PostgreSQL + pgvector)

### 1. 克隆并配置环境

```bash
git clone <repo-url> Echoing_Through_Millennia
cd Echoing_Through_Millennia

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件，填入你的 LLM API Key：

```ini
# LLM 设置
LLM_API_KEY=your-api-key-here
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 文物知识库
RELIC_DATABASE_URL=postgresql+asyncpg://echobot:echobot_dev@localhost:5432/echobot_relics

# Embedding 设置 (文物语义检索)
EMBEDDING_API_KEY=your-api-key-here
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_DIMENSIONS=1024
```

### 3. 启动 PostgreSQL

```bash
docker compose -f docker/docker-compose.dev.yml up -d
```

### 4. 导入文物数据

```bash
python seed_data.py
```

将 52 件历史文物（含故事、情感标签、人生启示）导入 PostgreSQL，并生成 1024 维向量嵌入。

### 5. 启动服务

```bash
python -m echobot app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/web 打开 Web Console。

### 其他启动方式

```bash
# 命令行交互模式
python -m echobot chat

# 多渠道网关模式 (QQ/Telegram)
python -m echobot gateway
```

## 项目结构

```
Echoing_Through_Millennia/
├── echobot/                    # 核心 Python 包
│   ├── app/                    # FastAPI 应用
│   │   ├── routers/            # API 路由
│   │   │   ├── chat.py         # 聊天流 (NDJSON stream)
│   │   │   ├── relics.py       # 文物 CRUD + 语义搜索
│   │   │   ├── roles.py        # 角色管理
│   │   │   ├── sessions.py     # 会话管理
│   │   │   └── ...
│   │   ├── services/           # 服务层
│   │   │   └── relic_service.py
│   │   └── web/                # Web Console (原生 JS)
│   ├── orchestration/          # 对话编排
│   │   ├── coordinator.py      # 核心协调器 (含 relic_context_hook)
│   │   ├── decision.py         # 意图路由
│   │   ├── roleplay.py         # 角色扮演 (含 extra_context 注入)
│   │   └── roles.py            # 角色卡系统
│   ├── relic_knowledge/        # 文物知识库模块
│   │   ├── db.py               # PostgreSQL + pgvector 连接
│   │   ├── models.py           # Relic 表模型 (Vector 1024)
│   │   ├── emotion_analyzer.py # LLM 情感分析
│   │   ├── emotion_models.py   # EmotionResult / DialoguePhase
│   │   ├── embeddings.py       # 向量嵌入服务
│   │   ├── retriever.py        # 语义检索 + 关键词检索
│   │   ├── relic_matcher.py    # 情感-文物匹配策略
│   │   └── guided_dialogue.py  # 四阶段对话策略指令
│   ├── runtime/                # 运行时 (bootstrap / sessions)
│   ├── providers/              # LLM Provider (OpenAI 兼容)
│   ├── agent.py                # Agent Core
│   ├── tools/                  # Agent 工具集
│   ├── tts/                    # TTS 服务 (Edge / Kokoro)
│   ├── asr/                    # ASR 服务 (SenseVoice)
│   ├── memory/                 # 长期记忆 (ReMe)
│   ├── scheduling/             # 定时任务 (Cron / Heartbeat)
│   └── channels/               # 多渠道 (QQ / Telegram)
├── roles/                      # 角色卡目录
│   └── 文物疗愈师.md
├── skills/                     # Agent 技能包
├── docker/                     # Docker Compose 配置
│   └── docker-compose.dev.yml
├── .echobot/                   # 运行时数据 (会话/Live2D/Agent Traces)
├── .env                        # 环境配置
├── seed_data.py                # 文物数据导入脚本 (52 件)
└── requirements.txt            # Python 依赖
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | 聊天流 (NDJSON)，`done` 事件含 `emotion` + `relic` 数据 |
| POST | `/api/chat` | 同步聊天 |
| GET | `/api/relics` | 文物列表 (分页/按朝代/分类筛选) |
| GET | `/api/relics/{id}` | 文物详情 |
| GET | `/api/relics/random` | 随机推荐文物 |
| POST | `/api/relics/search` | 文物语义搜索 |
| GET | `/api/roles` | 角色列表 |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/health` | 健康检查 |

## 工作原理

```
用户输入 → Decision Engine (意图判断)
                ↓ 闲聊路径
        EmotionAnalyzer (情感分析)
                ↓
        RelicMatcher (文物匹配, pgvector)
                ↓
        GuidedDialogue (阶段策略)
                ↓
        RoleplayEngine (角色扮演, 文物上下文注入)
                ↓
        NDJSON Stream → Web UI (文物卡片 + 情感标签)
```

当 Decision Engine 判断为需要 Agent 处理的任务时，走 Agent 路径（工具调用），不触发文物疗愈逻辑。
