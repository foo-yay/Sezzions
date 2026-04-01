export function normalizeSiteForm(form) {
  return {
    name: form.name || "",
    url: form.url || "",
    sc_rate: String(form.sc_rate ?? "1"),
    playthrough_requirement: String(form.playthrough_requirement ?? "1"),
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

export function getSiteColumnValue(site, columnKey) {
  if (columnKey === "status") return site.is_active ? "Active" : "Inactive";
  if (columnKey === "sc_rate") return String(site.sc_rate ?? "");
  if (columnKey === "playthrough_requirement") return String(site.playthrough_requirement ?? "");
  return String(site[columnKey] || "");
}
