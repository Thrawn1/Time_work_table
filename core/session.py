"""
Безопасное хранение сессий: JSON вместо pickle, атомарная запись.

Формат файла:
{
  "version": 1,
  "entries": {
    "2026-07-06": {
      "101": ["2026-07-06T16:00:00", "2026-07-06T08:00:00", "work"]
    }
  }
}

Ключи сотрудников — строки (JSON не поддерживает int-ключи).
Даты — ISO 8601 строки.
"""
import json
import os
import tempfile
from datetime import datetime

SESSION_VERSION = 1
SESSION_FILE = 'temporary.json'
SESSION_FILE_LEGACY = 'temporary.pickle'


class SessionBackupError(RuntimeError):
    """Не удалось сохранить существующую сессию перед новым расчётом.

    Выбрасывается вместо молчаливого None, чтобы вызывающий код
    не начинал новый расчёт поверх несохранённой сессии.
    """

# Единый набор статусов — источник в core.day_models (значения те же).
from core.day_models import ALLOWED_TAGS as _ALLOWED

ALLOWED_TAGS = set(_ALLOWED)


def _infer_period(time_table: dict) -> dict | None:
    """Вывести общий период YYYY-MM из ключей дат. None — пусто или разные месяцы."""
    if not time_table:
        return None
    periods = {k[:7] for k in time_table.keys() if isinstance(k, str) and len(k) >= 7}
    if len(periods) != 1:
        return None
    only = next(iter(periods))
    try:
        year_s, month_s = only.split('-')
        return {'year': int(year_s), 'month': int(month_s)}
    except (ValueError, AttributeError):
        return None


def save_session(time_table: dict, year: int | None = None, month: int | None = None) -> None:
    """Атомарная запись сессии: temp-файл + os.replace."""
    data = {
        'version': SESSION_VERSION,
        'entries': {},
    }
    if year is not None and month is not None:
        data['period'] = {'year': int(year), 'month': int(month)}
    else:
        inferred = _infer_period(time_table)
        if inferred is not None:
            data['period'] = inferred
    for date_key, employees in time_table.items():
        data['entries'][date_key] = {}
        for emp_id, marks in employees.items():
            go = getattr(marks, 'go', marks[0])
            come = getattr(marks, 'come', marks[1])
            tag = getattr(marks, 'tag', marks[2])
            data['entries'][date_key][str(emp_id)] = [
                go.isoformat(),
                come.isoformat(),
                tag,
            ]

    dir_name = os.path.dirname(os.path.abspath(SESSION_FILE))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, SESSION_FILE)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def validate_session_raw(raw: dict) -> tuple[dict | None, list[str]]:
    """Проверить схему и смысл сессии целиком. Возвращает (time_table|None, errors).

    Строгая проверка: любая ошибка делает восстановление невозможным
    (возвращается None + список ошибок), вместо молчаливого частичного расчёта.
    """
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ['корень сессии должен быть объектом']
    if 'version' not in raw or 'entries' not in raw:
        return None, ['отсутствуют обязательные поля version/entries']
    if raw['version'] != SESSION_VERSION:
        return None, [f"версия сессии {raw.get('version')} не совпадает с ожидаемой {SESSION_VERSION}"]
    entries = raw['entries']
    if not isinstance(entries, dict):
        return None, ['поле entries должно быть объектом {дата: {id: метки}}']
    if not entries:
        # Пустая таблица допустима только с явным периодом в заголовке
        # (месяц без отметок, восстановленный по метаданным).
        period_meta = raw.get('period')
        if isinstance(period_meta, dict) and 'year' in period_meta and 'month' in period_meta:
            try:
                _y = int(period_meta['year'])
                _m = int(period_meta['month'])
                if 1900 <= _y <= 2100 and 1 <= _m <= 12:
                    return {}, []
                errors.append(f'период {period_meta!r} в заголовке пустой сессии вне диапазона')
                return None, errors
            except (ValueError, TypeError):
                return None, ['некорректное поле period в заголовке пустой сессии']
        return None, ['пустая сессия без периода: нет entries и нет поля period '
                      '(невозможно определить месяц расчёта)']

    time_table: dict = {}
    periods: set[str] = set()
    for date_key, employees in entries.items():
        try:
            dt_key = datetime.strptime(str(date_key), '%Y-%m-%d')
        except (ValueError, TypeError):
            errors.append(f'{date_key}: некорректная дата (нужен формат YYYY-MM-DD)')
            continue
        periods.add(f'{dt_key.year:04d}-{dt_key.month:02d}')
        if not isinstance(employees, dict):
            errors.append(f'{date_key}: сотрудники должны быть объектом')
            continue
        day: dict = {}
        for emp_id_str, marks in employees.items():
            where = f'{date_key}/{emp_id_str}'
            try:
                emp_id = int(emp_id_str)
            except (ValueError, TypeError):
                errors.append(f'{where}: некорректный ID сотрудника')
                continue
            if not isinstance(marks, list) or len(marks) != 3:
                errors.append(f'{where}: метки должны быть списком из 3 элементов')
                continue
            try:
                dt_out = datetime.fromisoformat(marks[0])
                dt_in = datetime.fromisoformat(marks[1])
                tag = str(marks[2])
            except (ValueError, TypeError, AttributeError):
                errors.append(f'{where}: некорректные datetime/тег')
                continue
            if tag not in ALLOWED_TAGS:
                errors.append(f'{where}: недопустимый статус {tag!r} (нужен один из {sorted(ALLOWED_TAGS)})')
                continue
            if dt_out.tzinfo is not None or dt_in.tzinfo is not None:
                errors.append(
                    f'{where}: часовые пояса не поддерживаются — '
                    'используйте наивное локальное время без смещения'
                )
                continue
            try:
                inverted = dt_out < dt_in
            except TypeError:
                errors.append(f'{where}: несравнимые отметки (смешанные часовые пояса?)')
                continue
            if inverted:
                errors.append(
                    f'{where}: приход {dt_in.time()} позже ухода {dt_out.time()} — так нельзя'
                )
                continue
            if dt_out.date().isoformat() != str(date_key) or dt_in.date().isoformat() != str(date_key):
                errors.append(f'{where}: время не соответствует дате {date_key}')
                continue
            from core.day_models import DayMark

            day[emp_id] = DayMark(go=dt_out, come=dt_in, tag=tag)
        time_table[str(date_key)] = day

    if len(periods) > 1:
        errors.append(f'несогласованный период сессии: {sorted(periods)} (ожидался один месяц)')
    period_meta = raw.get('period')
    if isinstance(period_meta, dict) and 'year' in period_meta and 'month' in period_meta:
        try:
            meta = f"{int(period_meta['year']):04d}-{int(period_meta['month']):02d}"
            if periods and meta not in periods:
                errors.append(f'период {meta} из заголовка не совпадает с датами {sorted(periods)}')
        except (ValueError, TypeError):
            errors.append('некорректное поле period в заголовке сессии')

    if errors:
        return None, errors
    return time_table, []


def load_session(path: str = SESSION_FILE) -> dict | None:
    """
    Загрузка сессии из JSON.

    Возвращает time_table dict или None при ошибке.
    Старые pickle-файлы не загружаются — выводится предупреждение.
    """
    if not os.path.exists(path):
        return None

    if path.endswith('.pickle'):
        print(f'ВНИМАНИЕ: файл {path} в формате pickle больше не поддерживается. '
              'Удалите его и запустите программу заново.')
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f'Ошибка чтения сессии {path}: {e}')
        return None

    time_table, errors = validate_session_raw(raw)
    if errors:
        print(f'Ошибка валидации сессии {path}:')
        for err in errors:
            print(f'  - {err}')
        return None
    return time_table


def session_exists() -> bool:
    """Проверяет наличие файла сессии (JSON или legacy pickle)."""
    return os.path.exists(SESSION_FILE) or os.path.exists(SESSION_FILE_LEGACY)


def remove_session() -> None:
    """Удаляет файлы сессий."""
    for path in (SESSION_FILE, SESSION_FILE_LEGACY):
        try:
            os.remove(path)
        except OSError:
            pass


def _peek_period(path: str) -> tuple[int, int] | None:
    """Прочитать период сессии без строгой валидации. None — не удалось."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    period = raw.get('period')
    if isinstance(period, dict) and 'year' in period and 'month' in period:
        try:
            return int(period['year']), int(period['month'])
        except (ValueError, TypeError):
            pass
    entries = raw.get('entries')
    if isinstance(entries, dict) and entries:
        first = sorted(entries.keys())[0]
        try:
            dt = datetime.strptime(str(first), '%Y-%m-%d')
            return dt.year, dt.month
        except (ValueError, TypeError):
            return None
    return None


def _unique_backup_path(base: str) -> str:
    """Подобрать несуществующий путь бэкапа: base свободен — он, иначе с суффиксом.

    Суффикс из time_ns + uuid гарантирует уникальность повторных бэкапов
    одного периода в одну секунду (см. F09).
    """
    import time
    import uuid

    if not os.path.exists(base):
        return base
    root, ext = os.path.splitext(base)
    for _ in range(1000):
        candidate = f'{root}_{time.time_ns()}_{uuid.uuid4().hex[:8]}{ext}'
        if not os.path.exists(candidate):
            return candidate
    raise SessionBackupError(f'не удалось подобрать уникальное имя для {base!r}')


def backup_existing_session() -> str | None:
    """Сохранить игнорируемую сессию отдельно, чтобы новый расчёт её не затёр.

    Возвращает путь бэкапа или None, если сохранять нечего.
    При ошибке перемещения бросает SessionBackupError — вызывающий код
    обязан прервать новый расчёт и не удалять исходную сессию.
    Имя — temporary_YYYY_MM.json (период из сессии) либо с меткой времени;
    повторные бэкапы получают уникальный суффикс и не перезаписывают друг друга.
    """
    import time
    import uuid

    if not os.path.exists(SESSION_FILE) and not os.path.exists(SESSION_FILE_LEGACY):
        return None
    backup: str | None = None
    if os.path.exists(SESSION_FILE):
        period = _peek_period(SESSION_FILE)
        if period is not None:
            candidate = f'temporary_{period[0]:04d}_{period[1]:02d}.json'
            if os.path.abspath(candidate) == os.path.abspath(SESSION_FILE):
                candidate = (f'temporary_backup_{period[0]:04d}_{period[1]:02d}_'
                             f'{time.time_ns()}_{uuid.uuid4().hex[:8]}.json')
            else:
                candidate = _unique_backup_path(candidate)
            backup = candidate
        else:
            backup = (f'temporary_backup_{time.time_ns()}_{uuid.uuid4().hex[:8]}.json')
            while os.path.exists(backup):
                backup = (f'temporary_backup_{time.time_ns()}_{uuid.uuid4().hex[:8]}.json')
        try:
            os.replace(SESSION_FILE, backup)
        except OSError as e:
            raise SessionBackupError(f'не удалось сохранить {SESSION_FILE}: {e}') from e
    if os.path.exists(SESSION_FILE_LEGACY):
        if backup is not None:
            legacy_backup = _unique_backup_path(backup + '.pickle_legacy')
        else:
            legacy_backup = (f'temporary_backup_{time.time_ns()}_{uuid.uuid4().hex[:8]}.pickle')
            while os.path.exists(legacy_backup):
                legacy_backup = (f'temporary_backup_{time.time_ns()}_{uuid.uuid4().hex[:8]}.pickle')
        try:
            os.replace(SESSION_FILE_LEGACY, legacy_backup)
            if backup is None:
                backup = legacy_backup
        except OSError as e:
            raise SessionBackupError(f'не удалось сохранить {SESSION_FILE_LEGACY}: {e}') from e
    return backup
