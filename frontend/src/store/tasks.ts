/**
 * Стор задач: каталог, детали, отправка решения, черновик, прогресс.
 */

import i18n from '@/i18n';
import { create } from 'zustand';

import { api } from '@/lib/api';
import type {
  AttemptDetail,
  AttemptList,
  DraftStatus,
  RecommendedTaskList,
  ProgressSummary,
  SubmitResponse,
  TaskDetail,
  TaskDifficulty,
  TaskListItem,
  TaskStatus,
} from '@/types/api';

export interface TaskFilters {
  difficulty: TaskDifficulty | null;
  category: string | null;
  tag: string | null;
  status: TaskStatus | null;
  /** Поиск по названию и описанию */
  search: string;
}

interface TasksState {
  tasks: TaskListItem[];
  detail: TaskDetail | null;
  progress: ProgressSummary | null;
  submission: SubmitResponse | null;
  /** Результат пробной проверки (S42-001): попытка не засчитывается */
  checkResult: SubmitResponse | null;
  /** История попыток по задаче (S42-002) */
  attempts: AttemptList | null;
  /** Детальная попытка (S42-002) */
  attemptDetail: AttemptDetail | null;
  /** Рекомендации следующих задач (S42-005) */
  recommended: RecommendedTaskList | null;
  /** Когда черновик сохранён в последний раз (S42-003) */
  draftSavedAt: string | null;
  /** Идёт ли сохранение черновика (S42-003) */
  draftSaving: boolean;
  filters: TaskFilters;
  /** Всего найдено задач (с учётом фильтров) */
  found: number;
  loading: boolean;
  submitting: boolean;
  checking: boolean;
  error: string | null;

  loadTasks: () => Promise<void>;
  loadDetail: (taskId: string) => Promise<void>;
  loadProgress: () => Promise<void>;
  setFilter: (filters: Partial<TaskFilters>) => void;
  submit: (taskId: string, code: string) => Promise<void>;
  /** Пробная проверка: результат показывается, но попытка не засчитывается */
  check: (taskId: string, code: string) => Promise<void>;
  /** Загрузить историю попыток по задаче (S42-002) */
  /** Загрузить рекомендации следующих задач (S42-005) */
  loadRecommended: () => Promise<void>;
  loadAttempts: (taskId: string) => Promise<void>;
  /** Загрузить детальную попытку (S42-002) */
  loadAttempt: (taskId: string, attemptId: string) => Promise<void>;
  /** Сбросить все фильтры каталога (S42-004) */
  resetFilters: () => void;
  /** Сохранить черновик решения (S42-003) */
  saveDraft: (taskId: string, code: string) => Promise<void>;
  /** Очистить черновик решения (S42-003) */
  clearDraft: (taskId: string) => Promise<void>;
  resetSubmission: () => void;
}

export function buildQuery(filters: TaskFilters): string {
  const params = new URLSearchParams();
  if (filters.difficulty) {
    params.set('difficulty', filters.difficulty);
  }
  if (filters.category) {
    params.set('category', filters.category);
  }
  if (filters.tag) {
    params.set('tag', filters.tag);
  }
  if (filters.status) {
    params.set('status', filters.status);
  }
  const search = filters.search.trim();
  if (search) {
    params.set('q', search);
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

/** Текущий запрос каталога: его отменяет следующий (S42-004). */
let tasksRequest: AbortController | null = null;

export const useTasksStore = create<TasksState>((set, get) => ({
  tasks: [],
  detail: null,
  progress: null,
  submission: null,
  checkResult: null,
  attempts: null,
  attemptDetail: null,
  recommended: null,
  draftSavedAt: null,
  draftSaving: false,
  filters: { difficulty: null, category: null, tag: null, status: null, search: '' },
  found: 0,
  loading: false,
  submitting: false,
  checking: false,
  error: null,

  async loadTasks() {
    // Новый запрос отменяет предыдущий: устаревший ответ не должен
    // подменять результат свежего (S42-004).
    tasksRequest?.abort();
    const controller = new AbortController();
    tasksRequest = controller;

    set({ loading: true, error: null });
    try {
      const tasks = await api.get<TaskListItem[]>(
        `/tasks${buildQuery(get().filters)}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) {
        return;
      }
      set({ tasks, found: tasks.length, loading: false });
    } catch {
      if (controller.signal.aborted) {
        return;
      }
      set({ loading: false, error: i18n.t('errors.tasksLoad') });
    }
  },

  async loadDetail(taskId) {
    set({
      loading: true,
      error: null,
      detail: null,
      submission: null,
      checkResult: null,
      attempts: null,
      attemptDetail: null,
      recommended: null,
      draftSavedAt: null,
    });
    try {
      const detail = await api.get<TaskDetail>(`/tasks/${taskId}`);
      set({
        detail,
        loading: false,
        draftSavedAt: detail.draft_updated_at ?? null,
      });
    } catch {
      set({ loading: false, error: i18n.t('errors.taskNotFound') });
    }
  },

  async loadProgress() {
    try {
      const progress = await api.get<ProgressSummary>('/tasks/progress');
      set({ progress });
    } catch {
      set({ error: i18n.t('errors.progressLoad') });
    }
  },

  setFilter(filters) {
    set((state) => ({ filters: { ...state.filters, ...filters } }));
  },

  resetFilters() {
    set({
      filters: {
        difficulty: null,
        category: null,
        tag: null,
        status: null,
        search: '',
      },
    });
  },

  async submit(taskId, code) {
    set({ submitting: true, error: null, submission: null });
    try {
      const submission = await api.post<SubmitResponse>(`/tasks/${taskId}/submit`, {
        code,
      });
      set({ submitting: false, submission });
      const detail = get().detail;
      if (detail) {
        set({
          detail: {
            ...detail,
            status: submission.status,
            attempts: submission.attempts,
            // Решение засчитано — сервер очистил черновик.
            draft_code: null,
            draft_updated_at: null,
          },
        });
      }
      set({ draftSavedAt: null });
      void get().loadProgress();
    } catch {
      set({ submitting: false, error: i18n.t('errors.submit') });
    }
  },

  async check(taskId, code) {
    set({ checking: true, error: null, checkResult: null });
    try {
      const checkResult = await api.post<SubmitResponse>(`/tasks/${taskId}/check`, {
        code,
      });
      // Пробная проверка не меняет прогресс: ни attempts, ни status.
      set({ checking: false, checkResult });
    } catch {
      set({ checking: false, error: i18n.t('errors.check') });
    }
  },

  async loadRecommended() {
    try {
      const recommended = await api.get<RecommendedTaskList>('/tasks/recommended');
      set({ recommended });
    } catch {
      // Рекомендации вспомогательны: их отсутствие не должно
      // показывать ошибку на странице.
      set({ recommended: null });
    }
  },


  async loadAttempts(taskId) {
    set({ attempts: null, attemptDetail: null, error: null });
    try {
      const attempts = await api.get<AttemptList>(`/tasks/${taskId}/attempts`);
      set({ attempts });
    } catch {
      set({ error: i18n.t('errors.attemptsLoad') });
    }
  },

  async loadAttempt(taskId, attemptId) {
    set({ attemptDetail: null, error: null });
    try {
      const attemptDetail = await api.get<AttemptDetail>(
        `/tasks/${taskId}/attempts/${attemptId}`,
      );
      set({ attemptDetail });
    } catch {
      set({ error: i18n.t('errors.attemptLoad') });
    }
  },

  async saveDraft(taskId, code) {
    set({ draftSaving: true });
    try {
      const status = await api.patch<DraftStatus>(`/tasks/${taskId}/draft`, {
        code,
      });
      set({ draftSaving: false, draftSavedAt: status.updated_at });
    } catch {
      // Черновик вспомогателен: ошибка сохранения не должна прерывать
      // работу над решением.
      set({ draftSaving: false });
    }
  },

  async clearDraft(taskId) {
    try {
      await api.delete<DraftStatus>(`/tasks/${taskId}/draft`);
    } catch {
      // Ошибка очистки не критична: сервер тоже очищает черновик при отправке.
    }
    set({ draftSavedAt: null });
  },

  resetSubmission() {
    set({ submission: null, error: null });
  },
}));
