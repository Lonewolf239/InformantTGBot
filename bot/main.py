import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from config import BOT_TOKEN, OWNER_ID, COOKIES_FILE, USE_WEBHOOKS
from bot.handlers.message import handle_all_messages
from bot.middlewares import LoggingMiddleware
from bot.state import state
from bot.links.database import init_links_db
from bot.utils.database import db
from bot.utils.tokens_database import tokens_db
from bot.utils.user_settings import user_settings_db
from bot.links.handlers import links_callback_handler
from bot.utils.joke_api import more_joke_callback
from bot.utils.meme_api import more_meme_callback, add_favorite_callback, dislike_meme_callback
from bot.handlers.nsfw_settings import nsfw_callback_handler
from bot.utils.youtube_api import download_worker, process_yt_callback
from aiogram.types.message import ContentType
from bot.handlers.payments import process_buy_tokens_callback, process_check_payment_callback
from bot.webhooks.yookassa_webhook import setup_yookassa_routes
from bot.utils.music_api import process_music_callback, process_music_page_callback
from bot.utils.cat_api import more_cat_callback
from bot.utils.fact_api import more_fact_callback
from bot.utils.forecast_api import more_forecast_callback
from bot.utils.quote_api import more_quote_callback
from bot.utils.crypto_api import more_crypto_callback
from bot.utils.games_api import accept_duel_callback, cancel_duel_callback
from bot.utils.task_queue import queue_manager
from bot.owner_settings.database import owner_settings_db
from bot.owner_settings.handlers import system_settings_callback

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
    elif data and data.startswith("duel_accept:"):
        await accept_duel_callback(callback_query)
    elif data and data.startswith("duel_cancel:"):
        await cancel_duel_callback(callback_query)
    elif data == "more_cat":
        await more_cat_callback(callback_query)
    elif data == "more_fact":
        await more_fact_callback(callback_query)
    elif data == "more_forecast":
        await more_forecast_callback(callback_query)
    elif data == "more_quote":
        await more_quote_callback(callback_query)
    elif data == "more_crypto":
        await more_crypto_callback(callback_query)
    elif data and data.startswith("fav_meme"):
        await add_favorite_callback(callback_query)
    elif data and data.startswith("dislike_meme|"):
        await dislike_meme_callback(callback_query)
    elif data and data.startswith("nsfw_"):
        await nsfw_callback_handler(callback_query)
    elif data and data.startswith("yt_dl|"):
        await process_yt_callback(callback_query)
    elif data and data.startswith("buy_tokens:"):
        try:
            amount = int(data.split(":")[1])
            await process_buy_tokens_callback(callback_query, amount)
        except (IndexError, ValueError):
            await callback_query.answer("❌ Ошибка данных", show_alert=True)
    elif data and data.startswith("cp|"):
        try:
            _, payment_id, amount_str = data.split("|")
            await process_check_payment_callback(callback_query, payment_id, int(amount_str))
        except (IndexError, ValueError) as e:
            logger.error(f"Ошибка парсинга callback проверки платежа: {e}")
            await callback_query.answer("❌ Ошибка данных проверки", show_alert=True)
    elif data and data.startswith("yt_dl|"):
        await process_yt_callback(callback_query)
    elif data and data.startswith("mus_dl|"):
        await process_music_callback(callback_query)
    elif data and data.startswith("mus_page|"):
        await process_music_page_callback(callback_query)
    elif data and data.startswith("inst_dl|"):
        from bot.utils.myinstants_api import process_instants_download_callback
        await process_instants_download_callback(callback_query)
    elif data and data.startswith("inst_pg|"):
        from bot.utils.myinstants_api import process_instants_page_callback
        await process_instants_page_callback(callback_query)
    elif data and data.startswith("inst_more|"):
        from bot.utils.myinstants_api import process_instants_more_callback
        await process_instants_more_callback(callback_query)
    elif data and data.startswith("sys_set:"):
        await system_settings_callback(callback_query)

    try:
        await callback_query.answer()
    except Exception:
        pass


@dp.startup()
async def on_startup():
    await init_links_db()
    await db.init_db()
    await tokens_db.init_db()
    await user_settings_db.init_db()
    await owner_settings_db.init_db()

    logger.info("🚀 БОТ ЗАПУСКАЕТСЯ...")

    if not os.path.exists(COOKIES_FILE):
        logger.warning("=" * 60)
        logger.warning(f"⚠️ ВНИМАНИЕ: Файл '{COOKIES_FILE}' не найден!")
        logger.warning("Для корректной работы скачивания видео (обход 403 и 18+)")
        logger.warning(f"пожалуйста, положите файл '{COOKIES_FILE}' в корневую папку бота.")
        logger.warning("=" * 60)
    else:
        logger.info(f"✅ Файл '{COOKIES_FILE}' обнаружен и будет использоваться.")

    logger.info(f"👑 Владелец ID: {OWNER_ID}")
    logger.info(f"🤖 Автоответ: мгновенный при включённом режиме")
    await state.set_away_mode(False)

    queue_manager.register_queue("heavyweights", concurrency=1)
    queue_manager.register_queue("lightweights", concurrency=1)

    asyncio.create_task(download_worker())
    logger.info("📥 Воркер очереди YouTube успешно запущен в фоне.")


@dp.shutdown()
async def on_shutdown():
    logger.info("🛑 БОТ ОСТАНАВЛИВАЕТСЯ...")


async def start_web_app(bot_instance: Bot):
    app = web.Application()
    setup_yookassa_routes(app, bot_instance)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("🌐 Web-сервер для ЮKassa запущен на порту 8080")

    return runner


async def main():
    print("═" * 50)
    print("┌─ 📊 НАСТРОЙКИ АВТООТВЕТЧИКА")
    print("├─ Режим: МГНОВЕННЫЙ (включи !отошёл)")
    print("└─ Автоответ приходит сразу на каждое сообщение")
    print("═" * 50)
    print("┌─ 🎭 RP команды: ответь на сообщение и напиши !обнять")
    print("├─ 🔘 Включить автоответ: !отошёл")
    print("├─ 🔘 Выключить автоответ: !вернулся")
    print("├─ 📖 Публичная справка: !помощь")
    print("├─ 🔗 Команда ссылок: !ссылки (только для владельца)")
    print("├─ 🎬 Загрузка медиа: !скачать [ссылка]")
    print("└─ 👑 Приватная справка: !ownerhelp")
    print("═" * 50)

    if USE_WEBHOOKS:
        web_runner = await start_web_app(bot)

    try:
        await dp.start_polling(bot)
    finally:
        if USE_WEBHOOKS:
            await web_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
