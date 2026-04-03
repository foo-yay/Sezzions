export const initialGameForm = {
  name: "",
  game_type_id: "",
  rtp: "",
  notes: "",
  is_active: true
};

export const initialGameColumnFilters = {
  name: [],
  game_type_name: [],
  rtp: [],
  actual_rtp: [],
  status: [],
  notes: []
};

export const gameTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "game_type_name", label: "Game Type", sortable: true },
  { key: "rtp", label: "Expected RTP", sortable: true },
  { key: "actual_rtp", label: "Actual RTP", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

export const gamesPageSize = 100;
export const gamesFallbackPageSize = 500;
