from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation

from .config import Settings
from .handlers import router
from .member_repository import MemberRepository
from .repository import OrderRepository


async def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    repository = OrderRepository(settings.database_path)
    member_repository = MemberRepository(settings.database_path)
    await repository.initialize()
    await member_repository.initialize()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())
    dispatcher.include_router(router)
    await dispatcher.start_polling(
        bot,
        settings=settings,
        repository=repository,
        member_repository=member_repository,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
