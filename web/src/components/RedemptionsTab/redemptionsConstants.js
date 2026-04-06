function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function nowTimeISO() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export const initialRedemptionForm = {
  user_id: "",
  site_id: "",
  amount: "",
  fees: "",
  redemption_date: todayISO(),
  redemption_time: nowTimeISO(),
  redemption_method_id: "",
  is_free_sc: false,
  receipt_date: "",
  processed: false,
  more_remaining: false,
  notes: "",
};

export const initialRedemptionColumnFilters = {
  redemption_date: [],
  user_name: [],
  site_name: [],
  amount: [],
  fees: [],
  method_name: [],
  status: [],
  more_remaining: [],
  receipt_date: [],
  processed: [],
  cost_basis: [],
  net_pl: [],
  notes: [],
};

export const redemptionTableColumns = [
  { key: "redemption_date", label: "Date", sortable: true },
  { key: "user_name", label: "User", sortable: true },
  { key: "site_name", label: "Site", sortable: true },
  { key: "amount", label: "Amount", sortable: true },
  { key: "fees", label: "Fees", sortable: true },
  { key: "method_name", label: "Method", sortable: true },
  { key: "more_remaining", label: "Type", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "receipt_date", label: "Receipt Date", sortable: true },
  { key: "cost_basis", label: "Cost Basis", sortable: true },
  { key: "net_pl", label: "Net P&L", sortable: true },
  { key: "notes", label: "Notes", sortable: true },
];

export const redemptionsPageSize = 100;
export const redemptionsFallbackPageSize = 500;
