import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN, COMMAND_ALIASES, SFW_RP_ACTIONS, NSFW_RP_ACTIONS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("maintenance_bot")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

ALL_COMMANDS = {alias.lower() for aliases in COMMAND_ALIASES.values() for alias in aliases}
ALL_COMMANDS.update(cmd.lower() for cmd in SFW_RP_ACTIONS.keys())
ALL_COMMANDS.update(cmd.lower() for cmd in NSFW_RP_ACTIONS.keys())

MAINTENANCE_TEXT = (
    "<b>┌─ ⚠️ БОТ ОТКЛЮЧЕН</b>\n"
    "<b>├─</b> Я временно ушёл в оффлайн на техобслуживание или обновление.\n"
    "<b>└─</b> Сейчас команды недоступны. Попробуй позже."
)


async def send_maintenance_reply(message: types.Message):
    if not message.text:
        return

    text = message.text.strip().lower()
    command_trigger = text.split()[0] if text else ""

    if command_trigger in ALL_COMMANDS:
        try:
            await message.reply(MAINTENANCE_TEXT)
            logger.info(f"Отправлена заглушка пользователю {message.from_user.id} на команду {command_trigger}")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа: {e}")


@dp.message()
async def message_handler(message: types.Message):
    await send_maintenance_reply(message)


@dp.business_message()
async def business_message_handler(message: types.Message):
    await send_maintenance_reply(message)


async def main():
    print("═" * 50)
    print("┌─ 🛑 РЕЖИМ ТЕХОБСЛУЖИВАНИЯ")
    print("├─ Бот переведён в режим заглушки")
    print("└─ Ответ идёт только на команды из конфига")
    print("═" * 50)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Режим техподдержки остановлен.")
