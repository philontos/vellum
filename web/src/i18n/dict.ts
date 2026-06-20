// The single source of truth for every user-facing UI string. `en` is canonical
// — its key set defines the valid keys (see the `Key` type below), and the
// lockstep test (i18n.test.ts) + dev-time guard keep `zh` mirroring it exactly.
// Use {name} placeholders for interpolated values, e.g. "{n} entries".
//
// Keys are grouped by area with dotted names (nav.*, model.*, traces.*, …) so
// related strings stay together and new features get an obvious home.
export const DICT = {
  en: {
    // nav header
    "nav.chat": "Chat",
    "nav.you": "You",
    "nav.traces": "Traces",

    // composer
    "composer.placeholder": "Say something to it…",
    "composer.send": "Send",
    "composer.hint": "{key} to send · Enter for a new line",

    // chat
    "chat.error": "⚠️ Something went wrong, please retry",
    "chat.you": "You",
    "chat.vellum": "Vellum",
    "chat.processLive": "Thinking & searching…",
    "chat.process": "Reasoning & search",
    "chat.searchN": "{n} searches",

    // context rail (what Vellum is learning, alongside the conversation)
    "rail.title": "Vellum",
    "rail.sub": "What it's piecing together about you",
    "rail.factsTitle": "Recent reads",
    "rail.empty": "Nothing yet — it forms reads as you talk.",
    "rail.session": "This thread · {n} turns",

    // model panel (你是谁)
    "model.loading": "Loading…",
    "model.dossierTitle": "Dossier — who you are",
    "model.dossierEmpty": "(not generated yet)",
    "model.factsTitle": "Facts",
    "model.factsEmpty": "(no facts extracted yet)",
    "model.traitsTitle": "Trait dimensions",
    "model.traitsEmpty": "(no model yet — chat a bit more)",

    // traces panel
    "traces.allStages": "all stages",
    "traces.refresh": "Refresh",
    "traces.count": "{n} entries",
    "traces.pin": "pin (protect from prune)",
    "traces.hasReasoning": "includes reasoning",
    "traces.expand": "Expand",
    "traces.collapse": "Collapse",
    "traces.notePh": "note (good / broken / wrong extraction…)",
    "traces.empty": "No traces yet (chat a bit, wait for background modeling).",
    "traces.pruned": "(pruned by rotation; pin to protect future ones)",

    // evals panel
    "nav.evals": "Evals",
    "eval.run": "Run",
    "eval.runningBtn": "Running…",
    "eval.running": "running {done}/{total}",
    "eval.needsJudge": "needs judge",
    "eval.ruleBased": "rule-based",
    "eval.count": "{n} runs",
    "eval.expand": "Detail",
    "eval.collapse": "Collapse",
    "eval.empty": "No eval runs yet — pick a suite and Run.",
    "eval.noCases": "(no cases)",
    "eval.casesTitle": "Cases",
    "eval.tracesTitle": "Traces",
    "eval.tracePruned": "(no output)",

    // privacy screen (shoulder-surfing mask, NOT encryption)
    "privacy.hidden": "Hidden",
    "privacy.shown": "Shown",
    "privacy.clickToReveal": "Click to reveal (enter PIN)",
    "privacy.clickToHide": "Click to hide",
    "privacy.setTitle": "Set a PIN to reveal",
    "privacy.enterTitle": "Enter PIN to reveal",
    "privacy.placeholder": "PIN",
    "privacy.confirm": "OK",
    "privacy.wrong": "Wrong PIN",
    "privacy.forgot": "Forgot? Reset PIN",
    "privacy.resetConfirm": "Reset the PIN? Content stays hidden until you set a new one. Your data is not affected.",
  },
  zh: {
    "nav.chat": "聊天",
    "nav.you": "你是谁",
    "nav.traces": "Traces",

    "composer.placeholder": "跟它聊点什么…",
    "composer.send": "发送",
    "composer.hint": "{key} 发送 · Enter 换行",

    "chat.error": "⚠️ 出错了，请重试",
    "chat.you": "你",
    "chat.vellum": "Vellum",
    "chat.processLive": "思考与检索中…",
    "chat.process": "思考与检索",
    "chat.searchN": "{n} 次搜索",

    "rail.title": "Vellum",
    "rail.sub": "它正在拼凑对你的理解",
    "rail.factsTitle": "近期读到的你",
    "rail.empty": "还没有——它会随着聊天慢慢读出你。",
    "rail.session": "本次对话 · {n} 轮",

    "model.loading": "加载中…",
    "model.dossierTitle": "Dossier — 你是谁",
    "model.dossierEmpty": "（还没生成）",
    "model.factsTitle": "Facts",
    "model.factsEmpty": "（还没抽到事实）",
    "model.traitsTitle": "人格维度",
    "model.traitsEmpty": "（还没建模，多聊几轮）",

    "traces.allStages": "全部阶段",
    "traces.refresh": "刷新",
    "traces.count": "{n} 条",
    "traces.pin": "置顶（防止被清除）",
    "traces.hasReasoning": "包含推理过程",
    "traces.expand": "展开",
    "traces.collapse": "收起",
    "traces.notePh": "备注（好/塌了/抽错了…）",
    "traces.empty": "还没有 trace（聊几句、等后台建模触发）。",
    "traces.pruned": "（已滚动清除；pin 可保护未来的）",

    // evals panel
    "nav.evals": "评测",
    "eval.run": "运行",
    "eval.runningBtn": "运行中…",
    "eval.running": "运行中 {done}/{total}",
    "eval.needsJudge": "需裁判",
    "eval.ruleBased": "规则判定",
    "eval.count": "{n} 次运行",
    "eval.expand": "详情",
    "eval.collapse": "收起",
    "eval.empty": "还没有评测 run —— 选个套件点运行。",
    "eval.noCases": "（没有 case）",
    "eval.casesTitle": "Case 明细",
    "eval.tracesTitle": "Trace",
    "eval.tracePruned": "（无输出）",

    // privacy screen (shoulder-surfing mask, NOT encryption)
    "privacy.hidden": "已隐藏",
    "privacy.shown": "显示中",
    "privacy.clickToReveal": "点击显示（输入 PIN）",
    "privacy.clickToHide": "点击隐藏",
    "privacy.setTitle": "设置一个 PIN 以显示",
    "privacy.enterTitle": "输入 PIN 以显示",
    "privacy.placeholder": "PIN",
    "privacy.confirm": "确定",
    "privacy.wrong": "PIN 错误",
    "privacy.forgot": "忘记了？重置 PIN",
    "privacy.resetConfirm": "重置 PIN？在你设置新 PIN 前内容保持隐藏。你的数据不受影响。",
  },
} as const;

export type Lang = keyof typeof DICT;          // "en" | "zh"
export type Key = keyof (typeof DICT)["en"];   // union of every valid key
export const LANGS = Object.keys(DICT) as Lang[];
export const DEFAULT_LANG: Lang = "en";
