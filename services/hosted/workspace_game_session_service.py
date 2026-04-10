"""Hosted workspace-managed game sessions service."""

from __future__ import annotations

from decimal import Decimal

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_game_session_repository import HostedGameSessionRepository
from repositories.hosted_purchase_repository import HostedPurchaseRepository
from repositories.hosted_redemption_repository import HostedRedemptionRepository
from repositories.hosted_site_repository import HostedSiteRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.hosted_event_link_service import HostedEventLinkService
from services.hosted.hosted_recalculation_service import HostedRecalculationService
from services.hosted.hosted_timestamp_service import HostedTimestampService
from services.hosted.models import HostedGameSession, HostedWorkspace


class HostedWorkspaceGameSessionService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.account_repository = HostedAccountRepository()
        self.workspace_repository = HostedWorkspaceRepository()
        self.game_session_repository = HostedGameSessionRepository()
        self.purchase_repository = HostedPurchaseRepository()
        self.redemption_repository = HostedRedemptionRepository()
        self.site_repository = HostedSiteRepository()
        self.recalculation_service = HostedRecalculationService()
        self.event_link_service = HostedEventLinkService()
        self.timestamp_service = HostedTimestampService()

    # ------------------------------------------------------------------ list

    def list_game_sessions_page(
        self,
        *,
        supabase_user_id: str,
        limit: int,
        offset: int = 0,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            total_count = self.game_session_repository.count_by_workspace_id(
                session, workspace.id
            )
            game_sessions = self.game_session_repository.list_by_workspace_id(
                session,
                workspace.id,
                limit=limit,
                offset=offset,
            )
            next_offset = offset + len(game_sessions)
            has_more = next_offset < total_count
            return {
                "game_sessions": game_sessions,
                "offset": offset,
                "limit": limit,
                "next_offset": next_offset,
                "total_count": total_count,
                "has_more": has_more,
            }

    # ------------------------------------------------------------------ create

    def create_game_session(
        self,
        *,
        supabase_user_id: str,
        user_id: str,
        site_id: str,
        session_date: str,
        session_time: str | None = None,
        start_entry_time_zone: str | None = None,
        game_id: str | None = None,
        game_type_id: str | None = None,
        end_date: str | None = None,
        end_time: str | None = None,
        end_entry_time_zone: str | None = None,
        starting_balance: str = "0.00",
        ending_balance: str = "0.00",
        starting_redeemable: str = "0.00",
        ending_redeemable: str = "0.00",
        wager_amount: str = "0.00",
        rtp: float | None = None,
        purchases_during: str = "0.00",
        redemptions_during: str = "0.00",
        status_value: str = "Active",
        notes: str | None = None,
    ) -> HostedGameSession:
        # Validate DTO early (required fields, strip, etc.)
        candidate = HostedGameSession(
            user_id=user_id,
            site_id=site_id,
            session_date=session_date,
            session_time=session_time or "00:00:00",
            start_entry_time_zone=start_entry_time_zone,
            game_id=game_id,
            game_type_id=game_type_id,
            end_date=end_date,
            end_time=end_time,
            end_entry_time_zone=end_entry_time_zone,
            starting_balance=starting_balance,
            ending_balance=ending_balance,
            starting_redeemable=starting_redeemable,
            ending_redeemable=ending_redeemable,
            wager_amount=wager_amount,
            rtp=rtp,
            purchases_during=purchases_during,
            redemptions_during=redemptions_during,
            status=status_value,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            # Active session guard: only one active session per user+site
            if candidate.status == "Active":
                existing_active = self.game_session_repository.get_active_session(
                    session,
                    workspace_id=workspace.id,
                    user_id=candidate.user_id,
                    site_id=candidate.site_id,
                )
                if existing_active is not None:
                    raise ValueError(
                        "An active session already exists for this user and site. "
                        "Close the existing session before starting a new one."
                    )

            # Ensure unique start timestamp
            adj_date, adj_time, _ = self.timestamp_service.ensure_unique_timestamp(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                date_str=candidate.session_date,
                time_str=candidate.session_time,
                event_type="session_start",
            )
            candidate.session_date = adj_date
            candidate.session_time = adj_time

            # Ensure unique end timestamp (if closing immediately)
            if candidate.end_date and candidate.end_time:
                end_adj_date, end_adj_time, _ = self.timestamp_service.ensure_unique_timestamp(
                    session,
                    workspace_id=workspace.id,
                    user_id=candidate.user_id,
                    site_id=candidate.site_id,
                    date_str=candidate.end_date,
                    time_str=candidate.end_time,
                    event_type="session_end",
                )
                candidate.end_date = end_adj_date
                candidate.end_time = end_adj_time

            created = self.game_session_repository.create(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                session_date=candidate.session_date,
                session_time=candidate.session_time,
                start_entry_time_zone=candidate.start_entry_time_zone,
                game_id=candidate.game_id,
                game_type_id=candidate.game_type_id,
                end_date=candidate.end_date,
                end_time=candidate.end_time,
                end_entry_time_zone=candidate.end_entry_time_zone,
                starting_balance=candidate.starting_balance,
                ending_balance=candidate.ending_balance,
                starting_redeemable=candidate.starting_redeemable,
                ending_redeemable=candidate.ending_redeemable,
                wager_amount=candidate.wager_amount,
                rtp=candidate.rtp,
                purchases_during=candidate.purchases_during,
                redemptions_during=candidate.redemptions_during,
                status=candidate.status,
                notes=candidate.notes,
            )

            # Rebuild event links and FIFO for the affected (user, site) pair
            self.event_link_service.rebuild_links_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
            )
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
            )

            session.commit()

            return self.game_session_repository.get_by_id_and_workspace_id(
                session, game_session_id=created.id, workspace_id=workspace.id
            ) or created

    # ------------------------------------------------------------------ update

    def update_game_session(
        self,
        *,
        supabase_user_id: str,
        game_session_id: str,
        user_id: str,
        site_id: str,
        session_date: str,
        session_time: str | None = None,
        start_entry_time_zone: str | None = None,
        game_id: str | None = None,
        game_type_id: str | None = None,
        end_date: str | None = None,
        end_time: str | None = None,
        end_entry_time_zone: str | None = None,
        starting_balance: str = "0.00",
        ending_balance: str = "0.00",
        starting_redeemable: str = "0.00",
        ending_redeemable: str = "0.00",
        wager_amount: str = "0.00",
        rtp: float | None = None,
        purchases_during: str = "0.00",
        redemptions_during: str = "0.00",
        status_value: str = "Active",
        notes: str | None = None,
    ) -> HostedGameSession:
        candidate = HostedGameSession(
            user_id=user_id,
            site_id=site_id,
            session_date=session_date,
            session_time=session_time or "00:00:00",
            start_entry_time_zone=start_entry_time_zone,
            game_id=game_id,
            game_type_id=game_type_id,
            end_date=end_date,
            end_time=end_time,
            end_entry_time_zone=end_entry_time_zone,
            starting_balance=starting_balance,
            ending_balance=ending_balance,
            starting_redeemable=starting_redeemable,
            ending_redeemable=ending_redeemable,
            wager_amount=wager_amount,
            rtp=rtp,
            purchases_during=purchases_during,
            redemptions_during=redemptions_during,
            status=status_value,
            notes=notes,
        )

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            existing = self.game_session_repository.get_by_id_and_workspace_id(
                session, game_session_id=game_session_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError(
                    "Game session was not found in the authenticated workspace."
                )

            # Active session guard: if changing to Active, check no other active session
            if candidate.status == "Active":
                existing_active = self.game_session_repository.get_active_session(
                    session,
                    workspace_id=workspace.id,
                    user_id=candidate.user_id,
                    site_id=candidate.site_id,
                    exclude_id=game_session_id,
                )
                if existing_active is not None:
                    raise ValueError(
                        "An active session already exists for this user and site. "
                        "Close the existing session before opening another."
                    )

            old_user_id = existing.user_id
            old_site_id = existing.site_id

            # Ensure unique start timestamp
            adj_date, adj_time, _ = self.timestamp_service.ensure_unique_timestamp(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                date_str=candidate.session_date,
                time_str=candidate.session_time,
                exclude_id=game_session_id,
                event_type="session_start",
            )
            candidate.session_date = adj_date
            candidate.session_time = adj_time

            # Ensure unique end timestamp (if closing)
            if candidate.end_date and candidate.end_time:
                end_adj_date, end_adj_time, _ = self.timestamp_service.ensure_unique_timestamp(
                    session,
                    workspace_id=workspace.id,
                    user_id=candidate.user_id,
                    site_id=candidate.site_id,
                    date_str=candidate.end_date,
                    time_str=candidate.end_time,
                    exclude_id=game_session_id,
                    event_type="session_end",
                )
                candidate.end_date = end_adj_date
                candidate.end_time = end_adj_time

            updated = self.game_session_repository.update(
                session,
                game_session_id=game_session_id,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
                session_date=candidate.session_date,
                session_time=candidate.session_time,
                start_entry_time_zone=candidate.start_entry_time_zone,
                game_id=candidate.game_id,
                game_type_id=candidate.game_type_id,
                end_date=candidate.end_date,
                end_time=candidate.end_time,
                end_entry_time_zone=candidate.end_entry_time_zone,
                starting_balance=candidate.starting_balance,
                ending_balance=candidate.ending_balance,
                starting_redeemable=candidate.starting_redeemable,
                ending_redeemable=candidate.ending_redeemable,
                wager_amount=candidate.wager_amount,
                rtp=candidate.rtp,
                purchases_during=candidate.purchases_during,
                redemptions_during=candidate.redemptions_during,
                status=candidate.status,
                notes=candidate.notes,
            )
            if updated is None:
                raise LookupError(
                    "Game session was not found in the authenticated workspace."
                )

            # Rebuild event links and FIFO for current pair
            self.event_link_service.rebuild_links_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
            )
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=candidate.user_id,
                site_id=candidate.site_id,
            )

            # If (user, site) changed, also rebuild the old pair
            if old_user_id != candidate.user_id or old_site_id != candidate.site_id:
                self.event_link_service.rebuild_links_for_pair(
                    session,
                    workspace_id=workspace.id,
                    user_id=old_user_id,
                    site_id=old_site_id,
                )
                self.recalculation_service.rebuild_fifo_for_pair(
                    session,
                    workspace_id=workspace.id,
                    user_id=old_user_id,
                    site_id=old_site_id,
                )

            session.commit()

            return self.game_session_repository.get_by_id_and_workspace_id(
                session, game_session_id=game_session_id, workspace_id=workspace.id
            ) or updated

    # ------------------------------------------------------------------ delete

    def delete_game_session(
        self,
        *,
        supabase_user_id: str,
        game_session_id: str,
    ) -> None:
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            existing = self.game_session_repository.get_by_id_and_workspace_id(
                session, game_session_id=game_session_id, workspace_id=workspace.id
            )
            if existing is None:
                raise LookupError(
                    "Game session was not found in the authenticated workspace."
                )

            deleted = self.game_session_repository.delete(
                session,
                game_session_id=game_session_id,
                workspace_id=workspace.id,
            )
            if not deleted:
                raise LookupError(
                    "Game session was not found in the authenticated workspace."
                )

            # Rebuild event links and FIFO for affected pair
            self.event_link_service.rebuild_links_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
            )
            self.recalculation_service.rebuild_fifo_for_pair(
                session,
                workspace_id=workspace.id,
                user_id=existing.user_id,
                site_id=existing.site_id,
            )

            session.commit()

    def delete_game_sessions(
        self,
        *,
        supabase_user_id: str,
        game_session_ids: list[str],
    ) -> int:
        normalized_ids = list(dict.fromkeys(game_session_ids))
        if not normalized_ids:
            raise ValueError("At least one game session id is required.")

        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)

            # Collect affected pairs for post-deletion rebuild
            affected_pairs: set[tuple[str, str]] = set()
            for gsid in normalized_ids:
                existing = self.game_session_repository.get_by_id_and_workspace_id(
                    session, game_session_id=gsid, workspace_id=workspace.id
                )
                if existing is None:
                    raise LookupError(
                        "One or more game sessions were not found in the authenticated workspace."
                    )
                affected_pairs.add((existing.user_id, existing.site_id))

            deleted_count = self.game_session_repository.delete_many(
                session,
                game_session_ids=normalized_ids,
                workspace_id=workspace.id,
            )
            if deleted_count != len(normalized_ids):
                raise LookupError(
                    "One or more game sessions were not found in the authenticated workspace."
                )

            # Rebuild event links and FIFO for all affected pairs
            for uid, sid in affected_pairs:
                self.event_link_service.rebuild_links_for_pair(
                    session,
                    workspace_id=workspace.id,
                    user_id=uid,
                    site_id=sid,
                )
                self.recalculation_service.rebuild_fifo_for_pair(
                    session,
                    workspace_id=workspace.id,
                    user_id=uid,
                    site_id=sid,
                )

            session.commit()
            return deleted_count

    # -------------------------------------------------------- expected balances

    def compute_expected_balances(
        self,
        *,
        supabase_user_id: str,
        user_id: str,
        site_id: str,
        session_date: str,
        session_time: str = "00:00:00",
    ) -> dict[str, str]:
        """Compute expected starting SC and redeemable balances for a new session.

        Algorithm (Priority 2/3 — no checkpoint anchors yet):
        1. Find anchor: latest Closed session ending before the cutoff.
        2. If no closed session, start from (0, 0).
        3. Apply purchase and redemption events between anchor and cutoff.
        4. Floor at 0.
        """
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            wid = workspace.id

            # Site sc_rate for dollar→SC conversion on redemptions
            site_sc_rate = Decimal("1")
            site = self.site_repository.get_by_id_and_workspace_id(
                session, site_id=site_id, workspace_id=wid,
            )
            if site is not None:
                try:
                    parsed = Decimal(str(site.sc_rate))
                    if parsed > 0:
                        site_sc_rate = parsed
                except Exception:
                    pass

            cutoff = f"{session_date}T{session_time or '00:00:00'}"

            # --- Priority 2: latest closed session before cutoff ----
            all_sessions = self.game_session_repository.list_by_workspace_user_and_site(
                session, wid, user_id, site_id,
            )
            anchor_dt: str | None = None
            expected_total = Decimal("0")
            expected_redeemable = Decimal("0")

            for gs in all_sessions:
                if gs.status != "Closed" or not gs.end_date:
                    continue
                gs_end_dt = f"{gs.end_date}T{gs.end_time or '00:00:00'}"
                if gs_end_dt < cutoff and (anchor_dt is None or gs_end_dt > anchor_dt):
                    anchor_dt = gs_end_dt
                    expected_total = Decimal(str(gs.ending_balance or "0"))
                    expected_redeemable = Decimal(str(gs.ending_redeemable or "0"))

            # --- Timeline events after anchor, before cutoff --------
            purchases = self.purchase_repository.list_by_workspace_user_and_site(
                session, wid, user_id, site_id,
            )
            redemptions = self.redemption_repository.list_by_workspace_user_and_site(
                session, wid, user_id, site_id,
            )

            def redemption_amount_sc(amount_str: str) -> Decimal:
                return Decimal(str(amount_str or "0")) / site_sc_rate

            # Build timeline: (sort_key, event_type_order, id, type, record)
            timeline = []
            for p in purchases:
                p_dt = f"{p.purchase_date}T{p.purchase_time or '00:00:00'}"
                if anchor_dt is not None and p_dt <= anchor_dt:
                    continue
                if p_dt >= cutoff:
                    continue
                timeline.append((p_dt, 0, p.id or "", "purchase", p))

            for r in redemptions:
                r_status = getattr(r, "status", "PENDING") or "PENDING"
                r_dt = f"{r.redemption_date}T{r.redemption_time or '00:00:00'}"
                # Debit event at redemption time
                if (anchor_dt is None or r_dt > anchor_dt) and r_dt < cutoff:
                    timeline.append((r_dt, 1, r.id or "", "redemption_debit", r))
                # Credit event at cancellation time (two-event delta model)
                if r_status == "CANCELED":
                    canceled_at = getattr(r, "canceled_at", None)
                    if canceled_at:
                        # canceled_at is UTC ISO; extract comparable string
                        cancel_dt = canceled_at[:19].replace(" ", "T")
                        if (anchor_dt is None or cancel_dt > anchor_dt) and cancel_dt < cutoff:
                            timeline.append((cancel_dt, 2, r.id or "", "redemption_credit", r))

            timeline.sort(key=lambda e: (e[0], e[1], e[2]))

            for _, _, _, event_type, record in timeline:
                if event_type == "purchase":
                    expected_total = Decimal(str(record.starting_sc_balance or "0"))
                    if getattr(record, "starting_redeemable_balance", None) is not None:
                        expected_redeemable = Decimal(str(record.starting_redeemable_balance))
                elif event_type == "redemption_debit":
                    amt = redemption_amount_sc(record.amount)
                    expected_total -= amt
                    expected_redeemable -= amt
                elif event_type == "redemption_credit":
                    amt = redemption_amount_sc(record.amount)
                    expected_total += amt
                    expected_redeemable += amt

            expected_total = max(Decimal("0"), expected_total)
            expected_redeemable = max(Decimal("0"), expected_redeemable)

            return {
                "expected_start_total": f"{expected_total:.2f}",
                "expected_start_redeemable": f"{expected_redeemable:.2f}",
            }

    # -------------------------------------------------------- deletion impact

    def get_deletion_impact(
        self,
        *,
        supabase_user_id: str,
        game_session_id: str,
    ) -> dict[str, object]:
        """Check if deleting a closed session would affect subsequent redemptions.

        Returns a dict with ``has_impact`` (bool) and ``message`` (str).
        """
        with self.session_factory() as session:
            workspace = self._require_workspace(session, supabase_user_id)
            wid = workspace.id

            gs = self.game_session_repository.get_by_id_and_workspace_id(
                session, game_session_id=game_session_id, workspace_id=wid,
            )
            if gs is None or gs.status != "Closed" or not gs.end_date:
                return {"has_impact": False, "message": ""}

            end_dt = f"{gs.end_date}T{gs.end_time or '00:00:00'}"

            # Count non-canceled redemptions after this session's end
            redemptions = self.redemption_repository.list_by_workspace_user_and_site(
                session, wid, gs.user_id, gs.site_id,
            )
            subsequent = [
                r for r in redemptions
                if f"{r.redemption_date}T{r.redemption_time or '00:00:00'}" > end_dt
                and getattr(r, "status", "PENDING") not in ("CANCELED",)
            ]
            if not subsequent:
                return {"has_impact": False, "message": ""}

            count = len(subsequent)
            total_dollars = sum(Decimal(str(r.amount or "0")) for r in subsequent)

            # Find the previous closed session's ending balance
            all_sessions = self.game_session_repository.list_by_workspace_user_and_site(
                session, wid, gs.user_id, gs.site_id,
            )
            prev_balance = Decimal("0")
            start_dt = f"{gs.session_date}T{gs.session_time or '00:00:00'}"
            for s in all_sessions:
                if s.id == gs.id or s.status != "Closed" or not s.end_date:
                    continue
                s_end_dt = f"{s.end_date}T{s.end_time or '00:00:00'}"
                if s_end_dt < start_dt:
                    prev_balance = Decimal(str(s.ending_balance or "0"))

            ending_balance = Decimal(str(gs.ending_balance or "0"))
            msg = (
                f"Session: {gs.site_name or 'Unknown'} / {gs.user_name or 'Unknown'}\n"
                f"Session ended with {ending_balance:,.2f} SC\n"
                f"Found {count} redemption(s) after this session "
                f"totaling ${total_dollars:,.2f}\n\n"
                f"If you delete this session:\n"
                f"\u2022 Expected balance drops to {prev_balance:,.2f} SC\n"
                f"\u2022 Redemptions may temporarily exceed expected balance\n"
                f"\u2022 You won't be able to edit redemptions until you fix the gap"
            )
            return {"has_impact": True, "message": msg}

    # ------------------------------------------------------------------ helpers

    def _require_workspace(self, session, supabase_user_id: str) -> HostedWorkspace:
        account = self.account_repository.get_by_supabase_user_id(session, supabase_user_id)
        if account is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing game sessions."
            )

        workspace = self.workspace_repository.get_by_account_id(session, account.id)
        if workspace is None:
            raise LookupError(
                "Hosted workspace bootstrap must complete before managing game sessions."
            )

        return workspace
