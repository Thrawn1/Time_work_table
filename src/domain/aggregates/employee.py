
from dataclasses import dataclass
from decimal import Decimal
from domain.value_objects.identifiers import EmployeeId
from domain.value_objects.money import Money

@dataclass(frozen=True)
class FullName:
    """Полное имя. Объект-значение."""
    first_name: str
    last_name: str

@dataclass(frozen=True)
class SalaryRates:
    """Набор часовых ставок. Объект-значение."""
    base_rate: Money
    overtime_rate: Money
    holiday_rate: Money

@dataclass(frozen=True)
class Employee:
    """
    Сотрудник. Корень агрегата.
    Содержит только данные о сотруднике, но НЕ его рабочие дни.
    """
    id: EmployeeId
    full_name: FullName
    rates: SalaryRates
    is_active: bool = True
