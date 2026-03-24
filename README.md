# 千岁回响 (Echoing Through Millennia)

历史文物情感疗愈 AI 对话平台。融合普拉奇克情绪轮盘算法、pgvector 文物知识库与 LLM 大模型，以文物灵魂的视角提供沉浸式情感陪伴。

当用户倾诉心事时，系统通过 8 维情绪向量实时分析情感状态，从 52 件历史文物中语义匹配最契合的故事，注入角色扮演上下文——让千年前的文物用自己的经历，疗愈当下的人。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 核心框架 | Python 3.11+ / FastAPI / EchoBot |
| 对话编排 | Decision → Roleplay → Agent 三层架构 |
| 情感分析 | **普拉奇克情绪轮盘** (Plutchik's Wheel) — LLM 评分 + Python 确定性计算 |
| 文物知识库 | PostgreSQL 16 + pgvector (1024 维语义向量检索) |
| LLM | OpenAI 兼容接口 (Qwen / DeepSeek / OpenAI 可切换) |
| TTS / ASR | Edge TTS + Kokoro / SenseVoice (sherpa-onnx) |
| 前端 | 原生 JS + Live2D Cubism 4 + PixiJS |
| 多渠道 | Web Console / QQ / Telegram / CLI |
| 长期记忆 | ReMe Light (全文检索 + 向量检索) |
| 部署 | Docker Compose (PostgreSQL) + Python venv |

---

## 核心功能

### 普拉奇克情绪轮盘算法

本项目实现了完整的 [普拉奇克情绪轮盘](https://en.wikipedia.org/wiki/Robert_Plutchik) 情感分析模型：

**8 种基本情绪 × 3 级强度 × 24 种复合情绪**

```
                    狂喜 Ecstasy
                  /              \
          警觉 ──── 快乐 Joy ──── 崇敬
         /    Vigilance    \    Admiration    \
    期待 ────────────────────────────────── 信任
 Anticipation          乐观 Optimism          Trust
        \         爱 Love          /
    烦扰 ──── 愤怒 Anger ──── 恐惧 Fear ──── 忧虑
         \                                /
    嫌恶 ──── 厌恶 Disgust ──── 惊讶 Surprise ──── 分心
         \                                /
          鄙视 ──── 悲伤 Sadness ──── 敬畏
                  \              /
                    悲痛 Grief
```

**算法流程：**

1. **LLM 评分** — 调用大模型为 8 种基本情绪打分 (0.0-1.0)，返回结构化 JSON
2. **向量构建** — 从 8 个分数构建 `EmotionVector`，所有后续计算确定性完成
3. **复合情绪** — 自动检测 24 种 Dyads (初级/二级/三级配对)
4. **强度分级** — mild (平和) / basic (中等) / intense (强烈)
5. **对立冲突** — 检测快乐↔悲伤等 4 组对立情绪的同时激活
6. **轨迹追踪** — 通过余弦距离追踪情绪变化，动态推断对话阶段
7. **文物匹配** — 将情绪向量转化为语义查询，pgvector 检索最契合的文物

**24 种复合情绪 (Dyads)：**

| 分类 | 组合 | 复合情绪 |
|------|------|---------|
| 初级配对 | 快乐+信任 | **爱** Love |
| 初级配对 | 信任+恐惧 | **顺从** Submission |
| 初级配对 | 恐惧+惊讶 | **敬畏** Awe |
| 初级配对 | 惊讶+悲伤 | **不赞同** Disapproval |
| 初级配对 | 悲伤+厌恶 | **悔恨** Remorse |
| 初级配对 | 厌恶+愤怒 | **鄙视** Contempt |
| 初级配对 | 愤怒+期待 | **好斗** Aggressiveness |
| 初级配对 | 期待+快乐 | **乐观** Optimism |
| 二级配对 | 快乐+恐惧 | **内疚** Guilt |
| 二级配对 | 信任+惊讶 | **好奇** Curiosity |
| 二级配对 | 恐惧+悲伤 | **绝望** Despair |
| 二级配对 | 惊讶+厌恶 | **难以置信** Unbelief |
| 二级配对 | 悲伤+愤怒 | **嫉妒** Envy |
| 二级配对 | 厌恶+期待 | **愤世嫉俗** Cynicism |
| 二级配对 | 愤怒+快乐 | **骄傲** Pride |
| 二级配对 | 期待+信任 | **希望** Hope |
| 三级配对 | 快乐+惊讶 | **欣喜** Delight |
| 三级配对 | 信任+悲伤 | **感伤** Sentimentality |
| 三级配对 | 恐惧+厌恶 | **羞耻** Shame |
| 三级配对 | 惊讶+愤怒 | **义愤** Outrage |
| 三级配对 | 悲伤+期待 | **悲观** Pessimism |
| 三级配对 | 厌恶+快乐 | **病态** Morbidness |
| 三级配对 | 愤怒+信任 | **支配** Dominance |
| 三级配对 | 期待+恐惧 | **焦虑** Anxiety |

### 四阶段引导对话

```
倾听 (Listening)  →  共鸣 (Resonance)  →  引导 (Guiding)  →  升华 (Elevation)
    先充分共情          引入文物故事          以故事启发          温暖鼓励收尾
```

阶段推进基于**情绪动态**而非简单的对话轮次：
- 高强度负面情绪 → 保持倾听（用户需要被听到）
- 情绪趋于稳定 (cosine distance < 0.15) → 可以引导
- 正面情绪占主导 → 进入升华

每种 Dyad 附带专属治疗策略，例如：
- 检测到**悔恨** (悲伤+厌恶) → 帮助接纳过去，而非自我谴责
- 检测到**绝望** (恐惧+悲伤) → 先肯定勇气，再引入希望
- 检测到**焦虑** (期待+恐惧) → 帮助关注当下，而非未来不确定性

### 文物知识库

52 件精心编撰的历史文物，每件包含：
- 第一人称叙事故事（文物视角讲述自身经历）
- 情感标签（如"思念"、"敬畏"、"坚韧"）
- 人生启示（从文物故事中提炼的智慧）

**代表性文物：**

| 文物 | 朝代 | 情感主题 |
|------|------|---------|
| 司母戊鼎 | 商朝 | 思念 · 亲情 · 敬畏 |
| 越王勾践剑 | 春秋 | 坚韧 · 不甘 · 重生 |
| 长信宫灯 | 西汉 | 默默付出 · 忠诚 |
| 马踏飞燕 | 东汉 | 自由 · 突破 · 飞扬 |
| 兰亭集序 | 东晋 | 感悟 · 无常 · 珍惜 |
| 敦煌莫高窟壁画 | 十六国-元 | 孤独 · 信念 · 坚守 |
| 汝窑天青釉洗 | 北宋 | 残缺 · 接纳 · 美 |
| ... | ... | ... |

### 完整能力

- **Agent 工具系统** — 文件读写 / Shell 执行 / Web 请求 / 记忆检索 / Cron 调度 / 技能激活
- **Decision Engine** — 80+ 规则 + LLM 兜底，智能区分闲聊 (Roleplay) 与任务 (Agent)
- **角色卡系统** — Markdown 格式角色定义，支持多角色切换，内置"文物疗愈师"
- **Live2D 形象** — Cubism 4 + PixiJS，可交互的 2D 角色，支持舞台背景/光影/粒子效果
- **语音交互** — Edge TTS 语音合成 + SenseVoice WebSocket 实时语音识别
- **长期记忆** — ReMe Light 系统，全文检索 + 向量检索，跨会话记忆
- **定时任务** — Cron 调度 + Heartbeat 心跳，支持每日问候等周期任务
- **Agent Traces** — 完整的工具调用追踪可视化
- **技能系统** — 可扩展的 Agent 技能 (docx/pptx/xlsx/pdf 文档处理、新闻、天气等)

---

## 快速开始

### 前置条件

- Python 3.11+
- Docker (用于 PostgreSQL + pgvector)

### 1. 克隆并配置环境

```bash
git clone <repo-url> Echoing_Through_Millennia
cd Echoing_Through_Millennia

python3 -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件：

```ini
# ── LLM 设置 ──
LLM_API_KEY=your-api-key-here
LLM_MODEL=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ── 文物知识库 (PostgreSQL + pgvector) ──
RELIC_DATABASE_URL=postgresql+asyncpg://echobot:echobot_dev@localhost:5432/echobot_relics

# ── Embedding 设置 (文物语义检索) ──
EMBEDDING_API_KEY=your-api-key-here
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_DIMENSIONS=1024
```

> 支持任何 OpenAI 兼容接口的 LLM：Qwen (通义千问)、DeepSeek、GPT-4 等。

### 3. 启动 PostgreSQL

```bash
docker compose -f docker/docker-compose.dev.yml up -d
```

启动带有 pgvector 扩展的 PostgreSQL 16 容器。

### 4. 导入文物数据

```bash
python seed_data.py
```

将 52 件历史文物（含故事、情感标签、人生启示）导入 PostgreSQL，并生成 1024 维向量嵌入。

### 5. 启动服务

```bash
# Web Console 模式（推荐）
python -m echobot app --host 0.0.0.0 --port 8000

# 命令行交互模式
python -m echobot chat

# 多渠道网关模式 (QQ / Telegram)
python -m echobot gateway
```

访问 `http://localhost:8000/web` 打开 Web Console。

---

## 工作原理

### 整体架构

```
用户输入
  │
  ▼
┌──────────────────────────────┐
│  Decision Engine (意图路由)   │  80+ 规则 + LLM 兜底
│  闲聊 ← → 任务               │
└──────┬────────────┬──────────┘
       │            │
  闲聊路径       Agent 路径
       │            │
       ▼            ▼
┌─────────────┐  ┌──────────────────┐
│ Plutchik    │  │ SessionAgentRunner│
│ Emotion     │  │ (工具调用)        │
│ Analyzer    │  │ 文件/Shell/Web/   │
│ (8维评分)    │  │ Memory/Cron/Skills│
└──────┬──────┘  └──────────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────────────┐
│ EmotionVector│────→│ GuidedDialogue       │
│ (确定性计算)  │     │ (阶段策略 + Dyad指引) │
│ - Dyads      │     └──────────┬──────────┘
│ - Intensity  │                │
│ - Tensions   │                ▼
│ - Phase      │     ┌─────────────────────┐
└──────┬──────┘     │ RoleplayEngine       │
       │            │ (角色扮演 + 上下文注入) │
       ▼            └──────────┬──────────┘
┌─────────────┐                │
│ RelicMatcher │                ▼
│ (pgvector    │     ┌─────────────────────┐
│  语义匹配)   │     │ NDJSON Stream        │
└─────────────┘     │ → Web UI             │
                    │ (文物卡片+情感标签)    │
                    └─────────────────────┘
```

### Plutchik 情感分析流水线

```
用户: "最近总是感到很焦虑，不知道未来会怎样"
                    │
                    ▼
        ┌───── LLM 评分 ─────┐
        │ joy:        0.05   │
        │ trust:      0.10   │
        │ fear:       0.65   │    ← 恐惧(忧虑)
        │ surprise:   0.10   │
        │ sadness:    0.35   │    ← 悲伤(忧伤)
        │ disgust:    0.05   │
        │ anger:      0.10   │
        │ anticipation: 0.55 │    ← 期待(兴趣)
        └─────────────────────┘
                    │
         Python 确定性计算
                    │
        ┌───────────┴───────────┐
        │ 主导: 恐惧(忧虑) 0.65  │
        │       期待(兴趣) 0.55  │
        │ Dyad: 焦虑 (三级配对)  │  ← anticipation + fear
        │ 强度: basic (中等)     │
        │ 对立: 无               │
        │ 阶段: LISTENING        │
        │ 需求: 找到方向          │
        └───────────┬───────────┘
                    │
                    ▼
        pgvector 语义匹配 → 匹配文物
        "忧虑 兴趣 焦虑 找到方向 未来 迷茫"
                    │
                    ▼
        ┌───────────────────────┐
        │ 匹配: 指南针 (宋朝)    │
        │ 匹配度: 87%           │
        │ 人生启示: "方向从来不是 │
        │   一开始就清晰的..."   │
        └───────────────────────┘
```

### NDJSON 流式输出

聊天接口返回 NDJSON 格式的流式数据：

```json
{"type": "chunk", "delta": "我能感受到你内心的..."}
{"type": "chunk", "delta": "不安..."}
{"type": "done", "response": "完整回复文本",
  "emotion": {
    "emotion_vector": {"joy":0.05, "trust":0.10, "fear":0.65, ...},
    "dominant_emotions": [
      {"emotion":"fear", "score":0.65, "cn":"恐惧", "intensity_name_cn":"忧虑", "color":"#4CAF50"},
      {"emotion":"anticipation", "score":0.55, "cn":"期待", "intensity_name_cn":"兴趣", "color":"#FF9800"}
    ],
    "active_dyads": [
      {"type":"tertiary", "name_cn":"焦虑", "name_en":"anxiety", "score":0.55, "components":["anticipation","fear"]}
    ],
    "intensity_level": "basic",
    "opposite_tensions": [],
    "need": "找到方向",
    "phase": "listening",
    "keywords": ["焦虑", "未来", "迷茫"],
    "primary": "恐惧",
    "secondary": "期待",
    "intensity": 7
  },
  "relic": {
    "id": 12, "name": "指南针", "dynasty": "宋朝",
    "score": 0.8721, "match_reason": "semantic", ...
  }
}
```

---

## 项目结构

```
Echoing_Through_Millennia/
├── echobot/                           # 核心 Python 包
│   ├── app/                           # FastAPI 应用
│   │   ├── routers/                   # API 路由
│   │   │   ├── chat.py                #   聊天流 (NDJSON stream + 同步)
│   │   │   ├── relics.py              #   文物 CRUD + 语义搜索
│   │   │   ├── roles.py               #   角色管理
│   │   │   ├── sessions.py            #   会话管理
│   │   │   ├── web_console.py         #   前端配置 + Live2D/TTS/ASR
│   │   │   ├── cron.py                #   Cron 调度接口
│   │   │   ├── heartbeat.py           #   心跳配置接口
│   │   │   ├── health.py              #   健康检查
│   │   │   └── channels.py            #   多渠道配置
│   │   ├── services/                  # 服务层
│   │   │   └── relic_service.py       #   文物业务逻辑
│   │   └── web/                       # Web Console 前端
│   │       ├── index.html             #   SPA 入口
│   │       ├── app.js                 #   主逻辑
│   │       ├── styles.css             #   样式 (含 Plutchik 配色)
│   │       └── modules/               #   JS 模块
│   │           ├── chat.js            #     聊天交互 + Plutchik 渲染
│   │           ├── api.js             #     NDJSON 流处理
│   │           ├── messages.js        #     消息管理
│   │           ├── live2d.js          #     Live2D 角色
│   │           └── ...
│   ├── orchestration/                 # 对话编排层
│   │   ├── coordinator.py             #   核心协调器 (relic_context_hook)
│   │   ├── decision.py                #   意图路由 (80+ 规则 + LLM)
│   │   ├── roleplay.py                #   角色扮演引擎
│   │   ├── roles.py                   #   角色卡加载器
│   │   └── jobs.py                    #   异步任务管理
│   ├── relic_knowledge/               # 文物知识库 + Plutchik 情感引擎
│   │   ├── emotion_models.py          #   ★ Plutchik 数据模型
│   │   │                              #     PlutchikEmotion / EmotionVector /
│   │   │                              #     EmotionResult / PLUTCHIK_WHEEL
│   │   ├── emotion_analyzer.py        #   ★ LLM 情感分析器
│   │   │                              #     8维评分 + 确定性后处理 + 轨迹追踪
│   │   ├── guided_dialogue.py         #   ★ Dyad 感知对话策略
│   │   │                              #     22种复合情绪 → 专属治疗指引
│   │   ├── relic_matcher.py           #   ★ Plutchik 语义文物匹配
│   │   ├── db.py                      #   PostgreSQL + pgvector 连接
│   │   ├── models.py                  #   Relic 表模型 (Vector 1024)
│   │   ├── embeddings.py              #   向量嵌入服务
│   │   └── retriever.py               #   语义检索 + 关键词检索
│   ├── runtime/                       # 运行时
│   │   ├── bootstrap.py               #   服务初始化 + relic_context_hook
│   │   ├── sessions.py                #   会话存储
│   │   └── system_prompt.py           #   动态系统提示词构建
│   ├── providers/                     # LLM Provider
│   │   ├── base.py                    #   抽象接口
│   │   └── openai_compat.py           #   OpenAI 兼容实现
│   ├── agent.py                       # Agent Core (工具调用循环)
│   ├── tools/                         # Agent 工具集
│   │   ├── filesystem.py              #   文件读写 + 目录浏览
│   │   ├── shell.py                   #   Shell 命令执行
│   │   ├── web.py                     #   HTTP 请求
│   │   ├── memory.py                  #   记忆检索
│   │   ├── cron.py                    #   定时任务管理
│   │   └── skills.py                  #   技能激活
│   ├── tts/                           # 语音合成
│   │   ├── edge.py                    #   Edge TTS (Microsoft)
│   │   └── kokoro.py                  #   Kokoro TTS
│   ├── asr/                           # 语音识别
│   │   └── sensevoice.py              #   SenseVoice (sherpa-onnx)
│   ├── memory/                        # 长期记忆
│   │   └── support.py                 #   ReMe Light 集成
│   ├── scheduling/                    # 调度服务
│   │   ├── cron.py                    #   Cron 任务调度
│   │   └── heartbeat.py               #   心跳服务
│   ├── channels/                      # 多渠道
│   │   └── platforms/                 #   平台适配
│   │       ├── qq.py                  #     QQ 机器人
│   │       └── telegram.py            #     Telegram Bot
│   └── skills/                        # Agent 技能包 (Git 子模块)
├── roles/                             # 角色卡目录
│   └── 文物疗愈师.md                    #   内置疗愈师角色
├── docker/                            # Docker 配置
│   └── docker-compose.dev.yml         #   PostgreSQL 16 + pgvector
├── .echobot/                          # 运行时数据
│   ├── sessions/                      #   会话持久化
│   ├── cron/                          #   Cron 任务存储
│   ├── models/                        #   ASR 模型缓存
│   └── channels.json                  #   渠道配置
├── .env                               # 环境配置
├── seed_data.py                       # 文物数据导入 (52 件)
└── requirements.txt                   # Python 依赖
```

---

## API 接口

### 聊天

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | 聊天流 (NDJSON)，`done` 事件含 Plutchik 情感数据 + 文物匹配 |
| POST | `/api/chat` | 同步聊天 |
| GET | `/api/chat/jobs/{id}` | 获取异步任务状态 |
| GET | `/api/chat/jobs/{id}/trace` | 获取 Agent 工具调用追踪 |
| POST | `/api/chat/jobs/{id}/cancel` | 取消进行中的任务 |

### 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/current` | 当前会话 |
| PUT | `/api/sessions/current` | 切换会话 |
| POST | `/api/sessions` | 新建会话 |
| PATCH | `/api/sessions/{name}` | 重命名会话 |
| PUT | `/api/sessions/{name}/role` | 设置会话角色 |
| PUT | `/api/sessions/{name}/route-mode` | 设置路由模式 (chat/agent) |
| DELETE | `/api/sessions/{name}` | 删除会话 |

### 文物知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/relics` | 文物列表 (分页/按朝代/分类筛选) |
| GET | `/api/relics/{id}` | 文物详情 |
| GET | `/api/relics/random` | 随机推荐文物 |
| POST | `/api/relics/search` | 文物语义搜索 (pgvector) |

### 角色管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/roles` | 角色列表 |
| GET | `/api/roles/{name}` | 角色详情 |
| POST | `/api/roles` | 创建自定义角色 |
| PUT | `/api/roles/{name}` | 更新角色 |
| DELETE | `/api/roles/{name}` | 删除角色 |

### 语音服务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/web/tts/voices` | TTS 可用语音列表 |
| POST | `/api/web/tts` | 语音合成 (返回音频) |
| GET | `/api/web/asr/status` | ASR 服务状态 |
| POST | `/api/web/asr` | 单次语音识别 |
| WebSocket | `/api/web/asr/ws` | 实时流式语音识别 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET/PUT | `/api/heartbeat` | 心跳配置 |
| GET | `/api/cron/status` | Cron 调度状态 |
| GET | `/api/cron/jobs` | 定时任务列表 |
| GET/PUT | `/api/channels/config` | 多渠道配置 |
| GET | `/api/channels/status` | 渠道连接状态 |

---

## 环境变量

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `LLM_API_KEY` | 是 | LLM API Key | `sk-xxx` |
| `LLM_MODEL` | 是 | 模型名称 | `qwen-plus` / `gpt-4` / `deepseek-chat` |
| `LLM_BASE_URL` | 是 | API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `RELIC_DATABASE_URL` | 否 | PostgreSQL 连接串，未设置则禁用文物功能 | `postgresql+asyncpg://echobot:echobot_dev@localhost:5432/echobot_relics` |
| `EMBEDDING_API_KEY` | 否 | Embedding API Key (文物语义检索) | `sk-xxx` |
| `EMBEDDING_MODEL` | 否 | Embedding 模型 | `text-embedding-v3` |
| `EMBEDDING_BASE_URL` | 否 | Embedding API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `EMBEDDING_DIMENSIONS` | 否 | 向量维度 | `1024` |
| `TTS_PROVIDER` | 否 | TTS 引擎 | `edge` (默认) / `kokoro` |
| `ASR_AUTO_DOWNLOAD` | 否 | 自动下载 ASR 模型 | `true` / `false` |

---

## 依赖项

**核心框架：** FastAPI, Uvicorn, Pydantic, PyYAML

**数据库：** SQLAlchemy, asyncpg, pgvector

**AI/LLM：** agentscope, reme-ai[light]

**语音：** edge-tts, sherpa-onnx

**多渠道：** qq-botpy, python-telegram-bot

**工具：** Pillow, aiohttp

---

## 许可证

本项目仅用于学习和研究目的。
