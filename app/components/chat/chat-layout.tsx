import { useState } from "react";
import { ChatSidebar } from "./chat-sidebar";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "~/components/ui/sheet";
import { Button } from "~/components/ui/button";
import { Menu } from "lucide-react";

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface ChatLayoutProps {
  conversations: Conversation[];
  currentConversationId?: string;
  userEmail?: string;
  children: React.ReactNode;
}

export function ChatLayout({
  conversations,
  currentConversationId,
  userEmail,
  children,
}: ChatLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <div className="hidden md:flex md:w-[280px] md:flex-col md:border-r md:border-border">
        <ChatSidebar
          conversations={conversations}
          currentConversationId={currentConversationId}
          userEmail={userEmail}
        />
      </div>

      {/* Mobile sidebar */}
      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="absolute left-3 top-3 z-40 md:hidden"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-[280px] p-0">
          <SheetTitle className="sr-only">대화 목록</SheetTitle>
          <ChatSidebar
            conversations={conversations}
            currentConversationId={currentConversationId}
            userEmail={userEmail}
            onNavigate={() => setSidebarOpen(false)}
          />
        </SheetContent>
      </Sheet>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
