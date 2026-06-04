import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUp, Plus } from 'lucide-react';

import { Button } from '@/ui/base/button';
import { TextArea } from '@/ui/base/textarea';
import ChatS from '@/services/business/ChatS';
import I18nS from '@/services/tech/I18nS';
import MessageBubble from './MessageBubble';

interface Props {
  selected: string;
}

const ChatWindow = ({ selected }: Props) => {
  const { messages, isStreaming, send } = ChatS.useChat(selected);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => setInput(e.target.value),
    [],
  );

  const onSubmit = useCallback(() => {
    const question = input.trim();
    if (!question) return;
    send(question);
    setInput('');
  }, [input, send]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        onSubmit();
      }
    },
    [onSubmit],
  );

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0 py-6">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-muted-foreground text-sm">
              {I18nS.t(selected ? 'chat_empty_ready' : 'chat_empty_no_collection')}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-6 max-w-2xl mx-auto px-4 w-full">
            {messages.map(m => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        )}
      </div>

      <div className="px-4 pb-5 shrink-0">
        <div className="max-w-2xl mx-auto rounded-2xl border border-border bg-card shadow-sm">
          <TextArea
            value={input}
            onChange={onInputChange}
            onKeyDown={onKeyDown}
            placeholder={I18nS.t(selected ? 'chat_input_placeholder' : 'chat_input_disabled')}
            disabled={!selected || isStreaming}
            rows={1}
            className="px-4 pt-3 pb-1 min-h-[44px]"
          />
          <div className="flex items-center gap-2 px-3 py-2">
            <Button variant="ghost" size="icon-sm" disabled>
              <Plus />
            </Button>
            <span className="flex-1" />
            {selected && (
              <span className="text-xs text-muted-foreground truncate max-w-[140px]">{selected}</span>
            )}
            <Button
              size="icon-sm"
              className="rounded-full"
              onClick={onSubmit}
              disabled={!selected || !input.trim() || isStreaming}
            >
              <ArrowUp />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;
