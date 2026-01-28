"""Run 100 varied CRUD scenarios and write a Markdown report."""
from __future__ import annotations

import os
import sys
import tempfile
import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app_facade import AppFacade


def _dec(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")


def _metrics(facade: AppFacade) -> Tuple[Decimal, Decimal, Decimal, Dict[str, int]]:
    sessions = facade.game_session_repo.get_all()
    session_pl = sum(
        Decimal(str(s.net_taxable_pl or 0))
        for s in sessions
        if getattr(s, "status", "") == "Closed"
    )

    unrealized_positions = facade.unrealized_position_repo.get_all_positions()
    unrealized_pl = sum((pos.unrealized_pl for pos in unrealized_positions), Decimal("0.00"))

    realized = facade.realized_transaction_repo.get_all()
    realized_pl = sum((tx.net_pl for tx in realized), Decimal("0.00"))

    counts = {
        "purchases": len(facade.purchase_repo.get_all()),
        "redemptions": len(facade.redemption_repo.get_all()),
        "sessions": len(sessions),
        "realized": len(realized),
        "unrealized_positions": len(unrealized_positions),
    }

    return session_pl, unrealized_pl, realized_pl, counts


def _close_session(facade: AppFacade, session_id: int, end_date: date, end_time: str) -> None:
    facade.update_game_session(
        session_id,
        status="Closed",
        end_date=end_date,
        end_time=end_time,
    )


def run() -> str:
    tmp_dir = tempfile.mkdtemp(prefix="sezzions_crud_")
    db_path = os.path.join(tmp_dir, "crud_scenarios.db")
    facade = AppFacade(db_path)

    user1 = facade.create_user("Scenario User A", "a@example.com")
    user2 = facade.create_user("Scenario User B", "b@example.com")
    site1 = facade.create_site("Scenario Site A", "https://site-a.test", sc_rate=1.0)
    site2 = facade.create_site("Scenario Site B", "https://site-b.test", sc_rate=1.0)
    gtype = facade.create_game_type("Scenario Type")
    game1 = facade.create_game("Scenario Game A", gtype.id, rtp=96.0)
    game2 = facade.create_game("Scenario Game B", gtype.id, rtp=92.0)
    method = facade.create_redemption_method("ACH")

    rng = random.Random(20260123)
    start_date = date(2026, 1, 1)

    store: Dict[str, List[int]] = {
        "purchases": [],
        "redemptions": [],
        "sessions": [],
    }

    def pick_user(i: int):
        return user1 if i % 2 == 0 else user2

    def pick_site(i: int):
        return site1 if i % 3 == 0 else site2

    def pick_game(i: int):
        return game1 if i % 2 == 0 else game2

    def mk_date(i: int) -> date:
        return start_date + timedelta(days=i % 25)

    def mk_time(i: int) -> str:
        hour = 9 + (i % 8)
        minute = (i * 7) % 60
        return f"{hour:02d}:{minute:02d}:00"

    scenarios: List[Dict[str, str]] = []
    failures: List[Dict[str, str]] = []

    scenario_types = [
        "purchase_create",
        "purchase_edit_notes",
        "purchase_edit_amount",
        "purchase_delete",
        "redemption_fifo_create",
        "redemption_no_fifo",
        "redemption_edit_reprocess",
        "redemption_delete",
        "session_create_close",
        "session_mid_events",
    ]

    for i in range(1, 101):
        kind = scenario_types[(i - 1) % len(scenario_types)]
        user = pick_user(i)
        site = pick_site(i)
        game = pick_game(i)
        scenario_date = mk_date(i)
        scenario_time = mk_time(i)
        amount = _dec(25 + (i % 10) * 10 + rng.random())

        steps: List[str] = []
        status = "PASS"
        error = ""

        try:
            if kind == "purchase_create":
                p = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    purchase_date=scenario_date,
                    purchase_time=scenario_time,
                    sc_received=amount,
                    notes=f"Scenario {i} purchase",
                )
                store["purchases"].append(p.id)
                steps.append(f"Create purchase ${amount} at {scenario_date} {scenario_time}.")

            elif kind == "purchase_edit_notes":
                p = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    purchase_date=scenario_date,
                    purchase_time=scenario_time,
                    sc_received=amount,
                    notes=f"Scenario {i} purchase",
                )
                store["purchases"].append(p.id)
                facade.update_purchase(p.id, notes="Updated notes")
                steps.append("Create purchase then edit notes.")

            elif kind == "purchase_edit_amount":
                p = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    purchase_date=scenario_date,
                    purchase_time=scenario_time,
                    sc_received=amount,
                    notes=f"Scenario {i} purchase",
                )
                store["purchases"].append(p.id)
                facade.update_purchase(p.id, amount=amount + Decimal("10.00"))
                steps.append("Create purchase then edit amount.")

            elif kind == "purchase_delete":
                p = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    purchase_date=scenario_date,
                    purchase_time=scenario_time,
                    sc_received=amount,
                    notes=f"Scenario {i} purchase",
                )
                steps.append("Create purchase then delete.")
                facade.delete_purchase(p.id)

            elif kind == "redemption_fifo_create":
                p = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    purchase_date=scenario_date,
                    purchase_time="08:00:00",
                    sc_received=amount,
                )
                store["purchases"].append(p.id)
                r = facade.create_redemption(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount - Decimal("5.00"),
                    redemption_date=scenario_date,
                    redemption_time="12:00:00",
                    redemption_method_id=method.id,
                    apply_fifo=True,
                )
                store["redemptions"].append(r.id)
                steps.append("Create purchase then FIFO redemption.")

            elif kind == "redemption_no_fifo":
                r = facade.create_redemption(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    redemption_date=scenario_date,
                    redemption_time=scenario_time,
                    redemption_method_id=method.id,
                    apply_fifo=False,
                )
                store["redemptions"].append(r.id)
                steps.append("Create redemption without FIFO.")

            elif kind == "redemption_edit_reprocess":
                p = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    purchase_date=scenario_date,
                    purchase_time="09:00:00",
                    sc_received=amount,
                )
                store["purchases"].append(p.id)
                r = facade.create_redemption(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount - Decimal("1.00"),
                    redemption_date=scenario_date,
                    redemption_time="10:00:00",
                    redemption_method_id=method.id,
                    apply_fifo=True,
                )
                store["redemptions"].append(r.id)
                facade.update_redemption_reprocess(r.id, amount=amount - Decimal("2.00"))
                steps.append("Create FIFO redemption then edit w/ reprocess.")

            elif kind == "redemption_delete":
                p = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount,
                    purchase_date=scenario_date,
                    purchase_time="09:00:00",
                    sc_received=amount,
                )
                store["purchases"].append(p.id)
                r = facade.create_redemption(
                    user_id=user.id,
                    site_id=site.id,
                    amount=amount - Decimal("3.00"),
                    redemption_date=scenario_date,
                    redemption_time="11:00:00",
                    redemption_method_id=method.id,
                    apply_fifo=True,
                )
                steps.append("Create FIFO redemption then delete.")
                facade.delete_redemption(r.id)

            elif kind == "session_create_close":
                s = facade.create_game_session(
                    user_id=user.id,
                    site_id=site.id,
                    game_id=game.id,
                    session_date=scenario_date,
                    session_time="10:00:00",
                    starting_balance=_dec(100 + i),
                    starting_redeemable=_dec(0),
                    ending_balance=_dec(120 + i),
                    ending_redeemable=_dec(20),
                    notes=f"Scenario {i} session",
                )
                store["sessions"].append(s.id)
                _close_session(facade, s.id, scenario_date, "23:59:59")
                steps.append("Create session and close it.")

            elif kind == "session_mid_events":
                p1 = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=_dec(60),
                    purchase_date=scenario_date,
                    purchase_time="09:30:00",
                    sc_received=_dec(60),
                )
                p2 = facade.create_purchase(
                    user_id=user.id,
                    site_id=site.id,
                    amount=_dec(40),
                    purchase_date=scenario_date,
                    purchase_time="10:30:00",
                    sc_received=_dec(40),
                )
                store["purchases"].extend([p1.id, p2.id])
                s = facade.create_game_session(
                    user_id=user.id,
                    site_id=site.id,
                    game_id=game.id,
                    session_date=scenario_date,
                    session_time="10:00:00",
                    starting_balance=_dec(100),
                    starting_redeemable=_dec(0),
                    ending_balance=_dec(140),
                    ending_redeemable=_dec(40),
                )
                store["sessions"].append(s.id)
                r = facade.create_redemption(
                    user_id=user.id,
                    site_id=site.id,
                    amount=_dec(30),
                    redemption_date=scenario_date,
                    redemption_time="11:15:00",
                    redemption_method_id=method.id,
                    apply_fifo=True,
                )
                store["redemptions"].append(r.id)
                _close_session(facade, s.id, scenario_date, "12:00:00")
                steps.append("Create two purchases, session, and FIFO redemption during session.")

            else:
                steps.append("No-op scenario")

        except Exception as exc:  # noqa: BLE001 - capture for report
            status = "FAIL"
            error = f"{type(exc).__name__}: {exc}"
            failures.append({"id": f"{i:03d}", "kind": kind, "error": error})

        session_pl, unrealized_pl, realized_pl, counts = _metrics(facade)
        scenarios.append(
            {
                "id": f"{i:03d}",
                "kind": kind,
                "steps": " ".join(steps),
                "status": status,
                "error": error,
                "session_pl": f"{session_pl:.2f}",
                "unrealized_pl": f"{unrealized_pl:.2f}",
                "realized_pl": f"{realized_pl:.2f}",
                "counts": counts,
            }
        )

    session_pl, unrealized_pl, realized_pl, counts = _metrics(facade)

    report_lines: List[str] = []
    report_lines.append("# CRUD Scenario Matrix (100 cases)")
    report_lines.append("")
    report_lines.append(f"Temporary DB path: {db_path}")
    report_lines.append(f"Generated on: {date.today().isoformat()}")
    report_lines.append("")
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append(f"- Total scenarios: {len(scenarios)}")
    report_lines.append(f"- Failures: {len(failures)}")
    report_lines.append(f"- Final Game Session P/L total: ${session_pl:.2f}")
    report_lines.append(f"- Final Unrealized P/L total: ${unrealized_pl:.2f}")
    report_lines.append(f"- Final Realized P/L total: ${realized_pl:.2f}")
    report_lines.append(
        f"- Counts: purchases={counts['purchases']}, redemptions={counts['redemptions']}, "
        f"sessions={counts['sessions']}, realized={counts['realized']}, "
        f"unrealized_positions={counts['unrealized_positions']}"
    )
    report_lines.append("")

    report_lines.append("## Scenarios")
    report_lines.append("")
    report_lines.append("| ID | Type | Status | Steps | Game Session P/L | Unrealized P/L | Realized P/L |")
    report_lines.append("|---:|------|:------:|-------|-----------------:|--------------:|------------:|")
    for s in scenarios:
        report_lines.append(
            "| {id} | {kind} | {status} | {steps} | ${session_pl} | ${unrealized_pl} | ${realized_pl} |".format(
                **s
            )
        )

    report_lines.append("")
    report_lines.append("## Failures")
    report_lines.append("")
    if not failures:
        report_lines.append("- None")
    else:
        for f in failures:
            report_lines.append(f"- {f['id']} ({f['kind']}): {f['error']}")

    report_lines.append("")
    report_lines.append("## Remedy Notes")
    report_lines.append("")
    if not failures:
        report_lines.append("- No remediation needed.")
    else:
        report_lines.append("- Review errors above and correct the underlying inputs or workflow.")
        report_lines.append("- If errors are due to active sessions, ensure sessions are closed before creating another.")
        report_lines.append("- If errors are due to guarded edits, use reprocess update paths or create new records.")

    output_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "docs",
        f"crud_scenario_matrix_{date.today().isoformat()}.md",
    )
    output_path = os.path.abspath(output_path)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines))

    return output_path


if __name__ == "__main__":
    report_path = run()
    print(report_path)
