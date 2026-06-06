# Vellum — 设计 spec

> 状态：设计稿，待 review。
> 日期：2026-06-06
> 前身：engram（原型，位于 `/Users/wangyuhao/Develop/personal/engram`，保留作参考矿）。

---

## 1. 背景与动机

engram 是一个原型：用大量工程脚手架（backbone 知识图谱、router 多 lens、投射差集、forebodes/method_cases/contacts 多独立根、"灵魂一击 / 升维"等刻意设计）去补**当年模型不够强**的地方 —— 手搓图谱、手搓投射逻辑，本质是不信任模型自己能做深、能联想、能给出"你没想过的角度"。

判断变了：**现在的强模型在 context 内就能完成这些推理。** 那套脚手架不再是杠杆，而是负担 —— 架构和产品逻辑都被它拖乱。

所以本次重做的第一性原则：

> **把工程收敛到模型替代不了的部分；推理整个外包给模型。**

模型唯一替代不了的，是它**跨会话无状态**这件事。"记得聊过的一切""默默懂你"没法活在模型里，必须落在持久层。所以 Vellum 真正不可压缩的核心不是"推理"，而是两件朴素的事：

1. **存什么、怎么取回来** —— 长期记忆
2. **怎么把"你是谁"沉淀成会演化的东西、每轮喂回去** —— 个人模型

工程的艺术从"设计聪明的 pipeline"变成"设计往 context 里塞什么"。

---

## 2. 一期目标与范围

**一句话**：一个**懂你的对话产品** —— 长期记忆 + 默默建模 + 可插拔模型。

**一期做：**

- 单一对话场景（ChatGPT 式一问一答），**web 聊天是核心消费面**。
- 长期记忆：记得聊过的所有内容，按需召回。
- 默默建模：聊天过程中持续更新你的人格维度 / 性格 / 关键事实，作为回答参考。
- 可插拔模型接入层（chat / embedding）。

**一期不做（推后，非第一性反对，纯属节奏）：**

- MCP、其他采集 channel（微信/飞书等）。
- 检查面板（dossier / facts / 记忆检索 / 维度曲线）可做最小化或后置；维度面板不急。
- push / 主动打扰 / 常驻 advisor。
- 多用户 / 协作 / SaaS（永久反对：单用户、本地、数据隔离）。

**永久丢弃（相对 engram）：** 知识图谱 backbone、router 多 lens、投射差集、forebodes / method_cases / contacts 独立根、intent gate、"升维"叙事。

**用户契约（沿用 engram）**：单人 + 数据完全隔离；想用自己 clone 本地跑。

---

## 3. 架构总览

```
┌──────────────┐   消费回路（快）   ┌─────────────────────────────┐
│   你说一句    │ ─────────────────▶│ 组装 context → 强模型 → 流式答 │
└──────────────┘                    └─────────────┬───────────────┘
                                                  │ 对话告一段落
                                    沉淀回路（慢） ▼  异步后台
                              读未消化片段 + 当前模型 → 一趟 consolidation
                              → dossier 改写 / trait 贝叶斯更新 / facts 增改 / summary
```

三个支柱：

- **接入层**（可插拔）：chat + embedding。
- **两个回路**：消费（快、同步、面向用户）/ 沉淀（慢、异步、后台建模）。
- **四存储两层**：底层无损原始记忆 + 上层有损个人模型。

设计原则：每个单元单一职责、接口清晰、可独立理解与测试。文件长了就是职责过载的信号。

---

## 4. 接入层（可插拔模型）

直接搬 engram 成熟实现，几乎不改：

- **chat**：`shared/llm/client.py` → `api/app/llm/client.py`。OpenAI-compatible 统一协议，内置 12 家 preset（openai / anthropic / gemini / grok / openrouter / deepseek / moonshot / qwen / glm / minimax / ark / ollama），重试退避、JSON 健壮解析、temperature/response_format 跨厂兼容、流式、tool-calling、调用 trace。
- **embedding**：`api/app/lib/embed.py` → `api/app/llm/embed.py`。OpenAI-compatible `/embeddings`，`EMBED_* → LLM_*` 自动 fallback；支持 ark_multimodal style。

**关键不对称（写进实现约束）：**

- **chat 模型 = 每轮可热插拔**。今天 Claude 明天 GPT 无所谓，历史不受影响。
- **embedding 模型 = 装机时选定即钉死**。所有历史向量活在它的向量空间里；换 embedding ⇒ 维度/语义全变 ⇒ 旧向量全废，必须**重建索引迁移**才能换。

**模型选型推后**，接入层与具体模型解耦即可。embedding 默认值待定（候选：本地 `bge-m3` / `text-embedding-3-small`），中文检索质量是首要考量。

---

## 5. 存储模型

四张主表 + 一个向量索引，分两层。

### 5.1 底层 · 原始记忆（无损、即时写、不跑模型）

```
conversations
  id                       PK
  title                    可空（可后填）
  created_at
  last_active_at
  consolidated_through_turn  已消化到的 turn（幂等沉淀的水位线）

messages
  id            PK
  conv_id       -> conversations.id
  turn          会话内序号（排序 + 还原上下文）
  role          'user' | 'assistant'
  content       逐字原文（user 与 assistant 都存）
  created_at

vector_refs            -- 把 HNSW 的整型 label 映射回来源
  id            PK      （= HNSW label）
  ref_type      'message' | 'summary'
  ref_id        -> messages.id（仅 user 轮） / summaries.id
```

- **HNSW 向量索引**只索引值得当搜索键的东西：**user 消息 + summary**。assistant 回答**不进向量**（见 §6 理由）。
- 向量库只存 `embedding + label`；label 经 `vector_refs` 指回文本来源。**文本只有一个家：`messages` / `summaries`。**

### 5.2 上层 · 个人模型（对话边界蒸馏、可有损）

```
summaries
  id            PK
  conv_id       -> conversations.id
  content       1 段话摘要（聊了啥 / 结论 / 承诺）；被 embed
  created_at

dossier                   -- 单行（当前唯一真相源），叙述式"你是谁"
  content
  updated_at

trait_current             -- 当下切片：live、原地覆盖、进 context
  dimension     PK         e.g. 'ocean' / 'mbti' / 'schwartz' / 'regulatory_focus'
  content_json            各子维度当前贝叶斯状态 {score μ, tau τ, confidence, evidence}
  sample_count
  updated_at

trait_history             -- 历史轨迹：只增、冻结、画演化曲线
  id            PK
  dimension
  content_json            某次 consolidation 后该维度的冻结拷贝
  taken_at

facts                     -- pin board：无损原子，每轮常驻，用户可改
  id            PK
  text
  status        'active' | 'superseded'
  source_conv_id
  created_at
  updated_at
```

**三块个人模型各凭不同理由立身：**

- **trait_current / trait_history**：凭"能打分、能画演化曲线"（prose 做不到）。`trait_current` 原地覆盖；每次 consolidation 更新完 live、**紧接着**冻一份进 `trait_history`（**创建即归档**，不等下次更新，故永不丢失）。
- **facts（pin board）**：凭"无损"。dossier 会被 compaction 软化/丢弃，而过敏源、家人名字、身份锚、关键偏好必须逐字穿过每次压缩、原样进 context。它**不是 trait 维度**（无打分、无曲线），只有 active/superseded 生命周期。
- **dossier**：凭"具体性 + 让模型读你本人"。会长大 ⇒ 超预算时 compaction（模型重写压缩）。一期单行当前态，不做版本史。

**记忆 vs facts 的分工**：facts = 最吃重、值得每轮常驻的少数关键事实；原始记忆 = 长尾，按需检索。一个常驻、一个召回。

---

## 6. 消费回路（快 · 同步 · 面向用户）

每个用户轮：

```
1. 立刻持久化 user 消息（messages）+ embed → 写入向量索引（vector_refs: message）
2. 组装 context：
     system = 人设（默认中性 / 可切换）
            + 全部 active facts
            + trait_current 紧凑摘要（各维度 score）
            + dossier（当前）
     history = 召回的历史片段（见下）+ 本对话最近若干轮（短期连续性）
3. 流式产出回答（chat_text_stream）
4. 立刻持久化 assistant 消息（messages，不 embed）
```

**召回（历史片段）三步：**

1. 当前问题 embedding → 向量层搜 → 命中若干**锚点**（某条你的旧话 / 某段 summary）。
2. 拿锚点的 `conv_id`，按 `turn` 把那段对话前后捞出 —— **assistant 回答在这步被连带捞回（靠链接，不靠向量）**。
3. 去重、按 token 预算裁剪 → 进 context。

**为什么 assistant 回答不进向量** —— 不止省空间，更是质量：模型回答又长又杂，一条横跨多话题，embedding 很"浑"，当锚点反而搅乱召回；你的话短、summary 紧，是干净得多的钥匙。"我之前给你啥建议"这种回忆靠 summary 命中即可。（留开关：要极限召回可把 assistant 也嵌入，默认不嵌。）

**人设**：system prompt 注入。默认**中性懂你**（好用的通用助手，个性化只来自"它记得你、建模你"）；可切换到其他基调（如冷酷智者）。默认基调文案待定。

---

## 7. 沉淀回路（慢 · 异步 · 后台建模）

**触发**：对话边界 —— 显式开新会话 / 空闲超时 / 应用关闭。

**机制**：单用户本地，**一个 asyncio 后台任务**即可，不上 Celery/Redis。读 `consolidated_through_turn` 水位线，只处理**未消化的对话片段 + 当前模型状态**；以 `consolidated_through_turn` 标记推进，**崩了重跑幂等**。

**一趟 consolidation 的产物（读「未消化片段 + 当前模型」，同源并列输出）：**

1. **dossier 改写**：把新对话融进叙述；超 size 预算时一并 compaction（pinned facts 在独立表，不受影响）。
2. **trait 更新**：每个启用维度走 extract（搬 engram 的 `extract.spt` 提取 prompt，把"single entry"改述为"this conversation"）→ `profile_merge` 贝叶斯递推 → 写 `trait_current` + 冻结 `trait_history`。
3. **facts 增 / 改 / 退**（active ↔ superseded）。
4. **summary**：1 段话写入 `summaries` + embed → 写入向量索引（vector_refs: summary）。

节律总结：**底层逐句即时写（保证"记得"）；上层三块按对话边界批量重算（保证"懂你"）。** 单句几乎不该撼动人格，整段对话是一块连贯证据，整体消化比逐句打分更准也更省。

---

## 8. 从 engram 复用 / 丢弃清单

源仓库：`/Users/wangyuhao/Develop/personal/engram`

| 处理 | 模块 | 说明 |
|---|---|---|
| 几乎原样搬 | `shared/llm/client.py` | 可插拔 chat 接入层本体 |
| 几乎原样搬 | `api/app/lib/embed.py` | embedding 接入层 + fallback |
| 搬，轻改 | `api/app/lib/vector_store.py` | 60 行 HNSW 封装；改进点：勿每次 `add` 都存盘，批量化 |
| 搬核心逻辑 | `api/app/lib/profile_merge.py` | 贝叶斯共轭递推 = trait 累积。依赖 `graph_rules.PROFILE_MERGE`（gamma/tau_prior/tau_ref/min_conf）与一个 dimension loader，一并搬。改为**按对话边界**调用，而非按 entry |
| 搬资产 | `api/app/config/dimensions/{ocean,mbti,schwartz,regulatory_focus}` | config + extract.spt + rubric 三件套，提取 prompt 写得好（null 纪律 / 不许往中位数缩 / 要 evidence） |
| 升级搬 | `dimensions/facts` | 旧系统 facts 挂 dimension 走"覆盖"；新系统提升为独立 `facts` pin board 表（active/superseded、用户可改） |
| 丢弃 | `backbone_pipeline`(1420) `agent_tools`(1284) `agent_runtime`(627) `router` `slice_pipeline` `retrieval` `entry_signals` `capture_intent` | 图谱 / router / agent / 投射机器 |

---

## 9. 技术栈与目录

**栈（沿用 engram）**：Python 3.12 + FastAPI + SQLite + hnswlib（后端）；React + Vite + Tailwind（前端）。

```
vellum/
  api/
    app/
      main.py
      llm/        client.py · embed.py          # 接入层（搬）
      store/      db.py · vectors.py · messages.py · model.py   # 持久层 + DAO
      chat/       assemble.py · respond.py       # 消费回路
      consolidate/ runner.py · dossier.py · traits.py · facts.py · summary.py  # 沉淀回路
      config/
        dimensions/   ocean · mbti · schwartz · regulatory_focus   # 搬
        persona/      neutral（默认）· 其他基调
      routes/     chat.py · inspect.py · admin.py
    migrations/                                  # forward-only、幂等
    requirements.txt · .env.example
  web/                                           # 聊天面优先；检查面板后置
  docs/specs/
  AGENTS.md · README.md
```

**配置（沿用 engram 的 env 约定）**：`LLM_BASE_URL/API_KEY/MODEL`（或 `LLM_PROVIDER` preset）；`EMBED_*` 缺省 fallback 到 `LLM_*`。

**数据**：全新库，**不迁移 engram 原型数据**。迁移文件 forward-only + 幂等。

**约定（沿用 engram AGENTS.md 精神）**：canonical enum 用英文（`role`、`status`、`dimension` key、`node`…）；prompt 默认英文、指示模型"match user's language"，不在 prompt 里钉输出语种；中文是前端 i18n 展示层的事。

---

## 10. 一期验收标准

- 能聊：web 聊天，流式回答。
- 切 chat 模型不影响历史记忆与建模。
- 关掉/切换对话后，后台 consolidation 真的更新了 dossier / trait_current / facts / summaries。
- 新会话能召回旧对话内容（含当时 assistant 的建议），证明记忆生效。
- `trait_history` 随对话累积出多个时间点（曲线有料）。
- pinned facts 在多轮后仍逐字常驻，未被 dossier compaction 抹掉。

---

## 11. 待定（open）

- embedding 默认模型（押后；中文质量优先）。
- 人设默认基调的具体文案。
- 对话边界"空闲超时"的阈值。
- dossier 是否需要版本史（一期不做）。
- 检查面板做到什么程度（一期可最小或后置）。

---

## 设计取舍备忘（口径）

- **效果优先**：凡 token/算力 vs 质量的取舍，默认偏质量。
- **单一职责、小文件**：文件变大是职责过载信号。
- 推理外包给模型，工程只管"持久化 + 取回 + 沉淀 + 往 context 塞什么"。
