import { useRef, useEffect } from 'react';
import { Trash2, Pencil, MoreHorizontal } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { Chat } from '@/stores/chatStore';

interface ChatItemProps {
  chat: Chat;
  isActive: boolean;
  isEditing: boolean;
  isStreaming: boolean;
  editingTitle: string;
  onSelect: () => void;
  onStartEditing: () => void;
  onDeleteRequest: () => void;
  onTitleChange: (title: string) => void;
  onSaveTitle: () => void;
  onCancelEditing: () => void;
}

/**
 * ChatItem - A single chat row in the sidebar
 *
 * Layout structure:
 * [Title container (flex-1)] [Menu button (fixed 28px)]
 *
 * The title uses a CSS mask gradient to fade out text instead of ellipsis truncation.
 * Menu button is always visible on active chat, hover-visible on others.
 */
export function ChatItem({
  chat,
  isActive,
  isEditing,
  isStreaming,
  editingTitle,
  onSelect,
  onStartEditing,
  onDeleteRequest,
  onTitleChange,
  onSaveTitle,
  onCancelEditing,
}: ChatItemProps) {
  const editInputRef = useRef<HTMLInputElement>(null);

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [isEditing]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSaveTitle();
    } else if (e.key === 'Escape') {
      onCancelEditing();
    }
  };

  return (
    <div
      className={cn(
        'group relative flex items-center py-2.5 px-3 rounded-lg transition-colors overflow-hidden',
        isActive ? 'bg-sidebar-active' : 'hover:bg-sidebar-hover',
        // Disable interaction during streaming (except current chat for viewing)
        isStreaming && !isActive ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
      )}
      onClick={onSelect}
    >
      {/* Title container - takes remaining space minus menu button width */}
      <div className="flex-1 min-w-0 max-w-[calc(100%-var(--sidebar-menu-btn-size))] overflow-hidden">
        {isEditing ? (
          <input
            ref={editInputRef}
            type="text"
            value={editingTitle}
            onChange={(e) => onTitleChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={onSaveTitle}
            onClick={(e) => e.stopPropagation()}
            className="w-full text-sm bg-background border border-input rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-ring"
          />
        ) : (
          <p className="text-sm text-sidebar-foreground whitespace-nowrap overflow-hidden text-fade-right">
            {chat.title}
          </p>
        )}
      </div>

      {/* Menu button - fixed size, visibility based on active/hover state */}
      {!isEditing && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              disabled={isStreaming}
              className={cn(
                'sidebar-menu-btn',
                'text-muted-foreground hover:text-foreground hover:bg-sidebar-hover',
                'transition-opacity focus:outline-none',
                // Always visible on active chat, hover-visible on others
                isActive
                  ? 'opacity-100'
                  : 'opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100',
                isStreaming && 'opacity-50 cursor-not-allowed'
              )}
              onClick={(e) => e.stopPropagation()}
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" side="bottom" className="w-40">
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onStartEditing();
              }}
              className="cursor-pointer"
            >
              <Pencil className="h-4 w-4 mr-2" />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onDeleteRequest();
              }}
              className="cursor-pointer text-destructive focus:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
