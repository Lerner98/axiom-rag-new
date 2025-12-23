import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import type { Message, Source } from '@/stores/chatStore';

interface MessageBubbleProps {
  message: Message;
}

function SourceCitation({ source }: { source: Source }) {
  // Use filename, fall back to content_preview snippet, or chunk_id as last resort
  const displayName = source.filename && source.filename !== 'unknown' 
    ? source.filename 
    : source.content_preview 
      ? source.content_preview.slice(0, 20) + '...'
      : `Source ${source.chunk_id || source.id}`;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-citation text-citation-foreground hover:bg-citation-hover transition-colors">
          {displayName}
          {source.page && ` p.${source.page}`}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-4" align="start">
        <div className="space-y-3">
          <div>
            <h4 className="font-medium text-sm">{displayName}</h4>
            {source.page && (
              <p className="text-xs text-muted-foreground">Page {source.page}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full"
                style={{ width: `${source.relevance || source.relevance_score || 0}%` }}
              />
            </div>
            <span className="text-xs font-medium text-muted-foreground">
              {Math.round(source.relevance || source.relevance_score || 0)}% relevant
            </span>
          </div>
          <p className="text-sm text-muted-foreground line-clamp-4">
            {source.preview || source.content_preview || 'No preview available'}
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-4 py-3">
      <div className="typing-dot" />
      <div className="typing-dot" />
      <div className="typing-dot" />
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (message.isStreaming && !message.content) {
    return (
      <div className="flex justify-start animate-fade-in">
        <div className="max-w-[70%] rounded-2xl rounded-bl-md bg-assistant-bubble border border-assistant-bubble-border">
          <TypingIndicator />
          <p className="px-4 pb-3 text-xs text-muted-foreground">
            Searching documents...
          </p>
        </div>
      </div>
    );
  }

  // Filter sources: only show if they have valid data (not "unknown" filename or have content)
  const validSources = (message.sources || []).filter(source => 
    (source.filename && source.filename !== 'unknown') || 
    source.content_preview || 
    source.preview
  );

  return (
    <div
      className={cn(
        'flex animate-fade-in',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={cn(
          'group relative max-w-[70%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-user-bubble text-user-bubble-foreground rounded-br-md'
            : 'bg-assistant-bubble text-assistant-bubble-foreground border border-assistant-bubble-border rounded-bl-md'
        )}
      >
        {/* Copy button for assistant messages */}
        {!isUser && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute -top-2 -right-2 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity bg-card border shadow-sm"
            onClick={copyToClipboard}
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-500" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
        )}

        {/* Message content */}
        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
          {message.isStreaming && (
            <span className="inline-block w-0.5 h-4 bg-current ml-0.5 animate-pulse" />
          )}
        </div>

        {/* Source citations - ONLY show if there are valid sources */}
        {validSources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-assistant-bubble-border/50">
            <p className="text-xs text-muted-foreground mb-2">Sources:</p>
            <div className="flex flex-wrap gap-1.5">
              {validSources.map((source) => (
                <SourceCitation key={source.id || source.chunk_id} source={source} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
