# Feature: Allow window resize below minimum width with scroll bars

## Problem
The app currently has a hard minimum width that prevents users from resizing the window smaller. This can be inconvenient on smaller screens or when trying to view multiple windows side-by-side.

## Requested Behavior
- Allow the main window to be resized below the current minimum width
- Add horizontal scroll bars when content doesn't fit in the window
- Maintain usability at smaller window sizes

## Current Behavior
Window has a hard minimum width constraint that prevents further resizing.

## Proposed Solution
- Remove or reduce the minimum width constraint on MainWindow
- Wrap the main content area in a QScrollArea
- Enable horizontal scrolling when content exceeds viewport width
- Preserve existing layout and tab functionality

## Implementation Notes
- Main window is in `ui/main_window.py`
- Need to check current `setMinimumWidth()` or `setMinimumSize()` calls
- Wrap central widget or tab widget in QScrollArea
- Test with various window sizes to ensure scroll bars appear/disappear correctly

## Testing
- Manually resize window to very small widths
- Verify scroll bars appear when needed
- Verify all tabs remain accessible and functional
- Test on different screen resolutions
