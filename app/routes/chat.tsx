import { Outlet, redirect, useLoaderData } from "react-router";
import { createSupabaseServerClient } from "~/lib/supabase.server";
import { ChatLayout } from "~/components/chat/chat-layout";
import type { Route } from "./+types/chat";

export async function loader({ request }: Route.LoaderArgs) {
  try {
    const { supabase } = createSupabaseServerClient(request);
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) throw redirect("/auth/login");

    const { data: conversations } = await supabase
      .from("conversations")
      .select("id, title, updated_at")
      .eq("user_id", user.id)
      .order("updated_at", { ascending: false });

    return {
      conversations: conversations || [],
      userEmail: user.email,
    };
  } catch (e) {
    if (e instanceof Response) throw e;
    // Supabase unreachable — redirect to login
    throw redirect("/auth/login");
  }
}

export default function ChatLayoutRoute() {
  const { conversations, userEmail } = useLoaderData<typeof loader>();

  return (
    <ChatLayout conversations={conversations} userEmail={userEmail}>
      <Outlet />
    </ChatLayout>
  );
}
