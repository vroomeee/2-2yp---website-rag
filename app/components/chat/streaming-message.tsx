import { Bot } from "lucide-react";
import { RetrievedDocs } from "./retrieved-docs";
import type { RetrievedDoc } from "./chat-messages";

interface StreamingMessageProps {
  content: string;
  docs?: RetrievedDoc[];
}

export function StreamingMessage({ content, docs }: StreamingMessageProps) {
  return (
    <div className="flex gap-3">
      {/* Avatar */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Bot className="h-4 w-4" />
      </div>

      {/* Content */}
      <div className="flex flex-col gap-2 items-start max-w-[85%] md:max-w-[75%]">
        <div className="rounded-2xl bg-muted px-4 py-2.5 text-sm leading-relaxed text-foreground">
          <div className="whitespace-pre-wrap break-words">
            {content}
            <span className="inline-block w-1.5 h-4 ml-0.5 bg-foreground animate-pulse align-text-bottom" />
          </div>
        </div>

        {docs && docs.length > 0 && <RetrievedDocs docs={docs} />}
      </div>
    </div>
  );
}
