"""Консольный UI на rich с fallback на обычный print.

Правило: вся красивость — только здесь. Расчетные модули возвращают данные,
а не печатают. Если rich не установлен — те же функции печатают plain-текст.
"""

from __future__ import annotations

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    HAS_RICH = True
except ImportError:  # pragma: no cover - fallback проверяется без rich
    Console = None  # type: ignore
    Table = None  # type: ignore
    Panel = None  # type: ignore
    HAS_RICH = False

_console = None


def get_console():
    """Синглтон консоли rich (или None при fallback)."""
    global _console
    if not HAS_RICH:
        return None
    if _console is None:
        _console = Console()
    return _console


def summarize_employee(single_count: int, missed_count: int, has_marks: bool) -> dict:
    """Чистый статус сотрудника для дашборда.

    Возвращает {'status': str, 'style': str} где style — цвет rich.
    """
    if not has_marks:
        return {'status': 'Нет данных', 'style': 'red'}
    if single_count == 0 and missed_count == 0:
        return {'status': 'OK', 'style': 'green'}
    return {'status': 'Править', 'style': 'yellow'}


def build_dashboard_rows(time_table: dict, emp_ids: list[int], year: int, month: int) -> list[dict]:
    """Собрать строки дашборда. Чистая агрегация, без печати."""
    from core.config import EMPLOYEES
    from core.analysis import _get_marks_and_missed

    rows: list[dict] = []
    for emp_id in emp_ids:
        role = EMPLOYEES.get(emp_id)
        name = f'{role.last_name} {role.first_name}'.strip() if role else f'ID {emp_id}'
        has_marks = any(emp_id in day for day in time_table.values())
        list_marks, list_missed = _get_marks_and_missed(time_table, emp_id, year, month)
        single_count = len(list_marks) if isinstance(list_marks, list) else 0
        missed_count = len(list_missed) if isinstance(list_missed, list) else 0
        info = summarize_employee(single_count, missed_count, has_marks)
        rows.append({
            'emp_id': emp_id,
            'name': name,
            'single': single_count,
            'missed': missed_count,
            'has_marks': has_marks,
            'status': info['status'],
            'style': info['style'],
        })
    return rows


def print_dashboard(rows: list[dict], title: str = 'Сводка') -> None:
    """Напечатать дашборд: rich-таблица или plain-фолбэк."""
    if not HAS_RICH:
        print(f'=== {title} ===')
        for r in rows:
            print(f"{r['name']}: одиночных={r['single']} пропусков={r['missed']} [{r['status']}]")
        return
    console = get_console()
    table = Table(title=title)
    table.add_column('Сотрудник')
    table.add_column('Одиночные', justify='right')
    table.add_column('Пропуски', justify='right')
    table.add_column('Статус', justify='center')
    for r in rows:
        table.add_row(
            r['name'],
            str(r['single']),
            str(r['missed']),
            f"[{r['style']}]{r['status']}[/{r['style']}]",
        )
    console.print(table)


def print_header(title: str) -> None:
    """Заголовок стадии."""
    if not HAS_RICH:
        print(f'=== {title} ===')
        return
    get_console().rule(title)


def info(msg: str) -> None:
    """Обычное сообщение."""
    if not HAS_RICH:
        print(msg)
        return
    get_console().print(msg)


def warn(msg: str) -> None:
    """Предупреждение (желтое при rich)."""
    if not HAS_RICH:
        print(msg)
        return
    get_console().print(f'[yellow]{msg}[/yellow]')


def error(msg: str) -> None:
    """Ошибка (красная при rich)."""
    if not HAS_RICH:
        print(msg)
        return
    get_console().print(f'[red]{msg}[/red]')


def ask_menu(prompt: str, valid: tuple[str, ...], cancel_tokens: tuple[str, ...] = ('0', 'q', 'отмена')) -> str:
    """Запросить пункт меню до валидного. Возвращает выбор как есть.

    Ввод — через builtins input (мокается в тестах), оформление — через rich.
    cancel_tokens считаются валидным выбором «пропустить».
    """
    allowed = tuple(valid) + tuple(cancel_tokens)
    while True:
        raw = input(prompt).strip()
        if raw in allowed:
            return raw
        info(f'Введите один из: {", ".join(allowed)}.')


def confirm_save(preview: str) -> bool:
    """Подтверждение сохранения. True — сохранить, False — ввести заново."""
    while True:
        raw = input(f'{preview}\nПодтвердить? [д/н]: ').strip().lower()
        if raw in ('д', 'y', 'да', 'yes', '1'):
            return True
        if raw in ('н', 'n', 'нет', 'no', '0'):
            return False
        info('Введите "д" или "н".')


def print_day_card_single(name: str, date_key: str, existing) -> None:
    """Карточка одиночной отметки."""
    body = (f'Сотрудник: {name}\n'
            f'Дата: {date_key}\n'
            f'Сохранено: {existing}\n'
            '[1] приход  [2] уход  [0] пропустить')
    if not HAS_RICH:
        print(body)
        return
    get_console().print(Panel(body, title='Одиночная отметка', border_style='yellow'))


def print_missed_day_card(name: str, missed_day: str) -> None:
    """Карточка пропущенного дня."""
    body = (f'Сотрудник: {name}\n'
            f'Дата без отметок: {missed_day}\n'
            '[1] рабочий день  [2] отпуск  [3] прогул  [0] пропустить')
    if not HAS_RICH:
        print(body)
        return
    get_console().print(Panel(body, title='Нет данных за день', border_style='red'))
