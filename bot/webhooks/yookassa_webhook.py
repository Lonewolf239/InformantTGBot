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
        response_object = notification_object.object

        if notification_object.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            metadata = response_object.metadata
            user_id = int(metadata.get("user_id"))
            amount = int(metadata.get("amount"))

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
    app["bot"] = bot
    app.router.add_post("/webhooks/yookassa", yookassa_handler)
