/**
 * Связка стора чата с WebSocket: открывает сокет на активную сессию
 * и отправляет сообщения со стримингом (или REST-фолбэком).
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { openChatSocket, type ChatSocket } from '@/lib/chatSocket';
import { useChatStore } from '@/store/chat';

export function useChatSession(sessionId: string | null) {
  const socketRef = useRef<ChatSocket | null>(null);
  const [connected, setConnected] = useState(false);

  const startAssistantDraft = useChatStore((state) => state.startAssistantDraft);
  const appendToken = useChatStore((state) => state.appendToken);
  const finishStream = useChatStore((state) => state.finishStream);
  const failStream = useChatStore((state) => state.failStream);
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const sendViaRest = useChatStore((state) => state.sendViaRest);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    const socket = openChatSocket(sessionId, {
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
      onStart: () => startAssistantDraft(),
      onToken: (delta) => appendToken(delta),
      onDone: (full) => finishStream(full),
      onError: (detail) => failStream(detail),
    });

    socketRef.current = socket;

    return () => {
      socket?.close();
      socketRef.current = null;
      setConnected(false);
    };
  }, [sessionId, startAssistantDraft, appendToken, finishStream, failStream]);

  const send = useCallback(
    (content: string) => {
      const text = content.trim();
      if (!text) {
        return;
      }

      addUserMessage(text);

      const socket = socketRef.current;
      if (socket?.send(text)) {
        startAssistantDraft();
        return;
      }

      // WebSocket недоступен — обычный REST-запрос без стриминга
      void sendViaRest(text);
    },
    [addUserMessage, sendViaRest, startAssistantDraft],
  );

  return { send, connected };
}
