from datetime import datetime, timedelta
from calendar import monthrange
from core.config import EMPLOYEES
from core.constants import WEEKDAYS_NAME, MONTHS_NAME_GENITIVE, MONTHS_NAME_TO_RUSSIAN
from core.file_parser import definition_of_working_day


def generation_of_lists_of_days(year: int, month: int) -> list[list[str]]:
    last_day = monthrange(year, month)[1]
    work_days: list[str] = []
    non_work_days: list[str] = []
    for day in range(1, last_day + 1):
        day_str = f'{day:02d}'
        month_str = f'{month:02d}'
        date_str = f'{year}-{month_str}-{day_str}'
        tag, _ = definition_of_working_day(date_str)
        if tag == 'work':
            work_days.append(date_str)
        else:
            non_work_days.append(date_str)
    return [work_days, non_work_days]


def search_missed_work_days(time_table: dict, emp_id: int, year: int, month: int) -> list[str] | int:
    month_days = generation_of_lists_of_days(year, month)
    employee_dates = [d for d in time_table if emp_id in time_table[d]]
    if not employee_dates:
        return 0
    missed = [d for d in month_days[0] if d not in employee_dates]
    return missed if missed else 0


def search_missed_marks(time_table: dict, emp_id: int, year: int, month: int) -> list[list] | int:
    result: list[list] = []
    last_day = monthrange(year, month)[1]
    first = datetime(year, month, 1)
    last = datetime(year, month, last_day)
    current = first
    while current <= last:
        date_str = current.strftime('%Y-%m-%d')
        if date_str in time_table and emp_id in time_table[date_str]:
            cell = time_table[date_str][emp_id]
            if cell[0] == cell[1] and cell[2] in ('work', 'weekend'):
                result.append([date_str, cell[1]])
        current += timedelta(days=1)
    return result if result else 0


def format_datetime_russian(dt_obj: datetime, fmt: str) -> str:
    eng_name = dt_obj.strftime(fmt)
    if fmt == '%B':
        return MONTHS_NAME_GENITIVE.get(dt_obj.month, eng_name)
    if fmt == '%A':
        return WEEKDAYS_NAME.get(dt_obj.weekday(), eng_name)
    return eng_name


def analyze_for_print(time_table: dict, emp_id: int, year: int, month: int) -> None:
    from core.config import EMPLOYEES
    role = EMPLOYEES.get(emp_id)
    if role is None:
        return
    if role.role_id in (1, 4):
        list_marks = search_missed_marks(time_table, emp_id, year, month)
        list_missed = search_missed_work_days(time_table, emp_id, year, month)
    elif role.role_id == 3:
        list_marks = 0
        list_missed = search_missed_work_days(time_table, emp_id, year, month)
    else:
        list_marks = 0
        list_missed = 0
    name = f'{role.last_name} {role.first_name}'.strip()
    if list_marks != 0 or list_missed != 0:
        print('--------------------------------------------------------------------------------------------------------------------------------------------')
        print(f'\nФамилия работника:  {name}')
        if list_marks != 0:
            print('\n\t\tЕсть только одна метка:\n')
            print('\t\t\t--------------------')
            for mark in list_marks:
                mark_dt = mark[1]
                day_num = mark_dt.strftime('%d')
                month_ru = format_datetime_russian(mark_dt, '%B')
                weekday_ru = format_datetime_russian(mark_dt, '%A')
                time_str = mark_dt.strftime('%H:%M:%S')
                print(f'\t\t\t{day_num} {month_ru} | {time_str} | {weekday_ru}')
                print('\t\t\t---------------------')
        if list_missed != 0:
            print('\n\n\n\t\tДаты рабочих дней, где нет отметок:\n')
            print('\t\t\t------------------')
            for missed_day in list_missed:
                dt_obj = datetime.strptime(missed_day, '%Y-%m-%d')
                day_num = dt_obj.strftime('%d')
                month_ru = format_datetime_russian(dt_obj, '%B')
                weekday_ru = format_datetime_russian(dt_obj, '%A')
                print(f'\t\t\t{day_num} {month_ru} | {weekday_ru}')
                print('\t\t\t------------------')


def analyze_for_edit(time_table: dict, emp_id: int, year: int, month: int) -> None:
    from randomazer_time_value import time_data_generation
    from pickle import dump
    from sys import stderr

    from core.config import EMPLOYEES
    role = EMPLOYEES.get(emp_id)
    if role is None:
        return
    if role.role_id in (1, 4):
        list_marks = search_missed_marks(time_table, emp_id, year, month)
        list_missed = search_missed_work_days(time_table, emp_id, year, month)
    elif role.role_id == 3:
        list_marks = 0
        list_missed = search_missed_work_days(time_table, emp_id, year, month)
    else:
        list_marks = 0
        list_missed = 0
    name = f'{role.last_name} {role.first_name}'.strip()
    if list_marks != 0:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} имеет только одну отметку в рабочем дне!", file=stderr)
        for cell in list_marks:
            date_key = cell[0]
            print('Дата и время отметки, сохраненной в системе:', time_table[date_key][emp_id][0])
            print('\n\n\tВыберете, какой вариант отметки будет введен:\n\n\t1.Отметка прихода\n\t2.Отметка ухода')
            while True:
                choice = input('Выберете пункт меню:')
                if choice in ('1', '2'):
                    entered = input('Введите время в формате час*ПРОБЕЛ*минуты*ПРОБЕЛ*секунды(если есть) --- 00 00 00:  ')
                    entered_time = time_data_generation(entered)
                    dt_write = datetime.strptime(f'{date_key} {entered_time}', '%Y-%m-%d %H %M %S')
                    if choice == '1':
                        time_table[date_key][emp_id][1] = dt_write
                    else:
                        time_table[date_key][emp_id][0] = dt_write
                    with open('temporary.pickle', 'wb') as f:
                        dump(time_table, f)
                    print('Ввод данных об отметки подтвержден!', dt_write)
                    break
    if list_missed != 0:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} не имеет данных за рабочий день!", file=stderr)
        for missed_day in list_missed:
            print('Дата без отметок:', missed_day)
            print('Введите данные за день\n\n\t1.Рабочий день. Ввести отметку прихода и отметку ухода\n\t2.Отпускной день\n\t3.Прогул\n')
            while True:
                switch = input('Введите пункт меню:')
                if switch == '1':
                    print('Время прихода:\n')
                    t_begin = time_data_generation(input('Введите время: '))
                    dt_begin = datetime.strptime(f'{missed_day} {t_begin}', '%Y-%m-%d %H %M %S')
                    print('Время ухода:\n')
                    t_end = time_data_generation(input('Введите время: '))
                    dt_end = datetime.strptime(f'{missed_day} {t_end}', '%Y-%m-%d %H %M %S')
                    print('\nДанные за день введены\n')
                    try:
                        time_table[missed_day][emp_id] = [dt_end, dt_begin, 'work']
                    except KeyError:
                        time_table[missed_day] = {}
                        time_table[missed_day][emp_id] = [dt_end, dt_begin, 'work']
                    with open('temporary.pickle', 'wb') as f:
                        dump(time_table, f)
                    break
                elif switch == '2':
                    dt_vac = datetime.strptime(f'{missed_day} 00 00 01', '%Y-%m-%d %H %M %S')
                    try:
                        time_table[missed_day][emp_id] = [dt_vac, dt_vac, 'vacation']
                    except KeyError:
                        time_table[missed_day] = {}
                        time_table[missed_day][emp_id] = [dt_vac, dt_vac, 'vacation']
                    with open('temporary.pickle', 'wb') as f:
                        dump(time_table, f)
                    break
                elif switch == '3':
                    dt_truancy = datetime.strptime(f'{missed_day} 23 59 59', '%Y-%m-%d %H %M %S')
                    try:
                        time_table[missed_day][emp_id] = [dt_truancy, dt_truancy, 'truancy']
                    except KeyError:
                        time_table[missed_day] = {}
                        time_table[missed_day][emp_id] = [dt_truancy, dt_truancy, 'truancy']
                    with open('temporary.pickle', 'wb') as f:
                        dump(time_table, f)
                    break
                else:
                    print('Введите правильный пункт меню!')
