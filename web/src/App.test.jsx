import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const authMocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
  signInWithOAuth: vi.fn(),
  signOut: vi.fn(),
  unsubscribe: vi.fn()
}));

vi.mock("./lib/supabaseClient", () => ({
  supabaseConfigured: true,
  supabaseConfigError: null,
  supabase: {
    auth: {
      getSession: authMocks.getSession,
      onAuthStateChange: authMocks.onAuthStateChange,
      signInWithOAuth: authMocks.signInWithOAuth,
      signOut: authMocks.signOut
    }
  }
}));

describe("App", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.sezzions.test");
    authMocks.getSession.mockReset();
    authMocks.onAuthStateChange.mockReset();
    authMocks.signInWithOAuth.mockReset();
    authMocks.signOut.mockReset();
    authMocks.unsubscribe.mockReset();

    authMocks.getSession.mockResolvedValue({ data: { session: null }, error: null });
    authMocks.onAuthStateChange.mockReturnValue({
      data: {
        subscription: {
          unsubscribe: authMocks.unsubscribe
        }
      }
    });
    authMocks.signInWithOAuth.mockResolvedValue({ error: null });
    authMocks.signOut.mockResolvedValue({ error: null });
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        authenticated: true,
        user_id: "user-123",
        email: "owner@sezzions.com",
        audience: "authenticated",
        role: "authenticated"
      })
    });
  });

  it("shows the Sezzions web heading", async () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /sezzions web control tower/i })
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText(/sign in with google to activate the hosted web shell/i)
      ).toBeInTheDocument();
    });
  });

  it("starts Google sign-in when the button is clicked", async () => {
    render(<App />);

    fireEvent.click(screen.getAllByRole("button", { name: /continue with google/i })[0]);

    await waitFor(() => {
      expect(authMocks.signInWithOAuth).toHaveBeenCalledWith({
        provider: "google",
        options: {
          redirectTo: window.location.origin
        }
      });
    });
  });

  it("shows the signed-in email from the current session", async () => {
    authMocks.getSession.mockResolvedValue({
      data: {
        session: {
          access_token: "access-token-123",
          user: {
            email: "owner@sezzions.com"
          }
        }
      },
      error: null
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("owner@sezzions.com")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("https://api.sezzions.test/v1/session", {
        headers: {
          Authorization: "Bearer access-token-123"
        }
      });
    });
    expect(
      screen.getByText(/protected api handshake ready for owner@sezzions.com/i)
    ).toBeInTheDocument();
  });
});