import { useEffect, useState } from "react";
import { redirect, useLoaderData, useParams } from "react-router";
import { createSupabaseServerClient } from "~/lib/supabase.server";
import { ChatMessages } from "~/components/chat/chat-messages";
import { MessageInput } from "~/components/chat/message-input";
import { useChatStream } from "~/hooks/use-chat-stream";
import type { Route } from "./+types/chat.$conversationId";

export async function loader({ request, params }: Route.LoaderArgs) {
  try {
    const { supabase } = createSupabaseServerClient(request);
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) throw redirect("/auth/login");

    const { data: messages } = await supabase
      .from("messages")
      .select("*")
      .eq("conversation_id", params.conversationId)
      .order("created_at", { ascending: true });

    return {
      messages: messages || [],
      conversationId: params.conversationId,
    };
  } catch (e) {
    if (e instanceof Response) throw e;
    throw redirect("/auth/login");
  }
}

export default function ConversationPage() {
  const { messages: initialMessages, conversationId } =
    useLoaderData<typeof loader>();
  const params = useParams();

  const {
    messages,
    isStreaming,
    streamingContent,
    streamingDocs,
    sendMessage,
    setMessages,
  } = useChatStream({ conversationId });
  const [relaxContext, setRelaxContext] = useState(false);

  // Load initial messages from server
  useEffect(() => {
    setMessages(
      initialMessages.map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        retrieved_docs: m.retrieved_docs || [],
        created_at: m.created_at,
      }))
    );
  }, [params.conversationId, initialMessages, setMessages]);

  return (
    <>
      <ChatMessages
        messages={messages}
        streamingContent={streamingContent}
        streamingDocs={streamingDocs}
        isStreaming={isStreaming}
      />
      <MessageInput
        onSend={sendMessage}
        disabled={isStreaming}
        relaxContext={relaxContext}
        onRelaxChange={setRelaxContext}
      />
    </>
  );
}
