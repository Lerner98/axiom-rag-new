import { useEffect, useRef, useState } from 'react';
import { MessageSquare, ArrowDown, Upload, FileText, Search, BookOpen, Sparkles, Loader2, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MessageBubble } from './MessageBubble';
import { useChatStore, Message, StreamingPhase } from '@/stores/chatStore';
import { cn } from '@/lib/utils';

// Progress indicator component for streaming phases
function StreamingProgress({ phase, sourceCount }: { phase: StreamingPhase; sourceCount: number }) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Timer to show elapsed time during long operations
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedSeconds(s => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const phases = [
    { key: 'searching', label: 'Searching documents...', icon: Search },
    { key: 'found_sources', label: `Found ${sourceCount} document${sourceCount !== 1 ? 's' : ''}`, icon: BookOpen },
    { key: 'generating', label: 'Generating response...', icon: Sparkles },
  ];

  // Treat 'idle' as 'searching' for display purposes (streaming just started)
  const displayPhase = phase === 'idle' ? 'searching' : phase;
  const currentIndex = phases.findIndex(p => p.key === displayPhase);

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="max-w-[70%] rounded-2xl rounded-bl-md bg-assistant-bubble border border-assistant-bubble-border px-4 py-3">
        <div className="flex flex-col gap-2">
          {phases.map((p, index) => {
            const Icon = p.icon;
            const isActive = p.key === displayPhase;
            const isComplete = index < currentIndex;
            const isPending = index > currentIndex;

            return (
              <div
                key={p.key}
                className={cn(
                  'flex items-center gap-2 text-sm transition-all duration-300',
                  isActive && 'text-primary font-medium',
                  isComplete && 'text-green-600 dark:text-green-400',
                  isPending && 'text-muted-foreground/50'
                )}
              >
                <div className={cn(
                  'w-5 h-5 rounded-full flex items-center justify-center transition-all',
                  isActive && 'bg-primary/10',
                  isComplete && 'bg-green-500/10'
                )}>
                  {isComplete ? (
                    <Check className="w-3 h-3 text-green-500" />
                  ) : isActive ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-muted-foreground/30" />
                  )}
                </div>
                <span>{p.label}</span>
              </div>
            );
          })}
        </div>
        {/* Show elapsed time after 3 seconds to indicate activity */}
        {elapsedSeconds >= 3 && (
          <div className="mt-2 pt-2 border-t border-assistant-bubble-border/30 text-xs text-muted-foreground flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            <span>Processing... {elapsedSeconds}s</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function MessageList() {
  const {
    chats,
    currentChatId,
    setDocumentPanelOpen,
    isStreaming,
    streamingPhase,
    currentStreamingMessage,
    currentSources,
    error,
    getCurrentChatDocumentCount,
    sidebarOpen,
    documentPanelOpen,
  } = useChatStore();
  const currentChat = chats.find((c) => c.id === currentChatId);
  const messages = currentChat?.messages || [];
  const documentCount = getCurrentChatDocumentCount();

  // Create streaming message for display
  const streamingMessage: Message | null = isStreaming && currentStreamingMessage
    ? {
        id: 'streaming',
        role: 'assistant',
        content: currentStreamingMessage,
        sources: currentSources,
        timestamp: new Date(),
        isStreaming: true,
      }
    : null;

  const scrollRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.target as HTMLDivElement;
    const isNearBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 100;
    setShowScrollButton(!isNearBottom);
  };

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md animate-fade-in">
          <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-primary/10 flex items-center justify-center">
            <MessageSquare className="w-8 h-8 text-primary" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground mb-2">
            Start a conversation
          </h2>
          <p className="text-muted-foreground mb-2">
            Ask a question about your documents...
          </p>
          <p className="text-sm text-muted-foreground mb-6">
            {documentCount > 0
              ? `You have ${documentCount} document${documentCount !== 1 ? 's' : ''} uploaded to this chat.`
              : 'Upload documents to this chat to get started.'}
          </p>
          {currentChatId && (
            <Button
              variant="outline"
              onClick={() => setDocumentPanelOpen(true)}
              className="gap-2"
            >
              {documentCount > 0 ? (
                <>
                  <FileText className="h-4 w-4" />
                  View Documents ({documentCount})
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  Upload Documents
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 relative min-h-0">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="absolute inset-0 overflow-y-auto scrollbar-thin"
      >
        {/* 
          CENTERING FIX:
          The container uses w-full with max-w-chat and mx-auto.
          This centers the chat content within the available space.
          
          For a more "viewport-centered" feel, we can add some responsive
          left padding when sidebar is open on larger screens.
        */}
        <div className="w-full max-w-chat mx-auto px-4 sm:px-6 py-6 space-y-4">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {/* Show streaming message when content is being generated */}
          {streamingMessage && (
            <MessageBubble key="streaming" message={streamingMessage} />
          )}
          {/* Show progress phases when streaming but no content yet */}
          {isStreaming && !currentStreamingMessage && (
            <StreamingProgress phase={streamingPhase} sourceCount={currentSources.length} />
          )}
          {/* Show error if any */}
          {error && (
            <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-sm">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <Button
          variant="secondary"
          size="icon"
          onClick={scrollToBottom}
          className="absolute bottom-4 right-4 h-10 w-10 rounded-full shadow-lg animate-fade-in"
        >
          <ArrowDown className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
