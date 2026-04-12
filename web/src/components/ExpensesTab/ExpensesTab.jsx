import { useMemo } from "react";
import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import ExpenseModal from "./ExpenseModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialExpenseForm,
  initialExpenseColumnFilters,
  expenseTableColumns,
  expensesPageSize,
  expensesFallbackPageSize,
} from "./expensesConstants";
import { normalizeExpenseForm, getExpenseColumnValue } from "./expensesUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const expensesConfig = {
  entityName: "expenses",
  entitySingular: "expense",
  apiEndpoint: "/v1/workspace/expenses",
  responseKey: "expenses",
  batchDeleteIdKey: "expense_ids",
  columns: expenseTableColumns,
  initialForm: initialExpenseForm,
  initialColumnFilters: initialExpenseColumnFilters,
  pageSize: expensesPageSize,
  fallbackPageSize: expensesFallbackPageSize,
  getColumnValue: getExpenseColumnValue,
  getCellDisplayValue: getExpenseColumnValue,
  searchFilter: (expense, text) =>
    (expense.vendor || "").toLowerCase().includes(text)
    || (expense.category || "").toLowerCase().includes(text)
    || (expense.user_name || "").toLowerCase().includes(text)
    || (expense.expense_date || "").toLowerCase().includes(text)
    || (expense.description || "").toLowerCase().includes(text)
    || (expense.notes || "").toLowerCase().includes(text)
    || (expense.amount || "").includes(text),
  numericSortColumns: ["amount"],
  getItemLabel: (e) => `${e.expense_date || "unknown"} — ${e.vendor || "unknown"}`,
  normalizeForm: normalizeExpenseForm,
  itemToForm: (expense) => ({
    expense_date: expense.expense_date || "",
    expense_time: expense.expense_time || "",
    amount: expense.amount ?? "",
    vendor: expense.vendor || "",
    description: expense.description || "",
    category: expense.category || "",
    user_id: expense.user_id || "",
    notes: expense.notes || "",
  }),
  formToPayload: (form) => ({
    expense_date: form.expense_date || null,
    amount: form.amount || null,
    vendor: form.vendor?.trim() || null,
    expense_time: form.expense_time || null,
    description: form.description?.trim() || null,
    category: form.category || null,
    user_id: form.user_id || null,
    notes: form.notes?.trim() || null,
  }),
  buildFilterOptions: (items) => {
    const options = {};
    for (const col of expenseTableColumns) {
      options[col.key] = buildGenericFilterOptions(items, col.key, getExpenseColumnValue);
    }
    return options;
  },
  buildSuggestions: (items) => {
    const vendors = [...new Set(items.map((e) => e.vendor).filter(Boolean))].sort();
    const categories = [...new Set(items.map((e) => e.category).filter(Boolean))].sort();
    const notes = [...new Set(
      items.map((e) => e.notes || e.description).filter(Boolean),
    )].slice(0, 50);
    return { vendors, categories, notes };
  },
  extraLoaders: [
    { key: "users", endpoint: "/v1/workspace/users?limit=500&offset=0", responseKey: "users" },
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderExpenseCell(expense, columnKey, search) {
  if (columnKey === "user_name") {
    return <HighlightMatch text={getExpenseColumnValue(expense, columnKey)} query={search} />;
  }
  if (columnKey === "amount") {
    return <span>{getExpenseColumnValue(expense, columnKey)}</span>;
  }
  if (columnKey === "notes") {
    const text = expense.notes || expense.description || "";
    return <HighlightMatch text={(text).slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={getExpenseColumnValue(expense, columnKey)} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function ExpensesTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(expensesConfig, { apiBaseUrl, hostedWorkspaceReady });

  const suggestions = useMemo(
    () => expensesConfig.buildSuggestions(table.items || []),
    [table.items],
  );

  return (
    <EntityTable
      table={table}
      entityName="expenses"
      entitySingular="expense"
      columns={expenseTableColumns}
      getCellDisplayValue={getExpenseColumnValue}
      renderCell={renderExpenseCell}
      defaultColumnWidths={["110px", "180px", "160px", "120px", "110px", "1fr"]}
      defaultHeaderGridTemplate="36px 110px 180px 160px 120px 110px 1fr"
    >
      {table.modalMode ? (
        <ExpenseModal
          mode={table.modalMode}
          expense={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          users={table.extraData.users || []}
          suggestions={suggestions}
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
