import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  beforeEach(() => {
    window.history.pushState({}, "", "/");
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
    global.fetch = vi.fn().mockImplementation(async (url) => {
      if (url === "https://api.sezzions.test/v1/workspace/import-plan") {
        return {
          ok: true,
          json: async () => ({
            status: "source-db-path-missing",
            detail: "No source SQLite database path is recorded for this hosted workspace yet.",
            source_db_configured: false,
            source_db_accessible: false,
            workspace: {
              id: "workspace-123",
              account_id: "account-123",
              name: "owner@sezzions.com Workspace",
              source_db_path: null
            },
            inventory: null
          })
        };
      }

      if (url === "https://api.sezzions.test/v1/account/bootstrap") {
        return {
          ok: true,
          json: async () => ({
            created_account: true,
            created_workspace: true,
            account: {
              id: "account-123",
              supabase_user_id: "user-123",
              owner_email: "owner@sezzions.com",
              auth_provider: "google"
            },
            workspace: {
              id: "workspace-123",
              account_id: "account-123",
              name: "owner@sezzions.com Workspace",
              source_db_path: null
            }
          })
        };
      }

      return {
        ok: true,
        json: async () => ({
          authenticated: true,
          user_id: "user-123",
          email: "owner@sezzions.com",
          audience: "authenticated",
          role: "authenticated"
        })
      };
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

  it("renders the hosted account workspace summary after bootstrap", async () => {
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

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          authenticated: true,
          user_id: "user-123",
          email: "owner@sezzions.com",
          audience: "authenticated",
          role: "authenticated"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          created_account: true,
          created_workspace: true,
          account: {
            id: "account-123",
            supabase_user_id: "user-123",
            owner_email: "owner@sezzions.com",
            auth_provider: "google"
          },
          workspace: {
            id: "workspace-123",
            account_id: "account-123",
            name: "owner@sezzions.com Workspace",
            source_db_path: null
          }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "source-db-path-missing",
          detail: "No source SQLite database path is recorded for this hosted workspace yet.",
          source_db_configured: false,
          source_db_accessible: false,
          workspace: {
            id: "workspace-123",
            account_id: "account-123",
            name: "owner@sezzions.com Workspace",
            source_db_path: null
          },
          inventory: null
        })
      });

    render(<App />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        "https://api.sezzions.test/v1/account/bootstrap",
        {
          method: "POST",
          headers: {
            Authorization: "Bearer access-token-123"
          }
        }
      );
    });

    const hostedHeading = await screen.findByRole("heading", {
      name: /authenticated workspace bootstrap/i
    });
    const hostedSection = hostedHeading.closest("section");
    const importHeading = await screen.findByRole("heading", {
      name: /hosted workspace import readiness/i
    });
    const importSection = importHeading.closest("section");

    expect(hostedSection).not.toBeNull();
    expect(importSection).not.toBeNull();
    expect(within(hostedSection).getByText(/hosted account owner/i)).toBeInTheDocument();
    expect(within(hostedSection).getByText("owner@sezzions.com Workspace")).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        3,
        "https://api.sezzions.test/v1/workspace/import-plan",
        {
          headers: {
            Authorization: "Bearer access-token-123"
          }
        }
      );
    });
    expect(within(importSection).getByText(/no source sqlite database path is recorded/i)).toBeInTheDocument();
  });

  it("uploads a sqlite file from the migration page and renders the inventory summary", async () => {
    window.history.pushState({}, "", "/migration");
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

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          authenticated: true,
          user_id: "user-123",
          email: "owner@sezzions.com",
          audience: "authenticated",
          role: "authenticated"
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          created_account: true,
          created_workspace: true,
          account: {
            id: "account-123",
            supabase_user_id: "user-123",
            owner_email: "owner@sezzions.com",
            auth_provider: "google"
          },
          workspace: {
            id: "workspace-123",
            account_id: "account-123",
            name: "owner@sezzions.com Workspace",
            source_db_path: null
          }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "source-db-path-missing",
          detail: "No source SQLite database path is recorded for this hosted workspace yet.",
          source_db_configured: false,
          source_db_accessible: false,
          workspace: {
            id: "workspace-123",
            account_id: "account-123",
            name: "owner@sezzions.com Workspace",
            source_db_path: null
          },
          inventory: null
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "ready",
          detail: "Uploaded SQLite inventory is ready.",
          uploaded_filename: "sezzions.db",
          inventory: {
            db_path: "/tmp/upload.db",
            db_size_bytes: 1024,
            schema_version_count: 1,
            tables: [{ table_name: "users", row_count: 1 }],
            active_user_names: ["Elliot"],
            site_names: ["Stake"]
          }
        })
      });

    render(<App />);

    const uploadInput = await screen.findByLabelText(/sqlite database file/i);
    const file = new File(["sqlite"], "sezzions.db", { type: "application/octet-stream" });
    fireEvent.change(uploadInput, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /upload sqlite for planning/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        4,
        "https://api.sezzions.test/v1/workspace/import-upload-plan",
        expect.objectContaining({
          method: "POST",
          headers: {
            Authorization: "Bearer access-token-123"
          }
        })
      );
    });

    const inventoryHeading = await screen.findByRole("heading", {
      name: /uploaded sqlite inspection/i
    });
    const inventorySection = inventoryHeading.closest("section");

    expect(inventorySection).not.toBeNull();
    expect(within(inventorySection).getByText(/uploaded file/i)).toBeInTheDocument();
    expect(within(inventorySection).getByText("sezzions.db")).toBeInTheDocument();
    expect(within(inventorySection).getByText(/elliot/i)).toBeInTheDocument();
  });
});