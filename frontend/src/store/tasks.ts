/**
 * Стор задач: каталог, детали, отправка решения, прогресс.
 */

import i18n from '@/i18n';
import { create } from 'zustand';

import { api } from '@/lib/api';
import type {
  AttemptDetail,
  AttemptList,
  ProgressSummary,
  SubmitResponse,
  TaskDetail,
  TaskDifficulty,
  TaskListItem,
} from '@/types/api';

interface TaskFilters {
  difficulty: TaskDifficulty | null;
  category: string | null;
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
  filters: TaskFilters;
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
  loadAttempts: (taskId: string) => Promise<void>;
  /** Загрузить детальную попытку (S42-002) */
  loadAttempt: (taskId: string, attemptId: string) => Promise<void>;
  resetSubmission: () => void;
}

function buildQuery(filters: TaskFilters): string {
  const params = new URLSearchParams();
  if (filters.difficulty) {
    params.set('difficulty', filters.difficulty);
  }
  if (filters.category) {
    params.set('category', filters.category);
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

export const useTasksStore = create<TasksState>((set, get) => ({
  tasks: [],
  detail: null,
  progress: null,
  submission: null,
  checkResult: null,
  attempts: null,
  attemptDetail: null,
  filters: { difficulty: null, category: null },
  loading: false,
  submitting: false,
  checking: false,
  error: null,

  async loadTasks() {
    set({ loading: true, error: null });
    try {
      const tasks = await api.get<TaskListItem[]>(
        `/tasks${buildQuery(get().filters)}`,
      );
      set({ tasks, loading: false });
    } catch {
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
    });
    try {
      const detail = await api.get<TaskDetail>(`/tasks/${taskId}`);
      set({ detail, loading: false });
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
          },
        });
      }
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

  resetSubmission() {
    set({ submission: null, error: null });
  },
}));
