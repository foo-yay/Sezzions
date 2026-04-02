export const initialGameTypeForm = {
  name: "",
  notes: "",
  is_active: true
};

export const initialGameTypeColumnFilters = {
  name: [],
  status: [],
  notes: []
};

export const gameTypeTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

export const gameTypesPageSize = 100;
export const gameTypesFallbackPageSize = 500;
