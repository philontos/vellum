# Vellum — 设计 spec

> 状态：设计稿 v2（单一永恒流重构），待 review。
> 日期：2026-06-06
> 前身：engram（原型，位于 `/Users/wangyuhao/Develop/personal/engram`，保留作参考矿）。

---

## 1. 背景与动机

engram 是一个原型：用大量工程脚手架（backbone 知识图谱、router 多 lens、投射差集、forebodes/method_cases/contacts 多独立根、"灵魂一击 / 升维"等刻意设计）去补**当年模型不够强**的地方 —— 手搓图谱、手搓投射逻辑，本质是不信任模型自己能做深、能联想、能给出"你没想过的角度"。

判断变了：**现在的强模型在 context 内就能完成这些推理。** 那套脚手架不再是杠杆，而是负担。

本次重做的第一性原则：

> **把工程收敛到模型替代不了的部分；推理整个外包给模型。**

模型唯一替代不了的，是它**跨会话无状态**。所以 Vellum 真正不可压缩的核心不是"推理"，而是两件朴素的事：

1. **存什么、怎么取回来** —— 长期记忆
2. **怎么把"你是谁"沉淀成会演化的东西、每轮喂回去** —— 个人模型

工程的艺术从"设计聪明的 pipeline"变成"设计往 context 里塞什么"。

---

## 2. 一期目标与范围

**一句话**：一个**懂你的对话产品** —— 一条永不结束的对话流 + 长期记忆 + 默默建模 + 可插拔模型。

**一期做：**

- **单一永恒对话流**（见 §3、§4）：没有"新建会话"，永远在同一条线上往下聊。web 聊天是核心消费面。
- 长期记忆：记得聊过的所有内容，按需召回。
- 默默建模：聊天过程中持续更新你的人格维度 / 性格 / 关键事实，作为**背景参考**。
- 可插拔模型接入层（chat / embedding）。

**一期不做（推后，非第一性反对，纯属节奏）：** MCP、其他采集 channel；检查面板（dossier / facts / 记忆检索 / 维度曲线）可最小化或后置，维度面板不急；push / 主动打扰；多用户 / 协作 / SaaS（永久反对：单用户、本地、数据隔离）。

**永久丢弃（相对 engram）：** 知识图谱 backbone、router 多 lens、投射差集、forebodes / method_cases / contacts 独立根、intent gate、"升维"叙事。

---

## 3. 第一性 / 高度（设计铁律）

> **当前问题是主角；个人模型和过往都是 reference，不是镜头。**
> 先把问题本身答好；只在问题确实关于"你"时，才借这些参考。不硬套、不无端剖析用户。

这是老 engram 最大毛病的反面：老系统把"你是谁"当强制镜头扣在每个回答上（"根据你的 prevention-focus……"），什么问题都被掰成自我分析。Vellum 要反过来 —— **一个好用的助手，只是恰好懂你**。

两个推论：

- **重点是"怎么框"，不只是"塞什么"。** dossier / traits / 召回片段进 prompt 时明确标成「背景参考」，并附指令：直接回答当前问题，仅当参考对这个问题真有帮助时才用。同样的内容，框成"主题"还是"背景"，回答天差地别。
- **用多少由问题决定，模型自己调档。** "怎么垂直居中一个 div" → dossier 毫不相关，干净利落答；"我该不该接这个 offer" → 才把画像和过往拉满。框成参考 + 要求"先答问题"，强模型自然调档，不需要分类器。

**关于"永不消逝的上下文"**：模型 context 窗口有限，所以它不可能是字面意义的"把所有历史塞进窗口"，而是我们**构造出来的错觉**：

```
永不消逝的上下文 = 最近的尾巴（逐字在窗口里）
               + dossier + facts + traits（永远在场 = 一切的提炼）
               + 按需召回的旧片段（一提就回来）
```

**consolidation 是让这个错觉成立的引擎**：你一直聊、尾巴一直长，老的部分滑出窗口之前，consolidation 把它消化进 dossier / summary / facts —— **窗口始终有界，记忆却从不丢失**。

---

## 4. 架构总览

```
┌──────────────┐   消费回路（快·同步）   ┌─────────────────────────────┐
│   你说一句    │ ─────────────────────▶ │ 组装 context → 强模型 → 流式答 │
└──────────────┘                         └─────────────┬───────────────┘
       （永远同一条流，无"新对话"）                       │ 停顿 / 尾巴超预算
                                   沉淀回路（慢·异步）  ▼
                          消化"上次水位线 → 现在"这批 turn
                          → summary / dossier 改写 / trait 贝叶斯 / facts
```

三个支柱：**接入层**（可插拔 chat + embedding）；**两个回路**（消费快·同步 / 沉淀慢·异步）；**两层存储**（记忆层 + 个人模型层）。

设计原则：单一职责、接口清晰、可独立理解与测试；文件变大是职责过载信号。

---

## 5. 接入层（可插拔模型）

直接搬 engram 成熟实现，几乎不改：

- **chat**：`shared/llm/client.py` → `api/app/llm/client.py`。OpenAI-compatible 统一协议，内置 12 家 preset，重试退避、JSON 健壮解析、temperature/response_format 跨厂兼容、流式、tool-calling、调用 trace。
- **embedding**：`api/app/lib/embed.py` → `api/app/llm/embed.py`。`EMBED_* → LLM_*` 自动 fallback。

**关键不对称（写进约束）：**

- **chat 模型 = 每轮可热插拔**，历史不受影响。
- **embedding 模型 = 装机时选定即钉死**：历史向量活在它的向量空间里，换 embedding ⇒ 旧向量全废，须重建索引迁移。

**模型选型推后**，接入层与具体模型解耦。embedding 默认值待定；选择标准是**在用户日常使用语言上检索强**（不专指中文，看用户用什么语言）—— 这条写进 README 安装指引。

---

## 6. 存储模型

### 6.0 先分清：两套完全不同的存储

```
①  文本存储（SQLite 表）   —— 存所有真实文字，逐字
②  向量索引（HNSW 文件）   —— 只存 embedding（一串浮点 = 语义指纹）+ 一个指回①的编号；【里面没有任何文本】
```

向量索引像书的"索引页"：只有"关键词→页码"，正文还在书里。**文本只有一个家（①）；②只是搜索层。**

### 6.1 三种文字，按"缩放级别"理解

```
原始文本（messages）  = 1倍：每一句话逐字（user + assistant）
summary（summaries）  = 拉远：流的一段的要点，一段话
dossier               = 拉到最远：你这个人是谁，总共一份
```

区别只在缩放：**说了什么 → 这段聊了什么 → 你是谁**。

### 6.2 记忆层（原始 + 检索机器；单一永恒流）

**没有 conversations 表。整个就一条流。**

```
messages
  id           PK
  turn         全局单调序号（唯一顺序，不分 conv）
  role         'user' | 'assistant'
  content      逐字原文
  created_at

summaries                -- 流的一段的要点（= 检索钥匙），属于记忆机器，不是"个人模型"
  id           PK
  start_turn   段起
  end_turn     段止
  content      模型写的一段话；被 embed
  created_at

vector_refs              -- 把 HNSW 整型 label 映射回来源（②里的编号）
  label        PK (= HNSW label)
  ref_type     'message' | 'summary'
  ref_id       -> messages.id（仅 user 轮）/ summaries.id

state                    -- 单行键值
  consolidated_through_turn   全局水位线（已消化到第几 turn）
```

**谁会被算 embedding（在②里有一条）：**

| 东西 | 文字存① | ②里有向量 |
|---|---|---|
| user 消息 | messages 逐字 | ✅ |
| assistant 消息 | messages 逐字 | ❌ |
| summary | summaries | ✅ |

assistant 不进向量 —— 不止省空间，更是质量（长回答横跨多话题，embedding 浑、当锚点搅乱召回）。它靠 turn 邻域**链接还原**被连带召回（见 §7），照样完整取回。

### 6.3 个人模型层（你是谁；对话边界蒸馏、可有损）

```
dossier                  -- 单行，叙述式"你是谁"，每轮常驻 context
  content
  updated_at

trait_current            -- 当下切片：live、原地覆盖、进 context
  dimension    PK         'ocean' / 'mbti' / 'schwartz' / 'regulatory_focus'
  content_json           各子维度当前贝叶斯状态 {score μ, tau τ, confidence, evidence}
  sample_count
  updated_at

trait_history            -- 历史轨迹：只增、冻结、画演化曲线
  id           PK
  dimension
  content_json           某次 consolidation 后该维度的冻结拷贝
  taken_at

facts                    -- pin board：无损原子，每轮常驻，用户可改
  id           PK
  text
  status       'active' | 'superseded'
  source_turn
  created_at · updated_at
```

三块各凭不同理由立身：

- **trait_current / trait_history**：凭"能打分、能画曲线"。`trait_current` 原地覆盖；每次 consolidation 更新完 live、**紧接着**冻一份进 `trait_history`（**创建即归档**，不等下次更新，故永不丢失）。
- **facts（pin board）**：凭"无损"。dossier 会被 compaction 软化/丢弃，而过敏源、家人名字、身份锚、关键偏好必须逐字穿过每次压缩、原样进 context。它不是 trait（无打分、无曲线），只有 active/superseded 生命周期。
- **dossier**：凭"具体性 + 让模型读你本人"。会长大 ⇒ 超 size 预算时 compaction。一期单行当前态，不做版本史。

> **summaries vs dossier**（都浓缩文本，职责正交）：summary 是**情节**（多条、带 turn 区间、可搜的检索入口）；dossier 是**画像**（一份、当前、每轮常驻、不进搜索）。summary 答"找到聊过 X 的那段"，dossier 答"这个人是谁"。

---

## 7. 消费回路（快 · 同步 · 面向用户）

每个 user 轮：

```
1. 存 user 消息（messages，全局 turn++）+ embed → 写入②（vector_refs: message）
2. 组装 context（按 §3「当前问题是主角」框）：
     [指令]   先直接回答当前问题；以下为背景参考，仅当与问题相关时取用，勿硬套、勿无端剖析
     人设     默认中性 / 可切换
     [参考]   dossier + 全部 active facts + trait_current 紧凑摘要   —— 永远在场、框成参考
     [参考]   召回的旧片段（见下，阈值门控）
     尾巴     最近 N turn 逐字（短期连续性，预算内）
3. 流式产出回答（chat_text_stream）
4. 存 assistant 消息（messages，不 embed）
```

**召回（长期记忆）—— 每轮都搜，但只注入越过相关性阈值的：**

> 真正的成本不是"搜"（embedding+HNSW 几十毫秒、极便宜），而是"注入噪声"。所以每轮搜（防"忘了去看"），新话题没片段越线 → 自然零注入零噪声。

1. 当前问题 embedding → 搜② → 命中锚点（user 旧话 / summary），**按相关性阈值过滤**。
2. 顺锚点编号 → 按 `turn` 邻域把那段流前后捞出 —— **assistant 原话在这步被连带捞回（靠链接，不靠向量）**。
3. 去重、按 token 预算裁剪 → 作为「背景参考」进 context。
4. 之后**交给强模型在 context 里自己判断取舍、织进回答**，不做单独 re-rank / 二次推理。

短期（尾巴）vs 长期（召回）分清：尾巴永远在场、不需召回；召回只为够到滑出窗口的旧事。

（可选增强：再给模型一个 `recall_memory(query)` 工具，主动深挖。一期先做阈值常驻召回，工具作后续。）

**人设**：默认**中性懂你**；可切换其他基调。默认文案待定。

---

## 8. 沉淀回路（慢 · 异步 · 持续消化尾巴）

**触发**（不再是"对话结束"，因为对话永不结束）：

1. **空闲停顿**（如静默 N 分钟）。
2. **活跃尾巴超出 context 预算** —— 老 turn 将滑出窗口前，先消化它，保证窗口有界、记忆不丢。

**机制**：单用户本地，**一个 asyncio 后台任务**，不上 Celery/Redis。读 `consolidated_through_turn` 水位线，只处理 `(水位线, now]` 这批 turn + 当前模型状态；以水位线推进，**崩了重跑幂等**。

**一趟 consolidation 的产物（同源并列输出）：**

1. **summary**：给这批 turn `[start, end]` 写一段要点 → `summaries` + embed。
2. **dossier 改写**：融入新内容；超 size 预算时一并 compaction（pinned facts 在独立表，不受影响）。
3. **trait 更新**：每个启用维度 extract（搬 engram `extract.spt`，把"single entry"改述为"this span")→ `profile_merge` 贝叶斯递推 → 写 `trait_current` + 冻结 `trait_history`。
4. **facts 增 / 改 / 退**（active ↔ superseded）。

**turn 的一生**：逐字在尾巴 → （空闲/超预算）被消化 → 此后只活在 messages（可召回）+ 被蒸馏进 summary/dossier/trait/facts。节律：**逐句即时写（保证"记得"）；持续消化尾巴（保证"懂你" + 窗口有界）。**

---

## 9. 从 engram 复用 / 丢弃清单

源仓库：`/Users/wangyuhao/Develop/personal/engram`

| 处理 | 模块 | 说明 |
|---|---|---|
| 几乎原样搬 | `shared/llm/client.py` | 可插拔 chat 接入层本体 |
| 几乎原样搬 | `api/app/lib/embed.py` | embedding 接入层 + fallback |
| 搬，轻改 | `api/app/lib/vector_store.py` | 60 行 HNSW 封装；改进：勿每次 `add` 都存盘，批量化 |
| 搬核心逻辑 | `api/app/lib/profile_merge.py` | 贝叶斯共轭递推 = trait 累积。依赖 `graph_rules.PROFILE_MERGE`（gamma/tau_prior/tau_ref/min_conf）+ 一个 dimension loader，一并搬。改为**按消化批**调用 |
| 搬资产 | `config/dimensions/{ocean,mbti,schwartz,regulatory_focus}` | config + extract.spt + rubric；提取 prompt 写得好（null 纪律 / 不许往中位数缩 / 要 evidence） |
| 升级搬 | `dimensions/facts` | 旧系统挂 dimension 走"覆盖"；新系统提升为独立 `facts` pin board（active/superseded、用户可改） |
| 丢弃 | `backbone_pipeline`(1420) `agent_tools`(1284) `agent_runtime`(627) `router` `slice_pipeline` `retrieval` `entry_signals` `capture_intent` | 图谱 / router / agent / 投射机器 |

---

## 10. 技术栈与目录

**栈（沿用 engram）**：Python 3.12 + FastAPI + SQLite + hnswlib（后端）；React + Vite + Tailwind（前端）。

```
vellum/
  api/
    app/
      main.py
      llm/         client.py · embed.py              # 接入层（搬）
      store/       db.py · vectors.py · memory.py · model.py   # 记忆层 + 个人模型层 DAO
      chat/        assemble.py · respond.py           # 消费回路
      consolidate/ runner.py · summary.py · dossier.py · traits.py · facts.py  # 沉淀回路
      config/
        dimensions/   ocean · mbti · schwartz · regulatory_focus   # 搬
        persona/      neutral（默认）· 其他基调
      routes/      chat.py · inspect.py · admin.py
    migrations/                                       # forward-only、幂等
    requirements.txt · .env.example
  web/                                                # 单一永恒对话流 UI；检查面板后置
  docs/specs/
  AGENTS.md · README.md
```

**配置（沿用 engram env 约定）**：`LLM_BASE_URL/API_KEY/MODEL`（或 `LLM_PROVIDER` preset）；`EMBED_*` 缺省 fallback 到 `LLM_*`。

**数据**：全新库，**不迁移 engram 原型数据**。迁移 forward-only + 幂等。

**约定（沿用 engram AGENTS.md 精神）**：canonical enum 用英文（`role`、`status`、`dimension` key…）；prompt 默认英文、指示"match user's language"，不在 prompt 里钉输出语种；中文是前端 i18n 展示层的事。

---

## 11. 一期验收标准

- 能聊：web 单一对话流，流式回答。
- **高度对**：问"怎么居中 div"时不掉书袋剖析你；问人生决策时才拉满画像。
- 切 chat 模型不影响历史记忆与建模。
- 停顿/超预算后，后台 consolidation 真的更新了 summary / dossier / trait_current / facts，并推进水位线。
- 早期聊过、已滑出窗口的内容（含当时 assistant 建议），之后能被召回，证明"永不消逝的上下文"成立。
- `trait_history` 随消化累积出多个时间点（曲线有料）。
- pinned facts 多轮后仍逐字常驻，未被 dossier compaction 抹掉。

---

## 12. 待定（open）

- embedding 默认模型（押后；按用户主语言选）。
- 人设默认基调的具体文案。
- 触发参数：空闲超时 N、尾巴 token 预算、召回相关性阈值。
- dossier 是否需要版本史（一期不做）。
- 检查面板做到什么程度（一期可最小或后置）。

---

## 设计取舍备忘（口径）

- **高度**：当前问题是主角，个人模型/记忆是背景参考，不是镜头。
- **效果优先**：token/算力 vs 质量的取舍，默认偏质量。
- **单一职责、小文件**：文件变大是职责过载信号。
- 推理外包给模型，工程只管"持久化 + 取回 + 持续消化 + 往 context 怎么框"。
