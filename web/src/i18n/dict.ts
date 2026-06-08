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

    // chat
    "chat.error": "⚠️ Something went wrong, please retry",

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
  },
  zh: {
    "nav.chat": "聊天",
    "nav.you": "你是谁",
    "nav.traces": "Traces",

    "composer.placeholder": "跟它聊点什么…",
    "composer.send": "发送",

    "chat.error": "⚠️ 出错了，请重试",

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
  },
} as const;

export type Lang = keyof typeof DICT;          // "en" | "zh"
export type Key = keyof (typeof DICT)["en"];   // union of every valid key
export const LANGS = Object.keys(DICT) as Lang[];
export const DEFAULT_LANG: Lang = "en";
