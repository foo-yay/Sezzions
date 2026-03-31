export const initialSiteForm = {
  name: "",
  url: "",
  sc_rate: "1",
  playthrough_requirement: "1",
  notes: "",
  is_active: true
};

export const initialSiteColumnFilters = {
  name: [],
  url: [],
  sc_rate: [],
  playthrough_requirement: [],
  status: [],
  notes: []
};

export const siteTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "url", label: "URL", sortable: true },
  { key: "sc_rate", label: "SC Rate", sortable: true },
  { key: "playthrough_requirement", label: "Playthrough", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

export const sitesPageSize = 100;
export const sitesFallbackPageSize = 500;
