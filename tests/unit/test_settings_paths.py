from services.db_location_service import settings_file_path
from desktop.ui.settings import Settings, default_settings_file


def test_default_settings_file_uses_project_relative_path_when_not_frozen(monkeypatch):
    assert default_settings_file() == str(settings_file_path())


def test_default_settings_file_is_always_project_relative():
    assert default_settings_file() == str(settings_file_path())


def test_settings_uses_default_resolved_path_when_not_provided(monkeypatch, tmp_path):
    settings_path = tmp_path / "custom" / "settings.json"
    monkeypatch.setattr("desktop.ui.settings.default_settings_file", lambda: str(settings_path))

    settings = Settings()
    settings.set("theme", "Dark")

    assert settings.settings_file == str(settings_path)
    assert settings_path.exists()
