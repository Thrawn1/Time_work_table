from datetime import datetime, timedelta
from calendar import monthrange
from core.config import EMPLOYEES
from core.constants import WEEKDAYS_NAME, MONTHS_NAME_GENITIVE, MONTHS_NAME_TO_RUSSIAN
from core.file_parser import definition_of_working_day


def _get_marks_and_missed(time_table: dict, emp_id: int, year: int, month: int) -> tuple:
    role = EMPLOYEES.get(emp_id)
    if role is None:
        return 0, 0
    if role.role_id in (1, 4):
        return search_missed_marks(time_table, emp_id, year, month), search_missed_work_days(time_table, emp_id, year, month)
    if role.role_id == 3:
        return 0, search_missed_work_days(time_table, emp_id, year, month)
    return 0, 0


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
    if emp_id not in EMPLOYEES:
        return 0
    month_days = generation_of_lists_of_days(year, month)
    employee_dates = [d for d in time_table if emp_id in time_table[d]]
    if not employee_dates:
        return month_days[0] if month_days[0] else 0
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
            if cell[0] == cell[1] and cell[2] in ('work', 'weekend', 'holiday'):
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
    role = EMPLOYEES.get(emp_id)
    if role is None:
        return
    list_marks, list_missed = _get_marks_and_missed(time_table, emp_id, year, month)
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


def _validate_pair(come: datetime, go: datetime) -> str | None:
    """Проверить пару приход/уход. Вернуть текст ошибки или None если ок."""
    if come == go:
        return 'отметки совпадают — смена осталась незавершенной'
    if come > go:
        return f'приход {come.time()} позже ухода {go.time()} — так нельзя'
    if (go - come) <= timedelta(0):
        return 'нулевая или отрицательная длительность смены'
    return None


def _read_valid_time(prompt: str) -> tuple[str, list] | None:
    """Запросить время до валидного ввода. None — пользователь отменил (0)."""
    from randomazer_time_value import parse_and_fill, CANCEL_TOKENS

    while True:
        raw = input(prompt + ' (формат "Ч М С", 0 — пропустить): ')
        if raw.strip().lower() in CANCEL_TOKENS or raw.strip() == '0':
            return None
        try:
            time_str, randomized = parse_and_fill(raw)
        except ValueError as e:
            if str(e) == '__CANCEL__':
                return None
            print(f'Ошибка: {e} Попробуйте снова.')
            continue
        if randomized:
            names = {'M': 'минуты', 'S': 'секунды', 'H': 'часы'}
            what = ', '.join(names.get(k, k) for k in randomized)
            print(f'Внимание: {what} отсутствовали и дополнены случайно — проверьте итог.')
        return time_str, randomized


def _confirm_save(preview: str) -> bool:
    """Спросить подтверждение. True — сохранить, False — ввести заново."""
    while True:
        ans = input(f'{preview}\nПодтвердить? [д/н]: ').strip().lower()
        if ans in ('д', 'y', 'да', 'yes', '1'):
            return True
        if ans in ('н', 'n', 'нет', 'no', '0'):
            return False
        print('Введите "д" или "н".')


def _set_mark(time_table: dict, date_key: str, emp_id: int, marks: list) -> None:
    try:
        time_table[date_key][emp_id] = marks
    except KeyError:
        time_table[date_key] = {emp_id: marks}


def _save_session(time_table: dict) -> None:
    from core.session import save_session
    save_session(time_table)


def analyze_for_edit(time_table: dict, emp_id: int, year: int, month: int) -> None:
    from sys import stderr

    role = EMPLOYEES.get(emp_id)
    if role is None:
        return
    list_marks, list_missed = _get_marks_and_missed(time_table, emp_id, year, month)
    name = f'{role.last_name} {role.first_name}'.strip()
    if list_marks != 0:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} имеет только одну отметку в рабочем дне!", file=stderr)
        for cell in list_marks:
            date_key = cell[0]
            existing = time_table[date_key][emp_id][0]
            print('Дата и время отметки, сохраненной в системе:', existing)
            print('\n\n\tВыберете, какой вариант отметки будет введен:\n\n\t1.Отметка прихода\n\t2.Отметка ухода\n\t0.Пропустить')
            while True:
                choice = input('Выберете пункт меню:').strip()
                if choice in ('0', 'q', 'отмена'):
                    break
                if choice in ('1', '2'):
                    got = _read_valid_time('Введите время')
                    if got is None:
                        break  # пропуск этого дня
                    entered_time, randomized = got
                    try:
                        dt_write = datetime.strptime(f'{date_key} {entered_time}', '%Y-%m-%d %H %M %S')
                    except ValueError as e:
                        print(f'Ошибка: неверное время ({e}). Введите снова.')
                        continue
                    come, go = (dt_write, existing) if choice == '1' else (existing, dt_write)
                    err = _validate_pair(come, go)
                    if err is not None:
                        print(f'Ошибка: {err}. Не сохранено. Введите снова или 0 для пропуска.')
                        continue
                    preview = (f'Выйдет: приход {come.time()} уход {go.time()} '
                               f'длительность {go - come}.')
                    if randomized:
                        preview += ' (часть времени дополнена случайно — проверьте!)'
                    if _confirm_save(preview):
                        if choice == '1':
                            time_table[date_key][emp_id][1] = dt_write
                        else:
                            time_table[date_key][emp_id][0] = dt_write
                        _save_session(time_table)
                        print('Ввод данных об отметки подтвержден!', dt_write)
                        break
                    print('Не подтверждено. Введите снова или 0 для пропуска.')
                    continue
                print('Введите 1, 2 или 0.')
    if list_missed != 0:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} не имеет данных за рабочий день!", file=stderr)
        for missed_day in list_missed:
            print('Дата без отметок:', missed_day)
            print('Введите данные за день\n\n\t1.Рабочий день. Ввести отметку прихода и отметку ухода\n\t2.Отпускной день\n\t3.Прогул\n\t0.Пропустить день\n')
            while True:
                switch = input('Введите пункт меню:').strip()
                if switch in ('0', 'q', 'отмена'):
                    break
                if switch == '1':
                    got_begin = _read_valid_time('Время прихода')
                    if got_begin is None:
                        break
                    got_end = _read_valid_time('Время ухода')
                    if got_end is None:
                        break
                    t_begin, rand_begin = got_begin
                    t_end, rand_end = got_end
                    try:
                        dt_begin = datetime.strptime(f'{missed_day} {t_begin}', '%Y-%m-%d %H %M %S')
                        dt_end = datetime.strptime(f'{missed_day} {t_end}', '%Y-%m-%d %H %M %S')
                    except ValueError as e:
                        print(f'Ошибка: неверное время ({e}). Введите день заново.')
                        continue
                    err = _validate_pair(dt_begin, dt_end)
                    if err is not None:
                        print(f'Ошибка: {err}. Не сохранено. Введите день заново или 0 для пропуска.')
                        continue
                    preview = (f'Выйдет за {missed_day}: приход {dt_begin.time()} '
                               f'уход {dt_end.time()} длительность {dt_end - dt_begin}.')
                    if rand_begin[1] or rand_end[1]:
                        preview += ' (часть времени дополнена случайно — проверьте!)'
                    if _confirm_save(preview):
                        print('\nДанные за день введены\n')
                        _set_mark(time_table, missed_day, emp_id, [dt_end, dt_begin, 'work'])
                        _save_session(time_table)
                        break
                    print('Не подтверждено. Введите день заново или 0 для пропуска.')
                    continue
                elif switch == '2':
                    if _confirm_save(f'Отметить {missed_day} как отпуск?'):
                        dt_vac = datetime.strptime(f'{missed_day} 00 00 01', '%Y-%m-%d %H %M %S')
                        _set_mark(time_table, missed_day, emp_id, [dt_vac, dt_vac, 'vacation'])
                        _save_session(time_table)
                        break
                    continue
                elif switch == '3':
                    if _confirm_save(f'Отметить {missed_day} как прогул?'):
                        dt_truancy = datetime.strptime(f'{missed_day} 23 59 59', '%Y-%m-%d %H %M %S')
                        _set_mark(time_table, missed_day, emp_id, [dt_truancy, dt_truancy, 'truancy'])
                        _save_session(time_table)
                        break
                    continue
                else:
                    print('Введите правильный пункт меню!')
