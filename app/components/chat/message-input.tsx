import { useState, useRef, useEffect } from "react";
import { Button } from "~/components/ui/button";
import { SendHorizontal } from "lucide-react";

interface MessageInputProps {
  onSend: (message: string, options?: { relaxContext?: boolean }) => void;
  disabled?: boolean;
  relaxContext?: boolean;
  onRelaxChange?: (value: boolean) => void;
}

export function MessageInput({
  onSend,
  disabled,
  relaxContext = false,
  onRelaxChange,
}: MessageInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [value]);

  function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, { relaxContext });
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="border-t border-border bg-background px-4 py-3">
      <form
        onSubmit={handleSubmit}
        className="mx-auto flex max-w-3xl items-end gap-2"
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="질문을 입력하세요..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-input bg-background px-4 py-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        />
        <Button
          type="submit"
          size="icon"
          disabled={disabled || !value.trim()}
          className="h-11 w-11 shrink-0 rounded-xl"
        >
          <SendHorizontal className="h-4 w-4" />
        </Button>
      </form>
      <div className="mx-auto mt-2 flex max-w-3xl items-center gap-2 text-xs text-muted-foreground">
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={relaxContext}
            onChange={(e) => onRelaxChange?.(e.target.checked)}
            disabled={disabled}
          />
          문맥 완화(추정 허용)
        </label>
      </div>
    </div>
  );
}
