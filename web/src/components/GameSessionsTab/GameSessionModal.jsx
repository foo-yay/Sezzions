import { useRef, useEffect, useCallback, useState } from "react";
import { getGameSessionColumnValue } from "./gameSessionsUtils";
import { getAccessToken, authHeaders } from "../../services/api";
import TypeaheadSelect from "../common/TypeaheadSelect";

export default function GameSessionModal({
  mode,
  gameSession,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestClose,
  onRequestDelete,
  onEndAndStartNew,
  submitError,
  users,
  sites,
  games,
  gameTypes,
  apiBaseUrl,
}) {
  const readOnly = mode === "view";
  const isCreate = mode === "create";
  const isEdit = mode === "edit";
  const isClose = mode === "close";
  const isActive = form.status === "Active";
  const isClosed = form.status === "Closed";

  const title = isCreate
    ? "Start Session"
    : isClose
      ? "Close Session"
      : isEdit
        ? isActive ? "Edit Active Session" : "Edit Closed Session"
        : "View Session";

  // Validation
  const userInvalid = !form.user_id;
  const siteInvalid = !form.site_id;
  const dateInvalid = !form.session_date;
  const startBalInvalid = form.starting_balance === "" || isNaN(Number(form.starting_balance));
  const endDateInvalid = (isClosed || isClose) && !form.end_date;
  const endBalInvalid = (isClosed || isClose) && (form.ending_balance === "" || isNaN(Number(form.ending_balance)));

  const formInvalid = userInvalid || siteInvalid || dateInvalid || startBalInvalid
    || ((isClosed || isClose) && (endDateInvalid || endBalInvalid));

  const closeLabel = readOnly ? "Close" : "Cancel";

  // Auto-focus User field
  const userRef = useRef(null);
  useEffect(() => {
    if (!readOnly && !isClose && userRef.current) {
      const input = userRef.current.querySelector ? userRef.current.querySelector("input") : userRef.current;
      if (input) input.focus();
    }
  }, [readOnly, isClose]);

  // ── Close-mode defaults (pre-fill end date/time) ───────────────────────
  const closeModeInit = useRef(false);
  useEffect(() => {
    if (!isClose || closeModeInit.current) return;
    closeModeInit.current = true;
    setForm((prev) => ({
      ...prev,
      end_date: prev.end_date || prev.session_date,
      end_time: prev.end_time || new Date().toTimeString().slice(0, 8),
    }));
  }, [isClose, setForm]);

  // Filter games by game_type
  const filteredGames = form.game_type_id
    ? games.filter((g) => g.game_type_id === form.game_type_id)
    : games;

  // ── Expected Balances Auto-Fill (one-shot on create) ────────────────────
  const autoFillDone = useRef(false);

  useEffect(() => {
    if (!isCreate || autoFillDone.current) return;
    if (!form.user_id || !form.site_id || !form.session_date) return;

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const token = await getAccessToken();
        if (!token || controller.signal.aborted) return;
        const params = new URLSearchParams({
          user_id: form.user_id,
          site_id: form.site_id,
          session_date: form.session_date,
          session_time: form.session_time || "00:00:00",
        });
        const res = await fetch(
          `${apiBaseUrl}/v1/workspace/game-sessions/expected-balances?${params}`,
          { headers: authHeaders(token), signal: controller.signal },
        );
        if (!res.ok || controller.signal.aborted) return;
        const data = await res.json();
        autoFillDone.current = true;
        setForm((prev) => ({
          ...prev,
          starting_balance: data.expected_start_total || prev.starting_balance,
          starting_redeemable: data.expected_start_redeemable || prev.starting_redeemable,
        }));
      } catch {
        /* ignore */
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [isCreate, form.user_id, form.site_id, form.session_date, form.session_time, apiBaseUrl, setForm]);

  // ── Balance Check (always-on, mirrors PurchaseModal pattern) ──────────────
  const [balanceCheck, setBalanceCheck] = useState(null); // { status, message }
  const [redeemableCheck, setRedeemableCheck] = useState(null); // { status, message }

  useEffect(() => {
    if (readOnly) return;
    if (!form.user_id || !form.site_id || !form.session_date) {
      setBalanceCheck(null);
      setRedeemableCheck(null);
      return;
    }
    if (!form.starting_balance && !form.starting_redeemable) {
      setBalanceCheck(null);
      setRedeemableCheck(null);
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
          session_date: form.session_date,
          session_time: form.session_time || "00:00:00",
        });
        const res = await fetch(
          `${apiBaseUrl}/v1/workspace/game-sessions/expected-balances?${params}`,
          { headers: authHeaders(token), signal: controller.signal },
        );
        if (!res.ok || controller.signal.aborted) {
          setBalanceCheck(null);
          setRedeemableCheck(null);
          return;
        }
        const data = await res.json();

        // ── Total SC check ──
        if (form.starting_balance) {
          const expectedTotal = Number(data.expected_start_total);
          const enteredTotal = Number(form.starting_balance);
          const delta = enteredTotal - expectedTotal;

          if (Math.abs(delta) <= 0.01) {
            setBalanceCheck({
              status: "match",
              message: `Starting SC matches expected (${expectedTotal.toFixed(2)} SC)`,
            });
          } else if (delta > 0.01) {
            setBalanceCheck({
              status: "higher",
              message: `+ ${delta.toFixed(2)} SC above expected (${expectedTotal.toFixed(2)} SC)`,
            });
          } else {
            setBalanceCheck({
              status: "lower",
              message: `WARNING: ${Math.abs(delta).toFixed(2)} SC below expected (${expectedTotal.toFixed(2)} SC)`,
            });
          }
        } else {
          setBalanceCheck(null);
        }

        // ── Redeemable check ──
        if (form.starting_redeemable) {
          const expectedRedeem = Number(data.expected_start_redeemable);
          const enteredRedeem = Number(form.starting_redeemable);
          const deltaR = enteredRedeem - expectedRedeem;

          if (Math.abs(deltaR) <= 0.01) {
            setRedeemableCheck({
              status: "match",
              message: `Starting Redeemable matches expected (${expectedRedeem.toFixed(2)} SC)`,
            });
          } else if (deltaR > 0.01) {
            setRedeemableCheck({
              status: "higher",
              message: `+ ${deltaR.toFixed(2)} SC above expected redeemable (${expectedRedeem.toFixed(2)} SC)`,
            });
          } else {
            setRedeemableCheck({
              status: "lower",
              message: `WARNING: ${Math.abs(deltaR).toFixed(2)} SC below expected redeemable (${expectedRedeem.toFixed(2)} SC)`,
            });
          }
        } else {
          setRedeemableCheck(null);
        }
      } catch {
        if (!controller.signal.aborted) {
          setBalanceCheck(null);
          setRedeemableCheck(null);
        }
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [readOnly, form.user_id, form.site_id, form.session_date, form.session_time, form.starting_balance, form.starting_redeemable, apiBaseUrl]);

  // ── P/L Preview (for Closed sessions or close mode) ────────────────────
  const plPreview = (() => {
    if (!isClosed && !isClose) return null;
    const startBal = Number(form.starting_balance || 0);
    const endBal = Number(form.ending_balance || 0);
    const startRedeem = Number(form.starting_redeemable || 0);
    const endRedeem = Number(form.ending_redeemable || 0);
    const purchases = Number(form.purchases_during || 0);
    const redemptions = Number(form.redemptions_during || 0);
    // delta_total = ending_balance - starting_balance
    const deltaTotal = endBal - startBal;
    // discoverable_sc = ending - starting - purchases + redemptions
    const discoverableSC = endBal - startBal - purchases + redemptions;
    // delta_redeem = ending_redeemable - starting_redeemable
    const deltaRedeem = endRedeem - startRedeem;
    // Simplified P/L = discoverable_sc + delta_redeem (sc_rate=1 for preview)
    const netPL = discoverableSC + deltaRedeem;
    return { deltaTotal, discoverableSC, deltaRedeem, netPL };
  })();

  // ── End & Start New ───────────────────────────────────────────────────────
  const [endAndStartPending, setEndAndStartPending] = useState(false);

  const handleEndAndStartNew = useCallback(async () => {
    if (!isClose) return;
    setEndAndStartPending(true);
    try {
      const ok = await onSubmit();
      if (ok && onEndAndStartNew) {
        onEndAndStartNew(form);
      }
    } finally {
      setEndAndStartPending(false);
    }
  }, [isClose, onSubmit, onEndAndStartNew, form]);

  // ── Deletion Impact ───────────────────────────────────────────────────────
  const [deletionImpact, setDeletionImpact] = useState(null);

  const handleDeleteWithImpactCheck = useCallback(async () => {
    if (!gameSession?.id) {
      onRequestDelete();
      return;
    }
    try {
      const token = await getAccessToken();
      if (!token) { onRequestDelete(); return; }
      const res = await fetch(
        `${apiBaseUrl}/v1/workspace/game-sessions/${gameSession.id}/deletion-impact`,
        { headers: authHeaders(token) },
      );
      if (!res.ok) { onRequestDelete(); return; }
      const data = await res.json();
      if (data.has_impact) {
        setDeletionImpact(data.message);
      } else {
        onRequestDelete();
      }
    } catch {
      onRequestDelete();
    }
  }, [gameSession?.id, apiBaseUrl, onRequestDelete]);

  // ── View mode ─────────────────────────────────────────────────────────────
  if (readOnly && gameSession) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card entity-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="gs-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="gs-modal-title">View Session</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="modal-detail-body">
            <dl className="detail-grid modal-detail-grid">
              <div><dt>Date</dt><dd>{gameSession.session_date}</dd></div>
              <div><dt>Time</dt><dd>{gameSession.session_time || "—"}</dd></div>
              <div><dt>User</dt><dd>{gameSession.user_name || "—"}</dd></div>
              <div><dt>Site</dt><dd>{gameSession.site_name || "—"}</dd></div>
              <div><dt>Game</dt><dd>{gameSession.game_name || "—"}</dd></div>
              <div><dt>Game Type</dt><dd>{gameSession.game_type_name || "—"}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={gameSession.status === "Active" ? "status-chip active" : "status-chip inactive"}>
                    {gameSession.status}
                  </span>
                </dd>
              </div>
              {gameSession.status === "Closed" && (
                <>
                  <div><dt>End Date</dt><dd>{gameSession.end_date || "—"}</dd></div>
                  <div><dt>End Time</dt><dd>{gameSession.end_time || "—"}</dd></div>
                </>
              )}
              <div><dt>Starting SC</dt><dd>{getGameSessionColumnValue(gameSession, "starting_balance")}</dd></div>
              <div><dt>Ending SC</dt><dd>{getGameSessionColumnValue(gameSession, "ending_balance")}</dd></div>
              <div><dt>Starting Redeemable</dt><dd>{getGameSessionColumnValue(gameSession, "starting_redeemable")}</dd></div>
              <div><dt>Ending Redeemable</dt><dd>{getGameSessionColumnValue(gameSession, "ending_redeemable")}</dd></div>
              <div><dt>Purchases During</dt><dd>{getGameSessionColumnValue(gameSession, "purchases_during") || "—"}</dd></div>
              <div><dt>Redemptions During</dt><dd>{getGameSessionColumnValue(gameSession, "redemptions_during") || "—"}</dd></div>
              {gameSession.wager_amount != null && gameSession.wager_amount !== "" && (
                <div><dt>Wager</dt><dd>{Number(gameSession.wager_amount).toFixed(2)} SC</dd></div>
              )}
              {gameSession.rtp != null && gameSession.rtp !== "" && (
                <div><dt>RTP</dt><dd>{Number(gameSession.rtp).toFixed(2)}%</dd></div>
              )}
              {gameSession.status === "Closed" && gameSession.delta_redeem != null && (
                <div><dt>Δ Redeem</dt><dd>{Number(gameSession.delta_redeem).toFixed(2)} SC</dd></div>
              )}
              {gameSession.status === "Closed" && gameSession.basis_consumed != null && (
                <div><dt>Δ Basis</dt><dd>${Number(gameSession.basis_consumed).toFixed(2)}</dd></div>
              )}
              {gameSession.net_taxable_pl != null && (
                <div><dt>Net P/L</dt><dd>{getGameSessionColumnValue(gameSession, "net_taxable_pl")}</dd></div>
              )}
            </dl>

            <div className="modal-detail-notes">
              <p className="field-label">Notes</p>
              <div className="notes-display">{gameSession.notes || "—"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={handleDeleteWithImpactCheck}>Delete</button>
            </div>
            <div className="toolbar-row">
              {gameSession.status === "Active" && (
                <button className="ghost-button" type="button" onClick={onRequestClose}>Close Session</button>
              )}
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Session</button>
            </div>
          </div>

          {deletionImpact && (
            <div className="modal-backdrop" role="presentation" onClick={() => setDeletionImpact(null)}>
              <section
                className="modal-card entity-modal"
                role="dialog"
                aria-modal="true"
                onClick={(event) => event.stopPropagation()}
                style={{ maxWidth: "480px" }}
              >
                <div className="modal-header">
                  <h2>Deletion Impact</h2>
                  <button className="ghost-button" type="button" onClick={() => setDeletionImpact(null)}>Close</button>
                </div>
                <div className="modal-detail-body" style={{ whiteSpace: "pre-wrap" }}>
                  {deletionImpact}
                </div>
                <div className="modal-actions modal-actions-split">
                  <button className="ghost-button" type="button" onClick={() => setDeletionImpact(null)}>Cancel</button>
                  <button
                    className="ghost-button"
                    type="button"
                    style={{ color: "var(--danger)" }}
                    onClick={() => { setDeletionImpact(null); onRequestDelete(); }}
                  >
                    Delete Anyway
                  </button>
                </div>
              </section>
            </div>
          )}
        </section>
      </div>
    );
  }

  // ── Close mode ─────────────────────────────────────────────────────────
  if (isClose && gameSession) {
    const startBal = Number(gameSession.starting_balance || 0);
    const startRedeem = Number(gameSession.starting_redeemable || 0);
    const hasEnding = form.ending_balance !== "" && form.ending_balance !== undefined;

    // Find RTP from the game if present
    const sessionGame = gameSession.game_id
      ? games.find((g) => g.id === gameSession.game_id)
      : null;
    const sessionRtp = sessionGame?.rtp;

    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card entity-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="gs-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="gs-modal-title">Close Session</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>Cancel</button>
          </div>

          <div className="purchase-form">
            {/* ── Date / Time ── */}
            <div className="pf-section">
              <div className="pf-grid">
                <label className="field-label" style={{ gridRow: 1, gridColumn: 1 }}>Start Date</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 2 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>{gameSession.session_date}</span>
                </div>
                <label className="field-label" style={{ gridRow: 1, gridColumn: 3 }}>Start Time</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 4 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>{gameSession.session_time || "—"}</span>
                </div>
                <label className="field-label" htmlFor="gs-end-date-input" style={{ gridRow: 2, gridColumn: 1 }}>End Date</label>
                <div className="pf-cell" style={{ gridRow: 2, gridColumn: 2 }}>
                  <input
                    id="gs-end-date-input"
                    className={endDateInvalid ? "text-input invalid" : "text-input"}
                    type="date"
                    value={form.end_date}
                    onChange={(e) => setForm((c) => ({ ...c, end_date: e.target.value }))}
                  />
                </div>
                <label className="field-label" htmlFor="gs-end-time-input" style={{ gridRow: 2, gridColumn: 3 }}>End Time</label>
                <div className="pf-cell" style={{ gridRow: 2, gridColumn: 4 }}>
                  <input
                    id="gs-end-time-input"
                    className="text-input"
                    type="time"
                    step="1"
                    value={form.end_time}
                    onChange={(e) => setForm((c) => ({ ...c, end_time: e.target.value }))}
                  />
                </div>
              </div>
            </div>

            {/* ── Balances ── */}
            <div className="pf-section">
              <p className="pf-section-title"><span>💰</span> Balances</p>
              <div className="pf-grid">
                <label className="field-label" htmlFor="gs-end-bal-input" style={{ gridRow: 1, gridColumn: 1 }}>End Total SC</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 2 }}>
                  <input
                    id="gs-end-bal-input"
                    className={endBalInvalid ? "text-input invalid" : "text-input"}
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    title={endBalInvalid ? "Required" : undefined}
                    value={form.ending_balance}
                    onChange={(e) => setForm((c) => ({ ...c, ending_balance: e.target.value }))}
                  />
                </div>
                <label className="field-label" htmlFor="gs-end-redeem-input" style={{ gridRow: 1, gridColumn: 3 }}>End Redeemable SC</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 4 }}>
                  <input
                    id="gs-end-redeem-input"
                    className="text-input"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={form.ending_redeemable}
                    onChange={(e) => setForm((c) => ({ ...c, ending_redeemable: e.target.value }))}
                  />
                </div>
                <label className="field-label" htmlFor="gs-wager-input" style={{ gridRow: 2, gridColumn: 1 }}>Wager Amount</label>
                <div className="pf-cell" style={{ gridRow: 2, gridColumn: 2 }}>
                  <input
                    id="gs-wager-input"
                    className="text-input"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={form.wager_amount}
                    onChange={(e) => setForm((c) => ({ ...c, wager_amount: e.target.value }))}
                  />
                </div>
              </div>
            </div>

            {/* ── Session Details (read-only computed stats) ── */}
            <div className="pf-section">
              <p className="pf-section-title"><span>📊</span> Session Details</p>
              <div className="pf-grid">
                <span className="field-label" style={{ gridRow: 1, gridColumn: 1 }}>Start SC</span>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 2 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>{startBal.toFixed(2)}</span>
                </div>
                <span className="field-label" style={{ gridRow: 1, gridColumn: 3 }}>Start Redeemable</span>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 4 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>{startRedeem.toFixed(2)}</span>
                </div>

                <span className="field-label" style={{ gridRow: 2, gridColumn: 1 }}>Δ Total</span>
                <div className="pf-cell" style={{ gridRow: 2, gridColumn: 2 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>
                    {hasEnding ? plPreview.deltaTotal.toFixed(2) : "—"}
                  </span>
                </div>
                <span className="field-label" style={{ gridRow: 2, gridColumn: 3 }}>Δ Basis</span>
                <div className="pf-cell" style={{ gridRow: 2, gridColumn: 4 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>—</span>
                </div>

                <span className="field-label" style={{ gridRow: 3, gridColumn: 1 }}>Δ Redeemable</span>
                <div className="pf-cell" style={{ gridRow: 3, gridColumn: 2 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>
                    {hasEnding ? plPreview.deltaRedeem.toFixed(2) : "—"}
                  </span>
                </div>
                <span className="field-label" style={{ gridRow: 3, gridColumn: 3 }}>Net P/L</span>
                <div className="pf-cell" style={{ gridRow: 3, gridColumn: 4 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>
                    {hasEnding ? (
                      <span className={plPreview.netPL >= 0 ? "pl-positive" : "pl-negative"}>
                        {plPreview.netPL >= 0 ? "+" : ""}{plPreview.netPL.toFixed(2)}
                      </span>
                    ) : "—"}
                  </span>
                </div>

                <span className="field-label" style={{ gridRow: 4, gridColumn: 1 }}>Game Type</span>
                <div className="pf-cell" style={{ gridRow: 4, gridColumn: 2 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>{gameSession.game_type_name || "—"}</span>
                </div>
                <span className="field-label" style={{ gridRow: 4, gridColumn: 3 }}>Game</span>
                <div className="pf-cell" style={{ gridRow: 4, gridColumn: 4 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>{gameSession.game_name || "—"}</span>
                </div>

                <span className="field-label" style={{ gridRow: 5, gridColumn: 1 }}>RTP</span>
                <div className="pf-cell" style={{ gridRow: 5, gridColumn: 2 }}>
                  <span className="text-input" style={{ opacity: 0.7 }}>
                    {sessionRtp != null ? `${Number(sessionRtp).toFixed(2)}%` : "—"}
                  </span>
                </div>
              </div>
            </div>

            {/* ── Notes ── */}
            <div className="pf-notes-row">
              <label className="field-label" htmlFor="gs-notes-input">Notes</label>
              <textarea
                id="gs-notes-input"
                className="notes-input"
                placeholder="Optional"
                rows={2}
                value={form.notes}
                onChange={(e) => setForm((c) => ({ ...c, notes: e.target.value }))}
              />
            </div>
          </div>

          {submitError ? <p className="submit-error">{submitError}</p> : null}

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button
                className="ghost-button"
                type="button"
                onClick={handleEndAndStartNew}
                disabled={endAndStartPending || !form.ending_balance}
                title="Close this session and immediately start a new one"
              >
                End &amp; Start New
              </button>
            </div>
            <div className="toolbar-row">
              <button
                className="primary-button"
                type="button"
                onClick={onSubmit}
                disabled={formInvalid || endAndStartPending}
              >
                End Session
              </button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  // ── Create / Edit mode ────────────────────────────────────────────────────
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card entity-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="gs-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="gs-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="purchase-form">
          {/* ── Date / Time ── */}
          <div className="pf-datetime-row">
            <label className="field-label" htmlFor="gs-date-input">Date</label>
            <input
              id="gs-date-input"
              className={dateInvalid ? "text-input invalid" : "text-input"}
              type="date"
              value={form.session_date}
              readOnly={readOnly}
              onChange={(e) => setForm((c) => ({ ...c, session_date: e.target.value }))}
            />
            <label className="field-label" htmlFor="gs-time-input">Time</label>
            <input
              id="gs-time-input"
              className="text-input"
              type="time"
              step="1"
              value={form.session_time}
              readOnly={readOnly}
              onChange={(e) => setForm((c) => ({ ...c, session_time: e.target.value }))}
            />
          </div>

          {/* ── Session Details ── */}
          <div className="pf-section">
            <p className="pf-section-title"><span>🎰</span> Session Details</p>
            <div className="pf-grid">
              <label className="field-label" htmlFor="gs-user-input" style={{ gridRow: 1, gridColumn: 1 }}>User</label>
              <div className="pf-cell" ref={userRef} style={{ gridRow: 1, gridColumn: 2 }}>
                <TypeaheadSelect
                  id="gs-user-input"
                  options={users.map((u) => ({ value: u.id, label: u.name }))}
                  value={form.user_id}
                  onChange={(v) => setForm((c) => ({ ...c, user_id: v }))}
                  placeholder="Select…"
                  disabled={readOnly}
                  invalid={userInvalid}
                  title={userInvalid ? "Required" : undefined}
                />
              </div>
              <label className="field-label" htmlFor="gs-site-input" style={{ gridRow: 2, gridColumn: 1 }}>Site</label>
              <div className="pf-cell" style={{ gridRow: 2, gridColumn: 2 }}>
                <TypeaheadSelect
                  id="gs-site-input"
                  options={sites.map((s) => ({ value: s.id, label: s.name }))}
                  value={form.site_id}
                  onChange={(v) => setForm((c) => ({ ...c, site_id: v }))}
                  placeholder="Select…"
                  disabled={readOnly}
                  invalid={siteInvalid}
                  title={siteInvalid ? "Required" : undefined}
                />
              </div>
              <label className="field-label" htmlFor="gs-game-type-input" style={{ gridRow: 3, gridColumn: 1 }}>Game Type</label>
              <div className="pf-cell" style={{ gridRow: 3, gridColumn: 2 }}>
                <TypeaheadSelect
                  id="gs-game-type-input"
                  options={gameTypes.map((gt) => ({ value: gt.id, label: gt.name }))}
                  value={form.game_type_id}
                  onChange={(v) => setForm((c) => ({ ...c, game_type_id: v, game_id: v === c.game_type_id ? c.game_id : "" }))}
                  placeholder="Optional"
                  disabled={readOnly}
                />
              </div>

              <label className="field-label" htmlFor="gs-start-bal-input" style={{ gridRow: 1, gridColumn: 3 }}>Starting SC</label>
              <div className="pf-cell" style={{ gridRow: 1, gridColumn: 4 }}>
                <input
                  id="gs-start-bal-input"
                  className={startBalInvalid ? "text-input invalid" : "text-input"}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  title={startBalInvalid ? "Required" : undefined}
                  value={form.starting_balance}
                  readOnly={readOnly}
                  onChange={(e) => setForm((c) => ({ ...c, starting_balance: e.target.value }))}
                />
              </div>
              <label className="field-label" htmlFor="gs-start-redeem-input" style={{ gridRow: 2, gridColumn: 3 }}>Starting Redeem</label>
              <div className="pf-cell" style={{ gridRow: 2, gridColumn: 4 }}>
                <input
                  id="gs-start-redeem-input"
                  className="text-input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  value={form.starting_redeemable}
                  readOnly={readOnly}
                  onChange={(e) => setForm((c) => ({ ...c, starting_redeemable: e.target.value }))}
                />
              </div>
              <label className="field-label" htmlFor="gs-game-input" style={{ gridRow: 3, gridColumn: 3 }}>Game</label>
              <div className="pf-cell" style={{ gridRow: 3, gridColumn: 4 }}>
                <TypeaheadSelect
                  id="gs-game-input"
                  options={filteredGames.map((g) => ({ value: g.id, label: g.name }))}
                  value={form.game_id}
                  onChange={(v) => setForm((c) => ({ ...c, game_id: v }))}
                  placeholder={form.game_type_id ? "Select…" : "Optional"}
                  disabled={readOnly}
                />
              </div>
            </div>
          </div>

          {/* ── Balance Check ── */}
          {balanceCheck && (
            <div className={`pf-balance-check pf-balance-${balanceCheck.status}`}>
              {balanceCheck.message}
            </div>
          )}
          {redeemableCheck && (
            <div className={`pf-balance-check pf-balance-${redeemableCheck.status}`}>
              {redeemableCheck.message}
            </div>
          )}

          {/* ── End Session Section (Closed sessions only) ── */}
          {isClosed && (
            <div className="pf-section">
              <p className="pf-section-title"><span>🏁</span> Session End</p>
              <div className="pf-grid">
                <label className="field-label" htmlFor="gs-end-date-input" style={{ gridRow: 1, gridColumn: 1 }}>End Date</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 2 }}>
                  <input
                    id="gs-end-date-input"
                    className={endDateInvalid ? "text-input invalid" : "text-input"}
                    type="date"
                    value={form.end_date}
                    readOnly={readOnly}
                    onChange={(e) => setForm((c) => ({ ...c, end_date: e.target.value }))}
                  />
                </div>
                <label className="field-label" htmlFor="gs-end-time-input" style={{ gridRow: 2, gridColumn: 1 }}>End Time</label>
                <div className="pf-cell" style={{ gridRow: 2, gridColumn: 2 }}>
                  <input
                    id="gs-end-time-input"
                    className="text-input"
                    type="time"
                    step="1"
                    value={form.end_time}
                    readOnly={readOnly}
                    onChange={(e) => setForm((c) => ({ ...c, end_time: e.target.value }))}
                  />
                </div>

                <label className="field-label" htmlFor="gs-end-bal-input" style={{ gridRow: 1, gridColumn: 3 }}>Ending SC</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 4 }}>
                  <input
                    id="gs-end-bal-input"
                    className={endBalInvalid ? "text-input invalid" : "text-input"}
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    title={endBalInvalid ? "Required" : undefined}
                    value={form.ending_balance}
                    readOnly={readOnly}
                    onChange={(e) => setForm((c) => ({ ...c, ending_balance: e.target.value }))}
                  />
                </div>
                <label className="field-label" htmlFor="gs-end-redeem-input" style={{ gridRow: 2, gridColumn: 3 }}>Ending Redeem</label>
                <div className="pf-cell" style={{ gridRow: 2, gridColumn: 4 }}>
                  <input
                    id="gs-end-redeem-input"
                    className="text-input"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={form.ending_redeemable}
                    readOnly={readOnly}
                    onChange={(e) => setForm((c) => ({ ...c, ending_redeemable: e.target.value }))}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ── Purchases / Redemptions During ── */}
          {isClosed && (
            <div className="pf-section">
              <p className="pf-section-title"><span>📊</span> Activity During Session</p>
              <div className="pf-grid">
                <label className="field-label" htmlFor="gs-purch-during" style={{ gridRow: 1, gridColumn: 1 }}>Purchases</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 2 }}>
                  <input
                    id="gs-purch-during"
                    className="text-input"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={form.purchases_during}
                    readOnly={readOnly}
                    onChange={(e) => setForm((c) => ({ ...c, purchases_during: e.target.value }))}
                  />
                </div>
                <label className="field-label" htmlFor="gs-redeem-during" style={{ gridRow: 1, gridColumn: 3 }}>Redemptions</label>
                <div className="pf-cell" style={{ gridRow: 1, gridColumn: 4 }}>
                  <input
                    id="gs-redeem-during"
                    className="text-input"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={form.redemptions_during}
                    readOnly={readOnly}
                    onChange={(e) => setForm((c) => ({ ...c, redemptions_during: e.target.value }))}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ── P/L Preview ── */}
          {plPreview && (
            <div className={`pf-balance-check ${plPreview.netPL >= 0 ? "pf-balance-match" : "pf-balance-lower"}`}>
              P/L Preview: {plPreview.netPL >= 0 ? "+" : ""}{plPreview.netPL.toFixed(2)} SC
              {" "}(Discoverable: {plPreview.discoverableSC.toFixed(2)}, Δ Redeem: {plPreview.deltaRedeem.toFixed(2)})
            </div>
          )}

          {/* ── Notes ── */}
          <div className="pf-notes-row">
            <label className="field-label" htmlFor="gs-notes-input">Notes</label>
            <textarea
              id="gs-notes-input"
              className="notes-input"
              placeholder="Optional"
              rows={2}
              value={form.notes}
              readOnly={readOnly}
              onChange={(e) => setForm((c) => ({ ...c, notes: e.target.value }))}
            />
          </div>
        </div>

        {submitError ? <p className="submit-error">{submitError}</p> : null}

        <div className="modal-actions modal-actions-split">
          <div className="toolbar-row" />
          <div className="toolbar-row">
            <button
              className="primary-button"
              type="button"
              onClick={onSubmit}
              disabled={formInvalid}
            >
              {isCreate ? "Start Session" : "Save Session"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
