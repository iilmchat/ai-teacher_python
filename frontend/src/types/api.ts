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
  /** Заголовок сессии (S43-001); null — ещё нет первого вопроса */
  title: string | null;
  /** Закреплённая сессия в списке выше остальных (S43-001) */
  pinned: boolean;
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
  /** Провайдер, модель и версия промпта ответа (S12-006) */
  metadata?: Record<string, unknown>;
  /** Коды нарушений политики уровня (S12-005) */
  warnings?: string[];
}

export interface ChatSessionWithMessages extends ChatSession {
  messages: ChatMessage[];
}

/** Оценка ответа ассистента учеником (S43-003) */
export interface MessageFeedback {
  message_id: string;
  /** 1 — ответ помог, −1 — не помог */
  value: 1 | -1;
  comment: string | null;
  created_at: string;
}

/** Агрегат оценок по провайдеру или модели (S43-003) */
export interface QualityBreakdown {
  name: string;
  total: number;
  positive: number;
  negative: number;
  approval_rate: number;
}

/** Негативная оценка с текстом ответа — вход для LLM-as-judge (S43-003) */
export interface QualityNegativeItem {
  message_id: string;
  comment: string | null;
  content: string;
  provider: string;
  model: string;
  created_at: string;
}

/** Сводка качества ответов для администратора (S43-003) */
export interface AdminQualityResponse {
  total: number;
  positive: number;
  negative: number;
  approval_rate: number;
  by_provider: QualityBreakdown[];
  by_model: QualityBreakdown[];
  negative_samples: QualityNegativeItem[];
  generated_at: string;
}

export interface ChatTurn {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
}

export interface ChatSearchItem {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  score?: number;
}

export interface ChatSearchResponse {
  query: string;
  mode: 'semantic' | 'ilike';
  items: ChatSearchItem[];
  total: number;
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
  tags?: string[];
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
  tags?: string[];
  /** Сохранённый черновик решения (S42-003) */
  draft_code?: string | null;
  /** Когда черновик сохранён (S42-003) */
  draft_updated_at?: string | null;
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
  /** `true` для пробной проверки: попытка не засчитывается (S42-001) */
  practice?: boolean;
}

export interface DraftStatus {
  has_draft: boolean;
  updated_at: string | null;
}

export interface RecommendedTask {
  id: string;
  title: string;
  difficulty: TaskDifficulty;
  category: string;
  tags: string[];
  /** Машиночитаемая причина: continue | same_topic | easier | next_step | starter */
  reason: string;
  /** Пояснение для ученика */
  reason_text: string;
}

export interface RecommendedTaskList {
  items: RecommendedTask[];
}

export interface AttemptItem {
  id: string;
  task_id: string;
  passed: boolean;
  passed_count: number;
  total_count: number;
  created_at: string;
}

export interface AttemptDetail extends AttemptItem {
  code: string;
  results: TestCaseResult[];
}

export interface AttemptList {
  items: AttemptItem[];
  total: number;
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

/** Ограничения песочницы для блока «Ограничения» (S44-001) */
export interface SandboxLimits {
  timeout_seconds: number;
  memory_limit_mb: number;
  max_output_chars: number;
  max_concurrency: number;
  queue_timeout_seconds: number;
  max_code_length: number;
  allowed_modules: string[];
}

/** Разбор кода: замечания, метрики и сводка (S44-001) */
export interface AnalyzeResponse {
  issues: LintIssue[];
  stats: Record<string, number>;
  summary: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  app_name: string;
  llm_provider: string;
  llm: {
    provider: string;
    model: string | null;
    configured: boolean;
    reachable: boolean;
    status: 'ok' | 'degraded' | 'not_configured';
    fallback: string | null;
  };
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

export interface AnalyticsLLMWindow {
  window_hours: number;
  requests: number;
  errors: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  avg_first_token_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  by_provider: Record<string, Record<string, number>>;
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
  /** Метрики LLM из памяти процесса (S12-003) */
  llm: {
    last_hour: AnalyticsLLMWindow;
    last_24h: AnalyticsLLMWindow;
    fallback_used: number;
    recorded_at: string;
  };
  generated_at: string;
}

// --- Teacher Console (S15) ---------------------------------------------

export interface TeacherStudent {
  id: string;
  email: string;
  username: string;
  level: UserLevel;
  completed_tasks: number;
  attempts: number;
  last_active: string;
}

export interface TeacherStudentList {
  total: number;
  items: TeacherStudent[];
}

export interface TeacherProgressItem {
  task_id: string;
  title: string;
  difficulty: TaskDifficulty;
  status: TaskStatus;
  attempts: number;
  completed_at: string | null;
}

export interface TeacherStudentDetail {
  student: TeacherStudent;
  total_tasks: number;
  completed: number;
  in_progress: number;
  completion_rate: number;
  items: TeacherProgressItem[];
}

export interface TeacherTaskItem {
  id: string;
  title: string;
  difficulty: TaskDifficulty;
  category: string;
  tags: string[];
  test_cases_count: number;
  hints_count: number;
  is_active: boolean;
  created_at: string;
}

export interface TaskAdminDetail extends TaskDetail {
  test_cases: { input: string; expected_output: string; description: string | null }[];
  is_active: boolean;
}

export interface TeacherTaskList {
  total: number;
  items: TeacherTaskItem[];
}

export interface TaskImportPreview {
  tasks: number;
  errors: { index: number; title?: string | null; message: string }[];
}

export interface TaskImportReport {
  created: number;
  skipped: number;
  errors: { index: number; title?: string | null; message: string }[];
}

// --- Classrooms & assignments (S16) ------------------------------------

export interface Classroom {
  id: string;
  name: string;
  owner_id: string;
  join_code: string;
  created_at: string;
  members_count: number;
}

export interface ClassroomList {
  items: Classroom[];
}

export interface ClassroomMember {
  user_id: string;
  username: string;
  role: string;
  joined_at: string;
}

export interface ClassroomDetail extends Classroom {
  members: ClassroomMember[];
}

export interface Assignment {
  id: string;
  task_id: string;
  title: string;
  difficulty: TaskDifficulty;
  due_at: string | null;
  created_at: string;
  completed_count: number;
  total_members: number;
}

export interface AssignmentList {
  items: Assignment[];
}

export interface MyAssignment {
  id: string;
  classroom_id: string;
  classroom_name: string;
  task_id: string;
  title: string;
  difficulty: TaskDifficulty;
  due_at: string | null;
  status: TaskStatus;
  overdue: boolean;
}

export interface MyAssignmentList {
  items: MyAssignment[];
}

export interface ClassProgress {
  students: { id: string; username: string }[];
  tasks: { id: string; title: string }[];
  cells: {
    student_id: string;
    task_id: string;
    status: TaskStatus;
    attempts: number;
  }[];
  completion_rate: number;
  problem_tasks: {
    task_id: string;
    title: string;
    attempts: number;
    completed: number;
  }[];
}

// --- Engagement (S17) --------------------------------------------------

export interface Achievement {
  code: string;
  title: string;
  description: string;
  icon: string;
  earned_at: string;
}

export interface AchievementsResponse {
  items: Achievement[];
}

export interface UserStats {
  solved: number;
  attempts: number;
  avg_attempts: number;
  streak_days: number;
  achievements_count: number;
  chat_sessions: number;
  chat_messages: number;
}

export interface AppNotification {
  id: string;
  type: 'assignment' | 'deadline' | 'achievement';
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface NotificationsResponse {
  items: AppNotification[];
  unread: number;
}

export interface BulkAssignmentResult {
  created: string[];
  skipped: string[];
  unknown: string[];
}

export interface GradebookCell {
  student_id: string;
  task_id: string;
  status: TaskStatus;
  attempts: number;
  completed_at: string | null;
}

export interface GradebookResponse {
  students: { id: string; username: string }[];
  tasks: { id: string; title: string }[];
  cells: GradebookCell[];
  completion_rate: number;
  overdue: number;
}

export interface AssignmentTemplateItem {
  id: string;
  name: string;
  task_ids: string[];
  created_at: string;
}

export interface AssignmentTemplateList {
  items: AssignmentTemplateItem[];
  total: number;
}
