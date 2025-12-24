import { useState } from 'react';
import { Plus, Settings, MessageSquare, X, Trash2, Loader2 } from 'lucide-react';
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
import { ChatItem } from './ChatItem';

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
    if (isStreaming) return;
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
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-foreground/20 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar - Fixed on mobile, in-flow on desktop */}
      <aside
        className={cn(
          'h-full w-sidebar bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-200 ease-out shrink-0',
          // Mobile: fixed overlay
          'fixed z-50 lg:relative lg:z-auto',
          // Visibility
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:w-0 lg:translate-x-0 lg:border-0 lg:overflow-hidden'
        )}
      >
        {/* Header with app name and close button (mobile only) */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-sidebar-border bg-sidebar-hover/50">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
              <MessageSquare className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="font-semibold text-sidebar-foreground">RAG Chat</span>
          </div>
          {/* Close button - only on mobile, desktop uses header toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(false)}
            className="h-8 w-8 lg:hidden"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* New Chat Button - subtle row style like Claude */}
        <div className="px-2 py-3">
          <button
            onClick={handleNewChat}
            disabled={isStreaming}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium",
              "text-sidebar-foreground hover:bg-sidebar-hover transition-colors",
              isStreaming && "opacity-50 cursor-not-allowed"
            )}
          >
            <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center shrink-0">
              <Plus className="h-3.5 w-3.5 text-primary-foreground" />
            </div>
            New chat
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="px-4 py-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Recent Chats
            </span>
          </div>

          <ScrollArea className="flex-1 w-full">
            {chats.length === 0 ? (
              <div className="px-2 py-8 text-center">
                <MessageSquare className="h-10 w-10 mx-auto mb-3 text-muted-foreground opacity-50" />
                <p className="text-sm text-muted-foreground">No conversations yet</p>
                <p className="text-xs text-muted-foreground mt-1">Start a new chat to begin</p>
              </div>
            ) : (
              <div className="space-y-0.5 px-2 w-full">
                {chats.map((chat) => (
                  <ChatItem
                    key={chat.id}
                    chat={chat}
                    isActive={currentChatId === chat.id}
                    isEditing={editingChatId === chat.id}
                    isStreaming={isStreaming}
                    editingTitle={editingTitle}
                    onSelect={() => handleChatSelect(chat.id)}
                    onStartEditing={() => startEditing(chat)}
                    onDeleteRequest={() => setDeleteConfirmChat(chat)}
                    onTitleChange={setEditingTitle}
                    onSaveTitle={saveTitle}
                    onCancelEditing={cancelEditing}
                  />
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
