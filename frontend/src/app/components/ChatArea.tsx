import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  attachments?: string[];
  reasoning?: string;   // testo di ragionamento accumulato
  isThinking?: boolean; // true finché non arriva la risposta finale
}

interface ChatAreaProps {
  messages: Message[];
  onSuggestionClick?: (suggestion: string) => void;
}

function ThinkingBox({ reasoning }: { reasoning: string }) {
  return (
    <div className="flex justify-start mb-1">
      <div className="flex items-start gap-2 max-w-[80%] bg-gray-100 border border-gray-200 rounded-xl px-3 py-2">
        <span className="mt-0.5 shrink-0 w-2 h-2 rounded-full bg-gray-400 animate-pulse" />
        <div className="text-xs text-gray-500 italic leading-snug line-clamp-2 overflow-hidden">
          {reasoning ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{reasoning}</ReactMarkdown>
          ) : (
            'Thinking…'
          )}
        </div>
      </div>
    </div>
  );
}

export function ChatArea({ messages, onSuggestionClick }: ChatAreaProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto px-4 py-8 flex items-center justify-center">
        <div className="max-w-5xl mx-auto text-center">
          <h1 className="text-4xl font-bold text-gray-800">PunkAgent</h1>
          <p className="mt-3 text-sm text-gray-500">
            Il tuo assistente personale per la gestione finanziaria
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-8">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-8 pb-4 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-800">PunkAgent</h2>
        </div>

        <div className="space-y-6">
          {messages.map((message) => (
            <div key={message.id}>
              {/* Riquadro reasoning — visibile solo mentre isThinking è true */}
              {message.role === 'assistant' && message.isThinking && (
                <ThinkingBox reasoning={message.reasoning ?? ''} />
              )}

              {/* Bolla messaggio — per assistant appare solo quando c'è contenuto */}
              {(message.role === 'user' || message.content) && (
                <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-gray-700 text-white'
                        : 'bg-gray-200 text-gray-800'
                    }`}
                  >
                    <div className={`text-sm leading-relaxed prose prose-sm max-w-none ${message.role === 'user' ? 'prose-invert' : 'prose-gray'}`}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    </div>
                    {message.attachments && message.attachments.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {message.attachments.map((file, index) => (
                          <div key={index} className="text-xs opacity-70">
                            📎 {file}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}
