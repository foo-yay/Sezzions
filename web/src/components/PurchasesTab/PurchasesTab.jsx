import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import PurchaseModal from "./PurchaseModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialPurchaseForm,
  initialPurchaseColumnFilters,
  purchaseTableColumns,
  purchasesPageSize,
  purchasesFallbackPageSize,
} from "./purchasesConstants";
import { normalizePurchaseForm, getPurchaseColumnValue } from "./purchasesUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const purchasesConfig = {
  entityName: "purchases",
  entitySingular: "purchase",
  apiEndpoint: "/v1/workspace/purchases",
  responseKey: "purchases",
  batchDeleteIdKey: "purchase_ids",
  columns: purchaseTableColumns,
  initialForm: initialPurchaseForm,
  initialColumnFilters: initialPurchaseColumnFilters,
  pageSize: purchasesPageSize,
  fallbackPageSize: purchasesFallbackPageSize,
  getColumnValue: getPurchaseColumnValue,
  getCellDisplayValue: getPurchaseColumnValue,
  searchFilter: (purchase, text) =>
    (purchase.user_name || "").toLowerCase().includes(text)
    || (purchase.site_name || "").toLowerCase().includes(text)
    || (purchase.card_name || "").toLowerCase().includes(text)
    || (purchase.purchase_date || "").toLowerCase().includes(text)
    || (purchase.notes || "").toLowerCase().includes(text)
    || (purchase.amount || "").includes(text),
  numericSortColumns: ["amount", "sc_received", "starting_sc_balance", "cashback_earned", "remaining_amount"],
  normalizeForm: normalizePurchaseForm,
  itemToForm: (purchase) => ({
    user_id: purchase.user_id || "",
    site_id: purchase.site_id || "",
    amount: purchase.amount ?? "",
    purchase_date: purchase.purchase_date || "",
    purchase_time: purchase.purchase_time || "",
    sc_received: purchase.sc_received ?? "",
    starting_sc_balance: purchase.starting_sc_balance ?? "",
    cashback_earned: purchase.cashback_earned ?? "",
    cashback_is_manual: Boolean(purchase.cashback_is_manual),
    card_id: purchase.card_id || "",
    notes: purchase.notes || "",
  }),
  formToPayload: (form, mode) => ({
    user_id: form.user_id || null,
    site_id: form.site_id || null,
    amount: form.amount || null,
    purchase_date: form.purchase_date || null,
    card_id: form.card_id || null,
    starting_sc_balance: form.starting_sc_balance || "0.00",
    purchase_time: form.purchase_time || null,
    sc_received: form.sc_received || null,
    cashback_earned: form.cashback_earned || "0.00",
    cashback_is_manual: Boolean(form.cashback_is_manual),
    notes: form.notes || null,
    ...(mode === "edit" ? { status: "active" } : {}),
  }),
  buildFilterOptions: (items) => {
    const options = {};
    for (const col of purchaseTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Dormant", label: "Dormant", path: ["Dormant"], searchValue: "Dormant" },
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(items, col.key, getPurchaseColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: () => ({}),
  extraLoaders: [
    { key: "users", endpoint: "/v1/workspace/users?limit=500&offset=0", responseKey: "users" },
    { key: "sites", endpoint: "/v1/workspace/sites?limit=500&offset=0", responseKey: "sites" },
    { key: "cards", endpoint: "/v1/workspace/cards?limit=500&offset=0", responseKey: "cards" },
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderPurchaseCell(purchase, columnKey, search) {
  if (columnKey === "status") {
    const statusLabel = getPurchaseColumnValue(purchase, "status");
    const statusClass = statusLabel === "Active" ? "status-chip active" : "status-chip inactive";
    return (
      <span className={statusClass}>
        <HighlightMatch text={statusLabel} query={search} />
      </span>
    );
  }
  if (columnKey === "user_name" || columnKey === "site_name" || columnKey === "card_name") {
    return <HighlightMatch text={getPurchaseColumnValue(purchase, columnKey)} query={search} />;
  }
  if (["amount", "sc_received", "starting_sc_balance", "cashback_earned", "remaining_amount"].includes(columnKey)) {
    return <span>{getPurchaseColumnValue(purchase, columnKey)}</span>;
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(purchase.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={getPurchaseColumnValue(purchase, columnKey)} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function PurchasesTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(purchasesConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="purchases"
      entitySingular="purchase"
      columns={purchaseTableColumns}
      getCellDisplayValue={getPurchaseColumnValue}
      renderCell={renderPurchaseCell}
      defaultColumnWidths={["110px", "100px", "100px", "100px", "125px", "160px", "100px", "110px", "115px", "90px"]}
      defaultHeaderGridTemplate="36px 110px 100px 100px 100px 125px 160px 100px 110px 115px 90px 1fr"
    >
      {table.modalMode ? (
        <PurchaseModal
          mode={table.modalMode}
          purchase={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          users={table.extraData.users || []}
          sites={table.extraData.sites || []}
          cards={table.extraData.cards || []}
          apiBaseUrl={apiBaseUrl}
          onClose={table.requestCloseModal}
          onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
          onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
          onSubmit={table.submitModal}
        />
      ) : null}
    </EntityTable>
  );
}
