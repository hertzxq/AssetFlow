import time
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from typing import Callable, Any, Awaitable

class TimeMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any]
    ) -> Any:
        start_time = time.time()
        try:
            # Вызов следующего обработчика
            result = await handler(event, data)
        finally:
            execution_time = time.time() - start_time
            # Используем event.event_type напрямую как строку
            event_type = getattr(event, 'event_type', "unknown")
            print(f"Execution time for {event_type} (Update ID: {event.update_id}): {execution_time:.2f} seconds")
        return result