from core.config import (
    MANUAL_EXCLUSIONS, SETTLEMENT_EXCEPTIONS, full_name, staff_or_default,
)
from core.day_models import DayMark, TimeTable
from core.file_parser import definition_of_working_day, parse_attlog_line


def build_data_array(list_month: list[str], employees: dict | None = None) -> TimeTable:
    staff = staff_or_default(employees)
    time_table: TimeTable = {}
    for line in list_month:
        parsed = parse_attlog_line(line)
        if parsed is None:
            continue
        emp_id, dt = parsed
        date_key = dt.strftime('%Y-%m-%d')
        if emp_id not in staff:
            print(f'Ошибка! Не указан id пользователя {emp_id} в файле!')
            continue
        day = time_table.setdefault(date_key, {})
        existing = day.get(emp_id)
        if existing is None:
            day[emp_id] = DayMark(go=dt, come=dt, tag=definition_of_working_day(date_key)[0])
        else:
            existing.go = max(existing.go, dt)
            existing.come = min(existing.come, dt)
    return time_table


def get_employees_with_marks(time_table: dict, employees: dict | None = None) -> list[int]:
    """Только те, у кого есть хотя бы одна отметка за период, по порядку справочника.

    Это участники расчета по умолчанию: сотрудники без единой отметки
    (уволенные, другие смены) в расчет не включаются. Для genuinely
    отсутствовавшего весь месяц действующего сотрудника — флаг --include-empty.
    """
    with_marks = {emp_id for day in time_table.values() for emp_id in day}
    return [emp_id for emp_id in staff_or_default(employees) if emp_id in with_marks]


def get_name_employee(emp_id: int, employees: dict | None = None) -> str:
    """«Фамилия Имя» или '' — сотрудника нет в справочнике."""
    emp = staff_or_default(employees).get(emp_id)
    return full_name(emp) if emp is not None else ''


def display_name(emp_id: int, employees: dict | None = None) -> str:
    """«Фамилия Имя» или «ID 101» для сотрудника без карточки."""
    return get_name_employee(emp_id, employees) or f'ID {emp_id}'


def repairmen_attendance(time_table: dict, employees: dict | None,
                         year: int, month: int) -> dict[int, list[str]]:
    """Дни выходов ремонтников за месяц: {emp_id: [даты по порядку]} (R04, spec §2).

    Роль REPAIRMEN_ROLE_ID — без начислений и без проверки одиночных:
    одна отметка = выход. Ремонтник без выходов — пустой список.
    """
    from core.roles import REPAIRMEN_ROLE_ID

    prefix = f'{year:04d}-{month:02d}-'
    return {
        emp_id: sorted(d for d, day in time_table.items()
                       if d.startswith(prefix) and emp_id in day)
        for emp_id, emp in staff_or_default(employees).items()
        if getattr(emp, 'role_id', None) == REPAIRMEN_ROLE_ID
    }


def is_settlement_allowed(emp_id: int) -> bool:
    return emp_id not in SETTLEMENT_EXCEPTIONS and emp_id not in MANUAL_EXCLUSIONS


def exclusion_reason(emp_id: int, employees: dict | None = None,
                     include_manual: bool = True,
                     rules_by_role: dict | None = None) -> str:
    """Точная причина неучастия в начислениях (для дашборда/отчётов).

    Учитывает правила роли (напр. роль 0 «руководство — не участвует»),
    персональные исключения и исключения, выбранные оператором на этом запуске
    (include_manual=False — только правила справочников). Пустая строка — участвует.
    employees=None — глобальный DAT-справочник (legacy); переданный словарь
    (напр. объединённый DAT+SQLite) используется для поиска карточки (F02-union).
    rules_by_role — действующие SQLite-правила месяца (new-режим); без них —
    DAT-умолчание. Так роль, заведённая только в SQLite, не считается неизвестной.
    """
    from core.roles import resolve_rule

    emp = staff_or_default(employees).get(emp_id)
    if emp is None:
        return 'нет в справочнике сотрудников'
    role_id = getattr(emp, 'role_id', None)
    if role_id is not None:
        rule = resolve_rule(role_id, rules_by_role)
        if rule is None:
            return f'неизвестная роль {role_id}'
        if not rule.participates:
            return rule.exclude_reason or f'роль {role_id} не участвует'
    if emp_id in SETTLEMENT_EXCEPTIONS:
        return 'персональное исключение'
    if include_manual and emp_id in MANUAL_EXCLUSIONS:
        return MANUAL_EXCLUSIONS[emp_id]
    return ''


def is_included_in_settlement(emp_id: int, employees: dict | None = None,
                              rules_by_role: dict | None = None) -> bool:
    """Единый состав участников: анализ, правки и все строки отчётов."""
    return exclusion_reason(emp_id, employees, rules_by_role=rules_by_role) == ''
