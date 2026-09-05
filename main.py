import argparse
import sys
from os.path import exists
from pickle import load, dump

from core.config import load_config, set_secret_key
from core.file_parser import read_file_data
from core.data_array import build_data_array, get_all_employees_in_data, is_settlement_allowed
from core.analysis import analyze_for_print, analyze_for_edit
from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
from core.excel_builder import build_excel
from core.html_builder import build_html, _build_total_data
from core.constants import MONTHS_NAME_TO_RUSSIAN


def main():
    parser = argparse.ArgumentParser(
        description='Система расчета заработной платы и учета рабочего времени'
    )
    parser.add_argument('-f', '--file', default='1_attlog.dat', help='Файл данных')
    parser.add_argument('-y', '--year', type=int, help='Год')
    parser.add_argument('-m', '--month', type=int, help='Месяц (1-12)')
    parser.add_argument('-k', '--key', default='0', help='Секретный ключ (или t для без зарплаты)')
    parser.add_argument('--no-edit', action='store_true', help='Пропустить интерактивное редактирование')
    args = parser.parse_args()

    load_config()

    print('\n\t\tСистема расчета заработной платы и учета рабочего времени работников\n')
    key_input = args.key
    if key_input == 't' or key_input == '0':
        secret_key = 0.0
    elif key_input.isdigit() and 2 < len(key_input) < 123:
        secret_key = float(key_input) / 100
    else:
        secret_key = 0.0

    set_secret_key(secret_key)

    pickle_path = 'temporary.pickle'
    if exists(pickle_path):
        with open(pickle_path, 'rb') as f:
            data_array = load(f)
        first_date = list(data_array.keys())[0]
        year = int(first_date[:4])
        month = int(first_date[5:7])
    else:
        year = args.year or int(input('Введите год: '))
        month = args.month or int(input('Введите месяц: '))
        list_data = read_file_data(args.file, year, month)
        if not list_data:
            print('Нет данных для обработки!')
            sys.exit(1)
        data_array = build_data_array(list_data)

    print(f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} год')

    emp_ids = get_all_employees_in_data(data_array)

    for emp_id in emp_ids:
        if is_settlement_allowed(emp_id):
            analyze_for_print(data_array, emp_id, year, month)

    if not args.no_edit:
        for emp_id in emp_ids:
            if is_settlement_allowed(emp_id):
                analyze_for_edit(data_array, emp_id, year, month)

    for emp_id in emp_ids:
        if is_settlement_allowed(emp_id):
            analyze_for_print(data_array, emp_id, year, month)

    work_time = calculate_hours_per_day(data_array)
    summary, restructured = calculate_hours_per_month(work_time)
    wages = calculate_wages(summary, secret_key)
    build_excel(data_array, work_time, summary, wages)

    for emp_id in emp_ids:
        if is_settlement_allowed(emp_id):
            build_html(emp_id, data_array, work_time, summary, wages)

    for emp_id in emp_ids:
        if is_settlement_allowed(emp_id):
            td = _build_total_data(emp_id, summary, wages)
            print('--------------------------------------------------------------------------------------------------------------------------------------------')
            print(f'\nФамилия работника:  {td["family"]}')
            print('\n\t\t ВСЕГО ЗА МЕСЯЦ:\n')
            print(f'\n\t\tБудние рабочие дни за месяц: {td["all_work_weekdays"]}')
            print('\t\t\t--------------------------')
            print(f'\n\t\tПереработки за будние рабочие дни в месяце: {td["weekdays_overtime"]}')
            print('\t\t\t--------------------------')
            print(f'\n\t\tРабочие выходные дни за месяц: {td["work_weekend"]}')
            print('\t\t\t--------------------------')
            print(f'\n\t\tПереработки за рабочие выходные дни в месяце: {td["overtime_weekend"]}')
            print('\t\t\t--------------------------')
            print(f'\n\t\tКоличество дней отпуска: {td["vacation"]}')
            print('\t\t\t--------------------------')
            print(f'\n\t\tЗарплата (учитывая молоко, но без премий): {td["salary_whith_milk"]}')
            print('\t\t\t--------------------------')

    try:
        import os
        os.remove(pickle_path)
    except (FileNotFoundError, OSError):
        pass


if __name__ == '__main__':
    main()
