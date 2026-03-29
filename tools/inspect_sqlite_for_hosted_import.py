"""Print a read-only inventory of a local SQLite database before hosted migration."""

from __future__ import annotations

import argparse
import json

from services.hosted.sqlite_migration_inventory_service import SQLiteMigrationInventoryService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect a Sezzions SQLite database before hosted import."
    )
    parser.add_argument(
        "db_path",
        nargs="?",
        default="sezzions.db",
        help="Path to the SQLite database to inspect.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    inventory = SQLiteMigrationInventoryService().inspect_database(args.db_path)
    print(json.dumps(inventory.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
