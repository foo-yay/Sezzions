export function normalizeCardForm(form) {
  return {
    name: form.name || "",
    user_id: form.user_id || "",
    last_four: form.last_four || "",
    cashback_rate: String(form.cashback_rate ?? ""),
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

export function getCardColumnValue(card, columnKey) {
  if (columnKey === "status") return card.is_active ? "Active" : "Inactive";
  if (columnKey === "cashback_rate") {
    const rate = Number(card.cashback_rate);
    return Number.isFinite(rate) ? rate.toFixed(2) + "%" : "0.00%";
  }
  if (columnKey === "user_name") return card.user_name || "\u2014";
  if (columnKey === "last_four") return card.last_four || "\u2014";
  return String(card[columnKey] || "");
}
