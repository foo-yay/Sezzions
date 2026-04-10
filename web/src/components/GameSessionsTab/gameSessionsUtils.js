function formatCurrency(value) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (isNaN(num)) return String(value);
  return `$${num.toFixed(2)}`;
}

function formatSC(value) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (isNaN(num)) return String(value);
  return num.toFixed(2);
}

export function normalizeGameSessionForm(form) {
  return {
    user_id: form.user_id || "",
    site_id: form.site_id || "",
    session_date: form.session_date || "",
    session_time: form.session_time || "",
    game_id: form.game_id || "",
    game_type_id: form.game_type_id || "",
    end_date: form.end_date || "",
    end_time: form.end_time || "",
    starting_balance: form.starting_balance ?? "",
    ending_balance: form.ending_balance ?? "",
    starting_redeemable: form.starting_redeemable ?? "",
    ending_redeemable: form.ending_redeemable ?? "",
    wager_amount: form.wager_amount ?? "",
    rtp: form.rtp ?? "",
    purchases_during: form.purchases_during ?? "",
    redemptions_during: form.redemptions_during ?? "",
    status: form.status || "Active",
    notes: form.notes || "",
  };
}

export function getGameSessionColumnValue(session, columnKey) {
  if (columnKey === "session_date") {
    const date = session.session_date || "—";
    const time = session.session_time || "";
    return time && time !== "00:00:00" ? `${date} ${time}` : date;
  }
  if (columnKey === "status") {
    return session.status || "Active";
  }
  if (columnKey === "user_name") return session.user_name || "—";
  if (columnKey === "site_name") return session.site_name || "—";
  if (columnKey === "game_name") return session.game_name || "—";
  if (columnKey === "starting_balance") return formatSC(session.starting_balance);
  if (columnKey === "ending_balance") return formatSC(session.ending_balance);
  if (columnKey === "starting_redeemable") return formatSC(session.starting_redeemable);
  if (columnKey === "ending_redeemable") return formatSC(session.ending_redeemable);
  if (columnKey === "net_taxable_pl") {
    if (session.net_taxable_pl === null || session.net_taxable_pl === undefined) return "—";
    return formatCurrency(session.net_taxable_pl);
  }
  if (columnKey === "notes") return (session.notes || "").slice(0, 100) || "—";
  return String(session[columnKey] || "");
}
