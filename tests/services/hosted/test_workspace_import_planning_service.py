import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repositories.hosted_account_repository import HostedAccountRepository
from repositories.hosted_workspace_repository import HostedWorkspaceRepository
from services.hosted.persistence import HostedBase
from services.hosted.workspace_import_planning_service import (
    HostedWorkspaceImportPlanningService,
)


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _create_inventory_db(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO schema_version (version) VALUES (1)")
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, is_active INTEGER DEFAULT 1)"
        )
        connection.execute(
            "CREATE TABLE sites (id INTEGER PRIMARY KEY, name TEXT NOT NULL, is_active INTEGER DEFAULT 1)"
        )
        connection.execute("INSERT INTO users (name, is_active) VALUES ('Elliot', 1)")
        connection.execute("INSERT INTO sites (name, is_active) VALUES ('Stake', 1)")
        connection.commit()
    finally:
        connection.close()


def test_plan_import_returns_inventory_for_accessible_source_db(tmp_path: Path) -> None:
    db_path = tmp_path / "seed.db"
    _create_inventory_db(db_path)

    engine, session_factory = _session_factory()
    try:
        with session_factory() as session:
            account = HostedAccountRepository().create(
                session,
                owner_email="owner@sezzions.com",
                supabase_user_id="user-123",
            )
            HostedWorkspaceRepository().create(
                session,
                account_id=account.id,
                name="owner@sezzions.com Workspace",
                source_db_path=str(db_path),
            )
            session.commit()

        summary = HostedWorkspaceImportPlanningService(session_factory).plan_import(
            supabase_user_id="user-123"
        )
    finally:
        engine.dispose()

    assert summary.status == "ready"
    assert summary.source_db_configured is True
    assert summary.source_db_accessible is True
    assert summary.inventory is not None
    assert summary.inventory.active_user_names == ["Elliot"]
    assert summary.inventory.site_names == ["Stake"]


def test_plan_import_reports_missing_source_db_path() -> None:
    engine, session_factory = _session_factory()
    try:
        with session_factory() as session:
            account = HostedAccountRepository().create(
                session,
                owner_email="owner@sezzions.com",
                supabase_user_id="user-123",
            )
            HostedWorkspaceRepository().create(
                session,
                account_id=account.id,
                name="owner@sezzions.com Workspace",
            )
            session.commit()

        summary = HostedWorkspaceImportPlanningService(session_factory).plan_import(
            supabase_user_id="user-123"
        )
    finally:
        engine.dispose()

    assert summary.status == "source-db-path-missing"
    assert summary.source_db_configured is False
    assert summary.source_db_accessible is False
    assert summary.inventory is None


def test_plan_import_reports_missing_source_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.db"
    engine, session_factory = _session_factory()
    try:
        with session_factory() as session:
            account = HostedAccountRepository().create(
                session,
                owner_email="owner@sezzions.com",
                supabase_user_id="user-123",
            )
            HostedWorkspaceRepository().create(
                session,
                account_id=account.id,
                name="owner@sezzions.com Workspace",
                source_db_path=str(missing_path),
            )
            session.commit()

        summary = HostedWorkspaceImportPlanningService(session_factory).plan_import(
            supabase_user_id="user-123"
        )
    finally:
        engine.dispose()

    assert summary.status == "source-db-not-found"
    assert summary.source_db_configured is True
    assert summary.source_db_accessible is False
    assert summary.inventory is None


def test_plan_import_reports_safe_failure_when_inventory_inspection_breaks(tmp_path: Path) -> None:
    db_path = tmp_path / "seed.db"
    _create_inventory_db(db_path)

    class ExplodingInventoryService:
        def inspect_database(self, db_path: str):
            raise RuntimeError("boom")

    engine, session_factory = _session_factory()
    try:
        with session_factory() as session:
            account = HostedAccountRepository().create(
                session,
                owner_email="owner@sezzions.com",
                supabase_user_id="user-123",
            )
            HostedWorkspaceRepository().create(
                session,
                account_id=account.id,
                name="owner@sezzions.com Workspace",
                source_db_path=str(db_path),
            )
            session.commit()

        summary = HostedWorkspaceImportPlanningService(
            session_factory,
            inventory_service=ExplodingInventoryService(),
        ).plan_import(supabase_user_id="user-123")
    finally:
        engine.dispose()

    assert summary.status == "inspection-failed"
    assert summary.source_db_configured is True
    assert summary.source_db_accessible is False
    assert summary.inventory is None


def test_plan_import_requires_existing_bootstrapped_workspace() -> None:
    engine, session_factory = _session_factory()
    try:
        service = HostedWorkspaceImportPlanningService(session_factory)
        with pytest.raises(LookupError):
            service.plan_import(supabase_user_id="user-123")
    finally:
        engine.dispose()