/**
 * Общий стейт уведомлений (S47-005): список, фильтр и счётчик для бейджа.
 *
 * Бейдж в `AppLayout` и страница `/notifications` читают один и тот же
 * `unread`, поэтому `read` и `read-all` обновляют его сразу в обоих местах.
 */

import i18n from '@/i18n';
import { create } from 'zustand';

import { api } from '@/lib/api';
import type { AppNotification, NotificationsResponse } from '@/types/api';

interface NotificationsState {
  items: AppNotification[];
  unread: number;
  filterType: string;
  loading: boolean;
  error: string | null;

  load: (notificationType?: string) => Promise<void>;
  refreshUnread: () => Promise<void>;
  setFilterType: (notificationType: string) => void;
  markRead: (notificationId: string) => Promise<void>;
  markAllRead: () => Promise<void>;
}

export const useNotificationsStore = create<NotificationsState>((set, get) => ({
  items: [],
  unread: 0,
  filterType: '',
  loading: false,
  error: null,

  load: async (notificationType) => {
    const type = notificationType ?? get().filterType;
    set({ loading: true, error: null, filterType: type });
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (type) {
        params.set('type', type);
      }
      const data = await api.get<NotificationsResponse>(
        `/me/notifications?${params.toString()}`,
      );
      set({ items: data.items, unread: data.unread });
    } catch {
      set({ error: i18n.t('notifications.loadError') });
    } finally {
      set({ loading: false });
    }
  },

  refreshUnread: async () => {
    try {
      const data = await api.get<NotificationsResponse>(
        '/me/notifications?limit=1',
      );
      set({ unread: data.unread });
    } catch {
      // Бейдж не должен ломать интерфейс, если уведомления временно недоступны
    }
  },

  setFilterType: (notificationType) => set({ filterType: notificationType }),

  markRead: async (notificationId) => {
    const item = get().items.find((row) => row.id === notificationId);
    if (item?.read_at) {
      return;
    }
    try {
      await api.post<AppNotification>(
        `/me/notifications/${notificationId}/read`,
      );
      set({
        items: get().items.map((row) =>
          row.id === notificationId
            ? { ...row, read_at: new Date().toISOString() }
            : row,
        ),
        unread: Math.max(0, get().unread - 1),
      });
    } catch {
      set({ error: i18n.t('notifications.readError') });
    }
  },

  markAllRead: async () => {
    try {
      await api.post<{ updated: number }>('/me/notifications/read-all');
      const now = new Date().toISOString();
      set({
        items: get().items.map((row) =>
          row.read_at ? row : { ...row, read_at: now },
        ),
        unread: 0,
      });
    } catch {
      set({ error: i18n.t('notifications.readAllError') });
    }
  },
}));
