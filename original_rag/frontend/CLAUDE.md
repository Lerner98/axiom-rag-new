# CLAUDE.md - Frontend (React + TypeScript + Vite)

## Architecture

```
frontend/src/
├── components/
│   ├── chat/         # Chat-specific components
│   │   ├── ChatArea.tsx      # Main chat container
│   │   ├── MessageList.tsx   # Message rendering
│   │   ├── MessageBubble.tsx # Individual message
│   │   ├── MessageInput.tsx  # Input with shortcuts
│   │   ├── Sidebar.tsx       # Chat list, navigation
│   │   ├── DocumentPanel.tsx # Document management
│   │   └── *Modal.tsx        # Upload, settings, etc.
│   └── ui/           # shadcn/ui components
├── stores/
│   └── chatStore.ts  # Zustand state management
├── pages/
│   └── Index.tsx     # Main chat page
├── hooks/            # Custom React hooks
└── lib/              # Utilities
```

## State Management (Zustand)

```typescript
// stores/chatStore.ts - Single source of truth
interface ChatStore {
  // Session
  sessionId: string;

  // Streaming state
  isStreaming: boolean;
  streamingPhase: 'idle' | 'searching' | 'found_sources' | 'generating' | 'complete';
  currentStreamingMessage: string;
  currentSources: Source[];

  // Chats (ADR-007: Documents belong to chats)
  chats: Chat[];
  currentChatId: string | null;
}

// Always use store actions, never mutate directly
const { addUserMessage, startStreaming, appendStreamToken } = useChatStore();
```

## SSE Streaming Pattern

```typescript
// Consume backend SSE stream
const eventSource = new EventSource(`/api/chat/stream?...`);

eventSource.addEventListener('phase', (e) => {
  const { phase } = JSON.parse(e.data);
  setStreamingPhase(phase); // 'searching' | 'generating'
});

eventSource.addEventListener('sources', (e) => {
  const sources = JSON.parse(e.data);
  setSources(sources);
});

eventSource.addEventListener('token', (e) => {
  const { token } = JSON.parse(e.data);
  appendStreamToken(token); // Real-time token append
});

eventSource.addEventListener('done', (e) => {
  const metadata = JSON.parse(e.data);
  finishStreaming(metadata.wasGrounded, metadata.processingTimeMs);
});
```

## Component Patterns

### Message Bubbles
```typescript
// Role-based styling
<div className={cn(
  "rounded-lg p-3",
  message.role === 'user' ? "bg-primary text-primary-foreground ml-auto" : "bg-muted"
)}>
```

### Streaming Indicator
```typescript
// Show phase-based loading state
{isStreaming && (
  <div className="flex items-center gap-2">
    {streamingPhase === 'searching' && <Loader2 className="animate-spin" />}
    {streamingPhase === 'generating' && <span className="animate-pulse">●</span>}
  </div>
)}
```

### Document Panel (ADR-007)
```typescript
// Documents scoped to current chat
const documents = getCurrentChatDocuments();
// Upload adds to current chat's collection
addDocumentToChat(currentChatId, doc);
```

## Critical Rules

1. **Zustand for state** - No prop drilling, use store hooks
2. **Chat-scoped documents** - Documents belong to chats, not global (ADR-007)
3. **SSE for streaming** - EventSource, not WebSocket
4. **shadcn/ui components** - Use existing components from `components/ui/`
5. **Tailwind only** - No custom CSS files, use utility classes

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Ctrl+U` | Upload document |

## Key Files

| File | Purpose |
|------|---------|
| `stores/chatStore.ts` | All state management, streaming logic |
| `components/chat/ChatArea.tsx` | Main chat orchestration |
| `components/chat/MessageInput.tsx` | Input handling, shortcuts |
| `components/chat/Sidebar.tsx` | Chat list, new chat, delete |
| `components/chat/DocumentPanel.tsx` | Document upload, list, delete |
| `pages/Index.tsx` | Page layout, panel composition |

## Adding New Features

1. **New UI component**: Add to `components/chat/`, use shadcn/ui primitives
2. **New state**: Add to `chatStore.ts` interface and implementation
3. **New modal**: Create `*Modal.tsx`, trigger from relevant component
4. **New shortcut**: Add to `MessageInput.tsx` keyboard handler

## Style Guide

```typescript
// Use cn() for conditional classes
import { cn } from "@/lib/utils";
className={cn("base-class", condition && "conditional-class")}

// Prefer composition over props
<Button variant="ghost" size="icon">
  <Icon className="h-4 w-4" />
</Button>

// Use semantic color tokens
bg-primary, bg-muted, bg-destructive
text-primary-foreground, text-muted-foreground
```

## Development

```bash
# Start dev server (port 8080)
npm run dev

# Build for production
npm run build

# Type check
npm run typecheck
```
