"""Типизированные правила ролей для новой модели оплаты (план roles_rates, §3 шага 3).

Нормы и бонусы загружаются из версий БД (pay_store); DEFAULT_RULES — только
стартовая матрица для первичного переноса и fallback, когда справочник ещё
не заведён. Вне этого модуля решений об учёте/оплате по конкретным ID ролей
быть не должно: анализ и расчёт спрашивают time_mode/норму/флаги здесь.

Матрица по умолчанию (согласовано частично, остальное — явные допущения):
- роль 0 «Руководитель»: не участвует в начислениях (причина в exclude_reason),
  отдельный список в дашборде;
- роль 1 «Работник цеха»: фактический учёт, норма 8, все три бонуса;
- роль 2 «Кладовщик»: фактический учёт, норма 8, без бонусов
  (из обсуждения бонусы не предусмотрены);
- роль 3 «Проживающий в цеху»: фиксированная смена 8 ч за рабочий выход
  независимо от отметок (текущее поведение кода), без бонусов до согласования;
- роль 4: фактический учёт, норма 8, бонусы как у роли 1 (роль поддержана
  кодом и тестами; нужна ли в действующем справочнике — вопрос §3.6).

H_base=8 (база тарифа) хранится в общих условиях оплаты, а не здесь.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

TIME_ACTUAL = 'actual'
TIME_FIXED_SHIFT = 'fixed_shift'

DEFAULT_OVERTIME_COEF = Decimal('1.5')


@dataclass(frozen=True)
class RoleRule:
    role_id: int
    role_name: str
    time_mode: str  # 'actual' | 'fixed_shift'
    shift_norm_hours: Decimal  # норма смены роли для учёта/переработки
    check_single_mark: bool  # проверять одиночные отметки
    participates: bool  # участвует ли в начислениях
    exclude_reason: str = ''  # причина исключения (для дашборда)
    overtime_eligible: bool = False
    full_month_eligible: bool = False
    seniority_eligible: bool = False
    overtime_coef: Decimal = field(default=DEFAULT_OVERTIME_COEF)


def _rule(role_id: int, role_name: str, time_mode: str, norm: str,
          check_single: bool, participates: bool, reason: str = '',
          overtime: bool = False, full_month: bool = False,
          seniority: bool = False) -> RoleRule:
    return RoleRule(
        role_id=role_id, role_name=role_name, time_mode=time_mode,
        shift_norm_hours=Decimal(norm), check_single_mark=check_single,
        participates=participates, exclude_reason=reason,
        overtime_eligible=overtime, full_month_eligible=full_month,
        seniority_eligible=seniority, overtime_coef=DEFAULT_OVERTIME_COEF,
    )


DEFAULT_RULES: dict[int, RoleRule] = {
    0: _rule(0, 'Руководитель', TIME_ACTUAL, '8', False, False,
             reason='руководство — не участвует',
             overtime=False, full_month=False, seniority=False),
    1: _rule(1, 'Работник цеха', TIME_ACTUAL, '8', True, True,
             overtime=True, full_month=True, seniority=True),
    2: _rule(2, 'Кладовщик', TIME_ACTUAL, '8', True, True,
             overtime=False, full_month=False, seniority=False),
    3: _rule(3, 'Проживающий в цеху', TIME_FIXED_SHIFT, '8', False, True,
             overtime=False, full_month=False, seniority=False),
    4: _rule(4, 'Работник цеха (спец)', TIME_ACTUAL, '8', True, True,
             overtime=True, full_month=True, seniority=True),
}


def get_default_rule(role_id: int) -> RoleRule:
    """Правило по умолчанию; неизвестная роль — понятная ошибка до правок/отчётов."""
    try:
        return DEFAULT_RULES[role_id]
    except KeyError:
        raise KeyError(
            f'Неизвестная роль {role_id}: нет правила учёта/оплаты. '
            f'Заведите версию правил роли в справочнике.'
        ) from None


def known_default_role_ids() -> list[int]:
    return sorted(DEFAULT_RULES)


def monthly_norm_hours(rule: RoleRule, workdays: int) -> Decimal:
    """Месячная норма часов роли: норма смены × число рабочих дней."""
    return rule.shift_norm_hours * Decimal(workdays)
