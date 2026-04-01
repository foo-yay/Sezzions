export const initialMethodTypeForm = {
  name: "",
  notes: "",
  is_active: true
};

export const initialMethodTypeColumnFilters = {
  name: [],
  status: [],
  notes: []
};

export const methodTypeTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

export const methodTypesPageSize = 100;
export const methodTypesFallbackPageSize = 500;
