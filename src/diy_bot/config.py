from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load a small .env file without adding a runtime dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _int_from_env(name: str, default: int = 0) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"Переменная {name} должна быть целым числом") from error


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value or value == "0":
        return None
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"Переменная {name} должна быть целым числом") from error


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    target_chat_id: int
    orders_topic_id: int | None
    database_path: Path
    admin_ids: frozenset[int]
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("Переменная BOT_TOKEN обязательна")

        raw_admins = os.getenv("ADMIN_IDS", "")
        try:
            admin_ids = frozenset(
                int(item.strip()) for item in raw_admins.split(",") if item.strip()
            )
        except ValueError as error:
            raise ValueError("ADMIN_IDS должен содержать Telegram ID через запятую") from error

        return cls(
            bot_token=token,
            target_chat_id=_int_from_env("TARGET_CHAT_ID"),
            orders_topic_id=_optional_int("ORDERS_TOPIC_ID"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/bot.db")),
            admin_ids=admin_ids,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
