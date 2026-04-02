export function normalizeRedemptionMethodForm(form) {
  return {
    name: form.name || "",
    method_type_id: form.method_type_id || "",
    user_id: form.user_id || "",
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

export function getRedemptionMethodColumnValue(method, columnKey) {
  if (columnKey === "status") return method.is_active ? "Active" : "Inactive";
  if (columnKey === "method_type_name") return method.method_type_name || "\u2014";
  if (columnKey === "user_name") return method.user_name || "\u2014";
  return String(method[columnKey] || "");
}
