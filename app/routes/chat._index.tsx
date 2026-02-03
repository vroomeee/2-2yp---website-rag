import { useState } from "react";
import { useNavigate } from "react-router";
import { ChatMessages } from "~/components/chat/chat-messages";
import { MessageInput } from "~/components/chat/message-input";
import { useChatStream } from "~/hooks/use-chat-stream";

export default function NewChatPage() {
  const navigate = useNavigate();

  const {
    messages,
    isStreaming,
    streamingContent,
    streamingDocs,
    sendMessage,
  } = useChatStream({
    onConversationCreated: (id) => {
      // Navigate to the new conversation URL without triggering a full reload
      window.history.replaceState(null, "", `/chat/${id}`);
    },
  });
  const [relaxContext, setRelaxContext] = useState(false);

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
