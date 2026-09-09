from datetime import datetime
from core.config import EMPLOYEES, SETTLEMENT_EXCEPTIONS
from core.file_parser import read_file_data, definition_of_working_day
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
    import re
    pattern = re.compile(
        r'^\s*(\d+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
    )
    match = pattern.match(line)
    if not match:
        return None
    emp_id = int(match.group(1))
    dt = datetime.strptime(match.group(2), '%Y-%m-%d %H:%M:%S')
    return emp_id, dt


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
