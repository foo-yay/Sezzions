import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import GameTypeModal from "./GameTypeModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialGameTypeForm,
  initialGameTypeColumnFilters,
  gameTypeTableColumns,
  gameTypesPageSize,
  gameTypesFallbackPageSize
} from "./gameTypesConstants";
import { normalizeGameTypeForm, getGameTypeColumnValue } from "./gameTypesUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const gameTypesConfig = {
  entityName: "game_types",
  entitySingular: "game type",
  apiEndpoint: "/v1/workspace/game-types",
  responseKey: "game_types",
  batchDeleteIdKey: "game_type_ids",
  columns: gameTypeTableColumns,
  initialForm: initialGameTypeForm,
  initialColumnFilters: initialGameTypeColumnFilters,
  pageSize: gameTypesPageSize,
  fallbackPageSize: gameTypesFallbackPageSize,
  getColumnValue: getGameTypeColumnValue,
  getCellDisplayValue: getGameTypeColumnValue,
  searchFilter: (gt, text) =>
    gt.name.toLowerCase().includes(text)
    || (gt.notes || "").toLowerCase().includes(text),
  numericSortColumns: [],
  normalizeForm: normalizeGameTypeForm,
  itemToForm: (gt) => ({
    name: gt.name || "",
    notes: gt.notes || "",
    is_active: Boolean(gt.is_active)
  }),
  formToPayload: (form, mode) => ({
    name: form.name,
    notes: form.notes || null,
    ...(mode === "edit" ? { is_active: form.is_active } : {})
  }),
  buildFilterOptions: (items) => ({
    name: buildGenericFilterOptions(items, "name", getGameTypeColumnValue),
    status: [
      { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
      { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
    ],
    notes: buildGenericFilterOptions(items, "notes", getGameTypeColumnValue)
  }),
  buildSuggestions: (items) => ({
    names: [...new Set(items.map((gt) => gt.name).filter(Boolean))]
  }),
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderGameTypeCell(gameType, columnKey, search) {
  if (columnKey === "status") {
    return (
      <span className={gameType.is_active ? "status-chip active" : "status-chip inactive"}>
        {gameType.is_active ? "Active" : "Inactive"}
      </span>
    );
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(gameType.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={gameType[columnKey] || ""} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function GameTypesTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(gameTypesConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="game_types"
      entitySingular="game type"
      columns={gameTypeTableColumns}
      getCellDisplayValue={getGameTypeColumnValue}
      renderCell={renderGameTypeCell}
      defaultColumnWidths={["30%", "12%"]}
    >
      {table.modalMode ? (
        <GameTypeModal
          mode={table.modalMode}
          gameType={table.selectedItem}
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
