import { useCallback, useState } from "react";
import useEntityTable from "../../hooks/useEntityTable";
import EntityTable from "../common/EntityTable";
import HighlightMatch from "../common/HighlightMatch";
import RedemptionModal from "./RedemptionModal";
import MarkReceivedDialog from "./MarkReceivedDialog";
import { buildGenericFilterOptions } from "../../utils/tableUtils";
import {
  initialRedemptionForm,
  initialRedemptionColumnFilters,
  redemptionTableColumns,
  redemptionsPageSize,
  redemptionsFallbackPageSize,
} from "./redemptionsConstants";
import { normalizeRedemptionForm, getRedemptionColumnValue } from "./redemptionsUtils";
import { getAccessToken, authHeaders } from "../../services/api";

// ── Entity config ───────────────────────────────────────────────────────────

const redemptionsConfig = {
  entityName: "redemptions",
  entitySingular: "redemption",
  apiEndpoint: "/v1/workspace/redemptions",
  responseKey: "redemptions",
  batchDeleteIdKey: "redemption_ids",
  columns: redemptionTableColumns,
  initialForm: initialRedemptionForm,
  initialColumnFilters: initialRedemptionColumnFilters,
  pageSize: redemptionsPageSize,
  fallbackPageSize: redemptionsFallbackPageSize,
  getColumnValue: getRedemptionColumnValue,
  getCellDisplayValue: getRedemptionColumnValue,
  searchFilter: (redemption, text) =>
    (redemption.user_name || "").toLowerCase().includes(text)
    || (redemption.site_name || "").toLowerCase().includes(text)
    || (redemption.method_name || "").toLowerCase().includes(text)
    || (redemption.redemption_date || "").toLowerCase().includes(text)
    || (redemption.redemption_time || "").toLowerCase().includes(text)
    || (redemption.status || "").toLowerCase().includes(text)
    || (redemption.notes || "").toLowerCase().includes(text)
    || (redemption.amount || "").includes(text),
  numericSortColumns: ["amount", "fees", "cost_basis", "unbased"],
  getItemLabel: (r) => `${r.redemption_date || "unknown"} — ${r.user_name || "unknown"}`,
  normalizeForm: normalizeRedemptionForm,
  itemToForm: (redemption) => ({
    user_id: redemption.user_id || "",
    site_id: redemption.site_id || "",
    amount: redemption.amount ?? "",
    fees: redemption.fees ?? "",
    redemption_date: redemption.redemption_date || "",
    redemption_time: redemption.redemption_time || "",
    redemption_method_type_id: redemption.method_type_id || "",
    redemption_method_id: redemption.redemption_method_id || "",
    receipt_date: redemption.receipt_date || "",
    processed: Boolean(redemption.processed),
    more_remaining: Boolean(redemption.more_remaining),
    notes: redemption.notes || "",
  }),
  formToPayload: (form, mode) => ({
    user_id: form.user_id || null,
    site_id: form.site_id || null,
    amount: form.amount || null,
    redemption_date: form.redemption_date || null,
    redemption_time: form.redemption_time || null,
    redemption_method_id: form.redemption_method_id || null,
    fees: form.fees || "0.00",
    receipt_date: form.receipt_date || null,
    processed: Boolean(form.processed),
    more_remaining: Boolean(form.more_remaining),
    notes: form.notes || null,
    ...(mode === "edit" ? { status: "PENDING" } : {}),
  }),
  buildFilterOptions: (items) => {
    const options = {};
    for (const col of redemptionTableColumns) {
      if (col.key === "more_remaining") {
        options[col.key] = [
          { value: "Full", label: "Full", path: ["Full"], searchValue: "Full" },
          { value: "Partial", label: "Partial", path: ["Partial"], searchValue: "Partial" },
        ];
      } else if (col.key === "processed") {
        options[col.key] = [
          { value: "✓", label: "Yes", path: ["Yes"], searchValue: "✓" },
          { value: "", label: "No", path: ["No"], searchValue: "" },
        ];
      } else {
        options[col.key] = buildGenericFilterOptions(items, col.key, getRedemptionColumnValue);
      }
    }
    return options;
  },
  buildSuggestions: () => ({}),
  extraLoaders: [
    { key: "users", endpoint: "/v1/workspace/users?limit=500&offset=0", responseKey: "users" },
    { key: "sites", endpoint: "/v1/workspace/sites?limit=500&offset=0", responseKey: "sites" },
    { key: "methodTypes", endpoint: "/v1/workspace/redemption-method-types?limit=500&offset=0", responseKey: "redemption_method_types" },
    { key: "redemptionMethods", endpoint: "/v1/workspace/redemption-methods?limit=500&offset=0", responseKey: "redemption_methods" },
  ],
};

// ── Cell renderer ───────────────────────────────────────────────────────────

function renderRedemptionCell(redemption, columnKey, search) {
  if (columnKey === "receipt_date") {
    const display = getRedemptionColumnValue(redemption, "receipt_date");
    if (display === "PENDING" || display === "CANCELED" || display === "PENDING CANCEL") {
      const pillClass = display === "PENDING" && Number(redemption.amount) === 0
        ? "loss"
        : display === "CANCELED"
          ? "canceled"
          : display === "PENDING CANCEL"
            ? "pending-cancel"
            : "pending";
      return <span className={`receipt-pill ${pillClass}`}>{display}</span>;
    }
    return <HighlightMatch text={display} query={search} />;
  }
  if (["amount", "cost_basis", "unbased"].includes(columnKey)) {
    return <span>{getRedemptionColumnValue(redemption, columnKey)}</span>;
  }
  if (columnKey === "processed") {
    return <span style={{ textAlign: "center", display: "block" }}>{getRedemptionColumnValue(redemption, columnKey)}</span>;
  }
  if (columnKey === "user_name" || columnKey === "site_name" || columnKey === "method_name") {
    return <HighlightMatch text={getRedemptionColumnValue(redemption, columnKey)} query={search} />;
  }
  if (columnKey === "notes") {
    return <HighlightMatch text={(redemption.notes || "").slice(0, 100) || "—"} query={search} />;
  }
  return <HighlightMatch text={getRedemptionColumnValue(redemption, columnKey)} query={search} />;
}


// ── Component ───────────────────────────────────────────────────────────────

export default function RedemptionsTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const [pendingOnly, setPendingOnly] = useState(false);
  const [unprocessedOnly, setUnprocessedOnly] = useState(false);
  const [markReceivedOpen, setMarkReceivedOpen] = useState(false);

  const quickFilter = useCallback((r) => {
    if (pendingOnly) {
      const st = r.status || "PENDING";
      if (r.receipt_date || st === "CANCELED" || st === "PENDING_CANCEL") return false;
    }
    if (unprocessedOnly && r.processed) return false;
    return true;
  }, [pendingOnly, unprocessedOnly]);

  const table = useEntityTable(redemptionsConfig, { apiBaseUrl, hostedWorkspaceReady, quickFilter });

  // ── Quick action helpers ────────────────────────────────────────────────

  const selectedRedemptions = table.selectedItems || [];
  const singleSelected = selectedRedemptions.length === 1 ? selectedRedemptions[0] : null;

  const canCancel = singleSelected
    && singleSelected.status === "PENDING"
    && !singleSelected.receipt_date;

  const canUncancel = singleSelected
    && (singleSelected.status === "CANCELED" || singleSelected.status === "PENDING_CANCEL");

  const pendingSelected = selectedRedemptions.filter(
    (r) => r.status === "PENDING"
  );

  const hasUnreceivedSelected = selectedRedemptions.length > 0
    && selectedRedemptions.some((r) => r.status === "PENDING" && !r.receipt_date);

  const hasUnprocessedSelected = selectedRedemptions.length > 0
    && selectedRedemptions.some((r) => !r.processed);

  async function handleCancel() {
    if (!canCancel) return;
    try {
      const token = await getAccessToken();
      const resp = await fetch(`${apiBaseUrl}/v1/workspace/redemptions/${singleSelected.id}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(token) },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || "Cancel failed");
        return;
      }
      table.handleRefresh();
    } catch (e) {
      alert(`Cancel failed: ${e.message}`);
    }
  }

  async function handleUncancel() {
    if (!canUncancel) return;
    try {
      const token = await getAccessToken();
      const resp = await fetch(`${apiBaseUrl}/v1/workspace/redemptions/${singleSelected.id}/uncancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(token) },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || "Uncancel failed");
        return;
      }
      table.handleRefresh();
    } catch (e) {
      alert(`Uncancel failed: ${e.message}`);
    }
  }

  async function handleMarkProcessed() {
    if (!pendingSelected.length) return;
    try {
      const token = await getAccessToken();
      const resp = await fetch(`${apiBaseUrl}/v1/workspace/redemptions/bulk-mark-processed`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(token) },
        body: JSON.stringify({ redemption_ids: pendingSelected.map((r) => r.id) }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || "Mark Processed failed");
        return;
      }
      table.handleRefresh();
    } catch (e) {
      alert(`Mark Processed failed: ${e.message}`);
    }
  }

  async function handleMarkReceived(receiptDate) {
    if (!pendingSelected.length) return;
    try {
      const token = await getAccessToken();
      const resp = await fetch(`${apiBaseUrl}/v1/workspace/redemptions/bulk-mark-received`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders(token) },
        body: JSON.stringify({
          redemption_ids: pendingSelected.map((r) => r.id),
          receipt_date: receiptDate || null,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(err.detail || "Mark Received failed");
        return;
      }
      table.handleRefresh();
      setMarkReceivedOpen(false);
    } catch (e) {
      alert(`Mark Received failed: ${e.message}`);
    }
  }

  // ── Extra toolbar buttons ───────────────────────────────────────────────

  const extraButtons = (
    <>
      {hasUnreceivedSelected && (
        <button className="ghost-button" type="button" onClick={() => setMarkReceivedOpen(true)}>Mark Received</button>
      )}
      {hasUnprocessedSelected && (
        <button className="ghost-button" type="button" onClick={handleMarkProcessed}>Mark Processed</button>
      )}
      {canCancel && (
        <button className="ghost-button" type="button" onClick={handleCancel}>Cancel</button>
      )}
      {canUncancel && (
        <button className="ghost-button" type="button" onClick={handleUncancel}>Uncancel</button>
      )}
    </>
  );

  const quickFilterRow = (
    <>
      <label className="quick-filter-check" title="Show only redemptions with no receipt date">
        <input type="checkbox" checked={pendingOnly} onChange={(e) => setPendingOnly(e.target.checked)} />
        Pending
      </label>
      <label className="quick-filter-check" title="Show only redemptions that are not processed">
        <input type="checkbox" checked={unprocessedOnly} onChange={(e) => setUnprocessedOnly(e.target.checked)} />
        Unprocessed
      </label>
    </>
  );

  return (
    <>
      <EntityTable
        table={table}
        entityName="redemptions"
        entitySingular="redemption"
        columns={redemptionTableColumns}
        getCellDisplayValue={getRedemptionColumnValue}
        renderCell={renderRedemptionCell}
        defaultColumnWidths={["135px", "100px", "90px", "115px", "100px", "100px", "80px", "110px", "105px", "115px"]}
        defaultHeaderGridTemplate="36px 135px 100px 90px 115px 100px 100px 80px 110px 105px 115px 1fr"
        extraToolbarButtons={extraButtons}
        extraToolbarRow={quickFilterRow}
      >
        {table.modalMode ? (
          <RedemptionModal
            mode={table.modalMode}
            redemption={table.selectedItem}
            form={table.form}
            setForm={table.setForm}
            submitError={table.submitError}
            users={table.extraData.users || []}
            sites={table.extraData.sites || []}
            redemptionMethods={table.extraData.redemptionMethods || []}
            methodTypes={table.extraData.methodTypes || []}
            apiBaseUrl={apiBaseUrl}
            onClose={table.requestCloseModal}
            onRequestEdit={() => table.selectedItem && table.openModal("edit", table.selectedItem)}
            onRequestDelete={() => table.selectedItem && table.handleDelete([table.selectedItem])}
            onSubmit={table.submitModal}
          />
        ) : null}
      </EntityTable>
      {markReceivedOpen && (
        <MarkReceivedDialog
          count={pendingSelected.length}
          onSave={handleMarkReceived}
          onClose={() => setMarkReceivedOpen(false)}
        />
      )}
    </>
  );
}
