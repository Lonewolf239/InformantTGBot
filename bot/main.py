import asyncio
import logging
import os
import importlib
import pkgutil
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiohttp import web
from config import BOT_TOKEN, OWNER_ID, COOKIES_FILE, USE_WEBHOOKS, AI_PROVIDER
from bot.handlers.message import handle_all_messages
from bot.middlewares import LoggingMiddleware
from bot.state import state
from bot.links.database import init_links_db
from bot.utils.database import db
from bot.utils.tokens_database import tokens_db
from bot.utils.user_settings import user_settings_db
from bot.links.handlers import links_callback_handler
from bot.commands.joke_api import more_joke_callback
from bot.commands.meme_api import (
    more_meme_callback,
    add_favorite_callback,
    dislike_meme_callback,
)
from bot.handlers.nsfw_settings import nsfw_callback_handler
from bot.commands.youtube_api import download_worker, process_yt_callback
from bot.handlers.payments import (
    process_buy_tokens_callback,
    process_check_payment_callback,
)
from bot.webhooks.yookassa_webhook import setup_yookassa_routes
from bot.commands.music_api import process_music_callback, process_music_page_callback
from bot.commands.cat_api import more_cat_callback
from bot.commands.fact_api import more_fact_callback
from bot.commands.forecast_api import more_forecast_callback
from bot.commands.quote_api import more_quote_callback
from bot.commands.crypto_api import more_crypto_callback
from bot.commands.games_api import accept_duel_callback, cancel_duel_callback
from bot.utils.task_queue import queue_manager
from bot.owner_settings.database import owner_settings_db
from bot.owner_settings.handlers import system_settings_callback
from bot.commands.youtube_transcribe import process_yt_transcribe_callback
from bot.twin.database import twin_db
from bot.twin.pipeline import weekly_worker
from bot.twin.interview import init_interview_db
from bot.twin.collector import periodic_flush_worker, flush_pending
from bot.utils.callback_registry import register_callback, dispatch_callback
import bot.commands


def load_all_commands():
    for _, module_name, _ in pkgutil.iter_modules(bot.commands.__path__):
        importlib.import_module(f"bot.commands.{module_name}")


load_all_commands()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

tg_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.message.middleware(LoggingMiddleware())


@dp.message()
async def message_handler(message: types.Message, state: FSMContext):
    await handle_all_messages(message, state)


@dp.business_message()
async def business_message_handler(message: types.Message, state: FSMContext):
    await handle_all_messages(message, state)


@dp.business_connection()
async def business_connect(connection: types.BusinessConnection):
    logger.info(
        f"🔗 Бизнес подключение: {connection.id} от {connection.user.first_name}"
    )


@register_callback(prefix=("links_",))
async def _route_links(cq: types.CallbackQuery, state: FSMContext, data: str):
    await links_callback_handler(cq)


@register_callback(exact=("help_main", "aliases_main", "prices_main"))
async def _route_help_main(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.handlers.help_menus import process_menu_main_callback

    await process_menu_main_callback(cq)


@register_callback(prefix=("help_cat_", "aliases_cat_", "prices_cat_"))
async def _route_help_category(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.handlers.help_menus import process_menu_category_callback

    await process_menu_category_callback(cq)


@register_callback(exact=("more_joke",))
async def _route_more_joke(cq: types.CallbackQuery, state: FSMContext, data: str):
    await more_joke_callback(cq)


@register_callback(exact=("more_meme",))
async def _route_more_meme(cq: types.CallbackQuery, state: FSMContext, data: str):
    await more_meme_callback(cq)


@register_callback(prefix=("duel_accept:",))
async def _route_duel_accept(cq: types.CallbackQuery, state: FSMContext, data: str):
    await accept_duel_callback(cq)


@register_callback(prefix=("duel_cancel:",))
async def _route_duel_cancel(cq: types.CallbackQuery, state: FSMContext, data: str):
    await cancel_duel_callback(cq)


@register_callback(exact=("more_cat",))
async def _route_more_cat(cq: types.CallbackQuery, state: FSMContext, data: str):
    await more_cat_callback(cq)


@register_callback(exact=("more_fact",))
async def _route_more_fact(cq: types.CallbackQuery, state: FSMContext, data: str):
    await more_fact_callback(cq)


@register_callback(exact=("more_forecast",))
async def _route_more_forecast(cq: types.CallbackQuery, state: FSMContext, data: str):
    await more_forecast_callback(cq)


@register_callback(exact=("more_quote",))
async def _route_more_quote(cq: types.CallbackQuery, state: FSMContext, data: str):
    await more_quote_callback(cq)


@register_callback(exact=("more_crypto",))
async def _route_more_crypto(cq: types.CallbackQuery, state: FSMContext, data: str):
    await more_crypto_callback(cq)


@register_callback(prefix=("fav_meme",))
async def _route_fav_meme(cq: types.CallbackQuery, state: FSMContext, data: str):
    await add_favorite_callback(cq)


@register_callback(prefix=("dislike_meme|",))
async def _route_dislike_meme(cq: types.CallbackQuery, state: FSMContext, data: str):
    await dislike_meme_callback(cq)


@register_callback(prefix=("nsfw_",))
async def _route_nsfw(cq: types.CallbackQuery, state: FSMContext, data: str):
    await nsfw_callback_handler(cq)


@register_callback(prefix=("yt_dl|",))
async def _route_yt_dl(cq: types.CallbackQuery, state: FSMContext, data: str):
    await process_yt_callback(cq)


@register_callback(prefix=("buy_tokens:",))
async def _route_buy_tokens(cq: types.CallbackQuery, state: FSMContext, data: str):
    try:
        amount = int(data.split(":")[1])
        await process_buy_tokens_callback(cq, amount)
    except (IndexError, ValueError):
        await cq.answer("❌ Ошибка данных", show_alert=True)


@register_callback(prefix=("cp|",))
async def _route_check_payment(cq: types.CallbackQuery, state: FSMContext, data: str):
    try:
        _, payment_id, amount_str = data.split("|")
        await process_check_payment_callback(cq, payment_id, int(amount_str))
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга callback проверки платежа: {e}")
        await cq.answer("❌ Ошибка данных проверки", show_alert=True)


@register_callback(prefix=("mus_dl|",))
async def _route_music_dl(cq: types.CallbackQuery, state: FSMContext, data: str):
    await process_music_callback(cq)


@register_callback(prefix=("mus_page|",))
async def _route_music_page(cq: types.CallbackQuery, state: FSMContext, data: str):
    await process_music_page_callback(cq)


@register_callback(prefix=("inst_dl|",))
async def _route_instants_download(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.commands.myinstants_api import process_instants_download_callback

    await process_instants_download_callback(cq)


@register_callback(prefix=("inst_pg|",))
async def _route_instants_page(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.commands.myinstants_api import process_instants_page_callback

    await process_instants_page_callback(cq)


@register_callback(prefix=("inst_more|",))
async def _route_instants_more(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.commands.myinstants_api import process_instants_more_callback

    await process_instants_more_callback(cq)


@register_callback(prefix=("sys_set:",))
async def _route_system_settings(cq: types.CallbackQuery, state: FSMContext, data: str):
    await system_settings_callback(cq)


@register_callback(prefix=("yt_transcribe|",))
async def _route_yt_transcribe(cq: types.CallbackQuery, state: FSMContext, data: str):
    await process_yt_transcribe_callback(cq)


@register_callback(prefix=("chat_persona|",), exact=("chat_cancel",))
async def _route_chat_persona(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.commands.ai_api import process_chat_persona_callback

    await process_chat_persona_callback(cq, state)


@register_callback(prefix=("twin_fb:",))
async def _route_twin_feedback(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.twin.feedback import handle_feedback_callback

    await handle_feedback_callback(cq, data)


@register_callback(prefix=("twin_menu:",))
async def _route_twin_menu(cq: types.CallbackQuery, state: FSMContext, data: str):
    from bot.twin.menu import handle_menu_callback

    await handle_menu_callback(cq, data)


@dp.callback_query()
async def callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data and ":usr_" in data:
        base_data, allowed_user_part = data.rsplit(":usr_", 1)
        try:
            allowed_user_id = int(allowed_user_part)
            if user_id != allowed_user_id:
                await callback_query.answer(
                    "❌ Эта панель управления создана другим пользователем и недоступна для вас!",
                    show_alert=True,
                )
                return

        except ValueError:
            pass

        data = base_data
        callback_query = callback_query.model_copy(update={"data": base_data})

    await dispatch_callback(callback_query, state, data)

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
    await twin_db.init_db()
    await init_interview_db()

    logger.info("🚀 БОТ ЗАПУСКАЕТСЯ...")

    if not os.path.exists(COOKIES_FILE):
        logger.warning("=" * 60)
        logger.warning(f"⚠️ ВНИМАНИЕ: Файл '{COOKIES_FILE}' не найден!")
        logger.warning("Для корректной работы скачивания видео (обход 403 и 18+)")
        logger.warning(
            f"пожалуйста, положите файл '{COOKIES_FILE}' в корневую папку бота."
        )
        logger.warning("=" * 60)
    else:
        logger.info(f"✅ Файл '{COOKIES_FILE}' обнаружен и будет использоваться.")

    logger.info(f"👑 Владелец ID: {OWNER_ID}")
    logger.info("🤖 Автоответ: мгновенный при включённом режиме")
    await state.set_away_mode(False)

    queue_manager.register_queue("heavyweights", concurrency=1)
    queue_manager.register_queue("lightweights", concurrency=1)
    queue_manager.register_queue("twin_background", concurrency=1)

    asyncio.create_task(download_worker())
    logger.info("📥 Воркер очереди YouTube успешно запущен в фоне.")

    asyncio.create_task(weekly_worker())
    logger.info("🧬 Twin weekly worker успешно запущен в фоне.")

    asyncio.create_task(periodic_flush_worker())
    logger.info("🧬 Twin collector periodic flush успешно запущен в фоне.")


@dp.shutdown()
async def on_shutdown():
    logger.info("🛑 БОТ ОСТАНАВЛИВАЕТСЯ...")
    await flush_pending()


async def start_web_app(bot_instance: Bot):
    app = web.Application()
    setup_yookassa_routes(app, bot_instance)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", 8080)
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
    if AI_PROVIDER == "groq":
        print("├─ 💬 ИИ-ЧАТ: !ии_чат")
    print("├─ 🔗 Команда ссылок: !ссылки (только для владельца)")
    print("├─ 🎬 Загрузка медиа: !скачать [ссылка]")
    print("└─ 👑 Приватная справка: !ownerhelp")
    print("═" * 50)

    if USE_WEBHOOKS:
        web_runner = await start_web_app(tg_bot)

    try:
        await dp.start_polling(tg_bot)
    finally:
        if USE_WEBHOOKS:
            await web_runner.cleanup()
        await tg_bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
