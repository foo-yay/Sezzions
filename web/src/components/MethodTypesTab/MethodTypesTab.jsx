import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import MethodTypeModal from "./MethodTypeModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialMethodTypeForm,
  initialMethodTypeColumnFilters,
  methodTypeTableColumns,
  methodTypesPageSize,
  methodTypesFallbackPageSize
} from "./methodTypesConstants";
import { normalizeMethodTypeForm, getMethodTypeColumnValue } from "./methodTypesUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const methodTypesConfig = {
  entityName: "redemption_method_types",
  entitySingular: "method type",
  apiEndpoint: "/v1/workspace/redemption-method-types",
  responseKey: "redemption_method_types",
  batchDeleteIdKey: "redemption_method_type_ids",
  columns: methodTypeTableColumns,
  initialForm: initialMethodTypeForm,
  initialColumnFilters: initialMethodTypeColumnFilters,
  pageSize: methodTypesPageSize,
  fallbackPageSize: methodTypesFallbackPageSize,
  getColumnValue: getMethodTypeColumnValue,
  getCellDisplayValue: getMethodTypeColumnValue,
  searchFilter: (mt, text) =>
    mt.name.toLowerCase().includes(text)
    || (mt.notes || "").toLowerCase().includes(text),
  numericSortColumns: [],
  normalizeForm: normalizeMethodTypeForm,
  itemToForm: (mt) => ({
    name: mt.name || "",
    notes: mt.notes || "",
    is_active: Boolean(mt.is_active)
  }),
  formToPayload: (form, mode) => ({
    name: form.name,
    notes: form.notes || null,
    ...(mode === "edit" ? { is_active: form.is_active } : {})
  }),
  buildFilterOptions: (items) => ({
    name: buildGenericFilterOptions(items, "name", getMethodTypeColumnValue),
    status: [
      { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
      { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
    ],
    notes: buildGenericFilterOptions(items, "notes", getMethodTypeColumnValue)
  }),
  buildSuggestions: (items) => ({
    names: [...new Set(items.map((mt) => mt.name).filter(Boolean))]
  }),
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderMethodTypeCell(methodType, columnKey, search) {
  if (columnKey === "status") {
    return (
      <span className={methodType.is_active ? "status-chip active" : "status-chip inactive"}>
        {methodType.is_active ? "Active" : "Inactive"}
      </span>
    );
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(methodType.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={methodType[columnKey] || ""} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function MethodTypesTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(methodTypesConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="redemption_method_types"
      entitySingular="method type"
      columns={methodTypeTableColumns}
      getCellDisplayValue={getMethodTypeColumnValue}
      renderCell={renderMethodTypeCell}
      defaultColumnWidths={["30%", "12%"]}
    >
      {table.modalMode ? (
        <MethodTypeModal
          mode={table.modalMode}
          methodType={table.selectedItem}
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
