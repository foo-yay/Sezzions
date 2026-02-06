# Window expands beyond screen boundaries when expanding collapsible sections

## Problem

When expanding all collapsible sub-sections in Setup → Tools tab, the window resizes vertically to accommodate the content, extending beyond screen boundaries. Once expanded off-screen, collapsing the sections does not restore the window to its original size, leaving it stuck in an unusable state that cannot be resized back to fit the screen.

## Steps to Reproduce

1. Open Sezzions
2. Navigate to Setup → Tools tab
3. Expand all collapsible sections (Repair Mode, Recalculation Tools, CSV Import/Export, Adjustments & Corrections, Database Tools)
4. Observe window extends beyond bottom of screen
5. Collapse all sections again
6. Observe window height remains off-screen and cannot be manually resized to fit

## Expected Behavior

- Window should respect screen boundaries and never resize beyond visible area
- When content exceeds available space, a scroll area should appear within the tab content
- Collapsing sections should restore window to reasonable size or allow manual resize
- Window resize should be constrained to screen dimensions

## Current Behavior

- Window resizes dynamically based on expanded content without boundary checks
- Window can extend multiple screen heights beyond viewable area
- Once expanded, window height is locked and cannot be reduced via manual resize
- Only workaround is to restart the application

## Impact

- Makes Tools tab unusable when multiple sections need to be accessed
- Forces workflow of "expand one section at a time"
- Window state becomes corrupted requiring app restart
- Affects user experience and efficiency

## Scope

This issue may affect other areas of the application:
- Other tabs with expandable content
- Dialogs with dynamic content sizing
- Any UI component that triggers window resize events

## Proposed Solution

1. **Add scroll areas** to tab content containers so content can scroll within fixed window boundaries
2. **Implement window size constraints** based on screen dimensions (e.g., max height = 90% of screen height)
3. **Disable automatic window resize** on content expansion; rely on scroll areas instead
4. **Add resize event handlers** to ensure window can always be manually resized to fit screen
5. Consider **collapsible section UX improvements**: persist state, provide "expand all" / "collapse all" actions

## Technical Notes

- Issue discovered during Repair Mode QA (PR #75)
- Related to PySide6/Qt layout management and window resize policies
- May need to review `setSizePolicy` and `sizeHint` implementations
- Consider using `QScrollArea` for Tools tab and potentially other tabs

## Priority

Medium - workaround exists (restart app, use one section at a time) but significantly impacts usability.

## Labels

- `bug`
- `ui`
- `enhancement`
- `layout`
