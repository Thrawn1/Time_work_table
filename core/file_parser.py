import re
from datetime import datetime
from functools import lru_cache
from os import path
from core import config as _config

DAT_LINE_PATTERN = re.compile(
    r'^\s*(\d+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?:\s|$)'
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


def read_file_data_with_errors(file_name: str, year: int, month: int,
                                data_dir: str | None = None) -> tuple[list[str], list[str]]:
    """Импорт с диагностикой: (строки за период, ошибки с номерами строк).

    data_dir=None — каталог из core.config (CLI: --data-dir, дефолт 'data').
    """
    base = data_dir if data_dir is not None else _config.DATA_DIR
    file_path = path.join(base, file_name)
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
            errors.append(
                f'строка {lineno}: не распознана '
                f'(ожидался формат "<ID> YYYY-MM-DD HH:MM:SS...") — пропущена'
            )
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
            result.append(line.rstrip('\r\n'))
    if errors:
        print(f'ВНИМАНИЕ: пропущено строк импорта с ошибками: {len(errors)} (расчёт продолжен).')
        for err in errors[:10]:
            print(f'  - {err}')
        if len(errors) > 10:
            print(f'  ... и ещё {len(errors) - 10}')
    return result, errors


def read_file_data(file_name: str, year: int, month: int,
                   data_dir: str | None = None) -> list[str]:
    result, _ = read_file_data_with_errors(file_name, year, month, data_dir)
    return result


def load_holidays(year: int) -> tuple[str, ...]:
    return tuple(_load_calendar_file(path.abspath(_config.HOLIDAYS_FILE), year))


def load_postponed_days(year: int) -> tuple[str, ...]:
    return tuple(_load_calendar_file(path.abspath(_config.POSTPONED_DAYS_FILE), year))


def _parse_calendar_line(line: str, lineno: int, source: str) -> tuple[str, str, str | None]:
    """Разобрать 'ДД.ММ' или 'ГГГГ-ММ-ДД' (R16).

    Возвращает (day_str, month_str, year_str|None): year None — запись ДД.ММ
    для любого года (наследие, ненадёжно для переносов); иначе конкретный год.
    R16: комбинация дня и месяца проверяется календарём (31.02 отклоняется),
    а не только диапазонами по отдельности.
    """
    import calendar as _cal

    text = line.strip()
    if '-' in text and len(text.strip()) >= 8:
        # Полная дата ГГГГ-ММ-ДД (R16): привязана к году.
        try:
            y_s, m_s, d_s = [p.strip() for p in text.split('-')]
            y, m, d = int(y_s), int(m_s), int(d_s)
            _cal.monthrange(y, m)  # проверка месяца
            if not 1 <= d <= _cal.monthrange(y, m)[1]:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError(
                f'{source}:{lineno}: нужен формат "ДД.ММ" или "ГГГГ-ММ-ДД" '
                f'с существующей датой: {line.strip()!r}') from None
        return f'{d:02d}', f'{m:02d}', f'{y:04d}'
    parts = text.split('.')
    if len(parts) != 2:
        raise ValueError(
            f'{source}:{lineno}: нужен формат "ДД.ММ": {line.strip()!r}')
    day_raw, month_raw = parts[0].strip(), parts[1].strip()
    if not day_raw.isdigit() or not month_raw.isdigit():
        raise ValueError(
            f'{source}:{lineno}: день/месяц должны быть числами "ДД.ММ": {line.strip()!r}')
    day, month = int(day_raw), int(month_raw)
    if not 1 <= month <= 12:
        raise ValueError(
            f'{source}:{lineno}: месяц {month} вне 1..12: {line.strip()!r}')
    # R16: 31.02 и подобные отклоняются (проверка по невисокосному + високосному
    # невозможна без года — отклоняем заведомо невозможные: >29.02, 31.04/06/09/11).
    import calendar as _cal2

    max_day = 29 if (day == 29 and month == 2) else _cal2.monthrange(2024, month)[1]
    # 2024 високосный: февраль 29 допустим как ДД.ММ (год подставится позже
    # и перепроверится); остальные месяцы — по реальной длине.
    if not 1 <= day <= max_day:
        raise ValueError(
            f'{source}:{lineno}: невозможная дата {line.strip()!r} '
            f'(календарная проверка)')
    return f'{day:02d}', f'{month:02d}', None


@lru_cache(maxsize=16)
def _load_calendar_file(source: str, year: int) -> list[str]:
    """Прочитать календарный файл с диагностикой строк (F19/R16).

    Поддерживает 'ДД.ММ' (любой год, наследие) и 'ГГГГ-ММ-ДД' (только свой год).
    Невозможные даты отклоняются с файлом и строкой. Кэш привязан к
    абсолютному пути и году — при смене каталога (set_data_dir) не путается
    со старыми данными без явного clear_calendar_cache().
    """
    import calendar as _cal

    dates: list[str] = []
    with open(source, 'r', encoding='utf-8-sig') as f:
        for lineno, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            day_str, month_str, year_str = _parse_calendar_line(raw, lineno, source)
            if year_str is not None and int(year_str) != int(year):
                continue
            month, day = int(month_str), int(day_str)
            try:
                if not 1 <= day <= _cal.monthrange(int(year), month)[1]:
                    raise ValueError
            except ValueError:
                raise ValueError(
                    f'{source}:{lineno}: {raw.strip()!r} — нет такой даты '
                    f'в {year} году') from None
            dates.append(f'{year}-{month_str}-{day_str}')
    return dates


def find_calendar_conflicts(year: int) -> list[str]:
    """Пересечения праздника и перенесённого рабочего дня (R16).

    Разрешались неявным приоритетом праздника — теперь явная диагностика.
    """
    try:
        holidays = set(load_holidays(year))
        postponed = set(load_postponed_days(year))
    except (OSError, UnicodeDecodeError, ValueError):
        return []
    return sorted(holidays & postponed)


def clear_calendar_cache() -> None:
    """Сбросить кэш после изменения файлов или между запусками приложения."""
    _load_calendar_file.cache_clear()


def definition_of_working_day(date_str: str) -> tuple[str, str]:
    from calendar import weekday
    from core.constants import WEEKDAYS_NAME
    from core.day_models import TAG_HOLIDAY, TAG_WEEKEND, TAG_WORK

    year = int(date_str[0:4])
    month = int(date_str[5:7])
    day = int(date_str[8:10])

    holidays = load_holidays(year)
    postponed = load_postponed_days(year)

    num_day = weekday(year, month, day)
    weekday_name = WEEKDAYS_NAME[num_day]

    if date_str in holidays:
        return (TAG_HOLIDAY, weekday_name)
    if date_str in postponed:
        return (TAG_WORK, weekday_name)
    if num_day in (5, 6):
        return (TAG_WEEKEND, weekday_name)
    return (TAG_WORK, weekday_name)
