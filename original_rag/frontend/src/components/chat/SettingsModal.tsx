import { AlertTriangle, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useChatStore } from '@/stores/chatStore';
import { useState } from 'react';
import { api } from '@/lib/api';

export function SettingsModal() {
  const { settingsModalOpen, setSettingsModalOpen, chats } = useChatStore();
  const [confirmClearChats, setConfirmClearChats] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  const handleClearChats = async () => {
    if (confirmClearChats) {
      setIsClearing(true);
      try {
        // Delete each chat from backend to cascade-delete documents from ChromaDB
        await Promise.all(
          chats.map(chat => api.deleteChat(chat.id).catch(err => {
            // Log but don't fail if individual chat deletion fails
            console.warn(`Failed to delete chat ${chat.id} from backend:`, err);
          }))
        );
        // Clear all chats from frontend state
        useChatStore.setState({ chats: [], currentChatId: null });
      } finally {
        setIsClearing(false);
        setConfirmClearChats(false);
      }
    } else {
      setConfirmClearChats(true);
    }
  };

  return (
    <Dialog open={settingsModalOpen} onOpenChange={setSettingsModalOpen}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Data Management */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium">Data Management</h3>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Clear all conversations</p>
                  <p className="text-xs text-muted-foreground">
                    {chats.length} conversation{chats.length !== 1 ? 's' : ''} with their documents
                  </p>
                </div>
                <Button
                  variant={confirmClearChats ? 'destructive' : 'outline'}
                  size="sm"
                  onClick={handleClearChats}
                  onBlur={() => !isClearing && setConfirmClearChats(false)}
                  disabled={isClearing || chats.length === 0}
                >
                  {isClearing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : confirmClearChats ? (
                    'Confirm'
                  ) : (
                    'Clear'
                  )}
                </Button>
              </div>
            </div>

            {confirmClearChats && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <p>This will delete all conversations and their documents from the database. This cannot be undone.</p>
              </div>
            )}
          </div>

          <Separator />

          {/* About */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium">About</h3>
            <div className="text-sm text-muted-foreground space-y-1">
              <p>RAG Chat Interface v1.0</p>
              <p>Built with React, Tailwind CSS, and Zustand</p>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
