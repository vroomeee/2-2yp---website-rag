import { useState, useCallback, useRef } from "react";
import type { Message, RetrievedDoc } from "~/components/chat/chat-messages";
import { getSupabaseBrowserClient } from "~/lib/supabase.client";

interface UseChatStreamOptions {
  conversationId?: string;
  onConversationCreated?: (id: string) => void;
}

interface SendOptions {
  relaxContext?: boolean;
}

export function useChatStream({
  conversationId,
  onConversationCreated,
}: UseChatStreamOptions = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingDocs, setStreamingDocs] = useState<RetrievedDoc[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const convIdRef = useRef(conversationId);
  convIdRef.current = conversationId;

  const loadMessages = useCallback(async (convId: string) => {
    const supabase = getSupabaseBrowserClient();
    const { data } = await supabase
      .from("messages")
      .select("*")
      .eq("conversation_id", convId)
      .order("created_at", { ascending: true });

    if (data) {
      setMessages(
        data.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          retrieved_docs: m.retrieved_docs || [],
          created_at: m.created_at,
        }))
      );
    }
  }, []);

  const sendMessage = useCallback(
    async (content: string, options: SendOptions = {}) => {
      const supabase = getSupabaseBrowserClient();

      // Create conversation if needed
      let activeConvId: string | undefined = convIdRef.current;
      if (!activeConvId) {
        const {
          data: { user },
        } = await supabase.auth.getUser();
        if (!user) return;

        const { data: conv } = await supabase
          .from("conversations")
          .insert({
            user_id: user.id,
            title: content.slice(0, 50),
          })
          .select()
          .single();

        if (!conv) return;
        activeConvId = conv.id as string;
        convIdRef.current = activeConvId;
        onConversationCreated?.(activeConvId as string);
      }

      // Save user message to Supabase
      const { data: userMsg } = await supabase
        .from("messages")
        .insert({
          conversation_id: activeConvId,
          role: "user",
          content,
        })
        .select()
        .single();

      if (userMsg) {
        setMessages((prev) => [
          ...prev,
          {
            id: userMsg.id,
            role: "user",
            content: userMsg.content,
            created_at: userMsg.created_at,
          },
        ]);
      }

      // Start SSE stream
      setIsStreaming(true);
      setStreamingContent("");
      setStreamingDocs([]);

      const abortController = new AbortController();
      abortRef.current = abortController;

      try {
        const apiUrl = window.ENV?.VITE_API_URL || "http://localhost:8000";
        const response = await fetch(`${apiUrl}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: content,
            conversation_id: activeConvId,
            relax_context: Boolean(options.relaxContext),
          }),
          signal: abortController.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error("Stream request failed");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = "";
        let docs: RetrievedDoc[] = [];
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const jsonStr = line.slice(6).trim();
            if (!jsonStr || jsonStr === "[DONE]") continue;

            try {
              const event = JSON.parse(jsonStr);
              if (event.type === "token") {
                fullContent += event.content;
                setStreamingContent(fullContent);
              } else if (event.type === "docs") {
                docs = event.documents || [];
                setStreamingDocs(docs);
              } else if (event.type === "done") {
                fullContent = event.full_answer || fullContent;
              }
            } catch {
              // skip malformed JSON
            }
          }
        }

        // Save assistant message to Supabase
        const { data: assistantMsg } = await supabase
          .from("messages")
          .insert({
            conversation_id: activeConvId,
            role: "assistant",
            content: fullContent,
            retrieved_docs: docs,
          })
          .select()
          .single();

        if (assistantMsg) {
          setMessages((prev) => [
            ...prev,
            {
              id: assistantMsg.id,
              role: "assistant",
              content: assistantMsg.content,
              retrieved_docs: assistantMsg.retrieved_docs || [],
              created_at: assistantMsg.created_at,
            },
          ]);
        }

        // Update conversation title if it was the first message
        await supabase
          .from("conversations")
          .update({ updated_at: new Date().toISOString() })
          .eq("id", activeConvId);
      } catch (err: any) {
        if (err.name !== "AbortError") {
          console.error("Stream error:", err);
          // Add error message
          setMessages((prev) => [
            ...prev,
            {
              id: `error-${Date.now()}`,
              role: "assistant",
              content: "오류가 발생했습니다. 다시 시도해주세요.",
            },
          ]);
        }
      } finally {
        setIsStreaming(false);
        setStreamingContent("");
        setStreamingDocs([]);
        abortRef.current = null;
      }
    },
    [onConversationCreated]
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    messages,
    isStreaming,
    streamingContent,
    streamingDocs,
    sendMessage,
    stopStreaming,
    loadMessages,
    setMessages,
  };
}
