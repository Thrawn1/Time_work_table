import re
from datetime import datetime
from os import path
from core.config import HOLIDAYS_FILE, POSTPONED_DAYS_FILE

DAT_LINE_PATTERN = re.compile(
    r'^\s*(\d+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
)


def parse_attlog_line(line: str) -> tuple[int, datetime] | None:
    match = DAT_LINE_PATTERN.match(line)
    if not match:
        return None
    try:
        emp_id = int(match.group(1))
    except (ValueError, TypeError):
        return None
    try:
        dt = datetime.strptime(match.group(2), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        # Невозможная дата (напр. 2026-02-30): пропускаем строку, а не роняем импорт.
        return None
    return emp_id, dt


def read_file_data_with_errors(file_name: str, year: int, month: int) -> tuple[list[str], list[str]]:
    """Импорт с диагностикой: (строки за период, ошибки с номерами строк)."""
    file_path = path.join('data', file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print('Файл данных не найден:', file_path)
        return [], [f'{file_path}: файл не найден']
    result: list[str] = []
    errors: list[str] = []
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = DAT_LINE_PATTERN.match(line)
        if not match:
            continue
        try:
            dt = datetime.strptime(match.group(2), '%Y-%m-%d %H:%M:%S')
        except ValueError as e:
            errors.append(f'строка {lineno}: невозможная дата {match.group(2)!r} ({e}) — пропущена')
            continue
        try:
            int(match.group(1))
        except (ValueError, TypeError):
            errors.append(f'строка {lineno}: некорректный ID — пропущена')
            continue
        if dt.year == year and dt.month == month:
            result.append(line.rstrip('\n'))
    if errors:
        print(f'ВНИМАНИЕ: пропущено строк импорта с ошибками: {len(errors)} (расчёт продолжен).')
        for err in errors[:10]:
            print(f'  - {err}')
        if len(errors) > 10:
            print(f'  ... и ещё {len(errors) - 10}')
    return result, errors


def read_file_data(file_name: str, year: int, month: int) -> list[str]:
    result, _ = read_file_data_with_errors(file_name, year, month)
    return result


def load_holidays(year: int) -> list[str]:
    holidays = []
    with open(HOLIDAYS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('.')
            day_str = parts[0]
            month_str = parts[1]
            holidays.append(f'{year}-{month_str}-{day_str}')
    return holidays


def load_postponed_days(year: int) -> list[str]:
    postponed = []
    with open(POSTPONED_DAYS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('.')
            day_str = parts[0]
            month_str = parts[1]
            postponed.append(f'{year}-{month_str}-{day_str}')
    return postponed


def definition_of_working_day(date_str: str) -> tuple[str, str]:
    from calendar import weekday
    from core.constants import WEEKDAYS_NAME

    year = int(date_str[0:4])
    month = int(date_str[5:7])
    day = int(date_str[8:10])

    holidays = load_holidays(year)
    postponed = load_postponed_days(year)

    num_day = weekday(year, month, day)
    weekday_name = WEEKDAYS_NAME[num_day]

    if date_str in holidays:
        return ('holiday', weekday_name)
    if date_str in postponed:
        return ('work', weekday_name)
    if num_day in (5, 6):
        return ('weekend', weekday_name)
    return ('work', weekday_name)
