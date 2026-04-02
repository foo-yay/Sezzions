export const initialRedemptionMethodForm = {
  name: "",
  method_type_id: "",
  user_id: "",
  notes: "",
  is_active: true
};

export const initialRedemptionMethodColumnFilters = {
  name: [],
  method_type_name: [],
  user_name: [],
  status: [],
  notes: []
};

export const redemptionMethodTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "method_type_name", label: "Method Type", sortable: true },
  { key: "user_name", label: "User", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

export const redemptionMethodsPageSize = 100;
export const redemptionMethodsFallbackPageSize = 500;
