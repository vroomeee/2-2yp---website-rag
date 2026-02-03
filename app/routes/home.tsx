import { redirect } from "react-router";
import { createSupabaseServerClient } from "~/lib/supabase.server";
import type { Route } from "./+types/home";

export async function loader({ request }: Route.LoaderArgs) {
  try {
    const { supabase } = createSupabaseServerClient(request);
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (user) {
      throw redirect("/chat");
    }
  } catch (e) {
    // Re-throw redirects
    if (e instanceof Response) throw e;
    // Supabase unreachable — fall through to login
  }

  throw redirect("/auth/login");
}

export default function HomePage() {
  return null;
}
