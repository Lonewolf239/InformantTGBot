import random
import logging
from aiogram import types
from config import COMMAND_METADATA
from aiogram.types import InlineKeyboardButton
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, create_user_keyboard, spend_tokens

API_ICON = COMMAND_METADATA["!прогноз"]["icon"]
API_NAME = COMMAND_METADATA["!прогноз"]["name"]

logger = logging.getLogger(__name__)

FORECASTS = [
    "Сегодня звёзды советуют не напрягаться. Всё решится само собой.",
    "Отличный день для того, чтобы купить шаурму и посмотреть сериал.",
    "Возможны неожиданные финансовые поступления. Проверь карманы старой куртки.",
    "Не стоит сегодня спорить с техникой — она победит.",
    "Кто-то из прошлого о себе напомнит. Возможно, это просто спам.",
    "Идеальное время для начала чего-то нового. Например, новой пачки чипсов.",
    "Сегодня твоя харизма на максимуме — используй это с умом.",
    "Риск — благородное дело, но сегодня лучше обойтись без него.",
    "Пора сделать паузу и выпить кофе. Или чай. Или чего покрепче.",
    "Звёзды говорят, что сегодня ты случайно узнаешь какую-то тайну.",
    "Отличный день, чтобы послать всё нафиг и просто отдохнуть.",
    "Удача сегодня на твоей стороне! Главное — не спугни её нытьём.",
    "Внезапная встреча может перевернуть твои планы на вечер.",
    "Будь осторожен: кто-то может попытаться переложить на тебя свою работу.",
    "Сегодня день приятных мелочей. Обращай внимание на детали.",
    "Твоя энергия сегодня бьет ключом. Постарайся никого не убить этим ключом.",
    "Звёзды складываются в странную фигуру. Скорее всего, к вечеру захочется пиццы.",
    "Отличный момент, чтобы закрыть те 40 вкладок в браузере, которые висят с прошлого месяца.",
    "Сегодня кто-то тайно восхищается тобой. Наверное, твой кот. Или алгоритмы контекстной рекламы."
]


def get_forecast_keyboard(user_id: int):
    return create_user_keyboard([
        [InlineKeyboardButton(text="🔮 Ещё прогноз", callback_data="more_forecast")]
    ], user_id)


async def send_forecast(target, is_callback=False):
    forecast_text = random.choice(FORECASTS)

    msg_text = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=forecast_text
    )

    user_id = target.from_user.id
    keyboard = get_forecast_keyboard(user_id)

    try:
        message_obj = target.message if is_callback else target

        if is_callback:
            await message_obj.edit_text(msg_text, reply_markup=keyboard)
        else:
            await message_obj.reply(msg_text, reply_markup=keyboard)

        await db.increment_commands()
        await db.log_command("!прогноз", user_id)
        await spend_tokens(message_obj, "!прогноз")

    except Exception as e:
        logger.error(f"Ошибка отправки прогноза: {e}")


async def cmd_forecast(message: types.Message):
    await send_forecast(message)


async def more_forecast_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("🔄 Заглядываю в хрустальный шар...")
    await send_forecast(callback_query, is_callback=True)
