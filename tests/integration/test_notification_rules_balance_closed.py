from datetime import date, timedelta

from repositories.notification_repository import NotificationRepository
from services.notification_service import NotificationService
from services.notification_rules_service import NotificationRulesService
from ui.settings import Settings


def test_pending_receipt_rules_ignore_zero_amount_total_loss_rows(test_db, tmp_path):
    settings_path = tmp_path / "settings.json"
    notification_service = NotificationService(NotificationRepository(settings_file=str(settings_path)))
    settings = Settings(settings_file=str(settings_path))
    settings.settings["redemption_pending_receipt_threshold_days"] = 7
    settings.save()

    rules_service = NotificationRulesService(notification_service, settings, test_db)

    overdue_date = (date.today() - timedelta(days=10)).isoformat()

    test_db.execute("INSERT INTO users (id, name, notes) VALUES (1, 'Test User', '')")
    test_db.execute("INSERT INTO sites (id, name) VALUES (1, 'Test Site')")
    test_db.execute(
        """
        INSERT INTO redemptions (
            id, user_id, site_id, redemption_date, redemption_time, amount,
            receipt_date, processed, notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, 1, 1, overdue_date, "10:00:00", 125.00, None, 0, None, "PENDING"),
    )
    test_db.execute(
        """
        INSERT INTO redemptions (
            id, user_id, site_id, redemption_date, redemption_time, amount,
            receipt_date, processed, notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            2,
            1,
            1,
            overdue_date,
            "11:00:00",
            0.00,
            None,
            1,
            "Balance Closed - Net Loss: $50.00 ($1.00 SC marked dormant)",
            "PENDING",
        ),
    )
    test_db.commit()

    rules_service.evaluate_redemption_pending_rules()

    active = notification_service.get_all()
    subjects = {n.subject_id for n in active if n.type == "redemption_pending_receipt"}

    assert subjects == {"1"}
