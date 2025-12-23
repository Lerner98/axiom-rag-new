import { useEffect, useRef, useState } from 'react';
import { MessageSquare, ArrowDown, Upload, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MessageBubble } from './MessageBubble';
import { useChatStore, Message } from '@/stores/chatStore';

export function MessageList() {
  const {
    chats,
    currentChatId,
    setDocumentPanelOpen,
    isStreaming,
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
          {/* Show streaming message */}
          {streamingMessage && (
            <MessageBubble key="streaming" message={streamingMessage} />
          )}
          {/* Show loading indicator when streaming starts but no content yet */}
          {isStreaming && !currentStreamingMessage && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce" />
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce delay-75" />
              <div className="w-2 h-2 bg-primary rounded-full animate-bounce delay-150" />
            </div>
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
