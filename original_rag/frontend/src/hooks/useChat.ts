/**
 * useChat Hook
 * Handles chat interactions with streaming support.
 * ADR-007: Uses chat-scoped collections (chat_{chatId})
 */

import { useCallback } from 'react';
import { useChatStore, Source } from '@/stores/chatStore';
import { streamChat } from '@/lib/sse';

export function useChat() {
  const {
    sessionId,
    chats,
    currentChatId,
    isStreaming,
    currentStreamingMessage,
    currentSources,
    error,
    addUserMessage,
    startStreaming,
    appendStreamToken,
    setSources,
    finishStreaming,
    setError,
    clearMessages,
    resetSession,
  } = useChatStore();

  // Get current chat messages (with null safety for persisted state migration)
  const currentChat = chats?.find((chat) => chat.id === currentChatId);
  const messages = currentChat?.messages ?? [];

  // ADR-007: Collection name is derived from chat ID (chat_{chatId})
  const collectionName = currentChatId ? `chat_${currentChatId}` : null;

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming || !currentChatId) return;

      // Add user message to state
      addUserMessage(content);

      // Start streaming
      startStreaming();

      try {
        await streamChat(content, sessionId, collectionName || undefined, {
          onToken: (token) => {
            appendStreamToken(token);
          },
          onSources: (sources: Source[]) => {
            setSources(sources);
          },
          onDone: (_messageId, wasGrounded, _processingTimeMs) => {
            finishStreaming(wasGrounded);
          },
          onError: (err) => {
            setError(err.message);
          },
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      }
    },
    [
      sessionId,
      isStreaming,
      collectionName,
      addUserMessage,
      startStreaming,
      appendStreamToken,
      setSources,
      finishStreaming,
      setError,
    ]
  );

  return {
    // State
    messages,
    isStreaming,
    currentStreamingMessage,
    currentSources,
    error,
    sessionId,
    collectionName,

    // Actions
    sendMessage,
    clearMessages,
    resetSession,
  };
}
