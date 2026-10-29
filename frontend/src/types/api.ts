/**
 * Типы API, повторяющие контракты backend.
 */

export type UserRole = 'student' | 'teacher' | 'admin';
export type UserLevel = 'basic' | 'intermediate' | 'advanced';

export interface User {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  level: UserLevel;
  created_at: string;
  last_active: string;
  settings: Record<string, unknown>;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: Pick<User, 'id' | 'email' | 'username' | 'role' | 'level'>;
}

export interface LevelInfo {
  level: UserLevel;
  title: string;
  description: string;
  audience: string;
  gives_ready_code: boolean;
}

export interface LevelsResponse {
  levels: LevelInfo[];
}

export interface ChatSession {
  id: string;
  user_id: string;
  level: string;
  created_at: string;
  updated_at: string;
}

export type MessageRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  code_blocks: unknown[];
  created_at: string;
}

export interface ChatSessionWithMessages extends ChatSession {
  messages: ChatMessage[];
}

export interface ChatTurn {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}

export type TaskDifficulty = 'easy' | 'medium' | 'hard';
export type TaskStatus = 'not_started' | 'in_progress' | 'completed';

export interface TaskListItem {
  id: string;
  title: string;
  difficulty: TaskDifficulty;
  category: string;
  hints_count: number;
  status: TaskStatus;
}

export interface TaskDetail {
  id: string;
  title: string;
  description: string;
  difficulty: TaskDifficulty;
  category: string;
  hints: string[];
  solution_template: string | null;
  test_cases_count: number;
  status: TaskStatus;
  attempts: number;
}

export interface TestCaseResult {
  index: number;
  passed: boolean;
  description: string | null;
  input: string;
  expected_output: string;
  actual_output: string;
  error: string | null;
}

export interface SubmitResponse {
  passed: boolean;
  passed_count: number;
  total_count: number;
  attempts: number;
  status: TaskStatus;
  results: TestCaseResult[];
  message: string;
}

export interface ProgressItem {
  task_id: string;
  title: string;
  difficulty: TaskDifficulty;
  status: TaskStatus;
  attempts: number;
  completed_at: string | null;
}

export interface ProgressSummary {
  total_tasks: number;
  completed: number;
  in_progress: number;
  not_started: number;
  completion_rate: number;
  by_difficulty: Record<string, { total: number; completed: number }>;
  items: ProgressItem[];
}

export interface ExecutionResult {
  success: boolean;
  output: string;
  error: string | null;
  error_type: string | null;
  execution_time: number;
  violations: string[];
}

export interface LintIssue {
  line: number;
  column: number;
  code: string;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

export interface LintResponse {
  issues: LintIssue[];
  errors: number;
  warnings: number;
  infos: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  app_name: string;
  llm_provider: string;
}

export interface AdminUserItem {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  level: UserLevel;
  created_at: string;
  last_active: string;
}

export interface AdminUserListResponse {
  total: number;
  items: AdminUserItem[];
}

export interface AdminTaskItem {
  id: string;
  title: string;
  difficulty: TaskDifficulty;
  category: string;
  is_active: boolean;
  test_cases_count: number;
  hints_count: number;
  created_at: string;
  created_by: string | null;
}

export interface AdminTaskListResponse {
  total: number;
  items: AdminTaskItem[];
}

export interface AnalyticsResponse {
  users: {
    total: number;
    by_role: Record<string, number>;
    active_24h: number;
    active_7d: number;
  };
  tasks: {
    total: number;
    active: number;
    easy: number;
    medium: number;
    hard: number;
  };
  learning: {
    attempts: number;
    completed: number;
    started: number;
    average_attempts: number;
  };
  activity: {
    sessions: number;
    messages: number;
    executions: number;
    failed_executions: number;
  };
  generated_at: string;
}
