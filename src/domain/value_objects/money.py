
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Money:
    """Объект-значение для денег, чтобы избежать ошибок с float."""
    amount: Decimal
    currency: str = "RUB"
