function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (isNaN(num)) return String(value);
  return `$${num.toFixed(2)}`;
}

export function normalizeExpenseForm(form) {
  return {
    expense_date: form.expense_date || "",
    expense_time: form.expense_time || "",
    amount: form.amount ?? "",
    vendor: form.vendor || "",
    description: form.description || "",
    category: form.category || "",
    user_id: form.user_id || "",
    notes: form.notes || "",
  };
}

export function getExpenseColumnValue(expense, columnKey) {
  if (columnKey === "expense_date") return expense.expense_date || "—";
  if (columnKey === "category") return expense.category || "—";
  if (columnKey === "vendor") return expense.vendor || "—";
  if (columnKey === "user_name") return expense.user_name || "—";
  if (columnKey === "amount") return formatCurrency(expense.amount);
  if (columnKey === "notes") return expense.notes || expense.description || "—";
  return String(expense[columnKey] || "");
}
