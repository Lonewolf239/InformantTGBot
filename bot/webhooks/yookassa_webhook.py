from aiohttp import web
from yookassa.domain.notification import (
    WebhookNotificationEventType,
    WebhookNotificationFactory,
)
from bot.utils.tokens_database import tokens_db
from bot.utils.helpers import format_styled_message
import logging

logger = logging.getLogger(__name__)


async def yookassa_handler(request: web.Request):
    try:
        event_json = await request.json()
        notification_object = WebhookNotificationFactory().create(event_json)

        if notification_object.event != WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            return web.Response(status=200)

        payment_id = notification_object.object.id

        payment_provider = request.app["payment_provider"]
        payment_info = await payment_provider.get_payment(payment_id)

        if payment_info["status"] != "succeeded":
            logger.warning(
                f"Вебхук ЮKassa сообщил succeeded, но реальный статус платежа "
                f"{payment_id} — {payment_info['status']}. Игнорирую."
            )
            return web.Response(status=200)

        user_id = payment_info["user_id"]
        amount = payment_info["amount"]
        if not user_id or not amount:
            logger.error(f"Платёж {payment_id} без корректных metadata (user_id/amount).")
            return web.Response(status=200)

        if not await tokens_db.claim_payment(payment_id):
            logger.info(f"Платёж {payment_id} уже был зачислен ранее, повтор вебхука пропущен.")
            return web.Response(status=200)

        await tokens_db.add_tokens(user_id, amount)
        new_balance = await tokens_db.get_balance(user_id)

        bot = request.app["bot"]

        success_text = format_styled_message(
            emoji="✅",
            title="Оплата успешно прошла!",
            message=f"Начислено: {amount} токенов.\nТвой новый баланс: {new_balance} шт.\nСпасибо за поддержку бота!",
        )
        await bot.send_message(user_id, success_text)

    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука ЮKassa: {e}")
        return web.Response(status=400)

    return web.Response(status=200)


def setup_yookassa_routes(app: web.Application, bot):
    from bot.handlers.payments import payment_provider

    app["bot"] = bot
    app["payment_provider"] = payment_provider
    app.router.add_post("/webhooks/yookassa", yookassa_handler)
