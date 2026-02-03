import { useEffect, useRef } from "react";
import { MessageBubble } from "./message-bubble";
import { StreamingMessage } from "./streaming-message";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrieved_docs?: RetrievedDoc[];
  created_at?: string;
}

export interface RetrievedDoc {
  index?: number;
  title: string;
  link: string;
  text: string;
  meta?: string;
  rrf_score?: number;
  sim_score?: number;
}

interface ChatMessagesProps {
  messages: Message[];
  streamingContent?: string;
  streamingDocs?: RetrievedDoc[];
  isStreaming?: boolean;
}

export function ChatMessages({
  messages,
  streamingContent,
  streamingDocs,
  isStreaming,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        {messages.length === 0 && !isStreaming && (
          <div className="flex flex-col items-center justify-center pt-20 text-center">
            <div className="rounded-full bg-primary/10 p-4 mb-4">
              <svg
                className="h-8 w-8 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold">무엇이든 물어보세요</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              질문을 입력하면 관련 문서를 검색하여 답변해 드립니다
            </p>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isStreaming && (
          <StreamingMessage
            content={streamingContent || ""}
            docs={streamingDocs}
          />
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
