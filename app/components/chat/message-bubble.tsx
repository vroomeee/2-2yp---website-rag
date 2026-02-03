import { cn } from "~/lib/utils";
import { RetrievedDocs } from "./retrieved-docs";
import type { Message } from "./chat-messages";
import { User, Bot } from "lucide-react";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className={cn("flex flex-col gap-2", isUser ? "items-end" : "items-start", "max-w-[85%] md:max-w-[75%]")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-foreground"
          )}
        >
          <div className="whitespace-pre-wrap break-words">{message.content}</div>
        </div>

        {/* Retrieved docs for assistant messages */}
        {!isUser &&
          message.retrieved_docs &&
          message.retrieved_docs.length > 0 && (
            <RetrievedDocs docs={message.retrieved_docs} />
          )}
      </div>
    </div>
  );
}
