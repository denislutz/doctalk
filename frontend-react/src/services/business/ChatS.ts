import { useCallback, useEffect, useRef, useState } from 'react';

import type { ChatMessage, Message, SourceChunk } from '@/types/api';
import HttpS from '@/services/tech/HttpS';
import I18nS from '@/services/tech/I18nS';

// ============================================================================
// Private — wire-event interpretation (business knowledge of backend shapes)
// ============================================================================

const toConversation = (messages: Message[]): ChatMessage[] =>
  messages.map(m => ({ role: m.role, content: m.content }));

type StreamEvent =
  | { kind: 'sources'; sources: SourceChunk[] }
  | { kind: 'token'; token: string };

const parseEvent = (data: string): StreamEvent => {
  try {
    const parsed = JSON.parse(data) as { sources: SourceChunk[] };
    return { kind: 'sources', sources: parsed.sources };
  } catch {
    return { kind: 'token', token: data };
  }
};

// ============================================================================
// Public service API
// ============================================================================

export interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  send: (question: string) => void;
}

const useChat = (selected: string): ChatState => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(
    (question: string) => {
      if (!question || !selected || isStreaming) return;

      const assistantId = crypto.randomUUID();
      setMessages(prev => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', content: question },
        { id: assistantId, role: 'assistant', content: '', streaming: true },
      ]);
      setIsStreaming(true);

      const conversation = toConversation(messages);

      abortRef.current = HttpS.stream(
        '/query/stream',
        { question, topics: [selected], history: conversation },
        {
          onData: data => {
            const event = parseEvent(data);
            setMessages(prev =>
              prev.map(m => {
                if (m.id !== assistantId) return m;
                return event.kind === 'sources'
                  ? { ...m, sources: event.sources }
                  : { ...m, content: m.content + event.token };
              }),
            );
          },
          onDone: () => {
            setMessages(prev =>
              prev.map(m => (m.id === assistantId ? { ...m, streaming: false } : m)),
            );
            setIsStreaming(false);
          },
          onError: error => {
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: I18nS.t('error_prefix', { message: error.message }), streaming: false }
                  : m,
              ),
            );
            setIsStreaming(false);
          },
        },
      );
    },
    [messages, selected, isStreaming],
  );

  return { messages, isStreaming, send };
};

const ChatS = { useChat };
export default ChatS;
