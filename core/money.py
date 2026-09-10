"""Денежные правила проекта.

Единица ставки: **руб/смена** (оплата стандартной 8-часовой смены).
Стандартная смена: 8 ч (см. WORKING_DAY_HOURS).
Часовая доля ставки = ставка / 8 (точно в Decimal).

Правила округления:
- Все промежуточные вычисления — в Decimal с полной точностью.
- Квантование — только финальный итог (и итог с молоком) до копеек:
  quantize(Decimal('0.01'), ROUND_HALF_UP).
- Банковское округление Python round() для денег НЕ используется
  (у него HALF_EVEN: 2.345 -> 2.34, а бухгалтерии нужно 2.35).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANT = Decimal('0.01')
RATE_QUANT = Decimal('0.01')
MONEY_ROUNDING = ROUND_HALF_UP

SECONDS_PER_HOUR = Decimal('3600')


def quantize_money(value: Decimal | int | str) -> Decimal:
    """Округлить денежную сумму до копеек бухгалтерским HALF_UP."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(MONEY_QUANT, rounding=MONEY_ROUNDING)


def quantize_rate(value: Decimal | int | str) -> Decimal:
    """Округлить ставку до копеек HALF_UP."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(RATE_QUANT, rounding=MONEY_ROUNDING)


def as_decimal(value: Decimal | int | float | str) -> Decimal:
    """Безопасно привести число к Decimal (float — через str, без binary-мусора)."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def timedelta_to_seconds(td: timedelta) -> Decimal:
    """Точное число секунд в timedelta как Decimal (без float-ошибки total_seconds())."""
    total = td.days * 86400 + td.seconds
    if td.microseconds:
        return Decimal(total) + Decimal(td.microseconds) / Decimal('1000000')
    return Decimal(total)


def timedelta_to_hours(td: timedelta) -> Decimal:
    """Точное число часов в timedelta как Decimal."""
    return timedelta_to_seconds(td) / SECONDS_PER_HOUR


def format_money(value: Decimal | int | float | str) -> str:
    """Формат денег всегда с 2 знаками: 800 -> '800.00'."""
    return f'{quantize_money(as_decimal(value)):.2f}'
