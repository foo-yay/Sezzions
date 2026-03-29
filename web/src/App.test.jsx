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
    window.sessionStorage.clear();
    vi.unstubAllEnvs();
  });

  beforeEach(() => {
    window.history.pushState({}, "", "/#/");
    window.sessionStorage.clear();
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
      if (url === "https://api.sezzions.test/v1/workspace/users") {
        return {
          ok: true,
          json: async () => ({
            users: [
              {
                id: "user-1",
                name: "Elliot",
                email: "elliot@sezzions.com",
                notes: "Primary operator",
                is_active: true
              }
            ]
          })
        };
      }

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
              auth_provider: "google",
              role: "owner",
              status: "active"
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
      screen.getByRole("heading", { name: /hosted sezzions is ready for the first true app slice/i })
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText(/sign in with google to activate the hosted sezzions workspace/i)
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
    expect(window.sessionStorage.getItem("sezzions.oauthReturnRoute")).toBe("/");
  });

  it("preserves a hash-routed return target before Google sign-in", async () => {
    window.history.pushState({}, "", "/#/migration");

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /continue with google/i }));

    await waitFor(() => {
      expect(authMocks.signInWithOAuth).toHaveBeenCalledWith({
        provider: "google",
        options: {
          redirectTo: window.location.origin
        }
      });
    });
    expect(window.sessionStorage.getItem("sezzions.oauthReturnRoute")).toBe("/migration");
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
    expect(screen.getByText("owner@sezzions.com Workspace")).toBeInTheDocument();
  });

  it("renders the hosted app shell and users surface after bootstrap", async () => {
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
            auth_provider: "google",
            role: "owner",
            status: "active"
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
          users: [
            {
              id: "user-1",
              name: "Elliot",
              email: "elliot@sezzions.com",
              notes: "Primary operator",
              is_active: true
            }
          ]
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

    expect(await screen.findByRole("heading", { name: /hosted workspace/i })).toBeInTheDocument();
    const usersSections = await screen.findAllByRole("heading", { name: /^users$/i });
    expect(usersSections).toHaveLength(2);
    expect(screen.getByText("owner")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("Elliot")).toBeInTheDocument();
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
    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        4,
        "https://api.sezzions.test/v1/workspace/users",
        {
          headers: {
            Authorization: "Bearer access-token-123"
          }
        }
      );
    });
  });

  it("keeps the hosted workspace shell visible when bootstrap fetch fails", async () => {
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
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));

    render(<App />);

    expect(await screen.findByRole("heading", { name: /hosted workspace/i })).toBeInTheDocument();
    expect(screen.getByText("owner@sezzions.com")).toBeInTheDocument();
    expect(screen.getByText(/could not reach the hosted api/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry hosted connection/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add user/i })).toBeDisabled();
    expect(screen.getByText(/sign in to load hosted users|hosted users will load after workspace bootstrap/i)).toBeInTheDocument();
  });

  it("creates a hosted user from the users modal", async () => {
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
            auth_provider: "google",
            role: "owner",
            status: "active"
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
        json: async () => ({ users: [] })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "user-2",
          name: "Jordan",
          email: "jordan@sezzions.com",
          notes: "Night shift",
          is_active: true
        })
      });

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /add user/i }));
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Jordan" } });
    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: "jordan@sezzions.com" } });
    fireEvent.change(screen.getByLabelText(/^notes$/i), { target: { value: "Night shift" } });
    fireEvent.click(screen.getByRole("button", { name: /save user/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        5,
        "https://api.sezzions.test/v1/workspace/users",
        {
          method: "POST",
          headers: {
            Authorization: "Bearer access-token-123",
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            name: "Jordan",
            email: "jordan@sezzions.com",
            notes: "Night shift"
          })
        }
      );
    });

    expect(await screen.findByText("Jordan")).toBeInTheDocument();
    expect(screen.getByText("jordan@sezzions.com")).toBeInTheDocument();
  });

  it("edits a hosted user and toggles active status", async () => {
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
            auth_provider: "google",
            role: "owner",
            status: "active"
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
          users: [
            {
              id: "user-1",
              name: "Elliot",
              email: "elliot@sezzions.com",
              notes: "Primary operator",
              is_active: true
            }
          ]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "user-1",
          name: "Elliot Hart",
          email: "elliot@sezzions.com",
          notes: "Primary operator",
          is_active: false
        })
      });

    render(<App />);

    const elliotCell = await screen.findByText("Elliot");
    fireEvent.click(elliotCell);
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Elliot Hart" } });
    fireEvent.click(screen.getByLabelText(/^active$/i));
    fireEvent.click(screen.getByRole("button", { name: /save user/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        5,
        "https://api.sezzions.test/v1/workspace/users/user-1",
        {
          method: "PATCH",
          headers: {
            Authorization: "Bearer access-token-123",
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            name: "Elliot Hart",
            email: "elliot@sezzions.com",
            notes: "Primary operator",
            is_active: false
          })
        }
      );
    });

    expect(await screen.findByText("Elliot Hart")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("deletes a hosted user after confirmation", async () => {
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

    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
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
            auth_provider: "google",
            role: "owner",
            status: "active"
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
          users: [
            {
              id: "user-1",
              name: "Elliot",
              email: "elliot@sezzions.com",
              notes: "Primary operator",
              is_active: true
            }
          ]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        text: async () => ""
      });

    render(<App />);

    const elliotCell = await screen.findByText("Elliot");
    fireEvent.click(elliotCell);
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        5,
        "https://api.sezzions.test/v1/workspace/users/user-1",
        {
          method: "DELETE",
          headers: {
            Authorization: "Bearer access-token-123"
          }
        }
      );
    });

    expect(confirmSpy).toHaveBeenCalled();
    expect(screen.queryByText("Elliot")).not.toBeInTheDocument();
    confirmSpy.mockRestore();
  });

  it("uploads a sqlite file from the migration page and renders the inventory summary", async () => {
    window.history.pushState({}, "", "/#/migration");
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
            auth_provider: "google",
            role: "owner",
            status: "active"
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
        json: async () => ({ users: [] })
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
        5,
        "https://api.sezzions.test/v1/workspace/import-upload-plan",
        expect.objectContaining({
          method: "POST",
          headers: {
            Authorization: "Bearer access-token-123"
          }
        })
      );
    });

    const inventoryHeading = await screen.findByRole("heading", { name: /uploaded sqlite inspection/i });
    const inventorySection = inventoryHeading.closest("section");

    expect(inventorySection).not.toBeNull();
    expect(within(inventorySection).getByText(/uploaded file/i)).toBeInTheDocument();
    expect(within(inventorySection).getByText("sezzions.db")).toBeInTheDocument();
    expect(within(inventorySection).getByText(/elliot/i)).toBeInTheDocument();
  });
});