import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import RedemptionMethodModal from "./RedemptionMethodModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialRedemptionMethodForm,
  initialRedemptionMethodColumnFilters,
  redemptionMethodTableColumns,
  redemptionMethodsPageSize,
  redemptionMethodsFallbackPageSize
} from "./redemptionMethodsConstants";
import { normalizeRedemptionMethodForm, getRedemptionMethodColumnValue } from "./redemptionMethodsUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const redemptionMethodsConfig = {
  entityName: "redemption_methods",
  entitySingular: "redemption method",
  apiEndpoint: "/v1/workspace/redemption-methods",
  responseKey: "redemption_methods",
  batchDeleteIdKey: "redemption_method_ids",
  columns: redemptionMethodTableColumns,
  initialForm: initialRedemptionMethodForm,
  initialColumnFilters: initialRedemptionMethodColumnFilters,
  pageSize: redemptionMethodsPageSize,
  fallbackPageSize: redemptionMethodsFallbackPageSize,
  getColumnValue: getRedemptionMethodColumnValue,
  getCellDisplayValue: getRedemptionMethodColumnValue,
  searchFilter: (method, text) =>
    method.name.toLowerCase().includes(text)
    || (method.method_type_name || "").toLowerCase().includes(text)
    || (method.user_name || "").toLowerCase().includes(text)
    || (method.notes || "").toLowerCase().includes(text),
  numericSortColumns: [],
  normalizeForm: normalizeRedemptionMethodForm,
  itemToForm: (method) => ({
    name: method.name || "",
    method_type_id: method.method_type_id || "",
    user_id: method.user_id || "",
    notes: method.notes || "",
    is_active: Boolean(method.is_active)
  }),
  formToPayload: (form, mode) => ({
    name: form.name,
    method_type_id: form.method_type_id || null,
    user_id: form.user_id || null,
    notes: form.notes || null,
    ...(mode === "edit" ? { is_active: form.is_active } : {})
  }),
  buildFilterOptions: (items) => {
    const options = {};
    for (const col of redemptionMethodTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(items, col.key, getRedemptionMethodColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: (items) => ({
    names: [...new Set(items.map((m) => m.name).filter(Boolean))]
  }),
  extraLoaders: [
    { key: "users", endpoint: "/v1/workspace/users?limit=500&offset=0", responseKey: "users" },
    { key: "methodTypes", endpoint: "/v1/workspace/redemption-method-types?limit=500&offset=0", responseKey: "redemption_method_types" }
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderRedemptionMethodCell(method, columnKey, search) {
  if (columnKey === "status") {
    return (
      <span className={method.is_active ? "status-chip active" : "status-chip inactive"}>
        <HighlightMatch text={method.is_active ? "Active" : "Inactive"} query={search} />
      </span>
    );
  }
  if (columnKey === "method_type_name") {
    return <HighlightMatch text={method.method_type_name || "\u2014"} query={search} />;
  }
  if (columnKey === "user_name") {
    return <HighlightMatch text={method.user_name || "\u2014"} query={search} />;
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(method.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={method[columnKey] || ""} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function RedemptionMethodsTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(redemptionMethodsConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="redemption_methods"
      entitySingular="redemption method"
      columns={redemptionMethodTableColumns}
      getCellDisplayValue={getRedemptionMethodColumnValue}
      renderCell={renderRedemptionMethodCell}
      defaultColumnWidths={["22%", "16%", "16%", "10%"]}
      defaultHeaderGridTemplate="36px 22% 16% 16% 10% 1fr"
    >
      {table.modalMode ? (
        <RedemptionMethodModal
          mode={table.modalMode}
          method={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          suggestions={table.suggestions}
          users={table.extraData.users || []}
          methodTypes={table.extraData.methodTypes || []}
          onClose={table.requestCloseModal}
          onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
          onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
          onSubmit={table.submitModal}
        />
      ) : null}
    </EntityTable>
  );
}
