import uuid
import asyncio
from yookassa import Configuration, Payment
from bot.payments.base import BasePaymentProvider
from config import BOT_LINK


class YookassaProvider(BasePaymentProvider):
    def __init__(self, shop_id: str, secret_key: str):
        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key

    async def create_payment(
        self, amount: int, metadata: dict, description: str
    ) -> tuple[str, str]:
        def _create():
            idempotence_key = str(uuid.uuid4())
            payment = Payment.create(
                {
                    "amount": {"value": f"{amount}.00", "currency": "RUB"},
                    "confirmation": {"type": "redirect", "return_url": BOT_LINK},
                    "capture": True,
                    "description": description,
                    "metadata": metadata,
                },
                idempotence_key,
            )
            return payment.id, payment.confirmation.confirmation_url

        return await asyncio.to_thread(_create)

    async def check_payment(self, payment_id: str) -> str:
        def _check():
            payment = Payment.find_one(payment_id)
            return payment.status

        return await asyncio.to_thread(_check)

    async def get_payment(self, payment_id: str) -> dict:
        def _get():
            payment = Payment.find_one(payment_id)
            metadata = payment.metadata or {}
            return {
                "status": payment.status,
                "user_id": int(metadata.get("user_id", 0)),
                "amount": int(metadata.get("amount", 0)),
            }

        return await asyncio.to_thread(_get)
