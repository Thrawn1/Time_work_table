from datetime import datetime
from core.config import EMPLOYEES, MANUAL_EXCLUSIONS, SETTLEMENT_EXCEPTIONS
from core.day_models import DayMark, TimeTable
from core.file_parser import read_file_data, definition_of_working_day, parse_attlog_line
from core.constants import WEEKDAYS_NAME, MONTHS_NAME_TO_RUSSIAN


def build_data_array(list_month: list[str], employees: dict | None = None) -> TimeTable:
    import core.data_array as _self

    staff = getattr(_self, 'EMPLOYEES', None) if employees is None else employees
    if staff is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    time_table: TimeTable = {}
    for line in list_month:
        parsed = _parse_line(line)
        if parsed is None:
            continue
        emp_id, dt = parsed
        date_key = dt.strftime('%Y-%m-%d')
        if emp_id not in staff:
            print(f'Ошибка! Не указан id пользователя {emp_id} в файле!')
            continue
        if date_key not in time_table:
            time_table[date_key] = {}
        if emp_id in time_table[date_key]:
            existing = time_table[date_key][emp_id]
            if existing.go < dt:
                existing.go = dt
            if existing.come > dt:
                existing.come = dt
        else:
            tag_day = definition_of_working_day(date_key)[0]
            time_table[date_key][emp_id] = DayMark(go=dt, come=dt, tag=tag_day)
    return time_table


def _parse_line(line: str) -> tuple[int, datetime] | None:
    """Единый парсер DAT-строк (делегирует file_parser, оставлен ради тестов)."""
    return parse_attlog_line(line)


def get_employee_work_dates(time_table: dict, emp_id: int) -> list[str]:
    return [d for d in time_table if emp_id in time_table[d]]


def get_all_employees_in_data(time_table: dict, employees: dict | None = None) -> list[int]:
    """Все из справочника — для дашборда (включая бывших/без отметок)."""
    if employees is not None:
        return list(employees.keys())
    return list(EMPLOYEES.keys())


def get_employees_with_marks(time_table: dict, employees: dict | None = None) -> list[int]:
    """Только те, у кого есть хотя бы одна отметка за период, по порядку справочника.

    Это участники расчета по умолчанию: сотрудники без единой отметки
    (уволенные, другие смены) в расчет не включаются. Для genuinely
    отсутствовавшего весь месяц действующего сотрудника — флаг --include-empty.
    """
    import core.data_array as _self

    staff = getattr(_self, 'EMPLOYEES', None) if employees is None else employees
    if staff is None:
        staff = EMPLOYEES
    with_marks = {emp_id for day in time_table.values() for emp_id in day}
    return [emp_id for emp_id in staff if emp_id in with_marks]


def get_name_employee(emp_id: int, employees: dict | None = None) -> str:
    import core.data_array as _self

    staff = getattr(_self, 'EMPLOYEES', None) if employees is None else employees
    if staff is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    if emp_id in staff:
        emp = staff[emp_id]
        return f'{emp.last_name} {emp.first_name}'.strip()
    return ''


def is_settlement_allowed(emp_id: int) -> bool:
    return emp_id not in SETTLEMENT_EXCEPTIONS and emp_id not in MANUAL_EXCLUSIONS


def exclusion_reason(emp_id: int, employees: dict | None = None,
                     include_manual: bool = True) -> str:
    """Точная причина неучастия в начислениях (для дашборда/отчётов).

    Учитывает правила роли (напр. роль 0 «руководство — не участвует»),
    персональные исключения и исключения, выбранные оператором на этом запуске
    (include_manual=False — только правила справочников). Пустая строка — участвует.
    employees=None — глобальный DAT-справочник (legacy); переданный словарь
    (напр. объединённый DAT+SQLite) используется для поиска карточки (F02-union).
    """
    from core.roles import get_default_rule

    import core.data_array as _self

    staff = getattr(_self, 'EMPLOYEES', None) if employees is None else employees
    if staff is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    emp = staff.get(emp_id) if hasattr(staff, 'get') else None
    if emp is None:
        return 'нет в справочнике сотрудников'
    role_id = getattr(emp, 'role_id', None)
    if role_id is not None:
        try:
            rule = get_default_rule(role_id)
        except KeyError:
            return f'неизвестная роль {role_id}'
        if not rule.participates:
            return rule.exclude_reason or f'роль {role_id} не участвует'
    if emp_id in SETTLEMENT_EXCEPTIONS:
        return 'персональное исключение'
    if include_manual and emp_id in MANUAL_EXCLUSIONS:
        return MANUAL_EXCLUSIONS[emp_id]
    return ''


def is_included_in_settlement(emp_id: int, employees: dict | None = None) -> bool:
    """Единый состав участников: анализ, правки и все строки отчётов."""
    return exclusion_reason(emp_id, employees) == ''
