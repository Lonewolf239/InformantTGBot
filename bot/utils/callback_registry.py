from typing import Awaitable, Callable

CallbackHandler = Callable[..., Awaitable[None]]

CALLBACK_ROUTES: list[tuple[Callable[[str], bool], CallbackHandler]] = []


def register_callback(*, exact: tuple[str, ...] = (), prefix: tuple[str, ...] = ()):
    def decorator(handler: CallbackHandler) -> CallbackHandler:
        def matcher(data: str) -> bool:
            if exact and data in exact:
                return True
            if prefix and data.startswith(prefix):
                return True
            return False

        CALLBACK_ROUTES.append((matcher, handler))
        return handler

    return decorator


async def dispatch_callback(callback_query, state, data: str | None) -> bool:
    if not data:
        return False
    for matcher, handler in CALLBACK_ROUTES:
        if matcher(data):
            await handler(callback_query, state, data)
            return True
    return False
