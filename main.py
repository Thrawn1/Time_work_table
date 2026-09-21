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
from core.day_models import TimeTable
from core.analysis import analyze_for_print, analyze_for_edit
from core.calculations import calculate_hours_per_day, calculate_hours_per_month
from core.payroll_service import calculate_payroll
from core.excel_builder import build_excel
from core.html_builder import build_html
from core.constants import MONTHS_NAME_TO_RUSSIAN
from core.session import (load_session, session_exists, remove_session,
                          backup_existing_session, set_session_dir, adopt_cwd_session,
                          preserve_session_paths)


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

    data_array, year, month, rows_read, session_state = _load_input(args, parser)

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

    print_start_screen(build_start_info(
        args.file if session_state != 'resumed' else '(сессия)',
        year, month, rows_read, len(settlement_ids), session_state,
        output_dir=args.output_dir, data_dir=args.data_dir,
    ))

    print_header('Проверка')
    from core.config import EMPLOYEES as _STAFF
    for emp_id in settlement_ids:
        analyze_for_print(data_array, emp_id, year, month, employees=_STAFF)

    print_dashboard(
        build_dashboard_rows(data_array, get_all_employees_in_data(data_array), year, month,
                             employees=_STAFF),
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
    summary, _ = calculate_hours_per_month(work_time)
    outcome = calculate_payroll(data_array, work_time, summary, year, month, pay_dir,
                                salary_mode=salary_mode, employees=_STAFF)
    wages, pay_bundle = outcome.wages, outcome.bundle
    for warning in outcome.warnings:
        print(f'ВНИМАНИЕ: {warning}')
    if pay_bundle is not None:
        from core.ui import print_pay_details
        print_pay_details(pay_bundle)
        versions_file = _join(args.output_dir, f'payroll_versions_{year}_{month:02d}.json')
        pay_bundle.save_versions(versions_file)
        print(f'Версии условий и календарь сохранены: {versions_file}')
    preview_rows = build_preview_rows(summary, wages, employees=_STAFF)
    print_preview(preview_rows)

    print_header('Отчеты')
    build_excel(data_array, work_time, summary, wages, employees=_STAFF, bundle=pay_bundle,
                output_dir=args.output_dir)

    for emp_id in settlement_ids:
        if emp_id not in summary:
            print(f'Пропущен ID {emp_id}: нет данных расчета (роль не поддерживается?).')
            continue
        build_html(emp_id, data_array, work_time, summary, wages, employees=_STAFF, bundle=pay_bundle,
                   output_dir=args.output_dir)

    print_salary_report(preview_rows,
                        title=f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — зарплата к начислению')

    print_journal(get_journal())
    remove_session()


def _load_input(args: Namespace, parser: ArgumentParser) -> tuple[TimeTable, int, int, int, str]:
    """Импорт либо восстановление: таблица, период, число строк и состояние сессии."""
    if args.resume:
        if not session_exists():
            parser.error('сохранённая сессия для --resume не найдена')
        data_array = load_session()
        if not data_array:
            print('Не удалось восстановить сессию (файл пуст или повреждён)!')
            sys.exit(1)
        first_date = next(iter(data_array))
        year, month = int(first_date[:4]), int(first_date[5:7])
        rows_read = sum(len(day) for day in data_array.values())
        return data_array, year, month, rows_read, 'resumed'

    year, month = resolve_period(args, parser)
    session_state = 'fresh'
    if session_exists():
        saved = backup_existing_session()
        if saved:
            print(f'ВНИМАНИЕ: найден файл сессии. '
                  f'Он сохранён отдельно как {saved} и будет проигнорирован. '
                  'Используйте --resume для восстановления.')
        else:
            print('ВНИМАНИЕ: найден файл сессии. '
                  'Он будет проигнорирован. Используйте --resume для восстановления.')
        session_state = 'ignored'

    list_data = read_file_data(args.file, year, month, args.data_dir)
    if list_data:
        data_array = build_data_array(list_data)
    elif args.include_empty and exists(_join(args.data_dir, args.file)):
        print('ВНИМАНИЕ: за выбранный месяц отметок нет — '
              'начинаем с пустой таблицы (--include-empty).')
        data_array = {}
    else:
        print('Нет данных для обработки!')
        sys.exit(1)
    return data_array, year, month, len(list_data), session_state


if __name__ == '__main__':
    main()
