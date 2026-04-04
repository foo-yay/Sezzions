function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function nowTimeISO() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export const initialPurchaseForm = {
  user_id: "",
  site_id: "",
  amount: "",
  purchase_date: todayISO(),
  purchase_time: nowTimeISO(),
  sc_received: "",
  starting_sc_balance: "",
  cashback_earned: "",
  cashback_is_manual: false,
  card_id: "",
  notes: "",
};

export const initialPurchaseColumnFilters = {
  purchase_date: [],
  purchase_time: [],
  user_name: [],
  site_name: [],
  amount: [],
  sc_received: [],
  starting_sc_balance: [],
  card_name: [],
  cashback_earned: [],
  remaining_amount: [],
  status: [],
  notes: [],
};

export const purchaseTableColumns = [
  { key: "purchase_date", label: "Date", sortable: true },
  { key: "user_name", label: "User", sortable: true },
  { key: "site_name", label: "Site", sortable: true },
  { key: "amount", label: "Amount", sortable: true },
  { key: "sc_received", label: "SC Received", sortable: true },
  { key: "starting_sc_balance", label: "Post-Purchase SC", sortable: true },
  { key: "card_name", label: "Card", sortable: true },
  { key: "cashback_earned", label: "Cashback", sortable: true },
  { key: "remaining_amount", label: "Remaining", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true },
];

export const purchasesPageSize = 100;
export const purchasesFallbackPageSize = 500;
