import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { ArrowUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useChatStore } from '@/stores/chatStore';
import { useChat } from '@/hooks/useChat';
import { cn } from '@/lib/utils';

export function MessageInput() {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { chats, currentChatId } = useChatStore();
  const { sendMessage, isStreaming, collectionName } = useChat();

  // Get current chat for display
  const currentChat = chats?.find((c) => c.id === currentChatId);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');

    // Use the useChat hook to send the message with streaming
    await sendMessage(userMessage);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-border bg-card shrink-0">
      <div className="max-w-chat mx-auto px-6 py-4">
        {/* Active chat indicator - shows document count if any */}
        {currentChat && currentChat.documents && currentChat.documents.length > 0 && (
          <p className="text-xs text-muted-foreground mb-2">
            Searching in: <span className="font-medium">{currentChat.documents.length} document{currentChat.documents.length !== 1 ? 's' : ''}</span>
          </p>
        )}

        <div className="relative flex items-center">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your documents..."
            disabled={isStreaming}
            rows={1}
            className={cn(
              'w-full resize-none rounded-xl border border-input bg-background px-4 py-3.5 pr-14 text-sm',
              'placeholder:text-muted-foreground',
              'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
              'disabled:cursor-not-allowed disabled:opacity-50',
              'min-h-[48px] max-h-[200px] overflow-y-auto scrollbar-auto'
            )}
          />
          <Button
            size="icon"
            onClick={handleSubmit}
            disabled={!input.trim() || isStreaming}
            className={cn(
              'absolute right-3 h-8 w-8 rounded-lg',
              'transition-all duration-200',
              input.trim() && !isStreaming
                ? 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm'
                : 'bg-primary/70 text-primary-foreground/70 cursor-not-allowed'
            )}
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
        </div>

        <p className="text-xs text-muted-foreground mt-2 text-center">
          Press Enter to send, Shift + Enter for new line
        </p>
      </div>
    </div>
  );
}
