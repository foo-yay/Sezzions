function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function nowTimeISO() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export const initialGameSessionForm = {
  user_id: "",
  site_id: "",
  session_date: todayISO(),
  session_time: nowTimeISO(),
  game_id: "",
  game_type_id: "",
  end_date: "",
  end_time: "",
  starting_balance: "",
  ending_balance: "",
  starting_redeemable: "",
  ending_redeemable: "",
  wager_amount: "",
  rtp: "",
  purchases_during: "",
  redemptions_during: "",
  status: "Active",
  notes: "",
};

export const initialGameSessionColumnFilters = {
  session_date: [],
  user_name: [],
  site_name: [],
  game_name: [],
  status: [],
  starting_balance: [],
  ending_balance: [],
  starting_redeemable: [],
  ending_redeemable: [],
  net_taxable_pl: [],
  notes: [],
};

export const gameSessionTableColumns = [
  { key: "session_date", label: "Date", sortable: true },
  { key: "user_name", label: "User", sortable: true },
  { key: "site_name", label: "Site", sortable: true },
  { key: "game_name", label: "Game", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "starting_balance", label: "Start SC", sortable: true },
  { key: "ending_balance", label: "End SC", sortable: true },
  { key: "starting_redeemable", label: "Start Redeem", sortable: true },
  { key: "ending_redeemable", label: "End Redeem", sortable: true },
  { key: "net_taxable_pl", label: "Net P/L", sortable: true },
  { key: "notes", label: "Notes", sortable: true },
];

export const gameSessionsPageSize = 100;
export const gameSessionsFallbackPageSize = 500;
