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


def save_session(time_table: dict) -> None:
    """Атомарная запись сессии: temp-файл + os.replace."""
    data = {
        'version': SESSION_VERSION,
        'entries': {},
    }
    for date_key, employees in time_table.items():
        data['entries'][date_key] = {}
        for emp_id, marks in employees.items():
            data['entries'][date_key][str(emp_id)] = [
                marks[0].isoformat(),
                marks[1].isoformat(),
                marks[2],
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

    if not isinstance(raw, dict) or 'version' not in raw or 'entries' not in raw:
        print(f'Ошибка формата сессии {path}: отсутствуют обязательные поля')
        return None

    if raw['version'] != SESSION_VERSION:
        print(f'ВНИМАНИЕ: версия сессии {raw["version"]} не совпадает с ожидаемой {SESSION_VERSION}')
        return None

    time_table = {}
    for date_key, employees in raw['entries'].items():
        if not isinstance(employees, dict):
            continue
        time_table[date_key] = {}
        for emp_id_str, marks in employees.items():
            try:
                emp_id = int(emp_id_str)
            except (ValueError, TypeError):
                continue
            if not isinstance(marks, list) or len(marks) != 3:
                continue
            try:
                dt_out = datetime.fromisoformat(marks[0])
                dt_in = datetime.fromisoformat(marks[1])
                tag = str(marks[2])
            except (ValueError, TypeError):
                continue
            time_table[date_key][emp_id] = [dt_out, dt_in, tag]

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
