import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import SiteModal from "./SiteModal";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialSiteForm,
  initialSiteColumnFilters,
  siteTableColumns,
  sitesPageSize,
  sitesFallbackPageSize
} from "./sitesConstants";
import { normalizeSiteForm, getSiteColumnValue } from "./sitesUtils";

// ── Entity config ───────────────────────────────────────────────────────────

const sitesConfig = {
  entityName: "sites",
  entitySingular: "site",
  apiEndpoint: "/v1/workspace/sites",
  responseKey: "sites",
  batchDeleteIdKey: "site_ids",
  columns: siteTableColumns,
  initialForm: initialSiteForm,
  initialColumnFilters: initialSiteColumnFilters,
  pageSize: sitesPageSize,
  fallbackPageSize: sitesFallbackPageSize,
  getColumnValue: getSiteColumnValue,
  getCellDisplayValue: getSiteColumnValue,
  searchFilter: (site, text) =>
    site.name.toLowerCase().includes(text)
    || (site.url || "").toLowerCase().includes(text)
    || (site.notes || "").toLowerCase().includes(text),
  numericSortColumns: ["sc_rate", "playthrough_requirement"],
  normalizeForm: normalizeSiteForm,
  itemToForm: (site) => ({
    name: site.name || "",
    url: site.url || "",
    sc_rate: String(site.sc_rate ?? "1"),
    playthrough_requirement: String(site.playthrough_requirement ?? "1"),
    notes: site.notes || "",
    is_active: Boolean(site.is_active)
  }),
  formToPayload: (form, mode) => ({
    name: form.name,
    url: form.url || null,
    sc_rate: parseFloat(form.sc_rate) || 1.0,
    playthrough_requirement: parseFloat(form.playthrough_requirement) || 1.0,
    notes: form.notes || null,
    ...(mode === "edit" ? { is_active: form.is_active } : {})
  }),
  buildFilterOptions: (sites) => {
    const options = {};
    for (const col of siteTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(sites, col.key, getSiteColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: (sites) => ({
    names: [...new Set(sites.map((s) => s.name).filter(Boolean))]
  }),
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderSiteCell(site, columnKey, search) {
  if (columnKey === "status") {
    return (
      <span className={site.is_active ? "status-chip active" : "status-chip inactive"}>
        {site.is_active ? "Active" : "Inactive"}
      </span>
    );
  }
  if (columnKey === "sc_rate") return site.sc_rate;
  if (columnKey === "playthrough_requirement") return site.playthrough_requirement;
  if (columnKey === "notes") {
    return <HighlightMatch text={(site.notes || "").slice(0, 100) || "-"} query={search} />;
  }
  return <HighlightMatch text={site[columnKey] || ""} query={search} />;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function SitesTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const table = useEntityTable(sitesConfig, { apiBaseUrl, hostedWorkspaceReady });

  return (
    <EntityTable
      table={table}
      entityName="sites"
      entitySingular="site"
      columns={siteTableColumns}
      getCellDisplayValue={getSiteColumnValue}
      renderCell={renderSiteCell}
      defaultColumnWidths={["18%", "22%", "10%", "12%", "10%"]}
      defaultHeaderGridTemplate="36px 18% 22% 10% 12% 10% 1fr"
    >
      {table.modalMode ? (
        <SiteModal
          mode={table.modalMode}
          site={table.selectedItem}
          form={table.form}
          setForm={table.setForm}
          submitError={table.submitError}
          suggestions={table.suggestions}
          onClose={table.requestCloseModal}
          onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
          onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
          onSubmit={table.submitModal}
        />
      ) : null}
    </EntityTable>
  );
}
