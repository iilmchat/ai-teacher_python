import type { AppNotification } from '@/types/api';

/** Схема в начале строки: `http:`, `javascript:`, `data:` и т.п. */
const SCHEME = /^[a-zA-Z][a-zA-Z0-9+.-]*:/;

/**
 * Безопасная внутренняя ссылка уведомления (D-007).
 *
 * Разрешены только относительные пути, начинающиеся с одного `/`:
 * протоколы, `//host`, `\` и повторные `//` отбрасываются.
 */
export function isSafeNotificationLink(value: unknown): value is string {
  if (typeof value !== 'string') {
    return false;
  }
  const link = value.trim();
  if (!link.startsWith('/') || link.startsWith('//')) {
    return false;
  }
  if (link.includes('//') || link.includes('\\')) {
    return false;
  }
  return !SCHEME.test(link);
}

function safeId(value: unknown): string | null {
  if (typeof value !== 'string' && typeof value !== 'number') {
    return null;
  }
  const id = String(value).trim();
  return /^[a-zA-Z0-9-]+$/.test(id) ? id : null;
}

/**
 * Ссылка уведомления: `payload.link` после проверки, иначе fallback по типу.
 *
 * Fallback нужен старым уведомлениям, созданным до D-007.
 */
export function notificationLink(item: AppNotification): string | null {
  const fromPayload = item.payload.link;
  if (fromPayload !== undefined && fromPayload !== null && fromPayload !== '') {
    // Ссылка есть, но не прошла проверку — игнорируем её, fallback не берём:
    // иначе вредоносный payload мог бы подменить безопасный маршрут.
    return isSafeNotificationLink(fromPayload) ? fromPayload.trim() : null;
  }
  if (item.type === 'attempt_feedback') {
    const taskId = safeId(item.payload.task_id);
    return taskId ? `/tasks/${taskId}` : null;
  }
  if (item.type === 'announcement') {
    const classroomId = safeId(item.payload.classroom_id);
    return classroomId ? `/classrooms/${classroomId}` : null;
  }
  if (item.type === 'assignment' || item.type === 'deadline') {
    return '/assignments';
  }
  return null;
}

/** Человекочитаемый текст уведомления. */
export function notificationText(
  item: AppNotification,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const title = String(item.payload.title ?? '');
  if (item.type === 'assignment') {
    return t('dashboard.notifyAssignment', { title });
  }
  if (item.type === 'deadline') {
    return t('dashboard.notifyDeadline', { title });
  }
  if (item.type === 'achievement') {
    return t('dashboard.notifyAchievement', { title });
  }
  if (item.type === 'attempt_feedback') {
    return t('dashboard.notifyFeedback', {
      title,
      teacher: String(item.payload.teacher ?? ''),
    });
  }
  if (item.type === 'announcement') {
    return t('dashboard.notifyAnnouncement', {
      title: String(item.payload.classroom_name ?? ''),
    });
  }
  return title;
}
