from typing import Callable, Dict

COMMAND_HANDLERS: Dict[str, Callable] = {}


def register_command(cmd_name: str, is_enabled: bool = True):
    def decorator(func: Callable):
        if is_enabled:
            COMMAND_HANDLERS[cmd_name] = func
        return func

    return decorator
