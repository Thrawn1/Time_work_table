from datetime import datetime
from core.config import EMPLOYEES, SETTLEMENT_EXCEPTIONS
from core.file_parser import read_file_data, definition_of_working_day, parse_attlog_line
from core.constants import WEEKDAYS_NAME, MONTHS_NAME_TO_RUSSIAN


def build_data_array(list_month: list[str]) -> dict[str, dict[int, list]]:
    time_table: dict[str, dict[int, list]] = {}
    for line in list_month:
        parsed = _parse_line(line)
        if parsed is None:
            continue
        emp_id, dt = parsed
        date_key = dt.strftime('%Y-%m-%d')
        if emp_id not in EMPLOYEES:
            print(f'Ошибка! Не указан id пользователя {emp_id} в файле!')
            continue
        if date_key not in time_table:
            time_table[date_key] = {}
        if emp_id in time_table[date_key]:
            existing = time_table[date_key][emp_id]
            if existing[0] < dt:
                existing[0] = dt
            if existing[1] > dt:
                existing[1] = dt
        else:
            tag_day = definition_of_working_day(date_key)[0]
            time_table[date_key][emp_id] = [dt, dt, tag_day]
    return time_table


def _parse_line(line: str) -> tuple[int, datetime] | None:
    """Единый парсер DAT-строк (делегирует file_parser, оставлен ради тестов)."""
    return parse_attlog_line(line)


def get_employee_work_dates(time_table: dict, emp_id: int) -> list[str]:
    return [d for d in time_table if emp_id in time_table[d]]


def get_all_employees_in_data(time_table: dict) -> list[int]:
    """Все из справочника — для дашборда (включая бывших/без отметок)."""
    return list(EMPLOYEES.keys())


def get_employees_with_marks(time_table: dict) -> list[int]:
    """Только те, у кого есть хотя бы одна отметка за период, по порядку справочника.

    Это участники расчета по умолчанию: сотрудники без единой отметки
    (уволенные, другие смены) в расчет не включаются. Для genuinely
    отсутствовавшего весь месяц действующего сотрудника — флаг --include-empty.
    """
    with_marks = {emp_id for day in time_table.values() for emp_id in day}
    return [emp_id for emp_id in EMPLOYEES if emp_id in with_marks]


def get_name_employee(emp_id: int) -> str:
    if emp_id in EMPLOYEES:
        emp = EMPLOYEES[emp_id]
        return f'{emp.last_name} {emp.first_name}'.strip()
    return ''


def is_settlement_allowed(emp_id: int) -> bool:
    return emp_id not in SETTLEMENT_EXCEPTIONS


def exclusion_reason(emp_id: int) -> str:
    """Точная причина неучастия в начислениях (для дашборда/отчётов).

    Учитывает правила роли (напр. роль 0 «руководство — не участвует»)
    и персональные исключения. Пустая строка — участвует.
    """
    from core.roles import get_default_rule

    emp = EMPLOYEES.get(emp_id)
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
    return ''


def is_included_in_settlement(emp_id: int) -> bool:
    """Единый состав участников: анализ, правки и все строки отчётов."""
    return exclusion_reason(emp_id) == ''
