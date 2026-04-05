import { useRef, useEffect, useCallback, useState } from "react";
import { getPurchaseColumnValue } from "./purchasesUtils";
import { getAccessToken, authHeaders } from "../../services/api";
import TypeaheadSelect from "../common/TypeaheadSelect";

export default function PurchaseModal({
  mode,
  purchase,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  users,
  sites,
  cards,
  apiBaseUrl,
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Purchase" : mode === "edit" ? "Edit Purchase" : "View Purchase";
  const userInvalid = !form.user_id;
  const siteInvalid = !form.site_id;
  const amountRaw = form.amount;
  const amountInvalid = !amountRaw || isNaN(Number(amountRaw)) || Number(amountRaw) <= 0;
  const dateInvalid = !form.purchase_date;
  const cardInvalid = !form.card_id;
  const scBalanceRaw = form.starting_sc_balance;
  const scBalanceInvalid = !scBalanceRaw || scBalanceRaw === "" || isNaN(Number(scBalanceRaw)) || Number(scBalanceRaw) < 0;
  const formInvalid = userInvalid || siteInvalid || amountInvalid || dateInvalid || cardInvalid || scBalanceInvalid;
  const closeLabel = readOnly ? "Close" : "Cancel";

  // Auto-focus User field on mount (date/time are pre-filled)
  const userRef = useRef(null);
  useEffect(() => {
    if (!readOnly && userRef.current) {
      // TypeaheadSelect exposes the input via the wrapper; find the actual input
      const input = userRef.current.querySelector ? userRef.current.querySelector("input") : userRef.current;
      if (input) input.focus();
    }
  }, [readOnly]);

  // Filter cards by selected user
  const filteredCards = form.user_id
    ? cards.filter((c) => c.user_id === form.user_id)
    : cards;

  // Auto-calculate cashback when amount or card changes
  const calculateCashback = useCallback(
    (amount, cardId) => {
      if (!cardId || !amount || isNaN(Number(amount)) || Number(amount) <= 0) return "";
      const card = cards.find((c) => c.id === cardId);
      if (!card || !card.cashback_rate || Number(card.cashback_rate) <= 0) return "";
      const cashback = Number(amount) * Number(card.cashback_rate) / 100;
      return cashback.toFixed(2);
    },
    [cards],
  );

  // ── Balance Check ─────────────────────────────────────────────────────────
  const [balanceCheck, setBalanceCheck] = useState(null); // { status, message }

  useEffect(() => {
    if (readOnly) return;
    // Need user, site, date, and post-purchase SC to compute
    if (!form.user_id || !form.site_id || !form.purchase_date || !form.starting_sc_balance) {
      setBalanceCheck(null);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const token = await getAccessToken();
        if (!token || controller.signal.aborted) return;
        const params = new URLSearchParams({
          user_id: form.user_id,
          site_id: form.site_id,
          purchase_date: form.purchase_date,
        });
        if (form.purchase_time) params.set("purchase_time", form.purchase_time);
        if (mode === "edit" && purchase?.id) params.set("exclude_purchase_id", purchase.id);

        const res = await fetch(
          `${apiBaseUrl}/v1/workspace/purchases/expected-balance?${params}`,
          { headers: authHeaders(token), signal: controller.signal },
        );
        if (!res.ok || controller.signal.aborted) {
          setBalanceCheck(null);
          return;
        }
        const data = await res.json();
        // Backend returns the expected pre-purchase balance (last known post-SC).
        // Add sc_received to get the expected post-purchase balance, which is
        // what starting_sc_balance (Post SC) actually represents.
        const prePurchase = Number(data.expected_total);
        const scReceived = Number(form.sc_received || form.amount || 0);
        const expectedPost = prePurchase + scReceived;
        const enteredSC = Number(form.starting_sc_balance);
        const delta = enteredSC - expectedPost;

        if (Math.abs(delta) <= 0.01) {
          setBalanceCheck({
            status: "match",
            message: `Matches expected balance (${expectedPost.toFixed(2)} SC)`,
          });
        } else if (delta > 0.01) {
          setBalanceCheck({
            status: "higher",
            message: `+ ${delta.toFixed(2)} SC above expected (${expectedPost.toFixed(2)} SC)`,
          });
        } else {
          setBalanceCheck({
            status: "lower",
            message: `- WARNING: ${Math.abs(delta).toFixed(2)} SC less than expected (${expectedPost.toFixed(2)} SC)`,
          });
        }
      } catch {
        if (!controller.signal.aborted) setBalanceCheck(null);
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [readOnly, form.user_id, form.site_id, form.purchase_date, form.purchase_time, form.starting_sc_balance, form.sc_received, form.amount, mode, purchase?.id, apiBaseUrl]);

  if (readOnly && purchase) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card entity-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="purchase-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="purchase-modal-title">View Purchase</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="modal-detail-body">
            <dl className="detail-grid modal-detail-grid">
              <div><dt>Date</dt><dd>{purchase.purchase_date}</dd></div>
              <div><dt>Time</dt><dd>{purchase.purchase_time || "—"}</dd></div>
              <div><dt>User</dt><dd>{purchase.user_name || "—"}</dd></div>
              <div><dt>Site</dt><dd>{purchase.site_name || "—"}</dd></div>
              <div><dt>Card</dt><dd>{purchase.card_name || "—"}</dd></div>
              <div><dt>Amount</dt><dd>{getPurchaseColumnValue(purchase, "amount")}</dd></div>
              <div><dt>SC Received</dt><dd>{getPurchaseColumnValue(purchase, "sc_received")}</dd></div>
              <div><dt>Post-Purchase SC</dt><dd>{getPurchaseColumnValue(purchase, "starting_sc_balance")}</dd></div>
              <div><dt>Cashback</dt><dd>{getPurchaseColumnValue(purchase, "cashback_earned")}</dd></div>
              <div><dt>Remaining</dt><dd>{getPurchaseColumnValue(purchase, "remaining_amount")}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={purchase.status === "active" ? "status-chip active" : "status-chip inactive"}>
                    {getPurchaseColumnValue(purchase, "status")}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="modal-detail-notes">
              <p className="field-label">Notes</p>
              <div className="notes-display">{purchase.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Purchase</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card entity-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="purchase-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="purchase-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="purchase-form">
          {/* ── Date / Time — compact inline, pre-filled ── */}
          <div className="pf-datetime-row">
            <label className="field-label" htmlFor="purchase-date-input">Date</label>
            <input
              id="purchase-date-input"
              className={dateInvalid ? "text-input invalid" : "text-input"}
              type="date"
              value={form.purchase_date}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, purchase_date: event.target.value }))}
            />
            <label className="field-label" htmlFor="purchase-time-input">Time</label>
            <input
              id="purchase-time-input"
              className="text-input"
              type="time"
              step="1"
              value={form.purchase_time}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, purchase_time: event.target.value }))}
            />
          </div>

          {/* ── Purchase Details — 4-column grid ── */}
          <div className="pf-section">
            <p className="pf-section-title"><span>💳</span> Purchase Details</p>
            <div className="pf-grid">
              {/* Left column first for tab order: User → Site → Card */}
              <label className="field-label" htmlFor="purchase-user-input" style={{gridRow: 1, gridColumn: 1}}>User</label>
              <div className="pf-cell" ref={userRef} style={{gridRow: 1, gridColumn: 2}}>
                <TypeaheadSelect
                  id="purchase-user-input"
                  options={users.map((u) => ({ value: u.id, label: u.name }))}
                  value={form.user_id}
                  onChange={(userId) => {
                    setForm((current) => ({
                      ...current,
                      user_id: userId,
                      card_id: userId === current.user_id ? current.card_id : "",
                      ...(userId !== current.user_id
                        ? { cashback_earned: "", cashback_is_manual: false }
                        : {}),
                    }));
                  }}
                  placeholder="Select…"
                  disabled={readOnly}
                  invalid={userInvalid}
                  title={userInvalid ? "Required" : undefined}
                />
              </div>
              <label className="field-label" htmlFor="purchase-site-input" style={{gridRow: 2, gridColumn: 1}}>Site</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 2}}>
                <TypeaheadSelect
                  id="purchase-site-input"
                  options={sites.map((s) => ({ value: s.id, label: s.name }))}
                  value={form.site_id}
                  onChange={(siteId) => setForm((current) => ({ ...current, site_id: siteId }))}
                  placeholder="Select…"
                  disabled={readOnly}
                  invalid={siteInvalid}
                  title={siteInvalid ? "Required" : undefined}
                />
              </div>
              <label className="field-label" htmlFor="purchase-card-input" style={{gridRow: 3, gridColumn: 1}}>Card</label>
              <div className="pf-cell" style={{gridRow: 3, gridColumn: 2}}>
                <TypeaheadSelect
                  id="purchase-card-input"
                  options={filteredCards.map((c) => ({
                    value: c.id,
                    label: c.name + (c.last_four ? ` (${c.last_four})` : ""),
                  }))}
                  value={form.card_id}
                  onChange={(cardId) => {
                    setForm((current) => {
                      const newCashback = current.cashback_is_manual
                        ? current.cashback_earned
                        : calculateCashback(current.amount, cardId);
                      return { ...current, card_id: cardId, cashback_earned: newCashback };
                    });
                  }}
                  placeholder={form.user_id ? "Select…" : "Pick user first"}
                  disabled={readOnly}
                  noMatchText="No cards for this user"
                  invalid={cardInvalid}
                  title={cardInvalid ? "Required" : undefined}
                />
              </div>

              {/* Right column: Amount → (skip Cashback) → SC Recv'd → Post SC */}
              <label className="field-label" htmlFor="purchase-amount-input" style={{gridRow: 1, gridColumn: 3}}>Amount</label>
              <div className="pf-cell" style={{gridRow: 1, gridColumn: 4}}>
                <input
                  id="purchase-amount-input"
                  className={amountInvalid ? "text-input invalid" : "text-input"}
                  type="number"
                  min="0.01"
                  step="0.01"
                  placeholder="0.00"
                  title={amountInvalid ? "Required" : undefined}
                  value={form.amount}
                  readOnly={readOnly}
                  onChange={(event) => {
                    const newAmount = event.target.value;
                    setForm((current) => {
                      const newCashback = current.cashback_is_manual
                        ? current.cashback_earned
                        : calculateCashback(newAmount, current.card_id);
                      return { ...current, amount: newAmount, cashback_earned: newCashback };
                    });
                  }}
                />
              </div>
              <label className="field-label" htmlFor="purchase-cashback-input" style={{gridRow: 2, gridColumn: 3}}>Cashback</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 4}}>
                <input
                  id="purchase-cashback-input"
                  className="text-input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="Auto"
                  value={form.cashback_earned}
                  readOnly={readOnly}
                  tabIndex={-1}
                  onChange={(event) => setForm((current) => ({
                    ...current,
                    cashback_earned: event.target.value,
                    cashback_is_manual: true,
                  }))}
                />
              </div>
              <label className="field-label" htmlFor="purchase-sc-received-input" style={{gridRow: 3, gridColumn: 3}}>SC Recv'd</label>
              <div className="pf-cell" style={{gridRow: 3, gridColumn: 4}}>
                <input
                  id="purchase-sc-received-input"
                  className="text-input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="= Amount"
                  value={form.sc_received}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, sc_received: event.target.value }))}
                />
              </div>
              <label className="field-label" htmlFor="purchase-starting-sc-input" style={{gridRow: 4, gridColumn: 3}}>Post SC</label>
              <div className="pf-cell" style={{gridRow: 4, gridColumn: 4}}>
                <input
                  id="purchase-starting-sc-input"
                  className={scBalanceInvalid ? "text-input invalid" : "text-input"}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  title={scBalanceInvalid ? "Required" : undefined}
                  value={form.starting_sc_balance}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, starting_sc_balance: event.target.value }))}
                />
              </div>
            </div>
          </div>

          {/* ── Balance Check ── */}
          {balanceCheck ? (
            <div className={`pf-balance-check pf-balance-${balanceCheck.status}`}>
              {balanceCheck.message}
            </div>
          ) : null}

          {/* ── Notes — always visible, compact ── */}
          <div className="pf-notes-row">
            <label className="field-label" htmlFor="purchase-notes-input">Notes</label>
            <textarea
              id="purchase-notes-input"
              className="notes-input"
              placeholder="Optional"
              rows={2}
              value={form.notes}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
            />
          </div>
        </div>

        {submitError ? <p className="submit-error">{submitError}</p> : null}

        <div className="modal-actions modal-actions-end">
          <button
            className="primary-button"
            type="button"
            onClick={onSubmit}
            disabled={formInvalid}
          >
            Save Purchase
          </button>
        </div>
      </section>
    </div>
  );
}
