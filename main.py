import os
import sys
from argparse import ArgumentParser, Namespace
from os.path import exists, join as _join

from core.cli import build_parser, resolve_period, resolve_secret_key
from core.cli import parse_secret_key as parse_secret_key  # совместимость прежнего API main
from core.config import load_config, preserve_config, set_secret_key, set_data_dir, set_secret_file
from core.file_parser import read_file_data
from core.data_array import (
    build_data_array, get_all_employees_in_data, get_employees_with_marks, is_included_in_settlement,
)
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
    set_session_dir,
    adopt_cwd_session,
    preserve_session_paths,
)


def main(argv: list[str] | None = None) -> None:
    """Точка входа; каждый запуск изолирован от предыдущих вызовов в процессе."""
    parser = build_parser()
    args = parser.parse_args(argv)
    with preserve_config(), preserve_session_paths():
        _run(args, parser)


def _run(args: Namespace, parser: ArgumentParser) -> None:
    os.makedirs(args.output_dir, exist_ok=True)
    set_data_dir(args.data_dir)
    set_session_dir(args.output_dir)
    set_secret_file(_join(args.output_dir, '_secret_key.tmp'))
    adopted = adopt_cwd_session()
    if adopted:
        print(f'Сессия перенесена из текущего каталога в {adopted} '
              f'(теперь сессии живут в --output-dir).')
    pay_dir = args.pay_dir or _join(args.data_dir, 'pay_directory.db')

    load_config()

    print('\n\t\tСистема расчета заработной платы и учета рабочего времени работников\n')
    secret_key, salary_mode = resolve_secret_key(args)

    set_secret_key(secret_key)
    if salary_mode:
        print('Режим: расчет зарплаты (ключ принят).')
    else:
        print('Режим: учет времени БЕЗ зарплаты (оклад = 0, молоко считается).')

    from core.analysis import clear_journal
    clear_journal()

    list_data: list[str] = []
    if args.resume:
        if not session_exists():
            parser.error('сохранённая сессия для --resume не найдена')
        data_array = load_session()
        if data_array is None:
            print('Не удалось восстановить сессию!')
            sys.exit(1)
        if not data_array:
            # Пустой месяц, восстановленный по периоду из заголовка сессии.
            from core.session import SESSION_FILE, _peek_period as _peek_resume_period
            _period = _peek_resume_period(SESSION_FILE) if exists(SESSION_FILE) else None
            if _period is None:
                print('Не удалось восстановить сессию: пустая сессия без периода!')
                sys.exit(1)
            year, month = _period
        else:
            first_date = next(iter(data_array))
            year, month = int(first_date[:4]), int(first_date[5:7])
        session_state = 'resumed'
    else:
        year, month = resolve_period(args, parser)
        session_state = 'fresh'
        if session_exists():
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
        list_data = read_file_data(args.file, year, month, args.data_dir)
        if not list_data:
            _missing = not exists(_join(args.data_dir, args.file))
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

    # Этап 3 (+F02-union): единый контекст периода — до анализа и правок (F01/F02/F05).
    from core.config import EMPLOYEES as _DAT_STAFF
    from core.payroll import PayrollError as _PayrollError
    from core.pay_context import (
        combined_staff_for_import as _combined_staff,
        diagnose_roster_divergence as _diagnose_roster,
        resolve_context as _resolve_context,
        sqlite_excluded_map as _sqlite_excluded,
    )
    try:
        pay_ctx = _resolve_context(pay_dir, year, month, salary_mode)
    except _PayrollError as e:
        print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
        sys.exit(1)
    sqlite_excluded: dict = {}
    if pay_ctx.mode == 'new':
        print('Режим модели: новая (SQLite-условия действуют на месяц). Ошибки настройки фатальны.')
        try:
            active_staff = _combined_staff(_DAT_STAFF, pay_dir, pay_ctx.month_start)
        except _PayrollError as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        # Импорт на объединённом штате: SQLite-only отметки не отбрасываются (F02).
        if session_state != 'resumed' and list_data:
            data_array = build_data_array(list_data, employees=active_staff)
        try:
            sqlite_excluded = _sqlite_excluded(pay_dir, pay_ctx.month_start)
        except _PayrollError as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        for w in _diagnose_roster(pay_ctx, _DAT_STAFF, data_array):
            print(f'ВНИМАНИЕ (состав): {w}')
        if args.include_empty:
            emp_ids = list(active_staff.keys())
        else:
            _with_marks = {e for day in data_array.values() for e in day}
            emp_ids = [e for e in active_staff if e in _with_marks]
            _skipped = len(active_staff) - len(emp_ids)
            if _skipped:
                print(f'Без отметок за месяц пропущено сотрудников: {_skipped} '
                      f'(см. второй блок сводки; для включения — --include-empty).')
        # Единый состав: DAT-правила на объединённом штате + SQLite-исключения.
        settlement_ids = [e for e in emp_ids
                          if is_included_in_settlement(e, active_staff)
                          and e not in sqlite_excluded]
    else:
        print('Режим модели: legacy (действующих SQLite-условий на месяц нет).')
        active_staff = _DAT_STAFF
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
    if pay_ctx.mode == 'new':
        # До правок: отсутствие обязательного назначения — фатально, без silent fallback.
        from core.pay_store import connect as _connect, get_assignment as _get_assign
        try:
            _con = _connect(pay_dir)
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
            _names = ', '.join(f'{_nm(e, active_staff) or e}' for e in _missing)
            print(f'ОШИБКА: новая модель должна применяться, но нет назначения SQLite '
                  f'на {pay_ctx.month_start} для: {_names}. Расчет прерван без fallback.')
            sys.exit(1)

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
        output_dir=args.output_dir, data_dir=args.data_dir,
    ))

    print_header('Проверка')
    _STAFF = active_staff
    for emp_id in settlement_ids:
        analyze_for_print(data_array, emp_id, year, month, employees=_STAFF)

    _dashboard_ids = (list(active_staff.keys()) if pay_ctx.mode == 'new'
                      else get_all_employees_in_data(data_array))
    print_dashboard(
        build_dashboard_rows(data_array, _dashboard_ids, year, month,
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
    summary, _restructured = calculate_hours_per_month(work_time)
    # Режим уже выбран до правок (pay_ctx): new — обязателен и фатален
    # при ошибках настройки, legacy — старый адаптер. Silent fallback запрещён (F05).
    from core.payroll import PayrollError, build_bundle, bundle_to_wages
    pay_bundle = None
    if pay_ctx.mode == 'new':
        try:
            pay_bundle = build_bundle(data_array, work_time, summary, year, month,
                                      pay_dir, salary_mode=salary_mode,
                                      employees=active_staff)
        except PayrollError as e:
            print(f'ОШИБКА: новая модель должна применяться, но настройка ошибочна ({e}). '
                  f'Расчет прерван без fallback в legacy.')
            sys.exit(1)
    rates: dict = {}
    if pay_bundle is not None:
        wages = bundle_to_wages(pay_bundle)
        from core.ui import print_pay_details
        print_pay_details(pay_bundle)
        versions_file = _join(args.output_dir, f'payroll_versions_{year}_{month:02d}.json')
        pay_bundle.save_versions(versions_file)
        print(f'Версии условий и календарь сохранены: {versions_file}')
    elif salary_mode:
        from core.config import load_wage_rates as _load_rates
        # Одно чтение ставок за запуск: тот же dict идет в расчет и в предупреждения.
        rates = _load_rates()
        wages = calculate_wages(summary, rates=rates, employees=_STAFF)
    else:
        # Учёт времени без зарплаты: ставки не нужны, wage_rates.dat может отсутствовать.
        wages = calculate_wages(summary, rates=rates, employees=_STAFF)
    from core.data_array import get_name_employee
    if pay_bundle is None and salary_mode:
        zero_rate = [e for e in summary if rates.get(e, 0) == 0]
        for emp_id in zero_rate:
            print(f'ВНИМАНИЕ: {get_name_employee(emp_id, _STAFF) or emp_id} — ставка 0 '
                  f'(нет в wage_rates.dat или неверный ключ -k). Оклад будет нулевым, только молоко.')
    preview_rows = build_preview_rows(summary, wages, employees=_STAFF, bundle=pay_bundle)
    print_preview(preview_rows)

    print_header('Отчеты')
    build_excel(data_array, work_time, summary, wages, employees=_STAFF, bundle=pay_bundle,
                output_dir=args.output_dir)

    for emp_id in settlement_ids:
        if emp_id not in summary:
            print(f'Пропущен ID {emp_id}: нет данных расчета (роль не поддерживается?).')
            continue
        if pay_bundle is not None and emp_id not in pay_bundle.results:
            print(f'Пропущен ID {emp_id}: исключён новой моделью (см. сводку причин).')
            continue
        build_html(emp_id, data_array, work_time, summary, wages, employees=_STAFF, bundle=pay_bundle,
                   output_dir=args.output_dir)

    print_salary_report(preview_rows,
                        title=f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — зарплата к начислению')

    print_journal(get_journal())
    remove_session()


if __name__ == '__main__':
    main()
