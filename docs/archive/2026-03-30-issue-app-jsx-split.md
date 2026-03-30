## Problem

`web/src/App.jsx` is a single ~3000+ line file containing all React components, hooks, state management, API calls, and UI logic for the entire web app. As more tabs and features are added (purchases, redemptions, game sessions, reports, etc.), this file will become unmaintainable.

## Proposal

Split App.jsx into a standard React component architecture:

```
web/src/
  App.jsx                    # top-level shell: auth, tab routing (~100 lines)
  components/
    Layout/
      TabShell.jsx           # tab navigation bar
      Breadcrumb.jsx         # breadcrumb toolbar
    UsersTab/
      UsersTab.jsx           # users data grid
      UserModal.jsx          # add/edit user dialog
      UserExportModal.jsx    # export modal
    SetupTab/
      SetupTab.jsx           # setup landing
    common/
      DataGrid.jsx           # reusable table/grid component
      Modal.jsx              # reusable modal wrapper
      SearchBar.jsx          # reusable search input
      StatsBar.jsx           # reusable footer stats rail
  hooks/
    useAuth.js               # Supabase auth hook
    useApi.js                # API client hook
    useKeyboardNav.js        # arrow key / selection hook
  services/
    api.js                   # fetch wrappers for FastAPI endpoints
  styles.css                 # stays as-is (or split later)
```

This is a refactor-only change -- no behavior changes, no new features.

## Scope

- Extract components from App.jsx into separate files
- Extract custom hooks into hooks/
- Extract API call functions into services/
- Keep styles.css as-is for now
- Update imports
- Update tests to match new file structure

## Out of Scope

- No new features or UI changes
- No CSS refactoring (can be a follow-up)
- No changes to desktop or backend code

## Acceptance Criteria

- [ ] App.jsx is under 200 lines (shell + routing only)
- [ ] All extracted components render identically to current behavior
- [ ] All existing web tests pass (npm test -- --run)
- [ ] No desktop test regressions
- [ ] Each component file is self-contained with its own imports

## Test Plan

- Run web tests: cd web && npm test -- --run
- Run desktop tests: pytest -q
- Manual: launch web app, verify Users tab looks and behaves identically
- Manual: verify auth flow (login/logout) still works
