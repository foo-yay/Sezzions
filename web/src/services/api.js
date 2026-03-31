import { supabase } from "../lib/supabaseClient";

export function authHeaders(accessToken) {
  const supabaseApiKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() || null;
  return {
    Authorization: `Bearer ${accessToken}`,
    ...(supabaseApiKey ? { apikey: supabaseApiKey } : {})
  };
}

export async function getAccessToken() {
  if (!supabase?.auth) {
    return null;
  }

  const { data, error } = await supabase.auth.getSession();
  if (error) {
    throw error;
  }

  return data.session?.access_token || null;
}

export function describeFetchFailure(error, fallback) {
  if (error instanceof TypeError && /failed to fetch/i.test(error.message)) {
    return `${fallback} Verify that the hosted API URL is reachable from the browser and that CORS is allowing this origin.`;
  }

  return error instanceof Error ? error.message : fallback;
}

export function classifyStatusTone(message, { ready = false, available = true } = {}) {
  if (ready) {
    return "good";
  }

  if (!available) {
    return "bad";
  }

  const normalizedMessage = String(message || "").toLowerCase();

  if (
    normalizedMessage.includes("failed")
    || normalizedMessage.includes("could not reach")
    || normalizedMessage.includes("set vite_api_base_url")
    || normalizedMessage.includes("not signed in")
  ) {
    return "bad";
  }

  return "warn";
}
