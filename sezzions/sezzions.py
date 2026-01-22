#!/usr/bin/env python3
"""
Sezzions - Casino Session Tracker with FIFO Accounting

Main application entry point.
Run: python3 sezzions.py
"""
import sys
import os
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui
from app_facade import AppFacade
from ui.main_window import MainWindow


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
    
    # Set application style
    app.setStyle("Fusion")
    
    # Initialize backend facade with production database
    # Use a stable path so launching from different CWDs doesn't create a new empty DB.
    db_path = os.environ.get("SEZZIONS_DB_PATH")
    if not db_path:
        project_root = Path(__file__).resolve().parent.parent
        db_path = str(project_root / "sezzions.db")

    facade = AppFacade(db_path)
    
    # Create and show main window
    window = MainWindow(facade)
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

