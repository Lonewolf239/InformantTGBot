import random
import logging
from aiogram import types
from config import COMMAND_METADATA
from aiogram.types import InlineKeyboardButton
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, create_user_keyboard, get_raw_text
from bot.utils.tokens_database import tokens_db
from bot.utils.registry import register_command

API_ICON = COMMAND_METADATA["!рулетка"]["icon"]
API_NAME = COMMAND_METADATA["!рулетка"]["name"]
DUEL_ICON = COMMAND_METADATA["!дуэль"]["icon"]
DUEL_NAME = COMMAND_METADATA["!дуэль"]["name"]

logger = logging.getLogger(__name__)


@register_command("!рулетка")
async def cmd_roulette(message: types.Message):
    raw_text = get_raw_text(message)
    if not raw_text:
        return

    user_id = message.from_user.id
    parts = raw_text.split()

    if len(parts) < 2:
        await message.reply(
            format_styled_message(
                emoji=API_ICON,
                title=API_NAME,
                message="📝 Использование: <code>!рулетка [ставка]</code> или <code>!рулетка всё</code>",
            )
        )
        return

    balance = await tokens_db.get_balance(user_id)
    arg = parts[1].lower()

    if arg in ["всё", "все"]:
        amount = balance
    else:
        try:
            amount = int(arg)
        except ValueError:
            await message.reply(
                format_styled_message(
                    emoji="❌",
                    title=API_NAME,
                    message="Ставка должна быть целым числом.",
                )
            )
            return

    if amount <= 0:
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="Ставка должна быть больше 0 токенов.",
            )
        )
        return

    if balance < amount:
        await message.reply(
            format_styled_message(
                emoji="⛽",
                title=API_NAME,
                message=f"Недостаточно токенов. Твой баланс: <b>{balance}</b>",
            )
        )
        return

    win = random.choice([True, False])

    if win:
        await tokens_db.add_tokens(user_id, amount)
        new_bal = balance + amount
        msg = f"🎉 <b>Выигрыш!</b>\nТы удвоил ставку и поднял <b>{amount}</b> токенов!\n💰 Твой баланс: <b>{new_bal}</b>"
    else:
        await tokens_db.spend_tokens(user_id, amount)
        new_bal = balance - amount
        msg = f"📉 <b>Проигрыш...</b>\nФортуна повернулась задом. Ты потерял <b>{amount}</b> токенов.\n💰 Твой баланс: <b>{new_bal}</b>"

    await message.reply(
        format_styled_message(emoji=API_ICON, title=API_NAME, message=msg)
    )
    await db.increment_commands()
    await db.log_command("!рулетка", user_id)


@register_command("!дуэль")
async def cmd_duel(message: types.Message):
    user_id = message.from_user.id

    if not message.reply_to_message or message.reply_to_message.from_user.is_bot:
        await message.reply(
            format_styled_message(
                emoji="⚔️",
                title=DUEL_NAME,
                message="❌ Чтобы бросить вызов, <b>ответь командой на сообщение соперника</b>!",
            )
        )
        return

    target_id = message.reply_to_message.from_user.id
    if target_id == user_id:
        await message.reply(
            format_styled_message(
                emoji="⚔️",
                title=DUEL_NAME,
                message="❌ Нельзя вызвать на дуэль самого себя.",
            )
        )
        return

    raw_text = get_raw_text(message)
    if not raw_text:
        return

    parts = raw_text.split()
    try:
        amount = int(parts[1]) if len(parts) > 1 else 10
    except ValueError:
        amount = 10

    if amount <= 0:
        amount = 10

    bal_a = await tokens_db.get_balance(user_id)
    bal_b = await tokens_db.get_balance(target_id)

    if bal_a < amount:
        await message.reply(
            format_styled_message(
                emoji="⛽",
                title=DUEL_NAME,
                message=f"У тебя не хватает токенов! Нужно: {amount}, твой баланс: {bal_a}",
            )
        )
        return
    if bal_b < amount:
        await message.reply(
            format_styled_message(
                emoji="⛽",
                title=DUEL_NAME,
                message=f"У твоего соперника мало токенов для такой ставки (баланс: {bal_b}).",
            )
        )
        return

    keyboard = create_user_keyboard(
        [
            [
                InlineKeyboardButton(
                    text="⚔️ Принять вызов!",
                    callback_data=f"duel_accept:{user_id}:{amount}",
                )
            ]
        ],
        target_id,
    )

    keyboard.inline_keyboard.append(
        [
            InlineKeyboardButton(
                text="❌ Отменить дуэль",
                callback_data=f"duel_cancel:{user_id}:{target_id}",
            )
        ]
    )

    challenge_text = (
        f"{DUEL_ICON} <b>ВЫЗОВ НА ДУЭЛЬ!</b>\n\n"
        f"👤 Инициатор: {message.from_user.mention_html()}\n"
        f"🎯 Соперник: {message.reply_to_message.from_user.mention_html()}\n"
        f"💰 Ставка: <b>{amount} токенов</b> с каждого!\n\n"
        f"<i>Принять вызов может только соперник, отменить — участники.</i>"
    )

    await message.reply(challenge_text, reply_markup=keyboard)
    await db.increment_commands()
    await db.log_command("!дуэль", user_id)


async def accept_duel_callback(callback_query: types.CallbackQuery):
    data_parts = callback_query.data.split(":")
    creator_id = int(data_parts[1])
    amount = int(data_parts[2])
    target_id = callback_query.from_user.id

    if target_id == creator_id:
        await callback_query.answer(
            "❌ Вы не можете принять собственную дуэль!", show_alert=True
        )
        return

    bal_a = await tokens_db.get_balance(creator_id)
    bal_b = await tokens_db.get_balance(target_id)

    if bal_a < amount or bal_b < amount:
        await callback_query.answer("⚠️ Дуэль отменена.", show_alert=True)
        await callback_query.message.edit_text(
            format_styled_message(
                emoji="⚠️",
                title=DUEL_NAME,
                message="Дуэль отменена, так как у одного из игроков изменился баланс токенов.",
            )
        )
        return

    await callback_query.answer("⚔️ Бой начался!")

    winner_id = random.choice([creator_id, target_id])
    loser_id = target_id if winner_id == creator_id else creator_id

    await tokens_db.spend_tokens(loser_id, amount)
    await tokens_db.add_tokens(winner_id, amount)

    bot = callback_query.bot
    try:
        win_chat = await bot.get_chat(winner_id)
        lose_chat = await bot.get_chat(loser_id)
        win_name = win_chat.first_name
        lose_name = lose_chat.first_name
    except Exception:
        win_name = "Победитель"
        lose_name = "Проигравший"

    result_text = (
        f"⚡ <b>ДУЭЛЬ СОСТОЯЛАСЬ!</b> ⚡\n\n"
        f"🔫 Прозвучали выстрелы... На земле остался лежать <b>{lose_name}</b>.\n\n"
        f"🏆 <b>Победитель:</b> <b>{win_name}</b>\n"
        f"💰 Куш: <b>+{amount} токенов</b> (забрал у соперника!)"
    )

    await callback_query.message.edit_text(
        format_styled_message(emoji="💀", title="Итоги дуэли", message=result_text)
    )
    await db.increment_commands()


async def cancel_duel_callback(callback_query: types.CallbackQuery):
    data_parts = callback_query.data.split(":")
    creator_id = int(data_parts[1])
    target_id = int(data_parts[2])
    current_user_id = callback_query.from_user.id

    if current_user_id == creator_id:
        msg = "❌ Дуэль была отменена её инициатором."
    elif current_user_id == target_id:
        msg = "❌ Соперник отклонил вызов на дуэль."
    else:
        await callback_query.answer(
            "❌ Вы не участвуете в этой дуэли!", show_alert=True
        )
        return

    await callback_query.answer("Дуэль отменена.")
    await callback_query.message.edit_text(
        format_styled_message(emoji="❌", title=DUEL_NAME, message=msg)
    )
