import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import UserModal from "./UserModal";
import { authHeaders, getAccessToken } from "../../services/api";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialUserForm,
  initialUserColumnFilters,
  userTableColumns,
  usersPageSize,
  usersFallbackPageSize
} from "./usersConstants";
import { normalizeUserForm, getUserColumnValue } from "./usersUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const usersConfig = {
  entityName: "users",
  entitySingular: "user",
  apiEndpoint: "/v1/workspace/users",
  responseKey: "users",
  batchDeleteIdKey: "user_ids",
  columns: userTableColumns,
  initialForm: initialUserForm,
  initialColumnFilters: initialUserColumnFilters,
  pageSize: usersPageSize,
  fallbackPageSize: usersFallbackPageSize,
  getColumnValue: getUserColumnValue,
  getCellDisplayValue: getUserColumnValue,
  searchFilter: (user, text) =>
    user.name.toLowerCase().includes(text)
    || (user.email || "").toLowerCase().includes(text)
    || (user.notes || "").toLowerCase().includes(text),
  numericSortColumns: [],
  normalizeForm: normalizeUserForm,
  itemToForm: (user) => ({
    name: user.name || "",
    email: user.email || "",
    notes: user.notes || "",
    is_active: Boolean(user.is_active)
  }),
  formToPayload: (form, mode) => ({
    name: form.name,
    email: form.email || null,
    notes: form.notes || null,
    ...(mode === "edit" ? { is_active: form.is_active } : {})
  }),
  buildFilterOptions: (users) => ({
    name: buildGenericFilterOptions(users, "name", getUserColumnValue),
    email: buildGenericFilterOptions(users, "email", getUserColumnValue),
    status: [
      { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
      { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
    ],
    notes: buildGenericFilterOptions(users, "notes", getUserColumnValue)
  }),
  buildSuggestions: (users) => ({
    names: [...new Set(users.map((u) => u.name).filter(Boolean))],
    emails: [...new Set(users.map((u) => u.email).filter(Boolean))]
  }),
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderUserCell(user, columnKey, search) {
  if (columnKey === "status") {
    return (
      <span className={user.is_active ? "status-chip active" : "status-chip inactive"}>
        {user.is_active ? "Active" : "Inactive"}
      </span>
    );
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(user.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={user[columnKey] || ""} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function UsersTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(usersConfig, { apiBaseUrl, hostedWorkspaceReady });
  const devToolsVisible = Boolean(import.meta.env.DEV);

  async function handleSeedDemoUsers() {
    const accessToken = await getAccessToken();
    if (!accessToken || !apiBaseUrl) return;

    const demoUsers = Array.from({ length: 200 }, (_, index) => ({
      name: `Demo User ${String(index + 1).padStart(3, "0")}`,
      email: `demo.user.${String(index + 1).padStart(3, "0")}@sezzions.local`,
      notes: `Demo paging record ${index + 1}`,
      is_active: index % 5 !== 0
    }));

    for (const demoUser of demoUsers) {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/users`, {
        method: "POST",
        headers: {
          ...authHeaders(accessToken),
          "Content-Type": "application/json"
        },
        body: JSON.stringify(demoUser)
      });

      if (!response.ok) {
        const detail = response.headers.get("content-type")?.includes("application/json")
          ? (await response.json()).detail
          : `Hosted users save failed (${response.status}).`;
        return;
      }
    }

    table.clearSelection();
    table.handleRefresh();
  }

  return (
    <EntityTable
      table={table}
      entityName="users"
      entitySingular="user"
      columns={userTableColumns}
      getCellDisplayValue={getUserColumnValue}
      renderCell={renderUserCell}
      defaultColumnWidths={["20%", "30%", "12%"]}
      extraToolbarButtons={devToolsVisible ? (
        <button className="ghost-button" type="button" onClick={handleSeedDemoUsers} disabled={!hostedWorkspaceReady}>
          Seed 200 Demo Users
        </button>
      ) : null}
    >
      {table.modalMode ? (
        <UserModal
          mode={table.modalMode}
          user={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          suggestions={table.suggestions}
          onClose={table.requestCloseModal}
          onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
          onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
          onSubmit={table.submitModal}
        />
      ) : null}
    </EntityTable>
  );
}
