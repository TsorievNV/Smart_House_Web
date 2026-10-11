"""создатель задан константой через singleton."""
from dataclasses import dataclass
from functools import lru_cache

CURRENT_USER_ID = 1

@dataclass(frozen=True)
class CurrentUser:
    id: int

@lru_cache(maxsize=1)
def get_current_user() -> CurrentUser:
    """Один неизменяемый объект на процесс, без ORM-сессии в кеше."""
    return CurrentUser(CURRENT_USER_ID)
