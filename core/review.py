"""Интерактивный обзор месяца перед расчётом.

Порядок для оператора:
1. Таблица сотрудников: сколько у каждого дней с одной меткой и без меток, среднее
   время прихода и ухода (по настоящим данным терминала).
2. По номеру — полный список проблем сотрудника и выбор: закрывать по одной
   (вручную, отпуск, прогул, больничный, автозаполнение по среднему ± 5 минут)
   либо сразу автозаполнить все его одиночные отметки.
3. ``x<номер>`` — исключить сотрудника из расчёта на этот запуск (повторно — вернуть).
4. Пустой ввод — к расчёту.

Модуль только оркестрирует: проверки и правки живут в core.analysis, вывод — в core.ui.
"""

from __future__ import annotations

import re

from core.config import MANUAL_EXCLUSION_REASON, MANUAL_EXCLUSIONS

_CANCEL = ('', '0', 'q', 'й', 'отмена')
_EXCLUDE_RE = re.compile(r'^[xх]\s*(\d+)$')  # латинская x и русская х


def current_settlement_ids(candidate_ids: list[int], employees: dict,
                           extra_excluded: dict | None = None) -> list[int]:
    """Участники расчёта среди кандидатов: правила справочников, исключения, ручные."""
    from core.data_array import is_included_in_settlement

    extra = extra_excluded or {}
    return [e for e in candidate_ids
            if is_included_in_settlement(e, employees) and e not in extra]


def toggle_manual_exclusion(emp_id: int) -> bool:
    """Исключить сотрудника из расчёта (True) или вернуть обратно (False)."""
    if emp_id in MANUAL_EXCLUSIONS:
        del MANUAL_EXCLUSIONS[emp_id]
        return False
    MANUAL_EXCLUSIONS[emp_id] = MANUAL_EXCLUSION_REASON
    return True


def run_review(time_table: dict, employees: dict, candidate_ids: list[int],
               year: int, month: int, *, rules_by_role: dict | None = None,
               extra_excluded: dict | None = None, on_exclusion_change=None,
               title: str = 'Сводка') -> None:
    """Цикл обзора до пустого ввода. Правки пишутся в time_table и в сессию.

    on_exclusion_change() вызывается после смены ручных исключений — вызывающий код
    сохраняет их в контексте сессии. Закрытый ввод (EOF) и Ctrl+C завершают цикл.
    """
    from core import ui

    while True:
        included = set(current_settlement_ids(candidate_ids, employees, extra_excluded))
        rows = ui.build_dashboard_rows(
            time_table, list(employees), year, month, employees=employees,
            extra_excluded=extra_excluded or None, rules_by_role=rules_by_role,
            included_ids=included)
        ui.print_dashboard(rows, title=title, numbered=True)
        selectable = ui.review_numbering(rows)
        try:
            raw = input('Номер сотрудника — разобрать проблемы | x<номер> — исключить '
                        '(повторно — вернуть) | Enter — к расчёту: ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw in _CANCEL:
            return
        exclude = _EXCLUDE_RE.match(raw)
        number_text = exclude.group(1) if exclude else raw
        if not number_text.isdigit() or not 1 <= int(number_text) <= len(selectable):
            ui.error(f'Нет сотрудника с номером {raw!r}: введите число от 1 до {len(selectable)}.')
            continue
        row = selectable[int(number_text) - 1]
        if exclude:
            now_excluded = toggle_manual_exclusion(row['emp_id'])
            ui.info(f"{row['name']}: {'исключён из расчёта' if now_excluded else 'возвращён в расчёт'}.")
            if on_exclusion_change is not None:
                on_exclusion_change()
            continue
        if row.get('manual'):
            ui.warn(f"{row['name']} исключён вручную: x{number_text} вернёт его в расчёт.")
            continue
        review_employee(time_table, employees, row['emp_id'], year, month,
                        rules_by_role=rules_by_role)


def review_employee(time_table: dict, employees: dict, emp_id: int, year: int, month: int,
                    *, rules_by_role: dict | None = None) -> None:
    """Полный список проблем сотрудника и выбор способа их закрыть."""
    from core import ui
    from core.analysis import (
        _current_average, _get_marks_and_missed, analyze_for_edit, analyze_for_print,
        auto_fill_singles, format_average,
    )

    analyze_for_print(time_table, emp_id, year, month,
                      employees=employees, rules_by_role=rules_by_role)
    while True:
        singles, missed = _get_marks_and_missed(
            time_table, emp_id, year, month, employees=employees, rules_by_role=rules_by_role)
        if singles == 0 and missed == 0:
            ui.info('Проблем нет.')
            return
        n_single = len(singles) if isinstance(singles, list) else 0
        n_missed = len(missed) if isinstance(missed, list) else 0
        ui.info(f'Одна метка: {n_single}, нет меток: {n_missed}. '
                f'{format_average(_current_average(time_table, emp_id))}')
        choice = ui.ask_menu(
            '[1] закрывать по одной  [2] заполнить все одиночные отметки автоматически '
            '(по среднему ± 5 мин)  [0] назад:', ('1', '2'))
        if choice in ('0', 'q', 'отмена'):
            return
        if choice == '1':
            analyze_for_edit(time_table, emp_id, year, month,
                             employees=employees, rules_by_role=rules_by_role)
        else:
            auto_fill_singles(time_table, emp_id, year, month,
                              employees=employees, rules_by_role=rules_by_role)
