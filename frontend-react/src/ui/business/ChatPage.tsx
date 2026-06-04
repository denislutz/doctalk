import ChatWindow from '@/ui/business/ChatWindow';
import { useCollectionsState } from './CollectionsProvider';

const ChatPage = () => {
  const { selected } = useCollectionsState();
  return (
    <div className="h-full flex flex-col">
      <ChatWindow selected={selected} />
    </div>
  );
};

export default ChatPage;
