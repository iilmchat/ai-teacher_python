/**
 * Стор задач: каталог, детали, отправка решения, прогресс.
 */

import { create } from 'zustand';

import { api } from '@/lib/api';
import type {
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
  filters: TaskFilters;
  loading: boolean;
  submitting: boolean;
  error: string | null;

  loadTasks: () => Promise<void>;
  loadDetail: (taskId: string) => Promise<void>;
  loadProgress: () => Promise<void>;
  setFilter: (filters: Partial<TaskFilters>) => void;
  submit: (taskId: string, code: string) => Promise<void>;
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
  filters: { difficulty: null, category: null },
  loading: false,
  submitting: false,
  error: null,

  async loadTasks() {
    set({ loading: true, error: null });
    try {
      const tasks = await api.get<TaskListItem[]>(
        `/tasks${buildQuery(get().filters)}`,
      );
      set({ tasks, loading: false });
    } catch {
      set({ loading: false, error: 'Не удалось загрузить задачи' });
    }
  },

  async loadDetail(taskId) {
    set({ loading: true, error: null, detail: null, submission: null });
    try {
      const detail = await api.get<TaskDetail>(`/tasks/${taskId}`);
      set({ detail, loading: false });
    } catch {
      set({ loading: false, error: 'Задача не найдена' });
    }
  },

  async loadProgress() {
    try {
      const progress = await api.get<ProgressSummary>('/tasks/progress');
      set({ progress });
    } catch {
      set({ error: 'Не удалось загрузить прогресс' });
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
      set({ submitting: false, error: 'Не удалось проверить решение' });
    }
  },

  resetSubmission() {
    set({ submission: null, error: null });
  },
}));
