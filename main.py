import asyncio
import logging

import aiogram
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telethon import TelegramClient

from database import models
from database.database import async_engine, get_db
from handlers import main_handlers, domain_handlers, builder_handlers, spam_parse_handlers, spam_handlers
import config
from database.database import init_models, dispose_engine

BOT_TOKEN = config.BOT_TOKEN  # Замените на токен вашего бота
bot = Bot(token=BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()
logging.basicConfig(filename="bot.log", level=logging.INFO)

async def on_startup():
    await init_models()
    print('Бот запускается')
    print("Бот написан на: ", aiogram.__version__)
    print('Ботв написан пользователем: @zelen135')
    bot_info = await bot.get_me()
    logging.getLogger(__name__).info(f'Бот успешно запущен: {bot_info.username}')


async def on_shutdown():
    await bot.close()
    await dispose_engine()


async def main():
    dp.include_routers(main_handlers.router)
    dp.include_routers(domain_handlers.router)
    dp.include_routers(builder_handlers.router)
    dp.include_routers(spam_parse_handlers.router)
    dp.include_routers(spam_handlers.router)
    await on_startup()
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
