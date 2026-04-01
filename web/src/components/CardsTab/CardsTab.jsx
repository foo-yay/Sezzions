import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import CardModal from "./CardModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialCardForm,
  initialCardColumnFilters,
  cardTableColumns,
  cardsPageSize,
  cardsFallbackPageSize
} from "./cardsConstants";
import { normalizeCardForm, getCardColumnValue } from "./cardsUtils";

// ── Entity config ───────────────────────────────────────────────────────────

function getCardCellDisplayValue(card, columnKey) {
  if (columnKey === "status") return card.is_active ? "Active" : "Inactive";
  if (columnKey === "cashback_rate") {
    const rate = Number(card.cashback_rate);
    return Number.isFinite(rate) ? rate.toFixed(2) + "%" : "0.00%";
  }
  if (columnKey === "user_name") return card.user_name || "\u2014";
  if (columnKey === "last_four") return card.last_four || "\u2014";
  return String(card[columnKey] || "");
}

const cardsConfig = {
  entityName: "cards",
  entitySingular: "card",
  apiEndpoint: "/v1/workspace/cards",
  responseKey: "cards",
  batchDeleteIdKey: "card_ids",
  columns: cardTableColumns,
  initialForm: initialCardForm,
  initialColumnFilters: initialCardColumnFilters,
  pageSize: cardsPageSize,
  fallbackPageSize: cardsFallbackPageSize,
  getColumnValue: getCardColumnValue,
  getCellDisplayValue: getCardCellDisplayValue,
  searchFilter: (card, text) =>
    card.name.toLowerCase().includes(text)
    || (card.user_name || "").toLowerCase().includes(text)
    || (card.last_four || "").toLowerCase().includes(text)
    || (card.notes || "").toLowerCase().includes(text),
  numericSortColumns: ["cashback_rate"],
  normalizeForm: normalizeCardForm,
  itemToForm: (card) => ({
    name: card.name || "",
    user_id: card.user_id || "",
    last_four: card.last_four || "",
    cashback_rate: String(card.cashback_rate ?? "0"),
    notes: card.notes || "",
    is_active: Boolean(card.is_active)
  }),
  formToPayload: (form, mode) => ({
    name: form.name,
    user_id: form.user_id,
    last_four: form.last_four || null,
    cashback_rate: parseFloat(form.cashback_rate) || 0.0,
    notes: form.notes || null,
    ...(mode === "edit" ? { is_active: form.is_active } : {})
  }),
  buildFilterOptions: (cards) => {
    const options = {};
    for (const col of cardTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(cards, col.key, getCardColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: (cards) => ({
    names: [...new Set(cards.map((c) => c.name).filter(Boolean))]
  }),
  extraLoaders: [
    { key: "users", endpoint: "/v1/workspace/users?limit=500&offset=0", responseKey: "users" }
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderCardCell(card, columnKey, search) {
  if (columnKey === "status") {
    return (
      <span className={card.is_active ? "status-chip active" : "status-chip inactive"}>
        <HighlightMatch text={card.is_active ? "Active" : "Inactive"} query={search} />
      </span>
    );
  }
  if (columnKey === "cashback_rate") {
    return <HighlightMatch text={getCardCellDisplayValue(card, "cashback_rate")} query={search} />;
  }
  if (columnKey === "user_name") {
    return <HighlightMatch text={card.user_name || "\u2014"} query={search} />;
  }
  if (columnKey === "last_four") {
    return <HighlightMatch text={card.last_four || "\u2014"} query={search} />;
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(card.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={card[columnKey] || ""} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function CardsTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(cardsConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="cards"
      entitySingular="card"
      columns={cardTableColumns}
      getCellDisplayValue={getCardCellDisplayValue}
      renderCell={renderCardCell}
      defaultColumnWidths={["20%", "16%", "10%", "12%", "10%"]}
      defaultHeaderGridTemplate="36px 20% 16% 10% 12% 10% 1fr"
    >
      {table.modalMode ? (
        <CardModal
          mode={table.modalMode}
          card={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          suggestions={table.suggestions}
          users={table.extraData.users || []}
          onClose={table.requestCloseModal}
          onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
          onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
          onSubmit={table.submitModal}
        />
      ) : null}
    </EntityTable>
  );
}
