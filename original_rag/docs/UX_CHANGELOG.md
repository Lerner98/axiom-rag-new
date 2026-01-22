# UX Changelog

> Chronological record of UX/UI changes and improvements.

---

## December 2024

### Phase 3: TRUE STREAMING (V6)

#### Problem Identified
- Backend was using "fake streaming" - entire pipeline ran synchronously, then answer was split into words and "streamed"
- Sources were sent AFTER the answer, not before generation
- Frontend showed "Searching documents..." indefinitely because no SSE events came until the end
- 90+ second waits with no feedback

#### Solution: Complete Streaming Rewrite

**Backend Changes:**
- **`pipeline.py`**: Complete rewrite of `astream()` method
  - Now manually orchestrates pipeline steps instead of using `graph.ainvoke()`
  - Emits `phase` events in real-time: `searching` → `generating`
  - Emits `sources` BEFORE generation starts (user sees what was found)
  - Uses `self.llm.astream()` for TRUE token-by-token streaming
  - Tokens are yielded immediately as LLM generates them

- **`chat.py`**: Updated SSE handler
  - New `phase` event type for frontend progress indicator
  - Proper logging of streaming events
  - Error event propagation

**Frontend Changes:**
- **`types/index.ts`**: Added `SSEStreamingPhase` type for wire format
- **`sse.ts`**: Added `onPhase` callback, handles new event type
- **`useChat.ts`**: Wires `onPhase` to `setStreamingPhase` in store

#### Event Sequence (V6)
```
1. phase: "searching"     → Frontend shows "Searching documents..."
2. sources: [...]         → Frontend shows "Found X sources" (BEFORE generation!)
3. phase: "generating"    → Frontend shows "Generating response..."
4. token: "The"           → Tokens appear immediately as generated
5. token: " CAP"
6. token: " theorem"
7. ... (real-time)
8. done: {...}            → Stream complete with metadata
```

#### Why This Matters
- Users see immediate feedback (no more frozen UI)
- Sources shown BEFORE answer (builds trust)
- Real streaming feels fast even when total time is the same
- Progress phases reduce perceived wait time

**Files Changed:**
- `backend/rag/pipeline.py` - Complete `astream()` rewrite
- `backend/api/routes/chat.py` - Phase event handling
- `frontend/src/types/index.ts` - SSEStreamingPhase type
- `frontend/src/lib/sse.ts` - onPhase callback
- `frontend/src/hooks/useChat.ts` - Phase wiring

---

### Phase 2: Transparency & Progress UX

#### Streaming Progress Indicator
- **Added:** Three-phase progress display during RAG pipeline
  - "Searching documents..." (with pulsing search icon)
  - "Found X sources" (shows actual count)
  - "Generating response..." (when tokens start)
- **Files:** `MessageList.tsx`, `chatStore.ts`
- **Rationale:** 22-second waits feel broken with just bouncing dots. Phases show the system is working.

#### Grounded/Verified Indicator
- **Added:** Shield icon with "Verified" or "Unverified" label on responses
- **Files:** `MessageBubble.tsx`
- **Rationale:** RAG users need to know if responses are backed by documents

#### Processing Time Display
- **Added:** Clock icon with duration (e.g., "32.1s")
- **Threshold:** Only shown for responses >30 seconds
- **Behavior:** Fades after 8 seconds
- **Files:** `MessageBubble.tsx`
- **Rationale:** Quick responses don't need timing. Long responses deserve acknowledgment.

#### Store Updates
- **Added:** `StreamingPhase` type
- **Added:** `wasGrounded` and `processingTimeMs` on Message interface
- **Added:** `streamingStartTime` for client-side timing fallback
- **Files:** `chatStore.ts`, `useChat.ts`

---

### Phase 1: Layout & Sidebar Fixes

#### Issue 1: Sidebar Not Collapsible on Desktop
- **Problem:** No toggle button visible on desktop
- **Solution:** Added `PanelLeftOpen/PanelLeftClose` icons to header, always visible
- **Files:** `ChatArea.tsx`

#### Issue 2: Content Not Centered
- **Problem:** Fixed sidebar caused content to squash to right edge
- **Solution:** Changed sidebar to `lg:relative` positioning on desktop
- **Files:** `Sidebar.tsx`
- **Key insight:** Fixed positioning removes element from flow; relative keeps it in flexbox layout

#### Issue 3: Sidebar Text Overflow
- **Problem:** Long chat titles overflowed their container
- **Solution:** Added `min-w-0` to flex children, proper `truncate` class
- **Files:** `Sidebar.tsx`
- **Key insight:** `truncate` requires `min-w-0` on flex containers

#### Issue 4: Scrollbar Always Visible in Input
- **Problem:** Scrollbar visible even when not needed
- **Solution:** Created `.scrollbar-auto` utility class
- **Files:** `index.css`, `MessageInput.tsx`
- **Behavior:** Hidden by default, appears on hover/scroll

#### Sidebar Redesign (Claude-style)
- **Removed:** Chat icons from list items (pointless visual noise)
- **Replaced:** Dual edit/delete buttons with single "..." dropdown menu
- **Fixed:** Focus ring persisting after dropdown closes
- **Files:** `Sidebar.tsx`

---

## Design Decisions Log

### Why show "Unverified" instead of hiding the indicator?
Transparency is more important than clean UI. Users should know when they're getting answers that might not be from their documents.

### Why 30-second threshold for processing time?
Most quick RAG responses (5-15s) don't need timing acknowledgment. It's the long, complex queries where users appreciate knowing "that took 45 seconds to process."

### Why fade processing time after 8 seconds?
Permanent display adds clutter. The timing is a momentary acknowledgment, not permanent metadata. Claude does the same.

### Why dropdown menu instead of inline buttons?
- Cleaner hover state
- Actions are secondary to selection
- Matches Claude's pattern
- Single interaction point

---

*Maintained alongside code changes*
