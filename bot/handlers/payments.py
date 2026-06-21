# bot/handlers/payments.py
from aiogram import types
from aiogram.types import InlineKeyboardButton
from bot.utils.tokens_database import tokens_db
from bot.utils.helpers import create_user_keyboard, format_styled_message
from config import TOKEN_PRICE_RUB, MIN_TOKENS_BUY, MAX_TOKENS_BUY, TOKEN_PACKAGES, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, USE_WEBHOOKS
from bot.payments.yookassa_provider import YookassaProvider
import logging
from bot.owner_settings.config_getters import is_payments_enabled

logger = logging.getLogger(__name__)

payment_provider = YookassaProvider(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)

async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    balance = await tokens_db.get_balance(user_id)

    text = format_styled_message(
        emoji="💳",
        title="БАЛАНС ТОКЕНОВ",
        message=f"<b>Доступно:</b> {balance} шт.\nТокены тратятся на ИИ, загрузки и расшифровку.\nБаланс обновляется до базового каждую полночь."
    )

    keyboard = []
    current_row = []

    if await is_payments_enabled():
        for amount in TOKEN_PACKAGES:
            if MIN_TOKENS_BUY <= amount <= MAX_TOKENS_BUY:
                price_rub = amount * TOKEN_PRICE_RUB
                current_row.append(
                    InlineKeyboardButton(
                        text=f"🛒 {amount} шт ({price_rub}₽)", 
                        callback_data=f"buy_tokens:{amount}"
                    )
                )
                if len(current_row) == 2:
                    keyboard.append(current_row)
                    current_row = []

        if current_row:
            keyboard.append(current_row)

    markup = create_user_keyboard(keyboard, user_id)
    await message.reply(text, reply_markup=markup)


async def process_buy_tokens_callback(callback_query: types.CallbackQuery, amount: int):
    if not await is_payments_enabled() or not payment_provider:
        await callback_query.answer("❌ Оплата временно недоступна (не настроена касса)", show_alert=True)
        return

    if not (MIN_TOKENS_BUY <= amount <= MAX_TOKENS_BUY):
        await callback_query.answer("❌ Недопустимое количество токенов!", show_alert=True)
        return

    price_rub = amount * TOKEN_PRICE_RUB
    description = f"Пополнение бака: {amount} токенов"

    try:
        payment_id, pay_url = await payment_provider.create_payment(
            amount=price_rub,
            metadata={"user_id": callback_query.from_user.id, "amount": amount},
            description=description
        )
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        await callback_query.answer("❌ Ошибка соединения с кассой", show_alert=True)
        return

    text = format_styled_message(
        emoji="🚀",
        title="Пополнение бака",
        message=f"Покупка {amount} токенов за {price_rub}₽.\nОни плюсуются к текущему балансу и не сгорают при ежедневном сбросе!\n\n<i>Ссылка на оплату действительна короткое время.</i>"
    )

    pay_keyboard = [[InlineKeyboardButton(text=f"💳 Оплатить {price_rub}₽", url=pay_url)]]

    if not USE_WEBHOOKS:
        pay_keyboard.append([InlineKeyboardButton(text="🔄 Проверить платёж", callback_data=f"cp|{payment_id}|{amount}")])

    reply_markup = create_user_keyboard(pay_keyboard, callback_query.from_user.id)

    await callback_query.message.answer(text, reply_markup=reply_markup)
    await callback_query.answer()

async def process_check_payment_callback(callback_query: types.CallbackQuery, payment_id: str, amount: int):
    if not await is_payments_enabled() or not payment_provider:
        await callback_query.answer("❌ Оплата временно недоступна", show_alert=True)
        return

    try:
        status = await payment_provider.check_payment(payment_id)
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {e}")
        await callback_query.answer("❌ Ошибка соединения с кассой", show_alert=True)
        return

    if status == "succeeded":
        user_id = callback_query.from_user.id
        await tokens_db.add_tokens(user_id, amount)
        new_balance = await tokens_db.get_balance(user_id)

        success_text = format_styled_message(
            emoji="✅",
            title="Оплата успешно прошла!",
            message=f"Начислено: {amount} токенов.\nТвой новый баланс: {new_balance} шт.\nСпасибо за поддержку бота!"
        )
        await callback_query.message.edit_text(success_text, reply_markup=None)
        await callback_query.answer("✅ Платёж подтверждён! Токены зачислены.", show_alert=True)

    elif status == "pending":
        await callback_query.answer("⏳ Платёж ещё не завершён. Оплати и нажми кнопку снова.", show_alert=True)

    elif status == "canceled":
        cancel_text = format_styled_message(
            emoji="❌",
            title="Платёж отменён",
            message="Время жизни ссылки истекло, или платёж был отклонён."
        )
        await callback_query.message.edit_text(cancel_text, reply_markup=None)
        await callback_query.answer("❌ Платёж отменён кассой", show_alert=True)

    else:
        await callback_query.answer(f"ℹ️ Статус платежа: {status}", show_alert=True)
