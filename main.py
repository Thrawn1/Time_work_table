import argparse
import sys
from decimal import Decimal
from os.path import exists

from core.config import load_config, set_secret_key
from core.file_parser import read_file_data
from core.data_array import build_data_array, get_all_employees_in_data, get_employees_with_marks, is_included_in_settlement
from core.analysis import analyze_for_print, analyze_for_edit
from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
from core.excel_builder import build_excel
from core.html_builder import build_html
from core.constants import MONTHS_NAME_TO_RUSSIAN
from core.session import (
    SessionBackupError,
    load_session,
    session_exists,
    remove_session,
    backup_existing_session,
)


def parse_secret_key(key_input: str) -> tuple[Decimal, bool, str | None]:
    """Разобрать -k. Возвращает (secret, salary_mode, warning|None).

    salary_mode=False: режим без зарплаты (t/0/мусор) — оклад будет нулевым.
    Ключ — Decimal (точное деление на 100, без binary-ошибки float).
    """
    if key_input == 't' or key_input == '0':
        return Decimal('0.00'), False, None
    if key_input.isdigit() and 2 < len(key_input) < 123:
        return Decimal(key_input) / Decimal('100'), True, None
    return Decimal('0.00'), False, (
        f'ключ "{key_input}" не распознан (нужны только цифры, длина 3-122, '
        'или t для режима без зарплаты)'
    )


def main():
    parser = argparse.ArgumentParser(
        description='Система расчета заработной платы и учета рабочего времени'
    )
    parser.add_argument('-f', '--file', default='1_attlog.dat', help='Файл данных')
    parser.add_argument('-y', '--year', type=int, help='Год')
    parser.add_argument('-m', '--month', type=int, help='Месяц (1-12)')
    parser.add_argument('-k', '--key', default='0', help='Секретный ключ (или t для без зарплаты)')
    parser.add_argument('--no-edit', action='store_true', help='Пропустить интерактивное редактирование')
    parser.add_argument('--resume', action='store_true', help='Восстановить сохраненную сессию из temporary.json')
    parser.add_argument('--include-empty', action='store_true',
                        help='Включить в расчет сотрудников без единой отметки за месяц '
                             '(действующий, но отсутствовал весь месяц: отпуск/прогул)')
    parser.add_argument('--pay-dir', default='data/pay_directory.db',
                        help='SQLite-справочник новой модели оплаты '
                             '(нет файла/условий на месяц — legacy-режим)')
    args = parser.parse_args()

    load_config()

    print('\n\t\tСистема расчета заработной платы и учета рабочего времени работников\n')
    secret_key, salary_mode, key_warning = parse_secret_key(args.key)
    if key_warning:
        print(f'ВНИМАНИЕ: {key_warning}. Расчет в режиме БЕЗ зарплаты: оклад будет нулевым.')

    set_secret_key(secret_key)
    if salary_mode:
        print('Режим: расчет зарплаты (ключ принят).')
    else:
        print('Режим: учет времени БЕЗ зарплаты (оклад = 0, молоко считается).')

    from core.analysis import clear_journal
    clear_journal()

    pickle_path = 'temporary.pickle'
    json_path = 'temporary.json'
    session_state = 'none'
    list_data: list[str] = []
    if args.resume and (exists(json_path) or exists(pickle_path)):
        data_array = load_session()
        if data_array is None:
            print('Не удалось восстановить сессию!')
            sys.exit(1)
        if not data_array:
            # Пустой месяц, восстановленный по периоду из заголовка сессии.
            from core.session import _peek_period as _peek_resume_period
            _period = _peek_resume_period(json_path) if exists(json_path) else None
            if _period is None:
                print('Не удалось восстановить сессию: пустая сессия без периода!')
                sys.exit(1)
            year, month = _period
        else:
            first_date = list(data_array.keys())[0]
            year = int(first_date[:4])
            month = int(first_date[5:7])
        session_state = 'resumed'
    else:
        if not args.resume and session_exists():
            try:
                saved = backup_existing_session()
            except SessionBackupError as _be:
                print(f'ОШИБКА: не удалось сохранить существующую сессию ({_be}). '
                      f'Новый расчёт не начат, исходная сессия сохранена.')
                sys.exit(1)
            if saved:
                print(f'ВНИМАНИЕ: найден файл сессии. '
                      f'Он сохранён отдельно как {saved} и будет проигнорирован. '
                      f'Используйте --resume для восстановления.')
            else:
                print(f'ВНИМАНИЕ: найден файл сессии. '
                      'Он будет проигнорирован. Используйте --resume для восстановления.')
            session_state = 'ignored'
        else:
            session_state = 'fresh'
        year = args.year or int(input('Введите год: '))
        month = args.month or int(input('Введите месяц: '))
        list_data = read_file_data(args.file, year, month)
        if not list_data:
            from os.path import join as _join
            _missing = not exists(_join('data', args.file))
            if _missing:
                print('Нет данных для обработки!')
                sys.exit(1)
            if args.include_empty:
                print('ВНИМАНИЕ: за выбранный месяц отметок нет — '
                      'начинаем с пустой таблицы (--include-empty).')
                data_array = {}
            else:
                print('Нет данных для обработки!')
                sys.exit(1)
        else:
            data_array = build_data_array(list_data)

    print(f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} год')

    if args.include_empty:
        emp_ids = get_all_employees_in_data(data_array)
    else:
        emp_ids = get_employees_with_marks(data_array)
        skipped = len(get_all_employees_in_data(data_array)) - len(emp_ids)
        if skipped:
            print(f'Без отметок за месяц пропущено сотрудников: {skipped} '
                  f'(см. второй блок сводки; для включения — --include-empty).')

    # Единый состав участников расчёта: роль вне участия и персональные
    # исключения — только в дашборде (с причиной), в расчёт/превью/отчёты не попадают.
    settlement_ids = [e for e in emp_ids if is_included_in_settlement(e)]
    settlement_set = set(settlement_ids)

    # Этап 3: единый контекст периода — до анализа и правок (F01/F02/F05).
    from core.payroll import PayrollError as _PayrollError
    from core.pay_context import (
        diagnose_roster_divergence as _diagnose_roster,
        resolve_context as _resolve_context,
        sqlite_excluded_map as _sqlite_excluded,
    )
    try:
        pay_ctx = _resolve_context(args.pay_dir, year, month, salary_mode)
    except _PayrollError as e:
        print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
        sys.exit(1)
    sqlite_excluded: dict = {}
    if pay_ctx.mode == 'new':
        print('Режим модели: новая (SQLite-условия действуют на месяц). Ошибки настройки фатальны.')
        from core.config import EMPLOYEES as _DAT_STAFF
        for w in _diagnose_roster(pay_ctx, _DAT_STAFF, data_array):
            print(f'ВНИМАНИЕ (состав): {w}')
        try:
            sqlite_excluded = _sqlite_excluded(args.pay_dir, pay_ctx.month_start)
        except _PayrollError as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        # До правок: отсутствие обязательного назначения — фатально, без silent fallback.
        from core.pay_store import connect as _connect, get_assignment as _get_assign
        try:
            _con = _connect(args.pay_dir)
            try:
                _missing = []
                for emp_id in settlement_ids:
                    if emp_id in sqlite_excluded:
                        continue
                    if _get_assign(_con, emp_id, pay_ctx.month_start) is None:
                        _missing.append(emp_id)
            finally:
                try:
                    _con.close()
                except Exception:
                    pass
        except Exception as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        if _missing:
            from core.data_array import get_name_employee as _nm
            _names = ', '.join(f'{_nm(e) or e}' for e in _missing)
            print(f'ОШИБКА: новая модель должна применяться, но нет назначения SQLite '
                  f'на {pay_ctx.month_start} для: {_names}. Расчет прерван без fallback.')
            sys.exit(1)
    else:
        print('Режим модели: legacy (действующих SQLite-условий на месяц нет).')

    from core.ui import (
        build_dashboard_rows,
        build_preview_rows,
        build_start_info,
        print_dashboard,
        print_header,
        print_journal,
        print_preview,
        print_salary_report,
        print_start_screen,
    )
    from core.analysis import get_journal

    rows_read = len(list_data) if list_data else sum(len(day) for day in data_array.values())
    print_start_screen(build_start_info(
        args.file if session_state != 'resumed' else '(сессия)',
        year, month, rows_read, len(settlement_ids), session_state,
    ))

    print_header('Проверка')
    from core.config import EMPLOYEES as _STAFF
    for emp_id in settlement_ids:
        analyze_for_print(data_array, emp_id, year, month, employees=_STAFF)

    print_dashboard(
        build_dashboard_rows(data_array, get_all_employees_in_data(data_array), year, month,
                             employees=_STAFF, extra_excluded=sqlite_excluded or None),
        title=f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — сводка',
    )

    if not args.no_edit:
        print_header('Правки')
        for emp_id in settlement_ids:
            analyze_for_edit(data_array, emp_id, year, month, employees=_STAFF)

    for emp_id in settlement_ids:
        analyze_for_print(data_array, emp_id, year, month, employees=_STAFF)

    print_header('Расчет')
    work_time_all = calculate_hours_per_day(data_array, employees=_STAFF)
    work_time = {
        date_key: {emp_id: val for emp_id, val in emps.items() if emp_id in settlement_set}
        for date_key, emps in work_time_all.items()
    }
    work_time = {d: e for d, e in work_time.items() if e}
    summary, restructured = calculate_hours_per_month(work_time)
    # Режим уже выбран до правок (pay_ctx): new — обязателен и фатален
    # при ошибках настройки, legacy — старый адаптер. Silent fallback запрещён (F05).
    from core.payroll import PayrollError, build_bundle, bundle_to_wages
    pay_bundle = None
    if pay_ctx.mode == 'new':
        try:
            pay_bundle = build_bundle(data_array, work_time, summary, year, month,
                                      args.pay_dir, salary_mode=salary_mode)
        except PayrollError as e:
            print(f'ОШИБКА: новая модель должна применяться, но настройка ошибочна ({e}). '
                  f'Расчет прерван без fallback в legacy.')
            sys.exit(1)
    if pay_bundle is not None:
        wages = bundle_to_wages(pay_bundle)
        from core.ui import print_pay_details
        print_pay_details(pay_bundle)
        versions_file = f'payroll_versions_{year}_{month:02d}.json'
        pay_bundle.save_versions(versions_file)
        print(f'Версии условий и календарь сохранены: {versions_file}')
    else:
        from core.config import load_wage_rates as _load_rates
        from core.data_array import get_name_employee as _get_name
        # Одно чтение ставок за запуск: тот же dict идет в расчет и в предупреждения.
        rates = _load_rates()
        wages = calculate_wages(summary, rates=rates, employees=_STAFF)
    from core.data_array import get_name_employee
    if pay_bundle is None:
        zero_rate = [e for e in summary if rates.get(e, 0) == 0]
        for emp_id in zero_rate:
            print(f'ВНИМАНИЕ: {get_name_employee(emp_id, _STAFF) or emp_id} — ставка 0 '
                  f'(нет в wage_rates.dat или неверный ключ -k). Оклад будет нулевым, только молоко.')
    print_preview(build_preview_rows(summary, wages, employees=_STAFF, bundle=pay_bundle))

    print_header('Отчеты')
    build_excel(data_array, work_time, summary, wages, employees=_STAFF, bundle=pay_bundle)

    for emp_id in settlement_ids:
        if emp_id not in summary:
            print(f'Пропущен ID {emp_id}: нет данных расчета (роль не поддерживается?).')
            continue
        if pay_bundle is not None and emp_id not in pay_bundle.results:
            print(f'Пропущен ID {emp_id}: исключён новой моделью (см. сводку причин).')
            continue
        build_html(emp_id, data_array, work_time, summary, wages, employees=_STAFF, bundle=pay_bundle)

    print_salary_report(build_preview_rows(summary, wages, employees=_STAFF, bundle=pay_bundle),
                        title=f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — зарплата к начислению')

    print_journal(get_journal())
    remove_session()


if __name__ == '__main__':
    main()
