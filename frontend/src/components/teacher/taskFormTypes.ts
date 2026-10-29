/** Типы и значения формы задачи (S15-002) — отдельно от компонента. */

export interface TaskCaseValues {
  input: string;
  expected_output: string;
  description: string;
}

export interface TaskFormValues {
  id?: string;
  title: string;
  description: string;
  difficulty: 'easy' | 'medium' | 'hard';
  category: string;
  tags: string;
  hints: string;
  solution_template: string;
  test_cases: TaskCaseValues[];
}

export const EMPTY_TASK_FORM: TaskFormValues = {
  title: '',
  description: '',
  difficulty: 'easy',
  category: 'general',
  tags: '',
  hints: '',
  solution_template: '',
  test_cases: [{ input: '', expected_output: '', description: '' }],
};
