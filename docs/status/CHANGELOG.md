# Sezzions — Changelog (Human + AI Parsable)

Purpose: a chronological log of noteworthy changes.

Rules:
- One entry per meaningful change set.
- Prefer adding here over creating a new markdown file.
- Entries must include the metadata block.

---

## 2026-01-28

```yaml
id: 2026-01-28-12
type: feature
areas: [tools, database, ui, testing]
summary: "Complete database tools implementation (Issue #2): backup/restore/reset with automatic scheduling, audit logging, and comprehensive testing."
files_changed:
  - ui/tabs/tools_tab.py
  - ui/tools_dialogs.py
  - ui/settings.py
  - services/tools/backup_service.py
  - services/tools/restore_service.py
  - services/tools/reset_service.py
  - repositories/database.py
  - settings.json
  - tests/integration/test_database_tools_integration.py
  - tests/integration/test_database_tools_audit.py
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

Notes:
- **Manual Backup UI**: Directory selection, "Backup Now" button, timestamped files (backup_YYYYMMDD_HHMMSS.db), status display with file size
- **Restore UI**: RestoreDialog with three modes (Replace/Merge All/Merge Selected), safety backups, file validation, confirmations
- **Reset UI**: ResetDialog with preserve setup data option, table count preview, typed "DELETE" confirmation, optional pre-reset backup
- **Automatic Backup**: JSON-based configuration in settings.json with enable toggle, directory selection, frequency (1-168 hrs), QTimer scheduling (5-min checks), non-blocking execution, color-coded status, test button
- **Audit Logging**: DatabaseManager.log_audit() method, all operations log to audit_log table with action type/table/details/timestamp
- **Testing**: 19 tests total (9 existing database tools + 10 new audit logging tests), all passing
- **Services**: BackupService, RestoreService, ResetService use SQLite online backup API
- **Safety Features**: Integrity checks, automatic safety backups, multiple confirmations, typed confirmations for destructive actions

Refs: Issue #2

```yaml
id: 2026-01-28-01
type: docs
areas: [docs, workflow]
summary: "Consolidated docs governance; created master spec, index, status, and reduced root markdown sprawl."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/status/STATUS.md
  - docs/status/CHANGELOG.md
  - docs/TODO.md
  - docs/adr/0001-docs-governance.md
  - .github/copilot-instructions.md
  - AGENTS.md
```

Notes:
- Canonical docs are now in `docs/`.
- Historical docs are archived under `docs/archive/`.

```yaml
id: 2026-01-28-02
type: docs
areas: [docs, tooling]
summary: "Archived phase-era docs into a dated folder; updated canonical pointers; moved schema validation to tools."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/adr/0001-docs-governance.md
  - docs/status/CHANGELOG.md
  - README.md
  - GETTING_STARTED.md
  - tools/validate_schema.py
  - docs/archive/2026-01-28-docs-root-cleanup/README.md
```

Notes:
- `docs/` root now only contains the canonical set (spec/index/todo + status/adr/incidents).
- Phase/checklist documents are preserved under `docs/archive/2026-01-28-docs-root-cleanup/`.

```yaml
id: 2026-01-28-03
type: docs
areas: [docs, workflow]
summary: "Codified the required human+AI development workflow (TODO → code → tests → spec → changelog)."
files_changed:
  - docs/PROJECT_SPEC.md
  - docs/TODO.md
  - docs/adr/0001-docs-governance.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

Notes:
- Future work should follow the documented loop so TODO/spec/changelog stay authoritative.

```yaml
id: 2026-01-28-04
type: docs
areas: [docs, onboarding, workflow]
summary: "Added a contributor-facing workflow section to README so new humans+AI discover the required process immediately."
files_changed:
  - README.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-05
type: docs
areas: [tools, documentation]
summary: "Created tools/README.md listing supported utilities and clarifying archive folder status."
files_changed:
  - tools/README.md
  - docs/TODO.md
  - docs/status/CHANGELOG.md
```

Notes:
- Tools directory now has clear documentation for supported utilities (schema validation, CRUD matrix).
- Archive folder explicitly marked as not maintained.

```yaml
id: 2026-01-28-06
type: docs
areas: [workflow, governance]
summary: "Documented explicit ad-hoc request and rollback protocols so work stays auditable even when assigned verbally."
files_changed:
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-07
type: docs
areas: [workflow, governance, onboarding]
summary: "Added an owner-approval gate for closing TODO items and clarified when to use incidents vs TODO."
files_changed:
  - docs/TODO.md
  - docs/INDEX.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-08
type: tooling
areas: [github, ci, workflow]
summary: "Added GitHub-native team workflow scaffolding (Issue templates, PR template, CI workflow)."
files_changed:
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - .github/ISSUE_TEMPLATE/feature_request.yml
  - .github/pull_request_template.md
  - .github/workflows/ci.yml
  - README.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-09
type: docs
areas: [workflow, governance, github]
summary: "Made GitHub Issues the primary work tracker; kept docs/TODO.md as an optional offline mirror; added CODEOWNERS."
files_changed:
  - docs/TODO.md
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/INDEX.md
  - docs/adr/0001-docs-governance.md
  - AGENTS.md
  - .github/copilot-instructions.md
  - .github/CODEOWNERS
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-10
type: docs
areas: [workflow, github]
summary: "Documented a branching/PR policy (feature branches per Issue; PR review + CI before merge)."
files_changed:
  - README.md
  - docs/PROJECT_SPEC.md
  - docs/status/CHANGELOG.md
```

```yaml
id: 2026-01-28-11
type: docs
areas: [github, workflow]
summary: "Enhanced GitHub Issue templates to capture implementation/testing detail; instructed agents to draft issues using templates."
files_changed:
  - .github/ISSUE_TEMPLATE/feature_request.yml
  - .github/ISSUE_TEMPLATE/bug_report.yml
  - AGENTS.md
  - .github/copilot-instructions.md
  - docs/status/CHANGELOG.md
```
