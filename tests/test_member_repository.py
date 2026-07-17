from pathlib import Path

import pytest

from diy_bot.member_repository import MemberRepository


@pytest.mark.asyncio
async def test_rule_acceptance_is_persistent_and_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "bot.db"
    repository = MemberRepository(database_path)
    await repository.initialize()

    assert await repository.has_accepted_rules(chat_id=-1001, user_id=42) is False
    assert await repository.accept_rules(-1001, 42, "Иван") is True
    assert await repository.has_accepted_rules(chat_id=-1001, user_id=42) is True
    assert await repository.accept_rules(-1001, 42, "Иван") is False

    reopened = MemberRepository(database_path)
    await reopened.initialize()
    assert await reopened.has_accepted_rules(chat_id=-1001, user_id=42) is True


@pytest.mark.asyncio
async def test_acceptance_is_scoped_to_group(tmp_path: Path) -> None:
    repository = MemberRepository(tmp_path / "bot.db")
    await repository.initialize()
    await repository.accept_rules(-1001, 42, "Иван")

    assert await repository.has_accepted_rules(chat_id=-1002, user_id=42) is False
