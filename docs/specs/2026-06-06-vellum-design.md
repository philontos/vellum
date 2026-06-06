# Vellum — 设计 spec

> 状态：设计稿 v4（加入评测 + 观测/traces），待 review。
> 日期：2026-06-06 · 前身：engram（保留作参考矿，位于 `/Users/wangyuhao/Develop/personal/engram`）。

---

## 1. 背景与动机

engram 是一个原型：用大量工程脚手架（backbone 知识图谱、router 多 lens、投射差集、forebodes/method_cases/contacts 多独立根、"灵魂一击 / 升维"等刻意设计）去补**当年模型不够强**的地方 —— 手搓图谱、手搓投射逻辑，本质是不信任模型自己能做深、能联想。

判断变了：**现在的强模型在 context 内就能完成这些推理。** 那套脚手架不再是杠杆，而是负担。

本次重做的第一性原则：

> **把工程收敛到模型替代不了的部分；推理整个外包给模型。**

模型唯一替代不了的，是它**跨会话无状态**。所以 Vellum 真正不可压缩的核心不是"推理"，而是两件朴素的事：①存什么、怎么取回来（长期记忆）②怎么把"你是谁"沉淀成会演化的东西、每轮喂回去（个人模型）。工程的艺术从"设计聪明的 pipeline"变成"设计往 context 里塞什么"。

---

## 2. 一期目标与范围

**一句话**：一个**懂你的对话产品** —— 一条永不结束的对话流 + 长期记忆 + 默默建模 + 可插拔模型。

**一期做**：单一永恒对话流（无"新建会话"）、长期记忆、默默建模（人格维度/性格/关键事实作背景参考）、可插拔接入层（chat / embedding）。

**一期不做（推后）**：MCP、其他采集 channel；检查面板（dossier / facts / 记忆检索 / 维度曲线）可最小化或后置，维度面板不急；push / 主动打扰；多用户 / 协作 / SaaS（永久反对：单用户、本地、数据隔离）。

**永久丢弃（相对 engram）**：知识图谱 backbone、router 多 lens、投射差集、forebodes / method_cases / contacts 独立根、intent gate、"升维"叙事。

---

## 3. 第一性 / 高度（设计铁律）

> **当前问题是主角；个人模型和过往都是 reference，不是镜头。**
> 先把问题本身答好；只在问题确实关于"你"时，才借这些参考。不硬套、不无端剖析用户。

这是老 engram 最大毛病的反面（它把"你是谁"当强制镜头扣每个回答上，什么问题都掰成自我分析）。两个推论：

- **重点是"怎么框"，不只是"塞什么"。** dossier / traits / 召回片段进 prompt 时明确标成「背景参考」+ 指令"先答当前问题，相关才用"。
- **用多少由问题决定，模型自己调档。** "怎么居中 div" → dossier 无关，干净答；"该不该接 offer" → 才拉满。

**"永不消逝的上下文"是构造出来的错觉**（窗口有限，不可能全塞进去）：

```
= 最近的尾巴（逐字在窗口） + dossier+facts+traits（永远在场=一切的提炼） + 按需召回的旧片段
```

**建模是让错觉成立的引擎**：老 turn 滑出窗口前不必"等着被消化"——它仍在 messages、可召回；而 dossier/facts/traits 一直在提炼"你是谁"。窗口始终有界，记忆却从不丢失。

---

## 4. 架构总览

```
┌──────────────┐  消费回路(快·同步)  ┌─────────────────────────────┐
│   你说一句    │ ──────────────────▶│ 组装 context → 强模型 → 流式答 │
└──────────────┘ (永远同一条流，无新对话)└─────────────┬───────────────┘
        │ 每个 user 轮即时落库                          │
        ▼                                    后台建模(慢·异步·多游标)
  facts 每轮 eager 提取            trait 攒 K 轮批量 / summary 按段 / dossier 攒 M 轮
```

三支柱：**接入层**（可插拔 chat + embedding）；**两类处理**（消费快·同步 / 建模慢·异步）；**三层存储**（记忆层 + 个人模型层 + 观测层）。

设计原则：单一职责、接口清晰、可独立理解与测试；文件变大是职责过载信号。

---

## 5. 接入层（可插拔模型）

直接搬 engram 成熟实现，几乎不改：

- **chat**：`shared/llm/client.py` → `api/app/llm/client.py`。OpenAI-compatible，12 家 preset，重试退避、JSON 健壮解析、temperature/response_format 跨厂兼容、流式、tool-calling、调用 trace。
- **embedding**：`api/app/lib/embed.py` → `api/app/llm/embed.py`。`EMBED_* → LLM_*` 自动 fallback。

**关键不对称（写进约束）：**

- **chat 模型 = 每轮可热插拔**，历史不受影响。
- **embedding 模型 = 装机时选定即钉死**：历史向量活在它的向量空间里，换 embedding ⇒ 旧向量全废，须重建索引迁移。

模型选型推后。embedding 选择标准 = **在用户日常使用语言上检索强**（不专指中文，看用户用什么语言）—— 写进 README 安装指引。

---

## 6. 存储模型

### 6.0 先分清：两套完全不同的存储

```
①  文本存储（SQLite 表）   —— 存所有真实文字，逐字
②  向量索引（HNSW 文件）   —— 只存 embedding（语义指纹）+ 一个指回①的编号；【里面没有任何文本】
```

向量索引像书的"索引页"：只有"关键词→页码"，正文还在书里。**文本只有一个家（①）；②只是搜索层。**

### 6.1 三种文字，按"缩放级别"理解

```
原始文本（messages）  = 1倍：每一句话逐字（user + assistant）
summary（summaries）  = 拉远：流的一段的要点，一段话
dossier               = 拉到最远：你这个人是谁，总共一份
```

即"说了什么 → 这段聊了什么 → 你是谁"。

### 6.2 记忆层（原始 + 检索机器；单一永恒流，无 conversations 表）

```
messages
  id           PK
  turn         全局单调序号（唯一顺序，不分 conv）
  role         'user' | 'assistant'
  content      逐字原文
  created_at

summaries                -- 流的一段的要点（= 检索钥匙），属记忆机器，不是"个人模型"
  id           PK
  start_turn · end_turn
  content      模型写的一段话；被 embed
  created_at

vector_refs              -- 把 HNSW 整型 label 映射回来源
  label        PK (= HNSW label)
  ref_type     'message' | 'summary'
  ref_id       -> messages.id（仅 user 轮）/ summaries.id

cursors                  -- 每个建模 concern 一个独立水位线（见 §8）
  concern      PK        'facts' | 'trait' | 'summary' | 'dossier'
  through_turn           已处理到第几 turn
  updated_at
```

**谁会被算 embedding（在②里有一条）：** user 消息 ✅ / assistant ❌ / summary ✅。assistant 不进向量（长回答 embedding 浑、当锚点搅乱召回），靠 `turn` 邻域**链接还原**被连带召回（见 §7）。

### 6.3 个人模型层（你是谁；可有损）

```
dossier        content · updated_at                       -- 单行、每轮常驻
trait_current  dimension(PK) · content_json · sample_count · updated_at   -- live、原地覆盖、进 context
trait_history  id · dimension · content_json · taken_at    -- 只增、冻结、画曲线
facts          id · text · status('active'|'superseded') · source_turn · created_at · updated_at  -- pin board
```

三块各凭不同理由立身：

- **trait_current / trait_history**：凭"能打分、能画曲线"。`trait_current` 原地覆盖；每次更新完 live、**紧接着**冻一份进 `trait_history`（**创建即归档**，不等下次更新，永不丢失）。
- **facts（pin board）**：凭"无损"。dossier 会被 compaction 软化/丢弃，而过敏源、家人名字、身份锚、关键偏好必须逐字穿过每次压缩、原样进 context。不是 trait（无打分、无曲线），只有 active/superseded 生命周期。
- **dossier**：凭"具体性 + 让模型读你本人"。会长大 ⇒ 超 size 预算时 compaction。一期单行当前态，不做版本史。

> **summaries vs dossier**：summary = 情节（多条、带 turn 区间、可搜的检索入口）；dossier = 画像（一份、当前、每轮常驻、不进搜索）。

> **谁增谁不增**：增（都便宜）= messages · summaries · trait_history · 向量索引；有界 = dossier（覆盖）· trait_current（每维一行）· facts（生命周期）。

### 6.4 观测层（traces · 诊断 exhaust，与记忆/模型分开）

每次 LLM 调用的诊断记录，**不进检索、不进建模、不是记忆**，纯调试/分析/评测用。

```
traces
  id           PK
  turn         关联 turn（建模调用可空）
  stage        'chat' | 'facts' | 'trait' | 'summary' | 'dossier'
  model · params              model 名、temperature 等
  prompt · output            拼好的完整输入 + 原始输出（重字段）
  prompt_tokens · completion_tokens · duration_ms   轻量元数据
  pinned       bool          手动保留，豁免 prune
  created_at
```

**保留策略（默认"滚动窗口 + 元数据长留 + 手动 pin"）：**

- 完整 `prompt`/`output`：默认只留**最近 N 轮 / D 天**；prune 时**清空这两个重字段、保留整行**（元数据长留，很小，供长期成本/延迟分析）。
- `pinned=1`（神回答 / 翻车现场）豁免 prune。
- **不选"默认不存、手动勾选才存"**：出问题往往事先不知道要勾，正好丢现场。
- 复用 engram `capture_llm_calls` / `trace_recorder`。它是 §11 评测 B/D 层的原料（回放"当时到底喂了什么"）。

---

## 7. 消费回路（快 · 同步 · 面向用户）

每个 user 轮：

```
1. 存 user 消息（messages，全局 turn++）+ embed → 写入②（vector_refs: message）
2. 组装 context（按 §3「问题是主角」框）：
     [指令]  先直接回答当前问题；以下为背景参考，相关才用，勿硬套勿剖析
     人设    默认中性 / 可切换
     [参考]  dossier + 全部 active facts + trait_current 紧凑摘要   —— 永远在场、框成参考
     [参考]  召回的旧片段（阈值门控，见下）
     尾巴    最近 N turn 逐字（短期连续性，预算内）
3. 流式产出回答（chat_text_stream）
4. 存 assistant 消息（messages，不 embed）
```

**召回 = 每轮都搜、只注入越过相关性阈值的**（搜便宜，注入噪声才贵；新话题没片段越线 → 零注入零噪声）。

**向量命中怎么翻回原文（label → messages）：**

```
knn_query 返回 label →（vector_refs）→ ref_type, ref_id
  · message 命中：ref_id = messages.id → 取其 turn
       SELECT * FROM messages WHERE turn BETWEEN turn-W AND turn+W   ← 含中间的 assistant 轮 ★
  · summary 命中：ref_id = summaries.id
       两者都取回：① summary.content 总结文字（直接用）
                   ② [start_turn, end_turn] → 需要逐字就 WHERE turn BETWEEN start AND end 捞原始 messages
合并去重 → 按 token 预算裁剪 → 作为「背景参考」进 context
```

★ 这一步实现"assistant 不进向量也能被完整召回"——**向量只负责定位锚点，还原靠 `turn` 顺序在 messages 里切邻域。** 之后交给强模型自行取舍，不做二次 re-rank。

**人设**：默认**中性懂你**；可切换其他基调。默认文案待定。

---

## 8. 后台建模（慢 · 异步 · 多游标各自节奏）

**核心：建模与"窗口驱逐"彻底解耦。** turn 掉出尾巴只是从 prompt 移除，它仍在 `messages`、可召回 —— 所以不存在"出窗口前必须消化"，建模各组件按自己的节奏推进、不等驱逐（等驱逐才提，太晚，长会话里画像会一直陈旧）。

**窗口驱逐（纯聊天上下文，不属建模）**：尾巴只保留最近 N turn 逐字进 prompt；更老的掉出尾巴，仍在 messages、靠召回够回来。

**后台建模（单 asyncio 任务；每个 concern 一个游标 `cursors.through_turn`，处理 `(游标, now]` 的新 turn，成功后推进游标，崩了重跑幂等）：**

| concern | 节奏 | 做什么 | 写入 |
|---|---|---|---|
| **facts** | **eager，每个 user 轮**（异步，与回答并行，不加延迟） | 从该轮提取离散事实 | `facts` 增/改/退 |
| **trait** | **批量，每攒够 K 轮 / 或空闲** | 对这段跑**一次** extract（每维一次 LLM）→ 每子维度一个 `(x,c)` | `profile_merge` 贝叶斯（**算法不变**）→ `trait_current` 覆盖 + `trait_history` 冻结 |
| **summary** | 一段流闭合时（空闲 gap / 够长） | 给 `[start,end]` 写一段要点 | `summaries` + embed → ② |
| **dossier** | 每攒够 M 轮 / 或空闲 | 融入新内容，超 size 预算时 compaction | `dossier` 覆盖 |

**为什么 facts eager、trait 批量**：facts 常常"一句定"且即时价值高（刚说的事下句就要用）→ 每轮；trait"一句不撼动 OCEAN"、需要一个 span 才准 → 批量。节律差异从两者**本性**掉出来，不是硬定。

**trait 批量与贝叶斯怎么配**：`profile_merge` 是 cadence-agnostic 的，只吃观测 `(x,c)`，不在乎来自一句还是一批。批量 = 一批喂**一个**观测，算法零改动。批内天然做了平均，喂进去更干净 —— 批量对 trait 是正解不是妥协。唯一要重调的旋钮是遗忘因子 **γ ≈ γ_每轮^K**（每批只遗忘一次，要补偿更新次数变少）；追踪视野 1/(1−γ) 的单位从"条"变"批"。extract prompt 从 "single entry" 改 "this span"，让置信 `c` 反映"这段里信号多强/多一致"。

**turn 的一生**：逐字在尾巴 →（按各游标节奏）被各建模分别消化 → 此后只活在 messages（可召回）+ 蒸馏进 facts / trait / summary / dossier。

> 具体的 K / M / 空闲阈值 / γ / 召回阈值是**可调参数**（§13）；游标维护、触发循环、事务/幂等的**代码机制落在实现计划**，不在本 spec。

---

## 9. 从 engram 复用 / 丢弃清单

源仓库：`/Users/wangyuhao/Develop/personal/engram`

| 处理 | 模块 | 说明 |
|---|---|---|
| 几乎原样搬 | `shared/llm/client.py` | 可插拔 chat 接入层本体（含 `capture_llm_calls`） |
| 几乎原样搬 | `api/app/lib/embed.py` | embedding 接入层 + fallback |
| 搬，轻改 | `api/app/lib/vector_store.py` | 60 行 HNSW 封装；改进：勿每次 `add` 都存盘，批量化 |
| 搬核心逻辑 | `api/app/lib/profile_merge.py` | 贝叶斯共轭递推 = trait 累积。依赖 `graph_rules.PROFILE_MERGE` + dimension loader，一并搬。改为**按 trait 批**调用、γ 重调 |
| 搬资产 | `config/dimensions/{ocean,mbti,schwartz,regulatory_focus}` | config + extract.spt + rubric；"single entry"→"this span" |
| 升级搬 | `dimensions/facts` | 旧系统挂 dimension 走"覆盖"；新系统提升为独立 `facts` pin board + eager 每轮 |
| 参考 | `api/app/lib/trace_recorder.py` | traces 观测层 |
| 丢弃 | `backbone_pipeline`(1420) `agent_tools`(1284) `agent_runtime`(627) `router` `slice_pipeline` `retrieval` `entry_signals` `capture_intent` | 图谱 / router / agent / 投射机器 |

---

## 10. 技术栈与目录

**栈（沿用 engram）**：Python 3.12 + FastAPI + SQLite + hnswlib（后端）；React + Vite + Tailwind（前端）。

```
vellum/
  api/app/
    main.py
    llm/         client.py · embed.py                    # 接入层（搬）
    store/       db.py · vectors.py · memory.py · model.py · traces.py  # 三层存储 DAO + cursors
    chat/        assemble.py · respond.py                 # 消费回路
    model_loop/  runner.py · facts.py · traits.py · summary.py · dossier.py  # 后台建模（多游标）
    config/      dimensions/{ocean,mbti,schwartz,regulatory_focus} · persona/{neutral,...}
    routes/      chat.py · inspect.py · admin.py
  api/migrations/                                         # forward-only、幂等
  api/evals/                                              # golden 召回集 · 合成人格 harness · 高度 rubric
  api/requirements.txt · api/.env.example
  web/                                                    # 单一永恒对话流 UI；检查面板后置
  docs/specs/ · AGENTS.md · README.md
```

env 沿用（`LLM_*` / `EMBED_*` fallback）；全新库不迁老数据；迁移 forward-only 幂等；enum 英文、prompt 默认英文 match user's language、中文走前端 i18n。

---

## 11. 评测

没有"全部后置"——分层，机械层先行、保真/质量层持续。

| 层 | 测什么 | 怎么测 | 时机 |
|---|---|---|---|
| **A 管道正确性** | 落库/召回/游标幂等/贝叶斯算对/facts 穿过 compaction | 自动化单测（≈ §12 验收项） | **先行（TDD）** |
| **B 召回质量** | query → 召回是否相关 | **golden memory 集**：标注「query→应召回」，量 recall@k | 早搭、持续 |
| **C 建模保真** | trait/dossier 是否反映其人 | **合成人格 round-trip**（见下） | 早搭、持续 |
| **D 主观质量** | 像不像懂我 / 有没有乱剖析 | LLM-judge rubric + with/without-memory A/B + dogfood | 连续信号，**不设硬 gate** |

**合成人格 round-trip（C 层关键）**：造一个**已知**人格（"高开放、INTJ、重自主"）→ 用它生成一批对话喂入 → 验 `trait` 收敛到该人格 / `facts` 抓到 / `dossier` 吻合（dossier 用 LLM-judge 对照人格打分）。**Ground truth 由构造保证**，是唯一能客观给"建模 work 不 work"打分的手段。

**高度守卫（D 层可回归的一条）**：一批无关问题（"怎么居中 div"）→ LLM-judge 检查回答有没有乱剖析用户 → 作为回归测试，守住 §3 铁律。

trace（§6.4）是 B/D 层的原料（回放"当时到底喂了什么"）。

---

## 12. 一期验收标准

- 能聊：web 单一对话流，流式回答。
- **高度对**：问"怎么居中 div"不剖析你；问人生决策才拉满画像。
- 切 chat 模型不影响历史记忆与建模。
- facts 在你刚说完的几轮内就被钉上（eager 生效）。
- trait 按批更新：攒够 K 轮跑一次，`trait_current` 变、`trait_history` 多一格。
- 早期已滑出窗口的内容（含当时 assistant 建议），之后能被召回（"永不消逝"成立）。
- pinned facts 多轮后仍逐字常驻，未被 dossier compaction 抹掉。
- traces 滚动 prune 后元数据仍在、pinned 行不被清。

---

## 13. 待定（可调参数 / open）

- embedding 默认模型（按用户主语言）。
- 人设默认基调文案。
- 节律参数：trait 批 K、dossier 批 M、空闲超时、尾巴 token 预算、召回相关性阈值、γ（按 K 重调）。
- traces 保留期 N 轮 / D 天；评测跑的频率（本地手动 / CI）。
- dossier 是否需要版本史（一期不做）。
- 检查面板做到什么程度（一期可最小或后置）。

---

## 设计取舍备忘（口径）

- **高度**：当前问题是主角，个人模型/记忆是背景参考，不是镜头。
- **效果优先**：token/算力 vs 质量的取舍，默认偏质量。
- **单一职责、小文件**：文件变大是职责过载信号。
- 推理外包给模型，工程只管"持久化 + 取回 + 多游标持续建模 + 往 context 怎么框"。
