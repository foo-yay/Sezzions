export const initialUserForm = {
  name: "",
  email: "",
  notes: "",
  is_active: true
};

export const initialUserColumnFilters = {
  name: [],
  email: [],
  status: [],
  notes: []
};

export const userTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "email", label: "Email", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

export const usersPageSize = 100;
export const usersFallbackPageSize = 500;
