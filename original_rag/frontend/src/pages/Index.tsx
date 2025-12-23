import { Sidebar } from '@/components/chat/Sidebar';
import { ChatArea } from '@/components/chat/ChatArea';
import { DocumentPanel } from '@/components/chat/DocumentPanel';
import { SettingsModal } from '@/components/chat/SettingsModal';
import { useChatStore } from '@/stores/chatStore';

const Index = () => {
  const { currentChatId, chats } = useChatStore();
  const currentChat = chats.find((c) => c.id === currentChatId);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Sidebar />
      <ChatArea />
      {currentChatId && currentChat && (
        <DocumentPanel chatId={currentChatId} chatTitle={currentChat.title} />
      )}
      <SettingsModal />
    </div>
  );
};

export default Index;
