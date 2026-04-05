function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (isNaN(num)) return String(value);
  return `$${num.toFixed(2)}`;
}

export function normalizePurchaseForm(form) {
  return {
    user_id: form.user_id || "",
    site_id: form.site_id || "",
    amount: form.amount ?? "",
    purchase_date: form.purchase_date || "",
    purchase_time: form.purchase_time || "",
    sc_received: form.sc_received ?? "",
    starting_sc_balance: form.starting_sc_balance ?? "",
    cashback_earned: form.cashback_earned ?? "",
    cashback_is_manual: Boolean(form.cashback_is_manual),
    card_id: form.card_id || "",
    notes: form.notes || "",
  };
}

export function getPurchaseColumnValue(purchase, columnKey) {
  if (columnKey === "status") {
    const s = (purchase.status || "active").toLowerCase();
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
  if (columnKey === "user_name") return purchase.user_name || "—";
  if (columnKey === "site_name") return purchase.site_name || "—";
  if (columnKey === "card_name") return purchase.card_name || "—";
  if (columnKey === "amount") return formatCurrency(purchase.amount);
  if (columnKey === "sc_received") return formatCurrency(purchase.sc_received);
  if (columnKey === "starting_sc_balance") return formatCurrency(purchase.starting_sc_balance);
  if (columnKey === "cashback_earned") return formatCurrency(purchase.cashback_earned);
  if (columnKey === "remaining_amount") return formatCurrency(purchase.remaining_amount);
  if (columnKey === "purchase_date") return purchase.purchase_date || "—";
  if (columnKey === "purchase_time") return purchase.purchase_time || "—";
  return String(purchase[columnKey] || "");
}
