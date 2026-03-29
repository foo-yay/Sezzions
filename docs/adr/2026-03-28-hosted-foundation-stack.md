# ADR: Hosted Foundation Stack

Date: 2026-03-28

## Status

Accepted

## Context

Sezzions now has a staged web frontend shell, but the product data still lives in a local SQLite database tied to the desktop runtime. The next implementation phase needs a hosted data/auth foundation so the browser client can become real without duplicating accounting logic or inventing a second source of truth.

The user selected:
- Supabase project URL: configured outside the repository
- auth preference: Google only to start
- first migration source database: `sezzions.db`

## Decision

Sezzions will use this hosted foundation for the first shared desktop/web slice:

- Auth provider: Supabase Auth with Google sign-in enabled first
- Hosted database: Supabase-managed PostgreSQL
- API layer: Python FastAPI service in this repository
- Import source: existing local SQLite database, starting with `sezzions.db`

Key modeling rule:
- the current business-domain `users` table is not the hosted auth/account model
- hosted product identity must be represented separately as account/workspace ownership

## Consequences

Positive:
- one hosted system of record for future desktop + web access
- browser auth is delegated to a managed provider instead of hand-rolled credentials
- backend logic can be migrated incrementally behind the API
- existing desktop datasets have a defined migration path

Tradeoffs:
- the project temporarily operates in a mixed mode: desktop remains SQLite-first while hosted APIs are introduced
- Google auth requires Supabase provider configuration and Google OAuth credentials outside the repository
- import must transform local SQLite semantics into hosted account/workspace ownership, not just copy tables blindly

## Immediate Follow-through

- scaffold the hosted API package and configuration layer
- add read-only inventory tooling for SQLite migration planning
- define hosted account/workspace models and ownership boundaries
- implement the first authenticated vertical slice after Supabase Google provider settings are configured