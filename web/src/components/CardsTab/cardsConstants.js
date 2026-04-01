export const initialCardForm = {
  name: "",
  user_id: "",
  last_four: "",
  cashback_rate: "",
  notes: "",
  is_active: true
};

export const initialCardColumnFilters = {
  name: [],
  user_name: [],
  last_four: [],
  cashback_rate: [],
  status: [],
  notes: []
};

export const cardTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "user_name", label: "User", sortable: true },
  { key: "last_four", label: "Last Four", sortable: true },
  { key: "cashback_rate", label: "Cashback %", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

export const cardsPageSize = 100;
export const cardsFallbackPageSize = 500;
