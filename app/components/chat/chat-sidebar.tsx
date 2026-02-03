import { Link, useNavigate } from "react-router";
import { Button } from "~/components/ui/button";
import { Separator } from "~/components/ui/separator";
import { Plus, MessageSquare, LogOut } from "lucide-react";
import { cn } from "~/lib/utils";
import { getSupabaseBrowserClient } from "~/lib/supabase.client";

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface ChatSidebarProps {
  conversations: Conversation[];
  currentConversationId?: string;
  userEmail?: string;
  onNavigate?: () => void;
}

export function ChatSidebar({
  conversations,
  currentConversationId,
  userEmail,
  onNavigate,
}: ChatSidebarProps) {
  const navigate = useNavigate();

  async function handleLogout() {
    const supabase = getSupabaseBrowserClient();
    await supabase.auth.signOut();
    navigate("/auth/login");
  }

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      {/* New chat button */}
      <div className="p-3">
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          asChild
          onClick={onNavigate}
        >
          <Link to="/chat">
            <Plus className="h-4 w-4" />
            새 대화
          </Link>
        </Button>
      </div>

      <Separator />

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        <div className="space-y-1">
          {conversations.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              대화 내역이 없습니다
            </p>
          )}
          {conversations.map((conv) => (
            <Button
              key={conv.id}
              variant="ghost"
              className={cn(
                "w-full justify-start gap-2 text-left font-normal",
                currentConversationId === conv.id &&
                  "bg-sidebar-accent text-sidebar-accent-foreground"
              )}
              asChild
              onClick={onNavigate}
            >
              <Link to={`/chat/${conv.id}`}>
                <MessageSquare className="h-4 w-4 shrink-0" />
                <span className="truncate">{conv.title}</span>
              </Link>
            </Button>
          ))}
        </div>
      </div>

      <Separator />

      {/* User info + logout */}
      <div className="p-3">
        <div className="flex items-center justify-between">
          <span className="truncate text-sm text-muted-foreground">
            {userEmail}
          </span>
          <Button variant="ghost" size="icon" onClick={handleLogout} title="로그아웃">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
