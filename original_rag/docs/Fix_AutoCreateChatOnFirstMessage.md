# Fix: Auto-Create Chat on First Message

**Date:** 13-12-2025
**Status:** FIXED
**File Changed:** `frontend/src/hooks/useChat.ts`

---

## Problem

When a user opens the app fresh with **zero chats** and starts typing a message directly (without clicking "New Chat" in the sidebar), **nothing happens**:
- No message appears
- No chat is created
- No response from the backend
- The user sees no feedback

**Expected behavior:** The system should auto-create a new chat when the user sends their first message, then proceed normally.

---

## Root Cause

In `useChat.ts`, the `sendMessage` function had an early exit condition:

```typescript
const sendMessage = useCallback(
  async (content: string) => {
    if (!content.trim() || isStreaming || !currentChatId) return;  // <-- BUG HERE

    addUserMessage(content);  // Never reached when currentChatId is null
    // ...
  }
);
```

The condition `!currentChatId` caused the function to exit immediately when no chat was selected, **before** `addUserMessage()` was called.

**Irony:** The store's `addUserMessage()` function already had auto-create logic built in (lines 133-159 of `chatStore.ts`), but it was never reached because of the early exit.

---

## The Fix

Reordered the logic in `sendMessage`:

1. Remove `!currentChatId` from the early exit condition
2. Call `addUserMessage()` first (which auto-creates a chat if none exists)
3. Get the fresh `currentChatId` from the store after the auto-create
4. Derive the collection name from the new chat ID
5. Proceed with streaming

### Before (Broken)

```typescript
const sendMessage = useCallback(
  async (content: string) => {
    if (!content.trim() || isStreaming || !currentChatId) return;  // Early exit!

    addUserMessage(content);  // Never called if no chat
    startStreaming();

    await streamChat(content, sessionId, collectionName || undefined, {...});
  },
  [sessionId, isStreaming, collectionName, addUserMessage, ...]
);
```

### After (Fixed)

```typescript
const sendMessage = useCallback(
  async (content: string) => {
    if (!content.trim() || isStreaming) return;  // No currentChatId check

    // Add user message to state (this auto-creates a chat if none exists)
    addUserMessage(content);

    // Get the current chat ID after addUserMessage (may have just been created)
    const chatId = useChatStore.getState().currentChatId;
    if (!chatId) {
      setError('Failed to create chat');
      return;
    }

    // Derive collection name from the (possibly new) chat ID
    const collection = `chat_${chatId}`;

    startStreaming();

    await streamChat(content, sessionId, collection, {...});
  },
  [sessionId, isStreaming, addUserMessage, ...]  // Removed collectionName dependency
);
```

---

## Flow Comparison

### Before (Broken Flow)

```
User types message (no chat selected)
    ↓
sendMessage() called
    ↓
if (!currentChatId) return  ← STOPS HERE
    ↓
Nothing happens
```

### After (Fixed Flow)

```
User types message (no chat selected)
    ↓
sendMessage() called
    ↓
addUserMessage(content)
    ↓
Store detects currentChatId is null
    ↓
Store creates new chat with message, sets currentChatId
    ↓
useChatStore.getState().currentChatId returns new ID
    ↓
collection = "chat_{newId}"
    ↓
streamChat() sends to backend
    ↓
User sees response
```

---

## Key Changes

| Aspect | Before | After |
|--------|--------|-------|
| Early exit condition | `!currentChatId` blocked everything | Removed from condition |
| `addUserMessage()` timing | Never called if no chat | Called first, triggers auto-create |
| Chat ID retrieval | Used stale `currentChatId` from closure | Fresh `getState().currentChatId` |
| Collection name | Used stale `collectionName` | Derived fresh from new chat ID |
| Dependency array | Included `collectionName` | Removed (no longer needed) |

---

## Verification

```bash
# Build frontend (no errors)
cd frontend && npm run build

# Output: ✓ built in 2.66s
```

### Manual Test Steps

1. Clear browser localStorage: `localStorage.clear()`
2. Refresh the page
3. Type a message in the input (without clicking "New Chat")
4. Press Enter/Send
5. **Expected:** Chat is created, message appears, backend responds

---

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `frontend/src/hooks/useChat.ts` | 37-86 | Reordered sendMessage logic |

---

## Related

- **Store auto-create logic:** `frontend/src/stores/chatStore.ts` lines 133-159
- **ADR-007:** Chat-scoped collections (`chat_{chatId}`)
