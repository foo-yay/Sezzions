import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function pagedUsers(users, { offset = 0, totalCount = users.length } = {}) {
  return {
    users,
    offset,
    limit: 100,
    next_offset: offset + users.length,
    total_count: totalCount,
    has_more: offset + users.length < totalCount
  };
}

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
    vi.stubEnv("VITE_SUPABASE_ANON_KEY", "");
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
      if (String(url).startsWith("https://api.sezzions.test/v1/workspace/users?")) {
        return {
          ok: true,
          json: async () => pagedUsers([
              {
                id: "user-1",
                name: "Elliot",
                email: "elliot@sezzions.com",
                notes: "Primary operator",
                is_active: true
              }
            ])
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

  async function findUserCell(name) {
    const table = await screen.findByRole("table");
    return within(table).findByText(name);
  }

  it("shows the Sezzions web heading", async () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /sezzions for the web/i })
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

    expect(await screen.findByRole("heading", { name: /sezzions - sweepstakes session tracker/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open my account/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open settings/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open notifications/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open hosted status/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("https://api.sezzions.test/v1/session", {
        headers: {
          Authorization: "Bearer access-token-123"
        }
      });
    });
    fireEvent.click(screen.getByRole("button", { name: /open my account/i }));
    expect(screen.getByText("owner@sezzions.com")).toBeInTheDocument();
    expect(screen.getAllByText("owner@sezzions.com Workspace").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
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

    expect(await screen.findByRole("heading", { name: /sezzions - sweepstakes session tracker/i })).toBeInTheDocument();
    const usersSections = await screen.findAllByRole("heading", { name: /^users$/i });
    expect(usersSections).toHaveLength(1);
    expect(screen.getByRole("button", { name: /toggle setup navigation/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open my account/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open settings/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open notifications/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open hosted status/i })).toBeInTheDocument();
    expect(await findUserCell("Elliot")).toBeInTheDocument();
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
        "https://api.sezzions.test/v1/workspace/users?limit=100&offset=0",
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

    expect(await screen.findByRole("heading", { name: /sezzions - sweepstakes session tracker/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open my account/i })).toHaveAttribute("title", "owner@sezzions.com");
    expect(screen.getByRole("button", { name: /add user/i })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /open hosted status/i }));
    expect(screen.getByText(/could not reach the hosted api/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /connection health/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry hosted connection/i })).toBeInTheDocument();
  });

  it("opens settings directly from the compact header", async () => {
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

    fireEvent.click(await screen.findByRole("button", { name: /open settings/i }));
    const dialog = await screen.findByRole("dialog", { name: /settings/i });
    expect(within(dialog).getByText(/no settings available/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open my account/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open hosted status/i })).toBeInTheDocument();
  });

  it("lets the user edit directly from the view user dialog", async () => {
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
        json: async () => pagedUsers([
            {
              id: "user-1",
              name: "Elliot",
              email: "elliot@sezzions.com",
              notes: "Primary operator",
              is_active: true
            }
          ])
      });

    render(<App />);

    const elliotCell = await findUserCell("Elliot");
    fireEvent.doubleClick(elliotCell);

    expect(await screen.findByRole("heading", { name: /view user/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit user/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /edit user/i }));
    expect(await screen.findByRole("heading", { name: /edit user/i })).toBeInTheDocument();
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
        json: async () => pagedUsers([])
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
    const createDialog = await screen.findByRole("dialog", { name: /add user/i });
    fireEvent.change(within(createDialog).getByLabelText(/^name$/i), { target: { value: "Jordan" } });
    fireEvent.change(within(createDialog).getByLabelText(/^email$/i), { target: { value: "jordan@sezzions.com" } });
    fireEvent.change(within(createDialog).getByLabelText(/^notes$/i), { target: { value: "Night shift" } });
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

    const table = await screen.findByRole("table");
    expect(within(table).getByText("Jordan")).toBeInTheDocument();
    expect(within(table).getByText("jordan@sezzions.com")).toBeInTheDocument();
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
        json: async () => pagedUsers([
            {
              id: "user-1",
              name: "Elliot",
              email: "elliot@sezzions.com",
              notes: "Primary operator",
              is_active: true
            }
          ])
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

    const elliotCell = await findUserCell("Elliot");
    fireEvent.click(elliotCell);
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    const editDialog = await screen.findByRole("dialog", { name: /edit user/i });
    fireEvent.change(within(editDialog).getByLabelText(/^name$/i), { target: { value: "Elliot Hart" } });
    fireEvent.click(within(editDialog).getByLabelText(/^active$/i));
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

    const table = await screen.findByRole("table");
    expect(within(table).getByText("Elliot Hart")).toBeInTheDocument();
    expect(within(table).getByText("Inactive")).toBeInTheDocument();
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
        json: async () => pagedUsers([
            {
              id: "user-1",
              name: "Elliot",
              email: "elliot@sezzions.com",
              notes: "Primary operator",
              is_active: true
            }
          ])
      })
      .mockResolvedValueOnce({
        ok: true,
        text: async () => ""
      });

    render(<App />);

    const elliotCell = await findUserCell("Elliot");
    fireEvent.click(elliotCell);
    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    const deleteDialog = await screen.findByRole("alertdialog", { name: /delete user\?/i });
    fireEvent.click(within(deleteDialog).getByRole("button", { name: /delete user/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenNthCalledWith(
        5,
        "https://api.sezzions.test/v1/workspace/users/batch-delete",
        {
          method: "POST",
          headers: {
            Authorization: "Bearer access-token-123",
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ user_ids: ["user-1"] })
        }
      );
    });

    expect(within(await screen.findByRole("table")).queryByText("Elliot")).not.toBeInTheDocument();
  });

  it("prompts before Escape closes a dirty user modal", async () => {
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
        json: async () => pagedUsers([
          {
            id: "user-1",
            name: "Elliot",
            email: "elliot@sezzions.com",
            notes: "Primary operator",
            is_active: true
          }
        ])
      });

    render(<App />);

    await findUserCell("Elliot");
    fireEvent.click(screen.getByRole("button", { name: /add user/i }));
    const nameInput = screen.getByPlaceholderText(/required/i);
    nameInput.focus();
    fireEvent.change(nameInput, { target: { value: "Draft User" } });

    fireEvent.keyDown(window, { key: "Escape" });

    expect(nameInput).not.toHaveFocus();
    expect(screen.queryByRole("alertdialog", { name: /discard unsaved changes\?/i })).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.getByRole("alertdialog", { name: /discard unsaved changes\?/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /discard changes/i }));

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /add user/i })).not.toBeInTheDocument();
    });
  });

  it("uses Escape to exit a filter search field before closing the popup", async () => {
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
        json: async () => pagedUsers([
          {
            id: "user-2",
            name: "Zelda",
            email: "zelda@sezzions.com",
            notes: "Shift lead",
            is_active: false
          },
          {
            id: "user-1",
            name: "Elliot",
            email: "elliot@sezzions.com",
            notes: "Primary operator",
            is_active: true
          }
        ])
      });

    render(<App />);

    await findUserCell("Zelda");
    fireEvent.click(screen.getByRole("button", { name: /status options/i }));

    const filterDialog = screen.getByRole("dialog", { name: /status sort and filter/i });
    const searchInput = within(filterDialog).getByPlaceholderText(/search values/i);
    searchInput.focus();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(searchInput).not.toHaveFocus();
    expect(screen.getByRole("dialog", { name: /status sort and filter/i })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /status sort and filter/i })).not.toBeInTheDocument();
    });
  });

  it("supports desktop-style user sorting and column filters", async () => {
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
        json: async () => pagedUsers([
            {
              id: "user-2",
              name: "Zelda",
              email: "zelda@sezzions.com",
              notes: "Shift lead",
              is_active: false
            },
            {
              id: "user-1",
              name: "Elliot",
              email: "elliot@sezzions.com",
              notes: "Primary operator",
              is_active: true
            }
          ])
      });

    render(<App />);

    await findUserCell("Zelda");

    fireEvent.click(screen.getByRole("button", { name: /name options/i }));
    fireEvent.click(screen.getByRole("button", { name: /sort a to z/i }));

    const rows = screen.getAllByRole("row");
    const nameCellsAsc = rows.slice(1).map((row) => within(row).getAllByRole("cell")[0]);
    expect(nameCellsAsc[0]).toHaveTextContent("Elliot");

    fireEvent.click(screen.getByRole("button", { name: /status options/i }));
    const filterDialog = screen.getByRole("dialog", { name: /status sort and filter/i });
    const searchInput = within(filterDialog).getByPlaceholderText(/search values/i);
    expect(searchInput).toHaveAttribute("list", "header-filter-search-status");
    fireEvent.change(searchInput, { target: { value: "Inac" } });
    expect(within(filterDialog).getByRole("checkbox", { name: /inactive/i })).toBeInTheDocument();
    expect(within(filterDialog).queryByRole("checkbox", { name: /^Active$/i })).not.toBeInTheDocument();
    fireEvent.click(within(filterDialog).getByRole("button", { name: /clear all/i }));
    fireEvent.click(within(filterDialog).getByRole("checkbox", { name: /inactive/i }));
    fireEvent.click(within(filterDialog).getByRole("button", { name: /apply filter/i }));

    expect(await findUserCell("Zelda")).toBeInTheDocument();
    expect(within(await screen.findByRole("table")).queryByText("Elliot")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /clear all filters/i }));
    expect(await findUserCell("Elliot")).toBeInTheDocument();
    expect(await findUserCell("Zelda")).toBeInTheDocument();
  });

  it("supports infinite scroll loading and desktop-style multi-row delete", async () => {
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

    global.fetch = vi.fn().mockImplementation(async (url, options) => {
      const normalizedUrl = String(url);
      if (normalizedUrl === "https://api.sezzions.test/v1/session") {
        return {
          ok: true,
          json: async () => ({ authenticated: true, user_id: "user-123", email: "owner@sezzions.com", audience: "authenticated", role: "authenticated" })
        };
      }
      if (normalizedUrl === "https://api.sezzions.test/v1/account/bootstrap") {
        return {
          ok: true,
          json: async () => ({
            created_account: true,
            created_workspace: true,
            account: { id: "account-123", supabase_user_id: "user-123", owner_email: "owner@sezzions.com", auth_provider: "google", role: "owner", status: "active" },
            workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null }
          })
        };
      }
      if (normalizedUrl === "https://api.sezzions.test/v1/workspace/import-plan") {
        return {
          ok: true,
          json: async () => ({
            status: "source-db-path-missing",
            detail: "No source SQLite database path is recorded for this hosted workspace yet.",
            source_db_configured: false,
            source_db_accessible: false,
            workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null },
            inventory: null
          })
        };
      }
      if (normalizedUrl === "https://api.sezzions.test/v1/workspace/users?limit=100&offset=0") {
        return {
          ok: true,
          json: async () => pagedUsers([
            { id: "user-1", name: "Alpha", email: "alpha@sezzions.com", notes: "First", is_active: true }
          ], { offset: 0, totalCount: 2 })
        };
      }
      if (normalizedUrl === "https://api.sezzions.test/v1/workspace/users?limit=100&offset=1") {
        return {
          ok: true,
          json: async () => pagedUsers([
            { id: "user-2", name: "Beta", email: "beta@sezzions.com", notes: "Second", is_active: true }
          ], { offset: 1, totalCount: 2 })
        };
      }
      if (normalizedUrl === "https://api.sezzions.test/v1/workspace/users/user-1" || normalizedUrl === "https://api.sezzions.test/v1/workspace/users/user-2") {
        throw new Error(`Unexpected fetch ${normalizedUrl} ${options?.method || "GET"}`);
      }
      if (normalizedUrl === "https://api.sezzions.test/v1/workspace/users/batch-delete") {
        return {
          ok: true,
          json: async () => ({ deleted_count: 2 })
        };
      }

      throw new Error(`Unexpected fetch ${normalizedUrl} ${options?.method || "GET"}`);
    });

    render(<App />);

    expect(await findUserCell("Alpha")).toBeInTheDocument();
    expect(within(await screen.findByRole("table")).queryByText("Beta")).not.toBeInTheDocument();

    Object.defineProperty(window, "innerHeight", { configurable: true, value: 900, writable: true });
    Object.defineProperty(window, "scrollY", { configurable: true, value: 0, writable: true });
    Object.defineProperty(document.body, "scrollHeight", { configurable: true, value: 1000 });
    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 1000 });
    Object.defineProperty(document.documentElement, "scrollTop", { configurable: true, value: 0, writable: true });
    fireEvent.scroll(window);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(4);
    });

    Object.defineProperty(window, "scrollY", { configurable: true, value: 1200, writable: true });
    Object.defineProperty(document.body, "scrollHeight", { configurable: true, value: 2280 });
    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 2280 });
    Object.defineProperty(document.documentElement, "scrollTop", { configurable: true, value: 1200, writable: true });
    fireEvent.scroll(window);

    expect(await findUserCell("Beta")).toBeInTheDocument();

    const rows = within(await screen.findByRole("table")).getAllByRole("row");
    fireEvent.click(within(rows[1]).getByText("Alpha"));
    fireEvent.click(within(rows[2]).getByText("Beta"), { ctrlKey: true });
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));
    const deleteDialog = await screen.findByRole("alertdialog", { name: /delete users\?/i });
    fireEvent.click(within(deleteDialog).getByRole("button", { name: /delete 2 users/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("https://api.sezzions.test/v1/workspace/users/batch-delete", {
        method: "POST",
        headers: {
          Authorization: "Bearer access-token-123",
          "Content-Type": "application/json"
        }
        ,
        body: JSON.stringify({ user_ids: ["user-1", "user-2"] })
      });
    });

    expect(within(await screen.findByRole("table")).queryByText("Alpha")).not.toBeInTheDocument();
    expect(within(await screen.findByRole("table")).queryByText("Beta")).not.toBeInTheDocument();
  });

  it("caps the initial hosted users render to one page even if the API over-returns rows", async () => {
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

    const oversizedPage = Array.from({ length: 151 }, (_, index) => ({
      id: `user-${index + 1}`,
      name: `User ${String(index + 1).padStart(3, "0")}`,
      email: `user${index + 1}@sezzions.com`,
      notes: `Record ${index + 1}`,
      is_active: true
    }));

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true, user_id: "user-123", email: "owner@sezzions.com", audience: "authenticated", role: "authenticated" })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          created_account: true,
          created_workspace: true,
          account: { id: "account-123", supabase_user_id: "user-123", owner_email: "owner@sezzions.com", auth_provider: "google", role: "owner", status: "active" },
          workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "source-db-path-missing",
          detail: "No source SQLite database path is recorded for this hosted workspace yet.",
          source_db_configured: false,
          source_db_accessible: false,
          workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null },
          inventory: null
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          users: oversizedPage,
          offset: 0,
          limit: 100,
          next_offset: 151,
          total_count: 151,
          has_more: false
        })
      });

    render(<App />);

    expect(await findUserCell("User 001")).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(101);
    expect(within(table).queryByText("User 151")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /load more users/i })).toBeInTheDocument();
  });

  it("keeps paging available when the hosted API returns a full page but incorrect total metadata", async () => {
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

    const firstPage = Array.from({ length: 100 }, (_, index) => ({
      id: `user-${index + 1}`,
      name: `User ${String(index + 1).padStart(3, "0")}`,
      email: `user${index + 1}@sezzions.com`,
      notes: `Record ${index + 1}`,
      is_active: true
    }));

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true, user_id: "user-123", email: "owner@sezzions.com", audience: "authenticated", role: "authenticated" })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          created_account: true,
          created_workspace: true,
          account: { id: "account-123", supabase_user_id: "user-123", owner_email: "owner@sezzions.com", auth_provider: "google", role: "owner", status: "active" },
          workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "source-db-path-missing",
          detail: "No source SQLite database path is recorded for this hosted workspace yet.",
          source_db_configured: false,
          source_db_accessible: false,
          workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null },
          inventory: null
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          users: firstPage,
          offset: 0,
          limit: 100,
          next_offset: 100,
          total_count: 100,
          has_more: false
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          users: [
            { id: "user-101", name: "User 101", email: "user101@sezzions.com", notes: "Record 101", is_active: true }
          ],
          offset: 100,
          limit: 100,
          next_offset: 101,
          total_count: 101,
          has_more: false
        })
      });

    render(<App />);

    expect(await findUserCell("User 001")).toBeInTheDocument();
    expect(screen.queryByText(/101 total/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/more available/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/100 loaded/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /load more users/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /load more users/i }));

    expect(await findUserCell("User 101")).toBeInTheDocument();
  });

  it("falls back when the hosted API repeats the first page for later offsets", async () => {
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

    const firstPage = Array.from({ length: 100 }, (_, index) => ({
      id: `user-${index + 1}`,
      name: `User ${String(index + 1).padStart(3, "0")}`,
      email: `user${index + 1}@sezzions.com`,
      notes: `Record ${index + 1}`,
      is_active: true
    }));

    const fallbackPage = Array.from({ length: 151 }, (_, index) => ({
      id: `user-${index + 1}`,
      name: `User ${String(index + 1).padStart(3, "0")}`,
      email: `user${index + 1}@sezzions.com`,
      notes: `Record ${index + 1}`,
      is_active: true
    }));

    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true, user_id: "user-123", email: "owner@sezzions.com", audience: "authenticated", role: "authenticated" })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          created_account: true,
          created_workspace: true,
          account: { id: "account-123", supabase_user_id: "user-123", owner_email: "owner@sezzions.com", auth_provider: "google", role: "owner", status: "active" },
          workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "source-db-path-missing",
          detail: "No source SQLite database path is recorded for this hosted workspace yet.",
          source_db_configured: false,
          source_db_accessible: false,
          workspace: { id: "workspace-123", account_id: "account-123", name: "owner@sezzions.com Workspace", source_db_path: null },
          inventory: null
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          users: firstPage,
          offset: 0,
          limit: 100,
          next_offset: 100,
          total_count: 100,
          has_more: false
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          users: firstPage,
          offset: 100,
          limit: 100,
          next_offset: 200,
          total_count: 100,
          has_more: false
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          users: fallbackPage,
          offset: 0,
          limit: 500,
          next_offset: 151,
          total_count: 151,
          has_more: false
        })
      });

    render(<App />);

    expect(await findUserCell("User 001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /load more users/i }));

    expect(await findUserCell("User 151")).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.sezzions.test/v1/workspace/users?limit=500&offset=0",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer access-token-123"
        })
      })
    );
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