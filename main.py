import argparse
import sys
from os.path import exists

from core.config import load_config, set_secret_key
from core.file_parser import read_file_data
from core.data_array import build_data_array, get_all_employees_in_data, get_employees_with_marks, is_settlement_allowed
from core.analysis import analyze_for_print, analyze_for_edit
from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
from core.excel_builder import build_excel
from core.html_builder import build_html
from core.constants import MONTHS_NAME_TO_RUSSIAN
from core.session import load_session, session_exists, remove_session


def parse_secret_key(key_input: str) -> tuple[float, bool, str | None]:
    """Разобрать -k. Возвращает (secret, salary_mode, warning|None).

    salary_mode=False: режим без зарплаты (t/0/мусор) — оклад будет нулевым.
    """
    if key_input == 't' or key_input == '0':
        return 0.0, False, None
    if key_input.isdigit() and 2 < len(key_input) < 123:
        return float(key_input) / 100, True, None
    return 0.0, False, (
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
    parser.add_argument('--resume', action='store_true', help='Восстановить сохраненную сессию из temporary.pickle')
    parser.add_argument('--include-empty', action='store_true',
                        help='Включить в расчет сотрудников без единой отметки за месяц '
                             '(действующий, но отсутствовал весь месяц: отпуск/прогул)')
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
        first_date = list(data_array.keys())[0]
        year = int(first_date[:4])
        month = int(first_date[5:7])
        session_state = 'resumed'
    else:
        if not args.resume and session_exists():
            print(f'ВНИМАНИЕ: найден файл сессии. '
                  'Он будет проигнорирован. Используйте --resume для восстановления.')
            session_state = 'ignored'
        else:
            session_state = 'fresh'
        year = args.year or int(input('Введите год: '))
        month = args.month or int(input('Введите месяц: '))
        list_data = read_file_data(args.file, year, month)
        if not list_data:
            print('Нет данных для обработки!')
            sys.exit(1)
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
        year, month, rows_read, len(emp_ids), session_state,
    ))

    print_header('Проверка')
    for emp_id in emp_ids:
        if is_settlement_allowed(emp_id):
            analyze_for_print(data_array, emp_id, year, month)

    print_dashboard(
        build_dashboard_rows(data_array, get_all_employees_in_data(data_array), year, month),
        title=f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — сводка',
    )

    if not args.no_edit:
        print_header('Правки')
        for emp_id in emp_ids:
            if is_settlement_allowed(emp_id):
                analyze_for_edit(data_array, emp_id, year, month)

    for emp_id in emp_ids:
        if is_settlement_allowed(emp_id):
            analyze_for_print(data_array, emp_id, year, month)

    print_header('Расчет')
    work_time = calculate_hours_per_day(data_array)
    summary, restructured = calculate_hours_per_month(work_time)
    wages = calculate_wages(summary)
    from core.config import load_wage_rates
    from core.data_array import get_name_employee
    rates = load_wage_rates()
    zero_rate = [e for e in summary if rates.get(e, 0) == 0]
    for emp_id in zero_rate:
        print(f'ВНИМАНИЕ: {get_name_employee(emp_id) or emp_id} — ставка 0 '
              f'(нет в wage_rates.dat или неверный ключ -k). Оклад будет нулевым, только молоко.')
    print_preview(build_preview_rows(summary, wages))

    print_header('Отчеты')
    build_excel(data_array, work_time, summary, wages)

    for emp_id in emp_ids:
        if is_settlement_allowed(emp_id):
            if emp_id not in summary:
                print(f'Пропущен ID {emp_id}: нет данных расчета (роль не поддерживается?).')
                continue
            build_html(emp_id, data_array, work_time, summary, wages)

    print_salary_report(build_preview_rows(summary, wages),
                        title=f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — зарплата к начислению')

    print_journal(get_journal())
    remove_session()


if __name__ == '__main__':
    main()
