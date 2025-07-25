
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime
from typing import Tuple
from enum import Enum

from domain.value_objects.identifiers import EmployeeId, PayrollId
from domain.value_objects.money import Money


class ComponentType(Enum):
    """Тип компонента в расчетном листе."""
    EARNING = "Начисление"
    DEDUCTION = "Удержание"
    BENEFIT = "Льгота"


@dataclass(frozen=True)
class PayrollComponent:
    """
    Один универсальный компонент (строка) в расчетном листе.
    Может представлять собой любое начисление, удержание или льготу.
    """
    component_type: ComponentType
    description: str
    amount: Money
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Payroll:
    """
    Неизменяемый расчетный лист. Представляет собой финансовый документ
    о начислениях сотруднику за определенный период.
    """
    id: PayrollId
    employee_id: EmployeeId
    period_start: date
    period_end: date
    calculation_timestamp: datetime = field(default_factory=datetime.utcnow)
    components: Tuple[PayrollComponent, ...]

    @property
    def total_earnings(self) -> Money:
        """Общая сумма всех НАЧИСЛЕНИЙ."""
        total = sum(
            c.amount.amount
            for c in self.components
            if c.component_type == ComponentType.EARNING
        )
        return Money(total, currency="RUB")

    @property
    def total_deductions(self) -> Money:
        """Общая сумма всех УДЕРЖАНИЙ."""
        total = sum(
            c.amount.amount
            for c in self.components
            if c.component_type == ComponentType.DEDUCTION
        )
        return Money(total, currency="RUB")

    @property
    def total_to_pay(self) -> Money:
        """Итого к выплате (Начисления - Удержания)."""
        return Money(self.total_earnings.amount - self.total_deductions.amount, currency="RUB")
