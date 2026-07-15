import type { ManagedPrompt } from "../../api/prompts";

export const PROMPT_CATEGORY_META = {
  chat: {
    order: 0,
    labelKey: "prompts.category.chat",
    descriptionKey: "prompts.category.chatDescription",
  },
  memory: {
    order: 1,
    labelKey: "prompts.category.memory",
    descriptionKey: "prompts.category.memoryDescription",
  },
  traits: {
    order: 2,
    labelKey: "prompts.category.traits",
    descriptionKey: "prompts.category.traitsDescription",
  },
  tools: {
    order: 3,
    labelKey: "prompts.category.tools",
    descriptionKey: "prompts.category.toolsDescription",
  },
  protocol: {
    order: 4,
    labelKey: "prompts.category.protocol",
    descriptionKey: "prompts.category.protocolDescription",
  },
} as const;

type KnownPromptCategory = keyof typeof PROMPT_CATEGORY_META;

export type PromptCategoryGroup = {
  category: string;
  prompts: ManagedPrompt[];
};

export function promptCategoryMeta(category: string) {
  if (!Object.prototype.hasOwnProperty.call(PROMPT_CATEGORY_META, category)) {
    return null;
  }
  return PROMPT_CATEGORY_META[category as KnownPromptCategory];
}

export function groupPromptsByCategory(prompts: ManagedPrompt[]): PromptCategoryGroup[] {
  const grouped = new Map<string, { prompts: ManagedPrompt[]; firstSeen: number }>();
  prompts.forEach((prompt, index) => {
    const existing = grouped.get(prompt.category);
    if (existing) {
      existing.prompts.push(prompt);
    } else {
      grouped.set(prompt.category, { prompts: [prompt], firstSeen: index });
    }
  });

  return Array.from(grouped, ([category, group]) => ({
    category,
    prompts: group.prompts,
    firstSeen: group.firstSeen,
  }))
    .sort((left, right) => {
      const leftOrder = promptCategoryMeta(left.category)?.order ?? Number.MAX_SAFE_INTEGER;
      const rightOrder = promptCategoryMeta(right.category)?.order ?? Number.MAX_SAFE_INTEGER;
      return leftOrder - rightOrder || left.firstSeen - right.firstSeen;
    })
    .map(({ category, prompts: groupedPrompts }) => ({
      category,
      prompts: groupedPrompts,
    }));
}
