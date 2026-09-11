"""Новый расчёт оплаты по общей месячной базе (план roles_rates, §2/шаг 4).

Чистые функции на Decimal, скрытого чтения ставок/БД нет: вызывающая сторона
формирует PayInputs явно (общие условия + версия правил + назначение + стаж +
календарь + участники). Деньги — ROUND_HALF_UP, квантуются только отображаемые
компоненты; стаж считается от неокруглённых промежуточных сумм, итог сходится
как сумма отображаемых компонентов.

Решения шага 0 (зафиксированы пользователем 2026-09-11):
- переработка — месячная: H_overtime = max(0, факт − норма_роли_за_месяц);
  K_overtime — полная оплата сверхурочного часа (часы исключены из обычной
  оплаты через cap min(факт, норма), двойной оплаты нет);
- полный месяц — строгий: все D рабочих дней присутствуют, без отпуска/
  прогула, факт >= нормы, без незакрытых отметок, занятость весь месяц;
- стаж — основа = полная база M + B_overtime + B_full_month (не фактическая
  обычная оплата при неполном месяце), K_seniority — доля доплаты.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.money import as_decimal, quantize_money

_ZERO = Decimal('0')


@dataclass(frozen=True)
class PayInputs:
    monthly_base: Decimal      # M, напр. 60000.00
    base_day_hours: int        # H_base, 8
    full_month_bonus: Decimal  # 5000.00
    workdays: int              # D полного расчётного месяца
    shift_norm_hours: Decimal  # норма смены роли
    fact_hours: Decimal        # суммарный факт (часы, Decimal)
    workdays_present: int      # выходов в рабочие дни
    vacation_days: int = 0
    truancy_days: int = 0
    single_mark_issue: bool = False  # незакрытые/одиночные отметки
    employed_whole_month: bool = True  # приём/увольнение внутри месяца
    overtime_eligible: bool = False
    full_month_eligible: bool = False
    seniority_eligible: bool = False
    overtime_coef: Decimal = Decimal('1.5')  # K_overtime, полная оплата часа
    seniority_rate: Decimal = _ZERO  # K_seniority, доля (0.10 = 10%)
    milk_amount: Decimal = _ZERO  # молоко отдельно, в основу стажа не входит


@dataclass(frozen=True)
class PayResult:
    rate_day: Decimal       # R_day, точная (не квантовать до расчёта)
    rate_hour: Decimal      # R_hour, точная
    norm_hours: Decimal
    fact_hours: Decimal
    ordinary_hours: Decimal
    ordinary_pay: Decimal   # квантована
    overtime_hours: Decimal
    overtime_bonus: Decimal  # квантован
    full_month_bonus: Decimal  # квантован (5000.00 или 0.00)
    full_month_ok: bool
    full_month_reason: str
    seniority_rate: Decimal
    seniority_basis_exact: Decimal  # неокруглённая основа (для прозрачности)
    seniority_bonus: Decimal  # квантован
    total: Decimal  # сумма квантованных компонентов
    milk_amount: Decimal
    total_with_milk: Decimal


def monthly_rates(monthly_base: Decimal, workdays: int,
                  base_day_hours: int = 8) -> tuple[Decimal, Decimal]:
    """Производные ставки месяца точные (без квантования до копеек).

    Иначе 2727.27 × 22 = 59999.94 — потеря базы полного месяца.
    """
    if workdays <= 0:
        raise ValueError(
            f'Число рабочих дней месяца D={workdays}: расчёт невозможен '
            f'(пустой календарь?). Нужна явная диагностика, а не деление на 0.'
        )
    base = as_decimal(monthly_base)
    rate_day = base / Decimal(workdays)
    rate_hour = base / (Decimal(workdays) * Decimal(base_day_hours))
    return rate_day, rate_hour


def check_full_month(workdays: int, workdays_present: int, fact_hours: Decimal,
                     norm_hours: Decimal, vacation_days: int, truancy_days: int,
                     single_mark_issue: bool, employed_whole_month: bool,
                     eligible: bool) -> tuple[bool, str]:
    """Строгий критерий полного месяца. Возвращает (ok, причина)."""
    if not eligible:
        return False, 'роль не имеет права на бонус'
    if not employed_whole_month:
        return False, 'приём/увольнение внутри месяца'
    if vacation_days:
        return False, f'отпуск: {vacation_days} дн.'
    if truancy_days:
        return False, f'прогул: {truancy_days} дн.'
    if workdays_present != workdays:
        return False, f'выходов {workdays_present} из {workdays} рабочих дней'
    if single_mark_issue:
        return False, 'есть незакрытые отметки'
    if fact_hours < norm_hours:
        return False, f'факт {fact_hours} ч < нормы {norm_hours} ч'
    return True, 'все рабочие дни, норма выполнена'


def seniority_rate_for_service(scale: list[tuple[int, Decimal]],
                               years: float | Decimal) -> Decimal:
    """Ставка стажа по шкале [(порог_лет, доля)]: максимальный пройденный порог."""
    years_d = as_decimal(years)
    rate = _ZERO
    for threshold_years, percent in sorted(scale, key=lambda t: t[0]):
        if years_d >= Decimal(threshold_years):
            rate = as_decimal(percent)
    return rate


def calculate_pay(inp: PayInputs) -> PayResult:
    """Порядок: обычная оплата + переработка → 5000 → стаж (не входит в свою основу)."""
    rate_day, rate_hour = monthly_rates(inp.monthly_base, inp.workdays, inp.base_day_hours)
    norm_hours = as_decimal(inp.shift_norm_hours) * Decimal(inp.workdays)
    fact_hours = as_decimal(inp.fact_hours)

    ordinary_hours = min(fact_hours, norm_hours)
    ordinary_exact = ordinary_hours * rate_hour

    if inp.overtime_eligible:
        overtime_hours = max(_ZERO, fact_hours - norm_hours)
        overtime_exact = overtime_hours * rate_hour * as_decimal(inp.overtime_coef)
    else:
        overtime_hours = _ZERO
        overtime_exact = _ZERO

    full_ok, full_reason = check_full_month(
        inp.workdays, inp.workdays_present, fact_hours, norm_hours,
        inp.vacation_days, inp.truancy_days, inp.single_mark_issue,
        inp.employed_whole_month, inp.full_month_eligible,
    )
    full_exact = as_decimal(inp.full_month_bonus) if full_ok else _ZERO

    # Основа стажа — полная база M + неокруглённые бонусы (§2.4).
    seniority_basis_exact = as_decimal(inp.monthly_base) + overtime_exact + full_exact
    if inp.seniority_eligible and inp.seniority_rate:
        seniority_exact = seniority_basis_exact * as_decimal(inp.seniority_rate)
    else:
        seniority_exact = _ZERO

    ordinary_pay = quantize_money(ordinary_exact)
    overtime_bonus = quantize_money(overtime_exact)
    full_bonus = quantize_money(full_exact)
    seniority_bonus = quantize_money(seniority_exact)
    total = ordinary_pay + overtime_bonus + full_bonus + seniority_bonus
    milk = quantize_money(inp.milk_amount)
    total_with_milk = total + milk

    return PayResult(
        rate_day=rate_day, rate_hour=rate_hour,
        norm_hours=norm_hours, fact_hours=fact_hours,
        ordinary_hours=ordinary_hours, ordinary_pay=ordinary_pay,
        overtime_hours=overtime_hours, overtime_bonus=overtime_bonus,
        full_month_bonus=full_bonus, full_month_ok=full_ok,
        full_month_reason=full_reason,
        seniority_rate=as_decimal(inp.seniority_rate),
        seniority_basis_exact=seniority_basis_exact,
        seniority_bonus=seniority_bonus,
        total=total, milk_amount=milk, total_with_milk=total_with_milk,
    )
