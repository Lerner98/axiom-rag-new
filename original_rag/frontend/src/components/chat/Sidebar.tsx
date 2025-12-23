import { useState, useRef, useEffect } from 'react';
import { Plus, Settings, MessageSquare, X, Trash2, FileText, Loader2, Pencil, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useChatStore, Chat } from '@/stores/chatStore';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

export function Sidebar() {
  const {
    sidebarOpen,
    setSidebarOpen,
    chats,
    currentChatId,
    setCurrentChatId,
    createNewChat,
    deleteChat,
    renameChat,
    setSettingsModalOpen,
    isStreaming,
  } = useChatStore();

  const [deleteConfirmChat, setDeleteConfirmChat] = useState<Chat | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const editInputRef = useRef<HTMLInputElement>(null);

  // Focus input when editing starts
  useEffect(() => {
    if (editingChatId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingChatId]);

  const startEditing = (chat: Chat) => {
    setEditingChatId(chat.id);
    setEditingTitle(chat.title);
  };

  const saveTitle = () => {
    if (editingChatId && editingTitle.trim()) {
      renameChat(editingChatId, editingTitle.trim());
    }
    setEditingChatId(null);
    setEditingTitle('');
  };

  const cancelEditing = () => {
    setEditingChatId(null);
    setEditingTitle('');
  };

  const handleDeleteChat = async () => {
    if (!deleteConfirmChat) return;

    setIsDeleting(true);
    try {
      // Delete from backend (documents, memory, etc.)
      await api.deleteChat(deleteConfirmChat.id);
      // Delete from frontend store
      deleteChat(deleteConfirmChat.id);
    } catch (err) {
      console.error('Failed to delete chat:', err);
      // Still delete from frontend even if backend fails
      deleteChat(deleteConfirmChat.id);
    } finally {
      setIsDeleting(false);
      setDeleteConfirmChat(null);
    }
  };

  // Handle chat selection - disabled during streaming
  const handleChatSelect = (chatId: string) => {
    if (isStreaming) return; // Don't allow chat switching while streaming
    if (editingChatId !== chatId) {
      setCurrentChatId(chatId);
    }
  };

  // Handle new chat - disabled during streaming
  const handleNewChat = () => {
    if (isStreaming) return;
    createNewChat();
  };

  return (
    <>
      {/* 
        OVERLAY BEHAVIOR CHANGE:
        - When sidebar is open AND idle: overlay is clickable to close sidebar, but doesn't block pointer events on chat
        - When streaming: overlay prevents sidebar interactions (not chat interactions)
        
        Actually, let's just remove the blocking overlay entirely.
        The sidebar slides over - clicking outside closes it.
        This is the standard mobile drawer pattern.
      */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-foreground/20 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed z-50 h-full w-sidebar bg-sidebar border-r border-sidebar-border flex flex-col transition-transform duration-200 ease-out',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Header with app name and close button */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-sidebar-border bg-sidebar-hover/50">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
              <MessageSquare className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="font-semibold text-sidebar-foreground">RAG Chat</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(false)}
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* New Chat Button - disabled during streaming */}
        <div className="p-4">
          <Button
            onClick={handleNewChat}
            disabled={isStreaming}
            className={cn(
              "w-full justify-start gap-2 bg-primary text-primary-foreground hover:bg-primary/90",
              isStreaming && "opacity-50 cursor-not-allowed"
            )}
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>

        {/* Chat History */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="px-4 py-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Recent Chats
            </span>
          </div>

          <ScrollArea className="flex-1">
            {chats.length === 0 ? (
              <div className="px-2 py-8 text-center">
                <MessageSquare className="h-10 w-10 mx-auto mb-3 text-muted-foreground opacity-50" />
                <p className="text-sm text-muted-foreground">No conversations yet</p>
                <p className="text-xs text-muted-foreground mt-1">Start a new chat to begin</p>
              </div>
            ) : (
              <div className="space-y-1 px-2">
                {chats.map((chat) => (
                  <div
                    key={chat.id}
                    className={cn(
                      'group flex items-center gap-1.5 px-2 py-2 rounded-lg transition-colors',
                      currentChatId === chat.id
                        ? 'bg-sidebar-active border-l-2 border-sidebar-active-border'
                        : 'hover:bg-sidebar-hover',
                      // Disable interaction during streaming (except current chat for viewing)
                      isStreaming && currentChatId !== chat.id
                        ? 'opacity-50 cursor-not-allowed'
                        : 'cursor-pointer'
                    )}
                    onClick={() => handleChatSelect(chat.id)}
                    onDoubleClick={(e) => {
                      if (isStreaming) return;
                      e.stopPropagation();
                      startEditing(chat);
                    }}
                  >
                    <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0 overflow-hidden">
                      {editingChatId === chat.id ? (
                        <div className="flex items-center gap-1">
                          <input
                            ref={editInputRef}
                            type="text"
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                saveTitle();
                              } else if (e.key === 'Escape') {
                                cancelEditing();
                              }
                            }}
                            onBlur={saveTitle}
                            onClick={(e) => e.stopPropagation()}
                            className="w-full text-sm font-medium bg-background border border-input rounded px-1 py-0.5 focus:outline-none focus:ring-1 focus:ring-ring"
                          />
                        </div>
                      ) : (
                        <>
                          <p className="text-sm font-medium truncate text-sidebar-foreground">
                            {chat.title}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span className="truncate">
                              {chat.messages.length > 0
                                ? chat.messages[0].content.slice(0, 30)
                                : 'No messages'}
                            </span>
                            {chat.documents.length > 0 && (
                              <span className="flex items-center gap-0.5 shrink-0">
                                <FileText className="h-3 w-3" />
                                {chat.documents.length}
                              </span>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                    {editingChatId !== chat.id && (
                      <div className={cn(
                        "flex items-center gap-0.5 shrink-0 transition-opacity",
                        currentChatId === chat.id ? "opacity-100" : "opacity-0 group-hover:opacity-100",
                        isStreaming && "opacity-50"
                      )}>
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={isStreaming}
                          className="h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-sidebar-hover disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={(e) => {
                            e.stopPropagation();
                            startEditing(chat);
                          }}
                          title="Rename chat"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={isStreaming}
                          className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10 disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirmChat(chat);
                          }}
                          title="Delete chat"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Settings Button */}
        <div className="p-4 border-t border-sidebar-border">
          <Button
            variant="ghost"
            onClick={() => setSettingsModalOpen(true)}
            className="w-full justify-start gap-2 text-muted-foreground hover:text-sidebar-foreground"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Button>
        </div>
      </aside>

      {/* Delete chat confirmation dialog */}
      <AlertDialog open={!!deleteConfirmChat} onOpenChange={() => setDeleteConfirmChat(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" />
              Delete Chat Permanently
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p>
                  Are you sure you want to delete "<span className="font-medium text-foreground">{deleteConfirmChat?.title}</span>"?
                </p>

                <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 space-y-2">
                  <p className="font-medium text-destructive text-sm">This will permanently delete:</p>
                  <ul className="text-sm space-y-1 ml-4 list-disc text-muted-foreground">
                    <li>All chat messages and conversation history</li>
                    {deleteConfirmChat && deleteConfirmChat.documents.length > 0 ? (
                      <li className="text-foreground font-medium">
                        {deleteConfirmChat.documents.length} uploaded document{deleteConfirmChat.documents.length !== 1 ? 's' : ''} and their embeddings
                      </li>
                    ) : (
                      <li>Any documents uploaded to this chat</li>
                    )}
                    <li>All associated memory and context</li>
                  </ul>
                </div>

                <p className="text-sm font-medium text-destructive">
                  This action cannot be undone.
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteChat}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Everything
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
