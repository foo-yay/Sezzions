# Archived: Sezzions OOP Migration - Implementation Plan

Archived on: 2026-01-28

This document is retained for historical context. The current canonical spec is:
- [docs/PROJECT_SPEC.md](../PROJECT_SPEC.md)

---

<details>
<summary>Original content</summary>

```markdown
# Sezzions OOP Migration - Implementation Plan

## Executive Summary

This plan outlines the conversion of the Session App (21,000+ line procedural desktop app) to a modern OOP architecture called **Sezzions**, designed to support both desktop and eventual web/mobile deployment.

**Critical Success Criteria:**
- ✅ Preserve 100% of accounting algorithm accuracy (FIFO, session-based tax calculations)
- ✅ Support SQLite (desktop) and PostgreSQL (web) without code changes
- ✅ Enable platform portability (desktop → web → mobile)
- ✅ Maintain audit trail and data integrity
- ✅ Achieve 90%+ test coverage

**Timeline:** 4-6 months, phased approach with milestones

**Current Status:** Planning phase (no code written yet)

---

## Documentation Structure

This plan is split into focused documents for manageability:

| Document | Purpose | AI Usage |
|----------|---------|----------|
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Domain models, repositories, services design | Reference when building classes |
| **[DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** | Schema for dual-database support | Reference for migrations & queries |
| **[ACCOUNTING_LOGIC.md](docs/ACCOUNTING_LOGIC.md)** | FIFO & SessionManager algorithms | **CRITICAL** - Must implement exactly |
| **[TESTING_STRATEGY.md](archive/2026-01-28-docs-root-cleanup/TESTING_STRATEGY.md)** | pytest approach, verification tests | Follow for test-driven development |
| **[MIGRATION_PHASES.md](docs/MIGRATION_PHASES.md)** | Phase-by-phase timeline | Track progress, know what's next |
| **[DEPENDENCIES.md](archive/2026-01-28-docs-root-cleanup/DEPENDENCIES.md)** | Libraries, tools, rationale | Install and configure these first |

---

(Remaining content omitted in archive wrapper for brevity in the master spec.)
```

</details>
