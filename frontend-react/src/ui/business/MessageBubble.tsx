import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import SourceCard from './SourceCard';
import type { Message } from '@/types/api';

interface Props {
  message: Message;
}

const assistantComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  h1: ({ children }) => <h1 className="text-lg font-semibold mt-4 mb-2 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-base font-semibold mt-4 mb-2 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold mt-3 mb-1.5 first:mt-0">{children}</h3>,
  ul: ({ children }) => <ul className="mb-3 space-y-1 pl-4 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 space-y-1 pl-4 list-decimal last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed list-disc">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  code: ({ children, className }) => {
    const isBlock = className?.startsWith('language-');
    return isBlock ? (
      <code className="block bg-muted rounded-lg px-3 py-2 text-xs font-mono overflow-x-auto mb-3 last:mb-0">
        {children}
      </code>
    ) : (
      <code className="bg-muted rounded px-1 py-0.5 text-xs font-mono">{children}</code>
    );
  },
  pre: ({ children }) => <pre className="mb-3 last:mb-0">{children}</pre>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-border pl-3 text-muted-foreground mb-3 last:mb-0">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:opacity-70">
      {children}
    </a>
  ),
  hr: () => <hr className="border-border my-3" />,
};

const MessageBubble = ({ message }: Props) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex flex-col gap-3 ${isUser ? 'items-end' : 'items-start'}`}>
      {isUser ? (
        <div className="max-w-[80%] rounded-2xl px-4 py-2.5 text-sm bg-primary text-primary-foreground">
          {message.content}
        </div>
      ) : (
        <div className="text-sm leading-relaxed text-foreground w-full">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={assistantComponents}>
            {message.content}
          </ReactMarkdown>
          {message.streaming && (
            <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-current animate-pulse align-text-bottom" />
          )}
        </div>
      )}
      {!isUser && message.sources && message.sources.length > 0 && (
        <div className="grid grid-cols-1 gap-2 w-full sm:grid-cols-2">
          {message.sources.map((src, i) => (
            <SourceCard key={`${src.source_name}-${i.toString()}`} source={src} />
          ))}
        </div>
      )}
    </div>
  );
};

export default MessageBubble;
