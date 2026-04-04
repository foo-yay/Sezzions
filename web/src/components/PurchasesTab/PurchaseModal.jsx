import { useRef, useEffect, useCallback } from "react";
import { getPurchaseColumnValue } from "./purchasesUtils";
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

  // Auto-focus first form field on mount
  const dateRef = useRef(null);
  useEffect(() => {
    if (!readOnly && dateRef.current) {
      dateRef.current.focus();
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

  if (readOnly && purchase) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card purchase-modal"
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

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
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

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
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
        className="modal-card purchase-modal"
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

        <div className="form-grid">
          <label className="field-label" htmlFor="purchase-date-input">Date</label>
          <div>
            <input
              ref={dateRef}
              id="purchase-date-input"
              className={dateInvalid ? "text-input invalid" : "text-input"}
              type="date"
              value={form.purchase_date}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, purchase_date: event.target.value }))}
            />
            {dateInvalid ? <p className="field-error">Date is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="purchase-time-input">Time</label>
          <div>
            <input
              id="purchase-time-input"
              className="text-input"
              type="time"
              step="1"
              placeholder="Optional"
              value={form.purchase_time}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, purchase_time: event.target.value }))}
            />
          </div>

          <label className="field-label" htmlFor="purchase-user-input">User</label>
          <div>
            <TypeaheadSelect
              id="purchase-user-input"
              options={users.map((u) => ({
                value: u.id,
                label: u.name,
              }))}
              value={form.user_id}
              onChange={(userId) => {
                setForm((current) => ({
                  ...current,
                  user_id: userId,
                  // Clear card if user changes (card is user-scoped)
                  card_id: userId === current.user_id ? current.card_id : "",
                  // Recalculate cashback if card is cleared
                  ...(userId !== current.user_id
                    ? { cashback_earned: "", cashback_is_manual: false }
                    : {}),
                }));
              }}
              placeholder="Required"
              disabled={readOnly}
            />
            {userInvalid ? <p className="field-error">User is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="purchase-site-input">Site</label>
          <div>
            <TypeaheadSelect
              id="purchase-site-input"
              options={sites.map((s) => ({
                value: s.id,
                label: s.name,
              }))}
              value={form.site_id}
              onChange={(siteId) => setForm((current) => ({ ...current, site_id: siteId }))}
              placeholder="Required"
              disabled={readOnly}
            />
            {siteInvalid ? <p className="field-error">Site is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="purchase-card-input">Card</label>
          <div>
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
              placeholder="Required"
              disabled={readOnly}
              noMatchText="No cards for this user"
            />
            {cardInvalid ? <p className="field-error">Card is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="purchase-amount-input">Amount ($)</label>
          <div>
            <input
              id="purchase-amount-input"
              className={amountInvalid ? "text-input invalid" : "text-input"}
              type="number"
              min="0.01"
              step="0.01"
              placeholder="Required"
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
            {amountInvalid ? <p className="field-error">Amount must be greater than zero.</p> : null}
          </div>

          <label className="field-label" htmlFor="purchase-sc-received-input">SC Received</label>
          <div>
            <input
              id="purchase-sc-received-input"
              className="text-input"
              type="number"
              min="0"
              step="0.01"
              placeholder="Defaults to amount"
              value={form.sc_received}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, sc_received: event.target.value }))}
            />
          </div>

          <label className="field-label" htmlFor="purchase-starting-sc-input">Post-Purchase SC</label>
          <div>
            <input
              id="purchase-starting-sc-input"
              className={scBalanceInvalid ? "text-input invalid" : "text-input"}
              type="number"
              min="0"
              step="0.01"
              placeholder="Required"
              value={form.starting_sc_balance}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, starting_sc_balance: event.target.value }))}
            />
            {scBalanceInvalid ? <p className="field-error">Post-Purchase SC is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="purchase-cashback-input">Cashback ($)</label>
          <div>
            <input
              id="purchase-cashback-input"
              className="text-input"
              type="number"
              min="0"
              step="0.01"
              placeholder="Auto-calculated"
              value={form.cashback_earned}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({
                ...current,
                cashback_earned: event.target.value,
                cashback_is_manual: true,
              }))}
            />
          </div>

          <label className="field-label field-label-top" htmlFor="purchase-notes-input">Notes</label>
          <textarea
            id="purchase-notes-input"
            className="notes-input"
            placeholder="Optional"
            rows={3}
            value={form.notes}
            readOnly={readOnly}
            onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
          />
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
