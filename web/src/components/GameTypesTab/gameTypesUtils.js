export function normalizeGameTypeForm(form) {
  return {
    name: form.name || "",
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

export function getGameTypeColumnValue(gameType, columnKey) {
  if (columnKey === "status") {
    return gameType.is_active ? "Active" : "Inactive";
  }
  return String(gameType[columnKey] || "");
}
