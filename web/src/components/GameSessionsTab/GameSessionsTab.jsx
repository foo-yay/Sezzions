import { useCallback, useState } from "react";
import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import GameSessionModal from "./GameSessionModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialGameSessionForm,
  initialGameSessionColumnFilters,
  gameSessionTableColumns,
  gameSessionsPageSize,
  gameSessionsFallbackPageSize,
} from "./gameSessionsConstants";
import { normalizeGameSessionForm, getGameSessionColumnValue } from "./gameSessionsUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const gameSessionsConfig = {
  entityName: "game_sessions",
  entitySingular: "game session",
  apiEndpoint: "/v1/workspace/game-sessions",
  responseKey: "game_sessions",
  batchDeleteIdKey: "game_session_ids",
  columns: gameSessionTableColumns,
  initialForm: initialGameSessionForm,
  initialColumnFilters: initialGameSessionColumnFilters,
  pageSize: gameSessionsPageSize,
  fallbackPageSize: gameSessionsFallbackPageSize,
  getColumnValue: getGameSessionColumnValue,
  getCellDisplayValue: getGameSessionColumnValue,
  searchFilter: (gs, text) =>
    (gs.user_name || "").toLowerCase().includes(text)
    || (gs.site_name || "").toLowerCase().includes(text)
    || (gs.game_name || "").toLowerCase().includes(text)
    || (gs.session_date || "").toLowerCase().includes(text)
    || (gs.status || "").toLowerCase().includes(text)
    || (gs.notes || "").toLowerCase().includes(text),
  numericSortColumns: [
    "starting_balance", "ending_balance",
    "starting_redeemable", "ending_redeemable",
    "net_taxable_pl", "wager_amount",
  ],
  getItemLabel: (gs) => `${gs.session_date || "unknown"} — ${gs.user_name || "unknown"} @ ${gs.site_name || "unknown"}`,
  normalizeForm: normalizeGameSessionForm,
  itemToForm: (gs) => ({
    user_id: gs.user_id || "",
    site_id: gs.site_id || "",
    session_date: gs.session_date || "",
    session_time: gs.session_time || "",
    game_id: gs.game_id || "",
    game_type_id: gs.game_type_id || "",
    end_date: gs.end_date || "",
    end_time: gs.end_time || "",
    starting_balance: gs.starting_balance ?? "",
    ending_balance: gs.ending_balance ?? "",
    starting_redeemable: gs.starting_redeemable ?? "",
    ending_redeemable: gs.ending_redeemable ?? "",
    wager_amount: gs.wager_amount ?? "",
    rtp: gs.rtp ?? "",
    purchases_during: gs.purchases_during ?? "",
    redemptions_during: gs.redemptions_during ?? "",
    status: gs.status || "Active",
    notes: gs.notes || "",
  }),
  formToPayload: (form, mode) => ({
    user_id: form.user_id || null,
    site_id: form.site_id || null,
    session_date: form.session_date || null,
    session_time: form.session_time || null,
    game_id: form.game_id || null,
    game_type_id: form.game_type_id || null,
    end_date: form.end_date || null,
    end_time: form.end_time || null,
    starting_balance: form.starting_balance || "0.00",
    ending_balance: form.ending_balance || "0.00",
    starting_redeemable: form.starting_redeemable || "0.00",
    ending_redeemable: form.ending_redeemable || "0.00",
    wager_amount: form.wager_amount || "0.00",
    rtp: form.rtp ? parseFloat(form.rtp) : null,
    purchases_during: form.purchases_during || "0.00",
    redemptions_during: form.redemptions_during || "0.00",
    status: form.status || "Active",
    notes: form.notes || null,
  }),
  buildFilterOptions: (items) => {
    const options = {};
    for (const col of gameSessionTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Closed", label: "Closed", path: ["Closed"], searchValue: "Closed" },
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(items, col.key, getGameSessionColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: () => ({}),
  extraLoaders: [
    { key: "users", endpoint: "/v1/workspace/users?limit=500&offset=0", responseKey: "users" },
    { key: "sites", endpoint: "/v1/workspace/sites?limit=500&offset=0", responseKey: "sites" },
    { key: "games", endpoint: "/v1/workspace/games?limit=500&offset=0", responseKey: "games" },
    { key: "gameTypes", endpoint: "/v1/workspace/game-types?limit=500&offset=0", responseKey: "game_types" },
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderGameSessionCell(gs, columnKey, search) {
  if (columnKey === "status") {
    const label = getGameSessionColumnValue(gs, "status");
    const cls = label === "Active" ? "status-chip active" : "status-chip inactive";
    return (
      <span className={cls}>
        <HighlightMatch text={label} query={search} />
      </span>
    );
  }
  if (columnKey === "net_taxable_pl") {
    const val = getGameSessionColumnValue(gs, columnKey);
    const num = Number(gs.net_taxable_pl);
    const cls = isNaN(num) ? "" : num >= 0 ? "pl-positive" : "pl-negative";
    return <span className={cls}>{val}</span>;
  }
  if (["starting_balance", "ending_balance", "starting_redeemable", "ending_redeemable"].includes(columnKey)) {
    return <span>{getGameSessionColumnValue(gs, columnKey)}</span>;
  }
  if (columnKey === "user_name" || columnKey === "site_name" || columnKey === "game_name") {
    return <HighlightMatch text={getGameSessionColumnValue(gs, columnKey)} query={search} />;
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={getGameSessionColumnValue(gs, columnKey)} query={search} />;
  }
  return <HighlightMatch text={getGameSessionColumnValue(gs, columnKey)} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function GameSessionsTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const [activeOnly, setActiveOnly] = useState(false);

  const quickFilter = useCallback(
    (gs) => {
      if (activeOnly && gs.status !== "Active") return false;
      return true;
    },
    [activeOnly],
  );

  const table = useEntityTable(gameSessionsConfig, { apiBaseUrl, hostedWorkspaceReady, quickFilter });

  const quickFilterRow = (
    <label className="quick-filter-check" title="Show only active (open) sessions">
      <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
      Active Only
    </label>
  );

  return (
    <EntityTable
      table={table}
      entityName="game_sessions"
      entitySingular="game session"
      columns={gameSessionTableColumns}
      getCellDisplayValue={getGameSessionColumnValue}
      renderCell={renderGameSessionCell}
      defaultColumnWidths={["110px", "100px", "100px", "100px", "80px", "100px", "100px", "110px", "110px", "100px"]}
      defaultHeaderGridTemplate="36px 110px 100px 100px 100px 80px 100px 100px 110px 110px 100px 1fr"
      extraToolbarRow={quickFilterRow}
    >
      {table.modalMode ? (
        <GameSessionModal
          mode={table.modalMode}
          gameSession={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          users={table.extraData.users || []}
          sites={table.extraData.sites || []}
          games={table.extraData.games || []}
          gameTypes={table.extraData.gameTypes || []}
          apiBaseUrl={apiBaseUrl}
          onClose={table.requestCloseModal}
          onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
          onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
          onSubmit={table.submitModal}
          onEndAndStartNew={(closedSession) => {
            // After closing the current session, open a "create" modal pre-filled
            // with the closed session's ending state
            table.openModal("create");
            table.setForm((prev) => ({
              ...prev,
              user_id: closedSession.user_id || "",
              site_id: closedSession.site_id || "",
              game_id: closedSession.game_id || "",
              game_type_id: closedSession.game_type_id || "",
              starting_balance: closedSession.ending_balance || "",
              starting_redeemable: closedSession.ending_redeemable || "",
            }));
            table.handleRefresh();
          }}
        />
      ) : null}
    </EntityTable>
  );
}
