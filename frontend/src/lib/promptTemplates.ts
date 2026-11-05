/**
 * Стартовые шаблоны промптов для чата (S43-004).
 *
 * Шаблон — это заготовка вопроса: чип подставляет текст в поле ввода,
 * ученик дописывает своё и отправляет. Автоотправки нет: решение всегда
 * за учеником.
 *
 * Названия и тексты хранятся ключами i18n, поэтому шаблон одинаково
 * работает в русской и английской версиях интерфейса.
 */

import type { UserLevel } from '@/types/api';

export interface PromptTemplate {
  /** Идентификатор шаблона (сохраняется в `users.settings`) */
  id: string;
  /** Ключ i18n с названием чипа */
  titleKey: string;
  /** Ключ i18n с текстом, который подставляется в поле ввода */
  textKey: string;
  /** Уровни помощи, для которых шаблон уместен */
  levels: UserLevel[];
}

export const PROMPT_TEMPLATES: PromptTemplate[] = [
  {
    id: 'explain_code',
    titleKey: 'chat.templates.explainCode',
    textKey: 'chat.templates.explainCodeText',
    levels: ['basic', 'intermediate', 'advanced'],
  },
  {
    id: 'why_not_work',
    titleKey: 'chat.templates.whyNotWork',
    textKey: 'chat.templates.whyNotWorkText',
    levels: ['basic', 'intermediate'],
  },
  {
    id: 'check_my_solution',
    titleKey: 'chat.templates.checkSolution',
    textKey: 'chat.templates.checkSolutionText',
    levels: ['intermediate', 'advanced'],
  },
  {
    id: 'full_solution',
    titleKey: 'chat.templates.fullSolution',
    textKey: 'chat.templates.fullSolutionText',
    levels: ['advanced'],
  },
  {
    id: 'compare_ways',
    titleKey: 'chat.templates.compareWays',
    textKey: 'chat.templates.compareWaysText',
    levels: ['intermediate', 'advanced'],
  },
  {
    id: 'start_from_scratch',
    titleKey: 'chat.templates.startFromScratch',
    textKey: 'chat.templates.startFromScratchText',
    levels: ['basic'],
  },
];

/** Шаблоны, подходящие уровню помощи */
export function templatesForLevel(level: UserLevel): PromptTemplate[] {
  return PROMPT_TEMPLATES.filter((template) => template.levels.includes(level));
}

/** Найти шаблон по идентификатору */
export function findTemplate(templateId: string | null | undefined): PromptTemplate | undefined {
  if (!templateId) {
    return undefined;
  }
  return PROMPT_TEMPLATES.find((template) => template.id === templateId);
}
