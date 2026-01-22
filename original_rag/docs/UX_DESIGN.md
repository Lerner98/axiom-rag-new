# RAG Chat UX Design Document

> Design decisions, patterns, and rationale for the RAG Chat frontend user experience.

---

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Layout System](#layout-system)
3. [Sidebar Design](#sidebar-design)
4. [Chat Experience](#chat-experience)
5. [Response Transparency](#response-transparency)
6. [Loading & Progress States](#loading--progress-states)
7. [Micro-interactions](#micro-interactions)

---

## Design Philosophy

### Core Principles

1. **Clarity over decoration** - Every UI element must serve a purpose
2. **Reduce cognitive load** - Users should never wonder "what's happening?"
3. **Trust through transparency** - Show users how the RAG system works
4. **Respect user attention** - Only show information when relevant

### Inspiration

- Claude Web Interface (sidebar, chat layout, subtle metadata)
- ChatGPT (streaming experience, input patterns)
- Linear (clean, professional design system)

---

## Layout System

### Three-Panel Architecture

```
┌─────────────┬──────────────────────────────┬─────────────┐
│   Sidebar   │         Chat Area            │  Document   │
│   (Left)    │         (Center)             │   Panel     │
│  ~260px     │      Flexible width          │  (Right)    │
│             │      max-w-chat centered     │  ~320px     │
│  Collapsible│                              │  Collapsible│
└─────────────┴──────────────────────────────┴─────────────┘
```

### Responsive Behavior

| Breakpoint | Sidebar | Document Panel |
|------------|---------|----------------|
| Mobile (<1024px) | Overlay with backdrop | Overlay with backdrop |
| Desktop (≥1024px) | In-flow, pushes content | In-flow, pushes content |

### Key Decision: Relative vs Fixed Positioning

**Problem:** Fixed sidebar caused content to be squashed, not centered.

**Solution:** Desktop sidebar uses `lg:relative` positioning so it participates in flexbox layout. Content naturally centers in remaining space.

```tsx
// Sidebar positioning
className={cn(
  'fixed z-50 lg:relative lg:z-auto',  // Fixed on mobile, in-flow on desktop
  sidebarOpen
    ? 'translate-x-0'
    : '-translate-x-full lg:w-0 lg:translate-x-0 lg:border-0'
)}
```

---

## Sidebar Design

### Chat List Items

**Before:** Icon + Title + Two action buttons (edit, delete)
**After:** Title only + Single "..." dropdown menu

**Rationale:**
- Icons add visual noise without information
- Two buttons clutter the hover state
- Dropdown consolidates actions, matches Claude's pattern

### Text Truncation

**Problem:** Long chat titles overflowed their container.

**Solution:** Proper flex constraints with `min-w-0` on flex children.

```tsx
<div className="flex-1 min-w-0 pr-2">
  <p className="text-sm truncate">{chat.title}</p>
</div>
```

**Key insight:** `truncate` alone doesn't work in flex containers. The parent needs `min-w-0` to allow shrinking below content size.

### Dropdown Menu Behavior

- Appears on hover (opacity transition)
- Stays visible when open via `data-[state=open]:opacity-100`
- No persistent focus ring (removed with `focus:outline-none`)

---

## Chat Experience

### Message Bubbles

| Element | User Message | Assistant Message |
|---------|--------------|-------------------|
| Alignment | Right | Left |
| Background | Primary color | Muted/card background |
| Border radius | Rounded, except bottom-right | Rounded, except bottom-left |
| Max width | 70% | 70% |

### Input Area

- Auto-resizing textarea (min 48px, max 200px)
- Scrollbar hidden by default, appears on hover (`scrollbar-auto` utility)
- Send button positioned absolutely inside input
- Disabled state during streaming

### Streaming Behavior

When assistant is responding:
1. Input is disabled
2. Chat switching is disabled
3. New chat creation is disabled
4. Sidebar actions are disabled

---

## Response Transparency

### Grounded/Verified Indicator

**Purpose:** Show users whether the response is backed by retrieved documents.

| State | Icon | Color | Meaning |
|-------|------|-------|---------|
| Verified | ShieldCheck | Green | Response grounded in document sources |
| Unverified | ShieldAlert | Amber | Response may include external knowledge |

**Display:** Always visible on assistant messages (when `wasGrounded` is defined).

**Tooltip:** Explains what verified/unverified means on hover.

### Processing Time Display

**When shown:** Only for responses taking >30 seconds (complex queries).

**Behavior:**
1. Appears after response completes
2. Shows for 8 seconds
3. Fades out automatically

**Rationale:**
- Quick responses don't need timing feedback
- Permanent display adds clutter
- Brief display acknowledges the wait without being intrusive

```tsx
const PROCESSING_TIME_THRESHOLD_MS = 30000;  // 30 seconds
const PROCESSING_TIME_DISPLAY_DURATION_MS = 8000;  // 8 seconds visibility
```

### Source Citations

- Displayed as inline pills/badges
- Click to expand popover with:
  - Document name
  - Page number (if applicable)
  - Relevance score (visual bar)
  - Content preview

---

## Loading & Progress States

### Streaming Phases

During the RAG pipeline wait (can be 20+ seconds), users see progress through phases:

```
┌────────────────────────────────────┐
│ ○ Searching documents...           │  ← Active (pulsing icon)
│ ○ Found 3 sources                  │  ← Pending (faded)
│ ○ Generating response...           │  ← Pending (faded)
└────────────────────────────────────┘
```

**Phase transitions:**
1. `searching` → Set on `startStreaming()`
2. `found_sources` → Set when `onSources` callback fires
3. `generating` → Set on first token received

**Visual states:**
- Active phase: Primary color, pulsing icon
- Complete phase: Green dot, muted text
- Pending phase: Gray dot, faded text

### Why Not Simple Loading Dots?

**Problem:** Bouncing dots for 22 seconds feels broken.

**Solution:** Phase indicators show the system is working and progressing through stages. Users understand the wait has purpose.

---

## Micro-interactions

### Copy Button

- Hidden by default on assistant messages
- Appears on hover (top-right corner)
- Shows checkmark for 2 seconds after copying

### Scroll to Bottom

- Floating button appears when user scrolls up
- Smooth scroll animation on click
- Auto-scroll on new messages (unless user has scrolled up)

### Theme Toggle

- Sun/Moon icon in header
- Toggles `dark` class on document root
- Persists via CSS (not stored in state)

---

## Future Considerations

### Potential Improvements

1. **Keyboard navigation** - Arrow keys for chat selection
2. **Search** - Filter chats by title/content
3. **Drag-and-drop** - Reorder chats or upload files
4. **Voice input** - Microphone button for dictation
5. **Code syntax highlighting** - For code blocks in responses
6. **Markdown rendering** - Full markdown support in messages

### Accessibility

Current status:
- ✅ Keyboard-accessible buttons
- ✅ Focus management on modals
- ⚠️ Screen reader labels need review
- ⚠️ Color contrast in some states

---

## Implementation Files

| Feature | File(s) |
|---------|---------|
| Sidebar layout | `components/chat/Sidebar.tsx` |
| Chat area layout | `components/chat/ChatArea.tsx` |
| Message display | `components/chat/MessageBubble.tsx` |
| Message list | `components/chat/MessageList.tsx` |
| Input area | `components/chat/MessageInput.tsx` |
| State management | `stores/chatStore.ts` |
| Streaming hook | `hooks/useChat.ts` |
| Custom scrollbar | `index.css` (`.scrollbar-auto`) |

---

*Last updated: December 2024*
