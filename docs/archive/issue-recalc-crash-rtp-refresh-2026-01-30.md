## Problem
Two regressions observed around Tools → Recalculation:

1) **Crash on completion**
Running **Recalculate All** triggers an exception when the worker finishes:

```
Traceback (most recent call last):
  File "ui/tabs/tools_tab.py", line 465, in <lambda>
    worker.signals.finished.connect(lambda result: self._on_recalculation_finished(result, progress_dialog))
  File "ui/tabs/tools_tab.py", line 595, in _on_recalculation_finished
    operation = OperationType.RECALCULATE_ALL if result.operation == "all" else OperationType.RECALCULATE_SCOPED
                                                 ^^^^^^^^^^^^^^^^
AttributeError: 'RebuildResult' object has no attribute 'operation'
```

2) **Games tab not auto-refreshing Actual RTP**
After **Recalculate All**, the **Actual RTP** values on the **Games** tab do not update until the user manually clicks the refresh button.
Given Issue #9 implemented a unified global refresh system, this should update automatically.

## Steps To Reproduce
### Crash
1. Launch app.
2. Go to Setup → Tools → Recalculation.
3. Click **Recalculate All**.
4. When the background worker completes, observe crash/traceback above.

### Actual RTP not updating
1. Launch app.
2. Go to Setup → Games and note current Actual RTP values.
3. Go to Setup → Tools → Recalculation.
4. Click **Recalculate All**.
5. Return to Games tab.
6. Observe Actual RTP unchanged until clicking refresh.

## Expected
- Recalculate All/Scoped completes without exceptions.
- Completion emits a global data-change event (Issue #9) and tabs refresh automatically.
- Games tab refreshes so Actual RTP updates without manual refresh.

## Actual
- AttributeError crash in ToolsTab recalculation finished handler.
- Games tab Actual RTP does not update until user clicks refresh.

## Notes / Suspected Cause
- `RebuildResult` does not expose an `operation` attribute, but `ToolsTab._on_recalculation_finished()` assumes it exists.
  - Either: the worker should include operation metadata, or the UI should pass the mode (all/scoped) explicitly into the callback.
- Recalculation completion may not be emitting `AppFacade.emit_data_changed(...)` with the appropriate `OperationType` (or the Games tab may not implement/receive the standardized `refresh_data()` pathway).

## Acceptance Criteria
- No AttributeError when recalculation finishes.
- Recalculate All triggers a global refresh so Games tab Actual RTP updates automatically (no manual refresh).
- Recalculate Scoped (if supported) also behaves correctly.

## Test Plan (Suggested)
- **Unit**: `_on_recalculation_finished()` handles a `RebuildResult` that has no `.operation` attribute.
- **Integration/headless**: running recalculation emits a `DataChangeEvent` and results in `GamesTab.refresh_data()` being invoked (debounced behavior OK).
- **Failure injection**: worker error path does not leave the app in a “maintenance/operation active” state and does not crash.
