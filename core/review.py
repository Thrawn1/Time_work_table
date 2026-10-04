"""Интерактивный обзор месяца перед расчётом.

Порядок для оператора:
1. Таблица сотрудников: сколько у каждого дней с одной меткой и без меток, среднее
   время прихода и ухода (по настоящим данным терминала).
2. По номеру — полный список проблем сотрудника и выбор: закрывать по одной
   (вручную, отпуск, прогул, больничный, автозаполнение по среднему ± 5 минут)
   либо сразу автозаполнить все его одиночные отметки. Дни с недоработкой (отработано
   меньше нормы смены, на сколько бы ни было) правятся отдельным пунктом: по номеру дня.
3. ``x<номер>`` — исключить сотрудника из расчёта на этот запуск (повторно — вернуть).
4. Пустой ввод — к следующему этапу.
5. Этап «Недоработки» (run_undertime_review) — после того как пропуски закрыты (любым
   способом, в том числе автозаполнением): все дни участников расчёта, отработанные
   меньше нормы смены, одним списком; по номеру строки день правится. Пустой ввод —
   к расчёту.

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
        _current_average, _get_marks_and_missed, _get_undertime_days, analyze_for_edit,
        analyze_for_print, auto_fill_singles, edit_undertime_days, format_average,
        total_shortfall,
    )
    from core.calculations import str_timedelta

    analyze_for_print(time_table, emp_id, year, month,
                      employees=employees, rules_by_role=rules_by_role)
    while True:
        singles, missed = _get_marks_and_missed(
            time_table, emp_id, year, month, employees=employees, rules_by_role=rules_by_role)
        under = _get_undertime_days(
            time_table, emp_id, year, month, employees=employees, rules_by_role=rules_by_role)
        n_single = len(singles) if isinstance(singles, list) else 0
        n_missed = len(missed) if isinstance(missed, list) else 0
        if not (n_single or n_missed or under):
            ui.info('Проблем нет.')
            return
        info_line = f'Одна метка: {n_single}, нет меток: {n_missed}'
        if under:
            info_line += (f', недоработка: {len(under)} дн. '
                          f'(всего {str_timedelta(total_shortfall(under))})')
        ui.info(f'{info_line}. {format_average(_current_average(time_table, emp_id))}')
        options: list[tuple[str, str]] = []
        if n_single or n_missed:
            options.append(('1', 'закрывать по одной'))
        if n_single:
            options.append(('2', 'заполнить все одиночные отметки автоматически (по среднему ± 5 мин)'))
        if under:
            options.append(('3', 'править дни с недоработкой'))
        choice = ui.ask_menu(
            '  '.join(f'[{key}] {text}' for key, text in options) + '  [0] назад:',
            tuple(key for key, _text in options))
        if choice in ('0', 'q', 'отмена'):
            return
        if choice == '1':
            analyze_for_edit(time_table, emp_id, year, month,
                             employees=employees, rules_by_role=rules_by_role)
        elif choice == '2':
            auto_fill_singles(time_table, emp_id, year, month,
                              employees=employees, rules_by_role=rules_by_role)
        else:
            edit_undertime_days(time_table, emp_id, year, month,
                                employees=employees, rules_by_role=rules_by_role)


def build_undertime_rows(time_table: dict, employees: dict, emp_ids: list[int],
                         year: int, month: int, *, rules_by_role: dict | None = None
                         ) -> list[dict]:
    """Строки обзора недоработок: {'emp_id', 'name', 'item': UndertimeDay}.

    Порядок — как у ``emp_ids`` (справочник), внутри сотрудника — по датам.
    """
    from core.analysis import _get_undertime_days

    rows: list[dict] = []
    for emp_id in emp_ids:
        emp = employees.get(emp_id)
        name = f'{emp.last_name} {emp.first_name}'.strip() if emp else f'ID {emp_id}'
        for item in _get_undertime_days(time_table, emp_id, year, month,
                                        employees=employees, rules_by_role=rules_by_role):
            rows.append({'emp_id': emp_id, 'name': name, 'item': item})
    return rows


def run_undertime_review(time_table: dict, employees: dict, candidate_ids: list[int],
                         year: int, month: int, *, rules_by_role: dict | None = None,
                         extra_excluded: dict | None = None,
                         title: str = 'Недоработки') -> None:
    """Обзор недоработок участников расчёта и правка дней по номеру строки.

    Показываются только текущие участники расчёта (исключённые не видны). Список
    обновляется после каждой правки; день, оставшийся короче нормы, остаётся в нём.
    Пустой ввод, закрытый ввод (EOF) и Ctrl+C завершают этап.
    """
    from core import ui
    from core.analysis import _edit_undertime_day

    ui.print_header(title)
    while True:
        ids = current_settlement_ids(candidate_ids, employees, extra_excluded)
        rows = build_undertime_rows(time_table, employees, ids, year, month,
                                    rules_by_role=rules_by_role)
        if not rows:
            ui.info('Недоработок нет.')
            return
        ui.print_undertime_overview(rows)
        try:
            raw = input('Номер строки — править день | Enter — к расчёту: ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw in _CANCEL:
            return
        if not raw.isdigit() or not 1 <= int(raw) <= len(rows):
            ui.error(f'Нет строки с номером {raw!r}: введите число от 1 до {len(rows)}.')
            continue
        row = rows[int(raw) - 1]
        _edit_undertime_day(time_table, row['emp_id'], row['item'], row['name'],
                            employees=employees)
