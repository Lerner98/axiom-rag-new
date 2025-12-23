import { Menu, Sun, Moon, FileText, PanelRightOpen, PanelRightClose } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useChatStore } from '@/stores/chatStore';
import { useEffect, useState } from 'react';

export function ChatArea() {
  const {
    setSidebarOpen,
    sidebarOpen,
    chats,
    currentChatId,
    documentPanelOpen,
    setDocumentPanelOpen,
    getCurrentChatDocumentCount,
  } = useChatStore();

  const currentChat = chats.find((c) => c.id === currentChatId);
  const documentCount = getCurrentChatDocumentCount();
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const isDarkMode = document.documentElement.classList.contains('dark');
    setIsDark(isDarkMode);
  }, []);

  const toggleTheme = () => {
    const newIsDark = !isDark;
    setIsDark(newIsDark);
    document.documentElement.classList.toggle('dark', newIsDark);
  };

  return (
    <div className="flex-1 flex flex-col h-full min-w-0">
      {/* Header Bar */}
      <header className="h-14 border-b border-border bg-card flex items-center px-4 gap-4 shrink-0">
        {/* Hamburger menu - always visible when sidebar is closed */}
        {!sidebarOpen && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(true)}
            className="h-9 w-9 shrink-0"
          >
            <Menu className="h-5 w-5" />
          </Button>
        )}

        {/* Title - current chat name */}
        <div className="flex-1 min-w-0">
          <h1 className="font-medium text-foreground truncate">
            {currentChat ? currentChat.title : 'New Chat'}
          </h1>
        </div>

        {/* Document panel toggle - only show when there's a current chat */}
        {currentChatId && (
          <Button
            variant={documentPanelOpen ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setDocumentPanelOpen(!documentPanelOpen)}
            className="gap-2 shrink-0"
          >
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">Documents</span>
            {documentCount > 0 && (
              <Badge variant="secondary" className="h-5 px-1.5 text-xs">
                {documentCount}
              </Badge>
            )}
            {documentPanelOpen ? (
              <PanelRightClose className="h-4 w-4 hidden sm:block" />
            ) : (
              <PanelRightOpen className="h-4 w-4 hidden sm:block" />
            )}
          </Button>
        )}

        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className="h-9 w-9 shrink-0"
        >
          {isDark ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>
      </header>

      {/* Messages */}
      <MessageList />

      {/* Input */}
      <MessageInput />
    </div>
  );
}
