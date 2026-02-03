import { createBrowserClient } from "@supabase/ssr";

let supabase: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseBrowserClient() {
  if (supabase) return supabase;

  supabase = createBrowserClient(
    window.ENV.VITE_SUPABASE_URL,
    window.ENV.VITE_SUPABASE_ANON_KEY
  );

  return supabase;
}

declare global {
  interface Window {
    ENV: {
      VITE_SUPABASE_URL: string;
      VITE_SUPABASE_ANON_KEY: string;
      VITE_API_URL: string;
    };
  }
}
