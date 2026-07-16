from pathlib import Path

import pytest

from diy_bot.config import Settings


def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("TARGET_CHAT_ID", "-10042")
    monkeypatch.setenv("ORDERS_TOPIC_ID", "19")
    monkeypatch.setenv("ADMIN_IDS", "1, 2")
    monkeypatch.setenv("DATABASE_PATH", "custom.db")

    settings = Settings.from_env()

    assert settings.bot_token == "token"
    assert settings.target_chat_id == -10042
    assert settings.orders_topic_id == 19
    assert settings.admin_ids == frozenset({1, 2})
    assert settings.database_path == Path("custom.db")


def test_zero_topic_means_no_topic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("TARGET_CHAT_ID", "-10042")
    monkeypatch.setenv("ORDERS_TOPIC_ID", "0")

    assert Settings.from_env().orders_topic_id is None


def test_target_chat_can_be_left_zero_during_setup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.delenv("TARGET_CHAT_ID", raising=False)

    assert Settings.from_env().target_chat_id == 0
