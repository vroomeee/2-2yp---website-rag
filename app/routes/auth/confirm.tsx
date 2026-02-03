import { redirect } from "react-router";
import { createSupabaseServerClient } from "~/lib/supabase.server";
import type { Route } from "./+types/confirm";

export async function loader({ request }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const token_hash = url.searchParams.get("token_hash");
  const type = url.searchParams.get("type") as
    | "signup"
    | "recovery"
    | "invite"
    | "email"
    | null;

  if (token_hash && type) {
    const { supabase, headers } = createSupabaseServerClient(request);
    const { error } = await supabase.auth.verifyOtp({ token_hash, type });

    if (!error) {
      if (type === "recovery") {
        return redirect("/auth/update-password", { headers });
      }
      return redirect("/chat", { headers });
    }
  }

  return redirect("/auth/login");
}

export default function ConfirmPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <p className="text-muted-foreground">인증 처리 중...</p>
    </div>
  );
}
