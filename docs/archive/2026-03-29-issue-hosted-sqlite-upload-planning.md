## Summary
Add a temporary authenticated web migration page that lets the current operator upload a local Sezzions SQLite database to the hosted API for read-only inspection and migration planning.

## Problem
The current hosted import-planning endpoint can only inspect a `source_db_path` that is accessible to the API process. That is correct for a deployed backend, but it does not solve the actual one-user migration bridge needed right now: getting the local desktop SQLite database into the hosted flow without productizing a permanent desktop sync feature.

## Proposal
Implement a temporary hosted migration surface that:
- adds a separate authenticated migration page in the web app
- accepts a SQLite `.db` file upload from the browser
- sends the uploaded file to the hosted API for read-only inspection
- returns the same planning/inventory summary the existing SQLite inventory service already knows how to produce
- does not perform the hosted business-data import yet

## Scope
In scope:
- protected upload-based API endpoint for read-only SQLite inspection
- temporary file handling in the hosted API for inspection only
- separate migration/upload page or route in the web app
- focused tests for valid upload, invalid file, and failure handling
- docs/changelog updates

Out of scope:
- actual record import into hosted business tables
- background jobs or resumable upload processing
- multi-user polished admin tooling
- long-term desktop sync architecture

## Acceptance Criteria
- an authenticated user can open a dedicated migration/upload page in the web app
- the page accepts a SQLite database file and sends it to the hosted API
- the API inspects the uploaded file read-only and returns planning inventory data
- invalid or unreadable uploads fail safely with an actionable message
- temporary files are not treated as persistent hosted state
- no business-domain rows are imported yet

## Test Matrix
Happy path:
- authenticated upload of a valid SQLite file returns inventory summary

Edge cases:
- uploaded file is not a SQLite database
- uploaded file is empty or unreadable

Failure injection:
- inspection fails after temporary file creation and the API returns a safe error without persisting hosted business data

Invariants:
- request still requires bearer auth
- hosted account/workspace identity remains unchanged
- no hosted business-domain rows are created

## Manual Verification
- sign in on staged web
- navigate to the migration/upload page
- upload a real Sezzions SQLite file
- confirm the UI shows read-only planning inventory or a safe actionable error

## Labels
- feature
- status:ready
- type:feature
