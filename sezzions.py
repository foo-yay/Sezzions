#!/usr/bin/env python3
"""
Sezzions - Casino Session Tracker with FIFO Accounting

Main application entry point.
Run: python3 sezzions.py
"""
import sys
import os
from pathlib import Path
import traceback
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from ui.main_window import MainWindow


def resolve_db_path() -> str:
    configured = os.environ.get("SEZZIONS_DB_PATH")
    if configured:
        return configured

    if getattr(sys, "frozen", False):
        app_support_dir = Path.home() / "Library" / "Application Support" / "Sezzions"
        return str(app_support_dir / "sezzions.db")

    project_root = Path(__file__).resolve().parent
    return str(project_root / "sezzions.db")


def ensure_db_parent_exists(db_path: str) -> None:
    path = Path(db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)


def main():
    """Initialize and run the Qt application"""
    # Create Qt application
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Sezzions")
    app.setOrganizationName("Carolina Edge Gaming")

    class CompleterEventFilter(QtCore.QObject):
        def eventFilter(self, obj, event):
            if event.type() in (QtCore.QEvent.KeyPress, QtCore.QEvent.ShortcutOverride):
                key = event.key()
                if key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    return self._handle_commit(key)
            return False

        def _handle_commit(self, key):
            focus_widget = QtWidgets.QApplication.focusWidget()
            combo = None
            if isinstance(focus_widget, QtWidgets.QLineEdit):
                combo = self._combo_for_line_edit(focus_widget)
            elif isinstance(focus_widget, QtWidgets.QComboBox):
                combo = focus_widget if focus_widget.isEditable() else None

            if combo is not None and combo.isEditable():
                line_edit = combo.lineEdit()
                text = line_edit.text() if line_edit is not None else combo.currentText()
                committed = self._commit_from_combo(combo, text)
                if committed and key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    return True
            return False

        def _combo_for_line_edit(self, widget):
            if not isinstance(widget, QtWidgets.QLineEdit):
                return None
            parent = widget.parent()
            while parent is not None:
                if isinstance(parent, QtWidgets.QComboBox) and parent.lineEdit() is widget:
                    return parent
                parent = parent.parent()
            return None

        def _commit_from_combo(self, combo, text):
            text = (text or "").strip()
            if not text:
                return False
            model = combo.model()
            column = combo.modelColumn()
            text_lower = text.lower()
            for row in range(model.rowCount()):
                idx = model.index(row, column)
                data = model.data(idx)
                if data is None:
                    continue
                data_text = str(data)
                if data_text.lower().startswith(text_lower):
                    combo.setCurrentText(data_text)
                    completer = combo.completer()
                    if completer is not None and completer.popup() is not None:
                        completer.popup().hide()
                    return True
            return False

    app._completer_filter = CompleterEventFilter(app)
    app.installEventFilter(app._completer_filter)

    # Optional popup tracing (helps debug mysterious off-screen popups/menus)
    # Enable with: SEZZIONS_DEBUG_POPUPS=1 python3 sezzions.py
    if os.environ.get("SEZZIONS_DEBUG_POPUPS"):
        class PopupTraceFilter(QtCore.QObject):
            def eventFilter(self, obj, event):
                try:
                    if not isinstance(obj, QtWidgets.QWidget):
                        return False
                    if not obj.isWindow():
                        return False

                    if event.type() not in (QtCore.QEvent.Show, QtCore.QEvent.ShowToParent):
                        return False

                    flags = obj.windowFlags()
                    window_type = obj.windowType()
                    is_menu = isinstance(obj, QtWidgets.QMenu)
                    interesting_types = {
                        QtCore.Qt.Popup,
                        QtCore.Qt.Tool,
                        QtCore.Qt.ToolTip,
                        QtCore.Qt.SplashScreen,
                        QtCore.Qt.Sheet,
                        QtCore.Qt.Drawer,
                    }
                    interesting = is_menu or (window_type in interesting_types) or bool(flags & QtCore.Qt.FramelessWindowHint)
                    if not interesting:
                        return False

                    parent = obj.parentWidget()
                    geo = obj.geometry()
                    print("\n[SEZZIONS_DEBUG_POPUPS] window shown")
                    print(f"  class={obj.metaObject().className()} name={obj.objectName()!r} title={obj.windowTitle()!r}")
                    print(f"  windowType={int(window_type)} flags={int(flags)} frameless={bool(flags & QtCore.Qt.FramelessWindowHint)}")
                    print(f"  geom=({geo.x()},{geo.y()},{geo.width()},{geo.height()})")
                    if parent is not None:
                        print(f"  parent={parent.metaObject().className()} name={parent.objectName()!r} title={parent.windowTitle()!r}")
                    active_popup = QtWidgets.QApplication.activePopupWidget()
                    if active_popup is not None:
                        print(f"  activePopup={active_popup.metaObject().className()} name={active_popup.objectName()!r} title={active_popup.windowTitle()!r}")
                    # Stack trace helps pinpoint what triggered the popup.
                    stack = "".join(traceback.format_stack(limit=25))
                    print("  stack:\n" + stack)
                except Exception as e:
                    # Never crash the app due to debug tracing
                    print(f"[SEZZIONS_DEBUG_POPUPS] tracer error: {e}")
                return False

        app._popup_trace_filter = PopupTraceFilter(app)
        app.installEventFilter(app._popup_trace_filter)
    
    # Set application style
    app.setStyle("Fusion")
    
    db_path = resolve_db_path()
    ensure_db_parent_exists(db_path)

    facade = AppFacade(db_path)
    
    # Create and show main window
    window = MainWindow(facade)
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

