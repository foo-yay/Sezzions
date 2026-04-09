"""Tests for HostedGameSessionRepository — CRUD + queries against in-memory SQLite."""

from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repositories.hosted_game_session_repository import HostedGameSessionRepository
from services.hosted.persistence import (
    HostedBase,
    HostedGameRecord,
    HostedGameSessionRecord,
    HostedGameTypeRecord,
    HostedSiteRecord,
    HostedUserRecord,
    HostedWorkspaceRecord,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

W = "workspace-1"
U = "user-1"
S = "site-1"
G = "game-1"
GT = "game-type-1"


def _setup():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    repo = HostedGameSessionRepository()

    with Session() as session:
        session.add(HostedWorkspaceRecord(id=W, name="Test WS", account_id="acc-1"))
        session.add(HostedUserRecord(id=U, workspace_id=W, name="Alice"))
        session.add(HostedSiteRecord(id=S, workspace_id=W, name="CasinoA"))
        session.add(HostedGameTypeRecord(id=GT, workspace_id=W, name="Video Slots"))
        session.add(HostedGameRecord(id=G, workspace_id=W, name="Slots", game_type_id=GT))
        session.commit()

    return engine, Session, repo


# ------------------------------------------------------------------
# Tests — CRUD
# ------------------------------------------------------------------


def test_create_and_get():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            created = repo.create(
                session,
                workspace_id=W,
                user_id=U,
                site_id=S,
                session_date="2026-01-15",
                session_time="14:00:00",
                game_id=G,
                game_type_id=GT,
                starting_balance="100.00",
                notes="test session",
            )
            session.commit()

        assert created is not None
        assert created.id is not None
        assert created.user_name == "Alice"
        assert created.site_name == "CasinoA"
        assert created.game_name == "Slots"
        assert created.game_type_name == "Video Slots"
        assert created.session_date == "2026-01-15"
        assert created.starting_balance == "100.00"
        assert created.notes == "test session"

        # Re-fetch
        with Session() as session:
            fetched = repo.get_by_id_and_workspace_id(
                session, game_session_id=created.id, workspace_id=W,
            )
        assert fetched is not None
        assert fetched.id == created.id
    finally:
        engine.dispose()


def test_list_by_workspace_desc_order():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            repo.create(session, workspace_id=W, user_id=U, site_id=S,
                        session_date="2026-01-10", session_time="10:00:00")
            repo.create(session, workspace_id=W, user_id=U, site_id=S,
                        session_date="2026-01-15", session_time="14:00:00")
            repo.create(session, workspace_id=W, user_id=U, site_id=S,
                        session_date="2026-01-12", session_time="12:00:00")
            session.commit()

        with Session() as session:
            result = repo.list_by_workspace_id(session, W)
        assert len(result) == 3
        # DESC order: newest first
        assert result[0].session_date == "2026-01-15"
        assert result[1].session_date == "2026-01-12"
        assert result[2].session_date == "2026-01-10"
    finally:
        engine.dispose()


def test_list_by_user_and_site_asc_order():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            repo.create(session, workspace_id=W, user_id=U, site_id=S,
                        session_date="2026-01-15", session_time="14:00:00")
            repo.create(session, workspace_id=W, user_id=U, site_id=S,
                        session_date="2026-01-10", session_time="10:00:00")
            session.commit()

        with Session() as session:
            result = repo.list_by_workspace_user_and_site(session, W, U, S)
        assert len(result) == 2
        # ASC order: oldest first
        assert result[0].session_date == "2026-01-10"
        assert result[1].session_date == "2026-01-15"
    finally:
        engine.dispose()


def test_count_excludes_deleted():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            repo.create(session, workspace_id=W, user_id=U, site_id=S,
                        session_date="2026-01-10")
            gs2 = repo.create(session, workspace_id=W, user_id=U, site_id=S,
                              session_date="2026-01-15")
            session.commit()

        with Session() as session:
            assert repo.count_by_workspace_id(session, W) == 2
            repo.delete(session, game_session_id=gs2.id, workspace_id=W)
            session.commit()

        with Session() as session:
            assert repo.count_by_workspace_id(session, W) == 1
    finally:
        engine.dispose()


def test_update_session():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            created = repo.create(
                session, workspace_id=W, user_id=U, site_id=S,
                session_date="2026-01-15", starting_balance="100.00",
            )
            session.commit()

        with Session() as session:
            updated = repo.update(
                session,
                game_session_id=created.id, workspace_id=W,
                user_id=U, site_id=S,
                session_date="2026-01-15", starting_balance="200.00",
                ending_balance="300.00", status="Closed",
                end_date="2026-01-15", end_time="18:00:00",
            )
            session.commit()

        assert updated is not None
        assert updated.starting_balance == "200.00"
        assert updated.ending_balance == "300.00"
        assert updated.status == "Closed"
        assert updated.end_date == "2026-01-15"
    finally:
        engine.dispose()


def test_soft_delete():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            created = repo.create(
                session, workspace_id=W, user_id=U, site_id=S,
                session_date="2026-01-15",
            )
            session.commit()

        with Session() as session:
            result = repo.delete(session, game_session_id=created.id, workspace_id=W)
            session.commit()
        assert result is True

        # Soft-deleted session should not appear in queries
        with Session() as session:
            fetched = repo.get_by_id_and_workspace_id(
                session, game_session_id=created.id, workspace_id=W,
            )
        assert fetched is None

        # But the record still exists in DB (soft delete)
        with Session() as session:
            raw = session.get(HostedGameSessionRecord, created.id)
        assert raw is not None
        assert raw.deleted_at is not None
    finally:
        engine.dispose()


def test_delete_many_soft_deletes():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            gs1 = repo.create(session, workspace_id=W, user_id=U, site_id=S,
                              session_date="2026-01-10")
            gs2 = repo.create(session, workspace_id=W, user_id=U, site_id=S,
                              session_date="2026-01-15")
            gs3 = repo.create(session, workspace_id=W, user_id=U, site_id=S,
                              session_date="2026-01-20")
            session.commit()

        with Session() as session:
            count = repo.delete_many(
                session, game_session_ids=[gs1.id, gs3.id], workspace_id=W,
            )
            session.commit()
        assert count == 2

        with Session() as session:
            remaining = repo.list_by_workspace_id(session, W)
        assert len(remaining) == 1
        assert remaining[0].id == gs2.id
    finally:
        engine.dispose()


def test_get_active_session():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            active = repo.create(
                session, workspace_id=W, user_id=U, site_id=S,
                session_date="2026-01-15", status="Active",
            )
            repo.create(
                session, workspace_id=W, user_id=U, site_id=S,
                session_date="2026-01-10", status="Closed",
            )
            session.commit()

        with Session() as session:
            found = repo.get_active_session(
                session, workspace_id=W, user_id=U, site_id=S,
            )
        assert found is not None
        assert found.id == active.id
    finally:
        engine.dispose()


def test_get_active_session_exclude_id():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            active = repo.create(
                session, workspace_id=W, user_id=U, site_id=S,
                session_date="2026-01-15", status="Active",
            )
            session.commit()

        with Session() as session:
            found = repo.get_active_session(
                session, workspace_id=W, user_id=U, site_id=S,
                exclude_id=active.id,
            )
        assert found is None
    finally:
        engine.dispose()


def test_get_active_session_none_when_no_active():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            repo.create(
                session, workspace_id=W, user_id=U, site_id=S,
                session_date="2026-01-15", status="Closed",
            )
            session.commit()

        with Session() as session:
            found = repo.get_active_session(
                session, workspace_id=W, user_id=U, site_id=S,
            )
        assert found is None
    finally:
        engine.dispose()


def test_pagination():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            for i in range(5):
                repo.create(
                    session, workspace_id=W, user_id=U, site_id=S,
                    session_date=f"2026-01-{10 + i:02d}",
                )
            session.commit()

        with Session() as session:
            page1 = repo.list_by_workspace_id(session, W, limit=2, offset=0)
            page2 = repo.list_by_workspace_id(session, W, limit=2, offset=2)
            page3 = repo.list_by_workspace_id(session, W, limit=2, offset=4)
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1
    finally:
        engine.dispose()


def test_create_without_optional_game_fields():
    """Game and game type are optional — omitting should not error."""
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            created = repo.create(
                session, workspace_id=W, user_id=U, site_id=S,
                session_date="2026-01-15",
            )
            session.commit()
        assert created.game_id is None
        assert created.game_name is None
        assert created.game_type_id is None
        assert created.game_type_name is None
    finally:
        engine.dispose()


def test_delete_nonexistent_returns_false():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            result = repo.delete(
                session, game_session_id=str(uuid4()), workspace_id=W,
            )
        assert result is False
    finally:
        engine.dispose()


def test_update_nonexistent_returns_none():
    engine, Session, repo = _setup()
    try:
        with Session() as session:
            result = repo.update(
                session,
                game_session_id=str(uuid4()), workspace_id=W,
                user_id=U, site_id=S, session_date="2026-01-15",
            )
        assert result is None
    finally:
        engine.dispose()
