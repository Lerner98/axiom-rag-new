import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Source {
  id: string;
  filename: string;
  page?: number;
  relevance: number;
  preview: string;
  chunk_id?: string;
  relevance_score?: number;
  content_preview?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: Date;
  isStreaming?: boolean;
}

// ADR-007: Document belongs to a chat, not to a global collection
export interface Document {
  id: string;
  chatId: string;  // Foreign key to chat
  name: string;
  type: string;
  size: number;
  chunkCount: number;
  uploadedAt: Date;
}

// ADR-007: Chat owns its documents
export interface Chat {
  id: string;
  title: string;
  messages: Message[];
  documents: Document[];  // NEW: Documents belong to chat
  mode: 'local' | 'cloud';  // ADR-006: Per-chat mode
  createdAt: Date;
  updatedAt: Date;
}

interface ChatStore {
  // Session
  sessionId: string;
  setSessionId: (id: string) => void;
  resetSession: () => void;

  // Sidebar state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;

  // Document panel state (ADR-007)
  documentPanelOpen: boolean;
  setDocumentPanelOpen: (open: boolean) => void;

  // Streaming state
  isStreaming: boolean;
  currentStreamingMessage: string;
  currentSources: Source[];
  error: string | null;

  // Streaming actions
  addUserMessage: (content: string) => void;
  startStreaming: () => void;
  appendStreamToken: (token: string) => void;
  setSources: (sources: Source[]) => void;
  finishStreaming: (wasGrounded?: boolean) => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;

  // Chats
  chats: Chat[];
  currentChatId: string | null;
  setCurrentChatId: (id: string | null) => void;
  createNewChat: () => string;  // Returns the new chat ID
  deleteChat: (id: string) => void;
  renameChat: (id: string, newTitle: string) => void;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  setChatMode: (chatId: string, mode: 'local' | 'cloud') => void;

  // Chat Documents (ADR-007: Documents scoped to chat)
  addDocumentToChat: (chatId: string, doc: Omit<Document, 'uploadedAt' | 'chatId'>) => void;
  removeDocumentFromChat: (chatId: string, docId: string) => void;
  getDocumentsForChat: (chatId: string) => Document[];
  getCurrentChatDocuments: () => Document[];
  getCurrentChatDocumentCount: () => number;

  // Modals
  settingsModalOpen: boolean;
  setSettingsModalOpen: (open: boolean) => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);
const generateSessionId = () => `session_${Date.now()}_${generateId()}`;

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      // Session
      sessionId: generateSessionId(),
      setSessionId: (id) => set({ sessionId: id }),
      resetSession: () =>
        set({
          sessionId: generateSessionId(),
          chats: [],
          currentChatId: null,
          isStreaming: false,
          currentStreamingMessage: '',
          currentSources: [],
          error: null,
        }),

      // Sidebar
      sidebarOpen: true,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      // Document panel (ADR-007)
      documentPanelOpen: false,
      setDocumentPanelOpen: (open) => set({ documentPanelOpen: open }),

      // Streaming state
      isStreaming: false,
      currentStreamingMessage: '',
      currentSources: [],
      error: null,

      // Streaming actions
      addUserMessage: (content) => {
        const { currentChatId, chats } = get();

        if (!currentChatId) {
          const newChat: Chat = {
            id: generateId(),
            title: content.slice(0, 30) + (content.length > 30 ? '...' : ''),
            messages: [
              {
                id: generateId(),
                role: 'user',
                content,
                timestamp: new Date(),
              },
            ],
            documents: [],  // ADR-007: Start with empty documents
            mode: 'local',  // ADR-006: Default to local mode
            createdAt: new Date(),
            updatedAt: new Date(),
          };

          set({
            chats: [newChat, ...chats],
            currentChatId: newChat.id,
            error: null,
          });
          return;
        }

        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === currentChatId
              ? {
                  ...chat,
                  messages: [
                    ...chat.messages,
                    {
                      id: generateId(),
                      role: 'user' as const,
                      content,
                      timestamp: new Date(),
                    },
                  ],
                  title:
                    chat.messages.length === 0
                      ? content.slice(0, 30) + (content.length > 30 ? '...' : '')
                      : chat.title,
                  updatedAt: new Date(),
                }
              : chat
          ),
          error: null,
        }));
      },

      startStreaming: () => {
        set({
          isStreaming: true,
          currentStreamingMessage: '',
          currentSources: [],
          error: null,
        });
      },

      appendStreamToken: (token) => {
        set((state) => ({
          currentStreamingMessage: state.currentStreamingMessage + token,
        }));
      },

      setSources: (sources) => {
        set({ currentSources: sources });
      },

      finishStreaming: (_wasGrounded) => {
        const { currentStreamingMessage, currentSources, currentChatId } = get();

        if (currentChatId && currentStreamingMessage) {
          set((state) => ({
            chats: state.chats.map((chat) =>
              chat.id === currentChatId
                ? {
                    ...chat,
                    messages: [
                      ...chat.messages,
                      {
                        id: generateId(),
                        role: 'assistant' as const,
                        content: currentStreamingMessage,
                        sources: currentSources,
                        timestamp: new Date(),
                      },
                    ],
                    updatedAt: new Date(),
                  }
                : chat
            ),
            isStreaming: false,
            currentStreamingMessage: '',
            currentSources: [],
          }));
        } else {
          set({
            isStreaming: false,
            currentStreamingMessage: '',
            currentSources: [],
          });
        }
      },

      setError: (error) => {
        set({
          error,
          isStreaming: false,
          currentStreamingMessage: '',
        });
      },

      clearMessages: () => {
        const { currentChatId } = get();
        if (currentChatId) {
          set((state) => ({
            chats: state.chats.map((chat) =>
              chat.id === currentChatId
                ? { ...chat, messages: [], updatedAt: new Date() }
                : chat
            ),
            error: null,
          }));
        }
      },

      // Chats
      chats: [],
      currentChatId: null,
      setCurrentChatId: (id) => set({ currentChatId: id }),

      createNewChat: () => {
        const newChat: Chat = {
          id: generateId(),
          title: 'New Chat',
          messages: [],
          documents: [],  // ADR-007: Start with empty documents
          mode: 'local',  // ADR-006: Default to local mode
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        set((state) => ({
          chats: [newChat, ...state.chats],
          currentChatId: newChat.id,
        }));
        return newChat.id;
      },

      deleteChat: (id) => {
        set((state) => ({
          chats: state.chats.filter((chat) => chat.id !== id),
          currentChatId: state.currentChatId === id ? null : state.currentChatId,
        }));
      },

      renameChat: (id, newTitle) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === id
              ? { ...chat, title: newTitle, updatedAt: new Date() }
              : chat
          ),
        }));
      },

      addMessage: (message) => {
        const { currentChatId, chats } = get();

        if (!currentChatId) {
          const newChat: Chat = {
            id: generateId(),
            title: message.content.slice(0, 30) + (message.content.length > 30 ? '...' : ''),
            messages: [],
            documents: [],
            mode: 'local',
            createdAt: new Date(),
            updatedAt: new Date(),
          };

          const newMessage: Message = {
            ...message,
            id: generateId(),
            timestamp: new Date(),
          };

          newChat.messages.push(newMessage);

          set({
            chats: [newChat, ...chats],
            currentChatId: newChat.id,
          });
          return;
        }

        const newMessage: Message = {
          ...message,
          id: generateId(),
          timestamp: new Date(),
        };

        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === currentChatId
              ? {
                  ...chat,
                  messages: [...chat.messages, newMessage],
                  title:
                    chat.messages.length === 0 && message.role === 'user'
                      ? message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '')
                      : chat.title,
                  updatedAt: new Date(),
                }
              : chat
          ),
        }));
      },

      updateMessage: (id, updates) => {
        set((state) => ({
          chats: state.chats.map((chat) => ({
            ...chat,
            messages: chat.messages.map((msg) =>
              msg.id === id ? { ...msg, ...updates } : msg
            ),
          })),
        }));
      },

      setChatMode: (chatId, mode) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? { ...chat, mode, updatedAt: new Date() }
              : chat
          ),
        }));
      },

      // Chat Documents (ADR-007)
      addDocumentToChat: (chatId, doc) => {
        const newDoc: Document = {
          ...doc,
          chatId,
          uploadedAt: new Date(),
        };
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  documents: [...chat.documents, newDoc],
                  updatedAt: new Date(),
                }
              : chat
          ),
        }));
      },

      removeDocumentFromChat: (chatId, docId) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  documents: chat.documents.filter((d) => d.id !== docId),
                  updatedAt: new Date(),
                }
              : chat
          ),
        }));
      },

      getDocumentsForChat: (chatId) => {
        const chat = get().chats.find((c) => c.id === chatId);
        return chat?.documents || [];
      },

      getCurrentChatDocuments: () => {
        const { currentChatId, chats } = get();
        if (!currentChatId) return [];
        const chat = chats.find((c) => c.id === currentChatId);
        return chat?.documents || [];
      },

      getCurrentChatDocumentCount: () => {
        const { currentChatId, chats } = get();
        if (!currentChatId) return 0;
        const chat = chats.find((c) => c.id === currentChatId);
        return chat?.documents.length || 0;
      },

      // Modals
      settingsModalOpen: false,
      setSettingsModalOpen: (open) => set({ settingsModalOpen: open }),
    }),
    {
      name: 'rag_chat_store',
      partialize: (state) => ({
        sessionId: state.sessionId,
        chats: state.chats,
        currentChatId: state.currentChatId,
      }),
    }
  )
);
