import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import RedemptionModal from "./RedemptionModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialRedemptionForm,
  initialRedemptionColumnFilters,
  redemptionTableColumns,
  redemptionsPageSize,
  redemptionsFallbackPageSize,
} from "./redemptionsConstants";
import { normalizeRedemptionForm, getRedemptionColumnValue } from "./redemptionsUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const redemptionsConfig = {
  entityName: "redemptions",
  entitySingular: "redemption",
  apiEndpoint: "/v1/workspace/redemptions",
  responseKey: "redemptions",
  batchDeleteIdKey: "redemption_ids",
  columns: redemptionTableColumns,
  initialForm: initialRedemptionForm,
  initialColumnFilters: initialRedemptionColumnFilters,
  pageSize: redemptionsPageSize,
  fallbackPageSize: redemptionsFallbackPageSize,
  getColumnValue: getRedemptionColumnValue,
  getCellDisplayValue: getRedemptionColumnValue,
  searchFilter: (redemption, text) =>
    (redemption.user_name || "").toLowerCase().includes(text)
    || (redemption.site_name || "").toLowerCase().includes(text)
    || (redemption.method_name || "").toLowerCase().includes(text)
    || (redemption.redemption_date || "").toLowerCase().includes(text)
    || (redemption.status || "").toLowerCase().includes(text)
    || (redemption.notes || "").toLowerCase().includes(text)
    || (redemption.amount || "").includes(text),
  numericSortColumns: ["amount", "fees", "cost_basis", "net_pl"],
  normalizeForm: normalizeRedemptionForm,
  itemToForm: (redemption) => ({
    user_id: redemption.user_id || "",
    site_id: redemption.site_id || "",
    amount: redemption.amount ?? "",
    fees: redemption.fees ?? "",
    redemption_date: redemption.redemption_date || "",
    redemption_time: redemption.redemption_time || "",
    redemption_method_type_id: redemption.method_type_id || "",
    redemption_method_id: redemption.redemption_method_id || "",
    receipt_date: redemption.receipt_date || "",
    processed: Boolean(redemption.processed),
    more_remaining: Boolean(redemption.more_remaining),
    notes: redemption.notes || "",
  }),
  formToPayload: (form, mode) => ({
    user_id: form.user_id || null,
    site_id: form.site_id || null,
    amount: form.amount || null,
    redemption_date: form.redemption_date || null,
    redemption_time: form.redemption_time || null,
    redemption_method_id: form.redemption_method_id || null,
    fees: form.fees || "0.00",
    receipt_date: form.receipt_date || null,
    processed: Boolean(form.processed),
    more_remaining: Boolean(form.more_remaining),
    notes: form.notes || null,
    ...(mode === "edit" ? { status: "PENDING" } : {}),
  }),
  buildFilterOptions: (items) => {
    const options = {};
    for (const col of redemptionTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "PENDING", label: "Pending", path: ["PENDING"], searchValue: "PENDING" },
          { value: "CANCELED", label: "Canceled", path: ["CANCELED"], searchValue: "CANCELED" },
          { value: "PENDING_CANCEL", label: "Pending Cancel", path: ["PENDING_CANCEL"], searchValue: "PENDING_CANCEL" },
        ];
      } else if (col.key === "more_remaining") {
        options[col.key] = [
          { value: "Full", label: "Full", path: ["Full"], searchValue: "Full" },
          { value: "Partial", label: "Partial", path: ["Partial"], searchValue: "Partial" },
        ];
      } else if (col.key === "processed") {
        options[col.key] = [
          { value: "Yes", label: "Yes", path: ["Yes"], searchValue: "Yes" },
          { value: "No", label: "No", path: ["No"], searchValue: "No" },
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(items, col.key, getRedemptionColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: () => ({}),
  extraLoaders: [
    { key: "users", endpoint: "/v1/workspace/users?limit=500&offset=0", responseKey: "users" },
    { key: "sites", endpoint: "/v1/workspace/sites?limit=500&offset=0", responseKey: "sites" },
    { key: "methodTypes", endpoint: "/v1/workspace/redemption-method-types?limit=500&offset=0", responseKey: "redemption_method_types" },
    { key: "redemptionMethods", endpoint: "/v1/workspace/redemption-methods?limit=500&offset=0", responseKey: "redemption_methods" },
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderRedemptionCell(redemption, columnKey, search) {
  if (columnKey === "status") {
    const statusLabel = getRedemptionColumnValue(redemption, "status");
    const statusClass = statusLabel === "PENDING"
      ? "status-chip active"
      : statusLabel === "CANCELED"
        ? "status-chip inactive"
        : "status-chip";
    return (
      <span className={statusClass}>
        <HighlightMatch text={statusLabel} query={search} />
      </span>
    );
  }
  if (columnKey === "net_pl") {
    const val = Number(redemption.net_pl);
    const display = getRedemptionColumnValue(redemption, "net_pl");
    if (!isNaN(val) && val !== 0) {
      const color = val > 0 ? "var(--success-color, #4caf50)" : "var(--danger-color, #f44336)";
      return <span style={{ color }}>{display}</span>;
    }
    return <span>{display}</span>;
  }
  if (["amount", "fees", "cost_basis"].includes(columnKey)) {
    return <span>{getRedemptionColumnValue(redemption, columnKey)}</span>;
  }
  if (columnKey === "user_name" || columnKey === "site_name" || columnKey === "method_name") {
    return <HighlightMatch text={getRedemptionColumnValue(redemption, columnKey)} query={search} />;
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(redemption.notes || "").slice(0, 100) || "—"} query={search} />;
  }
  return <HighlightMatch text={getRedemptionColumnValue(redemption, columnKey)} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function RedemptionsTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(redemptionsConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="redemptions"
      entitySingular="redemption"
      columns={redemptionTableColumns}
      getCellDisplayValue={getRedemptionColumnValue}
      renderCell={renderRedemptionCell}
      defaultColumnWidths={["9%", "10%", "10%", "9%", "7%", "10%", "7%", "8%", "9%", "8%", "8%", "1fr"]}
      defaultHeaderGridTemplate="36px 9% 10% 10% 9% 7% 10% 7% 8% 9% 8% 8% 1fr"
    >
      {table.modalMode ? (
        <RedemptionModal
          mode={table.modalMode}
          redemption={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          users={table.extraData.users || []}
          sites={table.extraData.sites || []}
          redemptionMethods={table.extraData.redemptionMethods || []}
          methodTypes={table.extraData.methodTypes || []}
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
