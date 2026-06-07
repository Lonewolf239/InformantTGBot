from abc import ABC, abstractmethod


class BasePaymentProvider(ABC):
    @abstractmethod
    async def create_payment(self, amount: int, metadata: dict, description: str) -> tuple[str, str]:
        pass

    @abstractmethod
    async def check_payment(self, payment_id: str) -> str:
        pass
