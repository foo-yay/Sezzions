export function normalizeMethodTypeForm(form) {
  return {
    name: form.name || "",
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

export function getMethodTypeColumnValue(methodType, columnKey) {
  if (columnKey === "status") {
    return methodType.is_active ? "Active" : "Inactive";
  }
  return String(methodType[columnKey] || "");
}
