import sys
from pathlib import Path

from ui.settings import Settings, default_settings_file


def test_default_settings_file_uses_project_relative_path_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert default_settings_file() == "settings.json"


def test_default_settings_file_uses_app_support_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("ui.settings.Path.home", lambda: tmp_path)

    expected = tmp_path / "Library" / "Application Support" / "Sezzions" / "settings.json"
    assert default_settings_file() == str(expected)


def test_settings_uses_default_resolved_path_when_not_provided(monkeypatch, tmp_path):
    settings_path = tmp_path / "custom" / "settings.json"
    monkeypatch.setattr("ui.settings.default_settings_file", lambda: str(settings_path))

    settings = Settings()
    settings.set("theme", "Dark")

    assert settings.settings_file == str(settings_path)
    assert settings_path.exists()
