import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import GameModal from "./GameModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialGameForm,
  initialGameColumnFilters,
  gameTableColumns,
  gamesPageSize,
  gamesFallbackPageSize
} from "./gamesConstants";
import { normalizeGameForm, getGameColumnValue } from "./gamesUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const gamesConfig = {
  entityName: "games",
  entitySingular: "game",
  apiEndpoint: "/v1/workspace/games",
  responseKey: "games",
  batchDeleteIdKey: "game_ids",
  columns: gameTableColumns,
  initialForm: initialGameForm,
  initialColumnFilters: initialGameColumnFilters,
  pageSize: gamesPageSize,
  fallbackPageSize: gamesFallbackPageSize,
  getColumnValue: getGameColumnValue,
  getCellDisplayValue: getGameColumnValue,
  searchFilter: (game, text) =>
    game.name.toLowerCase().includes(text)
    || (game.game_type_name || "").toLowerCase().includes(text)
    || (game.notes || "").toLowerCase().includes(text),
  numericSortColumns: ["rtp", "actual_rtp"],
  normalizeForm: normalizeGameForm,
  itemToForm: (game) => ({
    name: game.name || "",
    game_type_id: game.game_type_id || "",
    rtp: game.rtp ?? "",
    notes: game.notes || "",
    is_active: Boolean(game.is_active)
  }),
  formToPayload: (form, mode) => ({
    name: form.name,
    game_type_id: form.game_type_id || null,
    rtp: form.rtp !== "" && form.rtp !== null ? Number(form.rtp) : null,
    notes: form.notes || null,
    ...(mode === "edit" ? { is_active: form.is_active } : {})
  }),
  buildFilterOptions: (items) => {
    const options = {};
    for (const col of gameTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(items, col.key, getGameColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: (items) => ({
    names: [...new Set(items.map((g) => g.name).filter(Boolean))]
  }),
  extraLoaders: [
    { key: "gameTypes", endpoint: "/v1/workspace/game-types?limit=500&offset=0", responseKey: "game_types" }
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderGameCell(game, columnKey, search) {
  if (columnKey === "status") {
    return (
      <span className={game.is_active ? "status-chip active" : "status-chip inactive"}>
        <HighlightMatch text={game.is_active ? "Active" : "Inactive"} query={search} />
      </span>
    );
  }
  if (columnKey === "game_type_name") {
    return <HighlightMatch text={game.game_type_name || "\u2014"} query={search} />;
  }
  if (columnKey === "rtp" || columnKey === "actual_rtp") {
    return <span>{getGameColumnValue(game, columnKey)}</span>;
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(game.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={game[columnKey] || ""} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function GamesTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(gamesConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="games"
      entitySingular="game"
      columns={gameTableColumns}
      getCellDisplayValue={getGameColumnValue}
      renderCell={renderGameCell}
      defaultColumnWidths={["22%", "14%", "12%", "12%", "10%"]}
      defaultHeaderGridTemplate="36px 22% 14% 12% 12% 10% 1fr"
    >
      {table.modalMode ? (
        <GameModal
          mode={table.modalMode}
          game={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          suggestions={table.suggestions}
          gameTypes={table.extraData.gameTypes || []}
          onClose={table.requestCloseModal}
          onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
          onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
          onSubmit={table.submitModal}
        />
      ) : null}
    </EntityTable>
  );
}
