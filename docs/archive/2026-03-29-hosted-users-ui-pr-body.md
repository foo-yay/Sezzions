## Summary

- compact the hosted signed-in header into desktop-style utility controls
- add desktop-style hosted Users sorting, filtering, multi-select, and dialog behavior
- add paged hosted users API support plus batch delete support
- harden the web client against incorrect paging metadata from the deployed Render backend

## What changed

- replaced the oversized hosted header with compact notifications, account, settings, and status utilities
- added desktop-style column sorting and filter popups for hosted Users
- added multi-row selection, batch delete, and related confirmation flows
- added paged hosted users API parameters and response metadata
- added repository/service/API support for hosted users batch delete
- added client-side resilience for bad `total_count` and repeated-page responses from the currently deployed backend
- simplified the Users summary chips so the UI only shows trustworthy totals

## Validation

- `/usr/local/bin/python3 -m pytest tests/api/test_workspace_users.py tests/services/hosted/test_workspace_user_service.py -q`
- `cd web && npm test`

## Known issue / follow-up

- the local backend code in this branch computes `total_count` correctly, but the deployed Render API currently used by `web/.env.local` is still returning inconsistent paging metadata and may repeat page 1 for later offsets
- the frontend now works around that deployed behavior, but the clean fix is to update/redeploy the hosted backend so `/v1/workspace/users` returns correct paging data consistently

## Manual verification

- exercised the hosted Users screen in the local Vite app while iterating on paging and batch delete behavior
- verified that initial render stays capped to one page and that additional rows can be loaded afterward