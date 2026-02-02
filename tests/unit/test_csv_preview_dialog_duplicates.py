import os

from PySide6.QtWidgets import QApplication

from services.tools.dtos import ImportPreview, ValidationError, ValidationSeverity
from ui.csv_dialogs import ImportPreviewDialog


def test_import_preview_dialog_renders_csv_duplicates_without_crash():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    preview = ImportPreview(
        to_add=[],
        to_update=[],
        exact_duplicates=[],
        conflicts=[],
        invalid_rows=[],
        csv_duplicates=[
            ValidationError(
                row_number=3,
                field="purchase_date",
                value="2024-01-15",
                message="Duplicate purchase found in CSV",
                severity=ValidationSeverity.ERROR,
            )
        ],
    )

    dialog = ImportPreviewDialog(preview, "purchases")
    dialog.show()
    app.processEvents()
    dialog.close()
