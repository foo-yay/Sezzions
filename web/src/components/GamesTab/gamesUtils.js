export function normalizeGameForm(form) {
  return {
    name: form.name || "",
    game_type_id: form.game_type_id || "",
    rtp: form.rtp ?? "",
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

function formatRtp(value) {
  if (value === null || value === undefined || value === "" || value === 0) return "\u2014";
  return `${Number(value).toFixed(2)}%`;
}

export function getGameColumnValue(game, columnKey) {
  if (columnKey === "status") return game.is_active ? "Active" : "Inactive";
  if (columnKey === "game_type_name") return game.game_type_name || "\u2014";
  if (columnKey === "rtp") return formatRtp(game.rtp);
  if (columnKey === "actual_rtp") return formatRtp(game.actual_rtp);
  return String(game[columnKey] || "");
}
