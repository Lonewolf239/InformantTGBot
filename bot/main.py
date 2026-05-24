import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN, OWNER_ID
from bot.handlers.message import handle_all_messages
from bot.middlewares import LoggingMiddleware
from bot.state import state
from bot.links.database import init_links_db
from bot.links.handlers import links_callback_handler
from bot.utils.joke_api import more_joke_callback
from bot.utils.meme_api import more_meme_callback, add_favorite_callback
from bot.handlers.nsfw_settings import nsfw_callback_handler
from bot.utils.ai_queue import get_queue
from bot.utils.youtube_api import download_worker, process_yt_callback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.message.middleware(LoggingMiddleware())


@dp.message()
async def message_handler(message: types.Message):
    await handle_all_messages(message)


@dp.business_message()
async def business_message_handler(message: types.Message):
    await handle_all_messages(message)


@dp.business_connection()
async def business_connect(connection: types.BusinessConnection):
    logger.info(f"🔗 Бизнес подключение: {connection.id} от {connection.user.first_name}")


@dp.callback_query()
async def callback_handler(callback_query: types.CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data and ":usr_" in data:
        base_data, allowed_user_part = data.rsplit(":usr_", 1)
        try:
            allowed_user_id = int(allowed_user_part)
            if user_id != allowed_user_id:
                await callback_query.answer("❌ Эта панель управления создана другим пользователем и недоступна для вас!", show_alert=True)
                return

        except ValueError:
            pass

        data = base_data
        callback_query = callback_query.model_copy(update={"data": base_data})

    if data and data.startswith("links_"):
        await links_callback_handler(callback_query)
    elif data == "more_joke":
        await more_joke_callback(callback_query)
    elif data == "more_meme":
        await more_meme_callback(callback_query)
    elif data and data.startswith("fav_meme"):
        await add_favorite_callback(callback_query)
    elif data and data.startswith("nsfw_"):
        await nsfw_callback_handler(callback_query)
    elif data and data.startswith("yt_dl|"):
        await process_yt_callback(callback_query)

    try:
        await callback_query.answer()
    except Exception:
        pass

@dp.startup()
async def on_startup():
    init_links_db()
    logger.info("🚀 БОТ ЗАПУСКАЕТСЯ...")
    logger.info(f"👑 Владелец ID: {OWNER_ID}")
    logger.info(f"🤖 Автоответ: мгновенный при включённом режиме")
    await state.set_away_mode(False)

    queue = get_queue()
    queue.start()

    asyncio.create_task(download_worker())
    logger.info("📥 Воркер очереди YouTube успешно запущен в фоне.")


@dp.shutdown()
async def on_shutdown():
    queue = get_queue()
    await queue.stop()
    logger.info("🛑 БОТ ОСТАНАВЛИВАЕТСЯ...")


async def main():
    print("═" * 50)
    print("📊 НАСТРОЙКИ АВТООТВЕТЧИКА")
    print("   ├─ Режим: МГНОВЕННЫЙ (включи !отошёл)")
    print("   └─ Автоответ приходит сразу на каждое сообщение")
    print("═" * 50)
    print("🎭 RP команды: ответь на сообщение и напиши !обнять")
    print("├─ 🔘 Включить автоответ: !отошёл")
    print("├─ 🔘 Выключить автоответ: !вернулся")
    print("├─ 📖 Публичная справка: !помощь")
    print("├─ 🔗 Команда ссылок: !ссылки (только для владельца)")
    print("├─ 🎬 Загрузка медиа: !скачать [ссылка]")
    print("└─ 👑 Приватная справка: !ownerhelp")
    print("═" * 50)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
