function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (isNaN(num)) return String(value);
  return `$${num.toFixed(2)}`;
}

export function normalizeRedemptionForm(form) {
  return {
    user_id: form.user_id || "",
    site_id: form.site_id || "",
    amount: form.amount ?? "",
    fees: form.fees ?? "",
    redemption_date: form.redemption_date || "",
    redemption_time: form.redemption_time || "",
    redemption_method_type_id: form.redemption_method_type_id || "",
    redemption_method_id: form.redemption_method_id || "",
    receipt_date: form.receipt_date || "",
    processed: Boolean(form.processed),
    more_remaining: Boolean(form.more_remaining),
    notes: form.notes || "",
  };
}

export function getRedemptionColumnValue(redemption, columnKey) {
  if (columnKey === "redemption_date") {
    const date = redemption.redemption_date || "—";
    const time = redemption.redemption_time || "";
    return time ? `${date} ${time}` : date;
  }
  if (columnKey === "user_name") return redemption.user_name || "—";
  if (columnKey === "site_name") return redemption.site_name || "—";
  if (columnKey === "method_name") return redemption.method_name || "—";
  if (columnKey === "amount") return formatCurrency(redemption.amount);
  if (columnKey === "fees") return formatCurrency(redemption.fees);
  if (columnKey === "cost_basis") return formatCurrency(redemption.cost_basis);
  if (columnKey === "unbased") {
    const amount = Number(redemption.amount);
    const costBasis = Number(redemption.cost_basis);
    if (isNaN(amount) || redemption.cost_basis === null || redemption.cost_basis === undefined) return "—";
    const unbased = Math.max(0, amount - costBasis);
    return formatCurrency(unbased);
  }
  if (columnKey === "receipt_date") {
    if (redemption.status === "CANCELED") return "CANCELED";
    if (redemption.status === "PENDING_CANCEL") return "PENDING CANCEL";
    if (redemption.receipt_date) return redemption.receipt_date;
    return "PENDING";
  }
  if (columnKey === "more_remaining") return redemption.more_remaining ? "Partial" : "Full";
  if (columnKey === "processed") return redemption.processed ? "✓" : "";
  return String(redemption[columnKey] || "");
}
