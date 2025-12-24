import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { ArrowUp, Plus, Paperclip, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { useChatStore } from '@/stores/chatStore';
import { useChat } from '@/hooks/useChat';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

export function MessageInput() {
  const [input, setInput] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadPopoverOpen, setUploadPopoverOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { chats, currentChatId, addDocumentToChat } = useChatStore();
  const { sendMessage, isStreaming, collectionName } = useChat();

  // Get current chat for display
  const currentChat = chats?.find((c) => c.id === currentChatId);

  const acceptedTypes = ['.pdf', '.txt', '.md', '.docx'];
  const acceptedTypesDisplay = 'PDF, TXT, MD, DOCX';

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Ctrl+U keyboard shortcut for file upload
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.ctrlKey && e.key === 'u' && !isUploading && !isStreaming) {
        e.preventDefault();
        fileInputRef.current?.click();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isUploading, isStreaming]);

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

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0 || !currentChatId) return;

    const files = Array.from(e.target.files).filter((file) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      return acceptedTypes.includes(ext);
    });

    if (files.length === 0) return;

    setIsUploading(true);
    setUploadPopoverOpen(false);

    try {
      const result = await api.uploadChatDocuments(currentChatId, files);

      // Add successfully uploaded documents to store
      for (const uploaded of result.uploaded) {
        const file = files.find((f) => f.name === uploaded.name);
        addDocumentToChat(currentChatId, {
          id: uploaded.id,
          name: uploaded.name,
          type: file?.type || 'application/octet-stream',
          size: file?.size || 0,
          chunkCount: uploaded.chunk_count,
        });
      }
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="bg-background shrink-0 pb-4">
      <div className="max-w-chat mx-auto px-6">
        <div className="rounded-xl border-2 border-muted-foreground/30 bg-background">
          {/* Text area - no border, sits inside container */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your documents..."
            disabled={isStreaming}
            rows={1}
            className={cn(
              'w-full resize-none bg-transparent px-4 pt-3 pb-1 text-sm leading-6',
              'placeholder:text-muted-foreground',
              'focus:outline-none',
              'disabled:cursor-not-allowed disabled:opacity-50',
              'min-h-[24px] max-h-[150px]',
              'overflow-y-auto scrollbar-thin'
            )}
          />
          {/* Button row - + button on left, send button on right */}
          <div className="flex items-center justify-between px-3 pb-2">
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept={acceptedTypes.join(',')}
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />

            {/* Add files button */}
            <Popover open={uploadPopoverOpen} onOpenChange={setUploadPopoverOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  disabled={isUploading || isStreaming}
                  className={cn(
                    'h-8 w-8 rounded-lg flex items-center justify-center',
                    'text-muted-foreground hover:text-foreground hover:bg-muted',
                    'transition-colors',
                    (isUploading || isStreaming) && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  {isUploading ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Plus className="h-5 w-5" />
                  )}
                </button>
              </PopoverTrigger>
              <PopoverContent
                side="top"
                align="start"
                sideOffset={8}
                className="p-1 shadow-lg w-44"
              >
                <button
                  type="button"
                  onClick={triggerFileSelect}
                  className={cn(
                    'flex items-center gap-2.5 px-2.5 py-1.5 rounded-md w-full text-left',
                    'text-sm hover:bg-muted transition-colors'
                  )}
                >
                  <Paperclip className="h-4 w-4 text-muted-foreground" />
                  <span>Add files</span>
                  <span className="ml-auto text-xs text-muted-foreground">Ctrl+U</span>
                </button>
              </PopoverContent>
            </Popover>

            {/* Send button */}
            <Button
              size="icon"
              onClick={handleSubmit}
              disabled={!input.trim() || isStreaming}
              className={cn(
                'h-8 w-8 rounded-lg',
                'transition-all duration-200',
                input.trim() && !isStreaming
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm'
                  : 'bg-primary/70 text-primary-foreground/70 cursor-not-allowed'
              )}
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
