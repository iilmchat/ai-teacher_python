import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/lib/api';
import { useTasksStore } from '@/store/tasks';
import type {
  AttemptDetail,
  AttemptList,
  ProgressSummary,
  SubmitResponse,
  TaskDetail,
  TaskListItem,
} from '@/types/api';

const TASK: TaskListItem = {
  id: '77777777-7777-7777-7777-777777777777',
  title: 'Сумма двух чисел',
  difficulty: 'easy',
  category: 'input_output',
  hints_count: 2,
  status: 'not_started',
};

const DETAIL: TaskDetail = {
  id: TASK.id,
  title: TASK.title,
  description: 'Считайте два числа и выведите сумму.',
  difficulty: 'easy',
  category: 'input_output',
  hints: ['int(input())', 'print(a + b)'],
  solution_template: 'a = int(input())\nb = int(input())\n',
  test_cases_count: 2,
  status: 'not_started',
  attempts: 0,
};

const PROGRESS: ProgressSummary = {
  total_tasks: 1,
  completed: 0,
  in_progress: 0,
  not_started: 1,
  completion_rate: 0,
  by_difficulty: { easy: { total: 1, completed: 0 } },
  items: [],
};

const SUBMIT: SubmitResponse = {
  passed: true,
  passed_count: 2,
  total_count: 2,
  attempts: 1,
  status: 'completed',
  results: [],
  message: 'Задача решена!',
};

const ATTEMPT_LIST: AttemptList = {
  items: [
    {
      id: 'att-1',
      task_id: TASK.id,
      passed: false,
      passed_count: 1,
      total_count: 2,
      created_at: '2026-11-05T10:00:00',
    },
  ],
  total: 1,
};

const ATTEMPT_DETAIL: AttemptDetail = {
  ...ATTEMPT_LIST.items[0],
  code: 'print(42)',
  results: [],
};

const CHECK: SubmitResponse = {
  passed: false,
  passed_count: 0,
  total_count: 2,
  attempts: 0,
  status: 'not_started',
  results: [],
  message: 'Пройдено 0 из 2 тестов. Пробная проверка — попытка не засчитывается.',
  practice: true,
};

function resetStore(): void {
  useTasksStore.setState({
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
  });
}

describe('tasks store', () => {
  beforeEach(() => {
    resetStore();
  });

  it('загружает задачи', async () => {
    vi.spyOn(api, 'get').mockResolvedValue([TASK]);

    await useTasksStore.getState().loadTasks();

    expect(useTasksStore.getState().tasks).toHaveLength(1);
  });

  it('передаёт фильтр сложности в запрос', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue([TASK]);
    useTasksStore.getState().setFilter({ difficulty: 'hard' });

    await useTasksStore.getState().loadTasks();

    expect(get).toHaveBeenCalledWith('/tasks?difficulty=hard');
  });

  it('загружает детали задачи и сбрасывает прошлый результат', async () => {
    useTasksStore.setState({ submission: SUBMIT });
    vi.spyOn(api, 'get').mockResolvedValue(DETAIL);

    await useTasksStore.getState().loadDetail(TASK.id);

    expect(useTasksStore.getState().detail?.title).toBe(TASK.title);
    expect(useTasksStore.getState().submission).toBeNull();
  });

  it('обрабатывает отсутствие задачи', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(new Error('404'));

    await useTasksStore.getState().loadDetail('missing');

    expect(useTasksStore.getState().detail).toBeNull();
    expect(useTasksStore.getState().error).toBeTruthy();
  });

  it('отправляет решение и обновляет статус в деталях', async () => {
    useTasksStore.setState({ detail: DETAIL });
    vi.spyOn(api, 'post').mockResolvedValue(SUBMIT);
    vi.spyOn(api, 'get').mockResolvedValue(PROGRESS);

    await useTasksStore.getState().submit(TASK.id, 'print(5)');

    const state = useTasksStore.getState();
    expect(state.submission?.passed).toBe(true);
    expect(state.detail?.status).toBe('completed');
    expect(state.detail?.attempts).toBe(1);
    expect(state.submitting).toBe(false);
  });

  it('фиксирует ошибку проверки', async () => {
    useTasksStore.setState({ detail: DETAIL });
    vi.spyOn(api, 'post').mockRejectedValue(new Error('500'));

    await useTasksStore.getState().submit(TASK.id, 'print(5)');

    expect(useTasksStore.getState().error).toBeTruthy();
    expect(useTasksStore.getState().submitting).toBe(false);
  });

  it('загружает прогресс', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(PROGRESS);

    await useTasksStore.getState().loadProgress();

    expect(useTasksStore.getState().progress?.total_tasks).toBe(1);
  });

  it('сбрасывает результат проверки', () => {
    useTasksStore.setState({ submission: SUBMIT });

    useTasksStore.getState().resetSubmission();

    expect(useTasksStore.getState().submission).toBeNull();
  });

  it('пробная проверка не меняет прогресс задачи', async () => {
    useTasksStore.setState({ detail: DETAIL });
    const post = vi.spyOn(api, 'post').mockResolvedValue(CHECK);

    await useTasksStore.getState().check(TASK.id, 'print(5)');

    const state = useTasksStore.getState();
    expect(post).toHaveBeenCalledWith(`/tasks/${TASK.id}/check`, { code: 'print(5)' });
    expect(state.checkResult?.practice).toBe(true);
    // Попытки и статус в карточке задачи не меняются
    expect(state.detail?.attempts).toBe(0);
    expect(state.detail?.status).toBe('not_started');
    expect(state.checking).toBe(false);
  });

  it('фиксирует ошибку пробной проверки', async () => {
    useTasksStore.setState({ detail: DETAIL });
    vi.spyOn(api, 'post').mockRejectedValue(new Error('500'));

    await useTasksStore.getState().check(TASK.id, 'print(5)');

    expect(useTasksStore.getState().error).toBeTruthy();
    expect(useTasksStore.getState().checkResult).toBeNull();
    expect(useTasksStore.getState().checking).toBe(false);
  });

  it('загружает историю попыток', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(ATTEMPT_LIST);

    await useTasksStore.getState().loadAttempts(TASK.id);

    const state = useTasksStore.getState();
    expect(state.attempts?.total).toBe(1);
    expect(state.attempts?.items[0].id).toBe('att-1');
  });

  it('загружает детальную попытку', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(ATTEMPT_DETAIL);

    await useTasksStore.getState().loadAttempt(TASK.id, 'att-1');

    expect(useTasksStore.getState().attemptDetail?.code).toBe('print(42)');
  });

  it('фиксирует ошибку загрузки истории попыток', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(new Error('500'));

    await useTasksStore.getState().loadAttempts(TASK.id);

    expect(useTasksStore.getState().error).toBeTruthy();
    expect(useTasksStore.getState().attempts).toBeNull();
  });

  it('очищает результат пробной проверки при загрузке задачи', async () => {
    useTasksStore.setState({ checkResult: CHECK });
    vi.spyOn(api, 'get').mockResolvedValue(DETAIL);

    await useTasksStore.getState().loadDetail(TASK.id);

    expect(useTasksStore.getState().checkResult).toBeNull();
  });
});
