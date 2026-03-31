## Problem / Motivation

The web app currently uses `useState` for tab switching inside `AppShell.jsx`. Clicking between Setup tabs (Users, Sites, etc.) does not update the browser URL. This means:

- No deep-linkable URLs (cannot bookmark or share a link to a specific tab)
- Browser back/forward buttons do not navigate between tabs
- Refreshing the page always resets to the default tab (Users)
- The only URL-level routing is a minimal hash check (`#/migration`) for shell selection

## Proposed Solution

Install `react-router-dom` v6 and implement proper URL-based routing:

- `/setup/users` - Users tab
- `/setup/sites` - Sites tab
- `/setup/cards` - Cards tab (when enabled)
- `/setup/redemption-methods` - Redemption Methods tab (when enabled)
- `/setup/game-types` - Game Types tab (when enabled)
- `/setup/games` - Games tab (when enabled)
- `/setup/tools` - Tools tab (when enabled)
- `/` redirects to `/setup/users` (or future dashboard)

Replace the current hash-based shell routing (`routing.js`) and state-based tab switching with `<BrowserRouter>`, `<Routes>`, `<Route>`, and `useNavigate()`. Update side rail links to use `<NavLink>` for automatic active styling.

## Scope

- Install `react-router-dom`
- Wrap app in `<BrowserRouter>` in `main.jsx`
- Convert `App.jsx` shell selection from hash-based to route-based
- Convert `AppShell.jsx` tab switching from `useState` to URL routes
- Update side rail nav items to `<NavLink>`
- Configure Vite dev server for SPA fallback (history API)
- Remove or deprecate `web/src/services/routing.js`

## Out of Scope

- Adding new tabs or features
- Authentication flow changes
- API routing changes

## Acceptance Criteria

- [ ] Clicking a Setup tab updates the browser URL to match (e.g. `/setup/sites`)
- [ ] Browser back/forward navigates between previously visited tabs
- [ ] Refreshing the page stays on the current tab
- [ ] Direct navigation to a tab URL (e.g. paste `/setup/sites`) loads the correct tab
- [ ] The migration shell route still works
- [ ] Unauthenticated users see the marketing shell (no change)
- [ ] All existing web tests pass
- [ ] Vite dev server handles SPA fallback correctly

## Test Plan

- Verify each tab URL renders the correct content
- Verify browser history navigation (back/forward)
- Verify page refresh persistence
- Verify direct URL entry
- Verify redirect from `/` to default tab
- Verify migration route still works
- Verify unauthenticated redirect behavior unchanged
