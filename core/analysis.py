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


def group_consecutive_days(dates: list[str]) -> list[list[str]]:
    """Сгруппировать даты 'YYYY-MM-DD' в диапазоны подряд идущих дней.

    Разрыв через выходные (<=3 к.дн., напр. пт->пн) диапазон не разбивает:
    отпуск обычно накрывает и выходные между рабочими днями.
    """
    if not dates:
        return []
    ordered = sorted(dates)
    groups = [[ordered[0]]]
    for prev, cur in zip(ordered, ordered[1:]):
        d_prev = datetime.strptime(prev, '%Y-%m-%d')
        d_cur = datetime.strptime(cur, '%Y-%m-%d')
        if (d_cur - d_prev).days <= 3:
            groups[-1].append(cur)
        else:
            groups.append([cur])
    return groups


def format_range(days: list[str]) -> str:
    """'21.07–31.07 (9 раб. дн.)' или '21.07' для одиночного дня."""
    if len(days) == 1:
        return f'{days[0][8:10]}.{days[0][5:7]}'
    return (f'{days[0][8:10]}.{days[0][5:7]}–'
            f'{days[-1][8:10]}.{days[-1][5:7]} ({len(days)} раб. дн.)')


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
            for group in group_consecutive_days(list_missed):
                if len(group) == 1:
                    dt_obj = datetime.strptime(group[0], '%Y-%m-%d')
                    day_num = dt_obj.strftime('%d')
                    month_ru = format_datetime_russian(dt_obj, '%B')
                    weekday_ru = format_datetime_russian(dt_obj, '%A')
                    print(f'\t\t\t{day_num} {month_ru} | {weekday_ru}')
                else:
                    print(f'\t\t\t{format_range(group)}')
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
    from core import ui

    while True:
        raw = input(prompt + ' (формат "Ч М С", 0 — пропустить): ')
        if raw.strip().lower() in CANCEL_TOKENS or raw.strip() == '0':
            return None
        try:
            time_str, randomized = parse_and_fill(raw)
        except ValueError as e:
            if str(e) == '__CANCEL__':
                return None
            ui.error(f'Ошибка: {e} Попробуйте снова.')
            continue
        if randomized:
            names = {'M': 'минуты', 'S': 'секунды', 'H': 'часы'}
            what = ', '.join(names.get(k, k) for k in randomized)
            ui.warn(f'Внимание: {what} отсутствовали и дополнены случайно — проверьте итог.')
        return time_str, randomized


def _confirm_save(preview: str) -> bool:
    """Спросить подтверждение. True — сохранить, False — ввести заново."""
    from core import ui

    return ui.confirm_save(preview)


def _set_mark(time_table: dict, date_key: str, emp_id: int, marks: list) -> None:
    try:
        time_table[date_key][emp_id] = marks
    except KeyError:
        time_table[date_key] = {emp_id: marks}


_JOURNAL: list[dict] = []


def _marks_repr(marks: list) -> str:
    """Кратко: 'приход -> уход [тег]'."""
    try:
        return f'{marks[1].time()} -> {marks[0].time()} [{marks[2]}]'
    except (IndexError, AttributeError):
        return str(marks)


def record_edit(emp_id: int, date_key: str, action: str,
                before: list | None, after: list, randomized: bool = False) -> None:
    """Записать правку в журнал запуска."""
    role = EMPLOYEES.get(emp_id)
    name = f'{role.last_name} {role.first_name}'.strip() if role else f'ID {emp_id}'
    _JOURNAL.append({
        'ts': datetime.now().isoformat(timespec='seconds'),
        'emp_id': emp_id,
        'name': name,
        'date': date_key,
        'action': action,
        'before': _marks_repr(before) if before is not None else '—',
        'after': _marks_repr(after),
        'randomized': bool(randomized),
    })


def get_journal() -> list[dict]:
    """Копия журнала правок за запуск."""
    return list(_JOURNAL)


def clear_journal() -> None:
    """Очистить журнал (начало запуска / изоляция тестов)."""
    _JOURNAL.clear()


def _save_session(time_table: dict) -> None:
    from core.session import save_session
    save_session(time_table)


def analyze_for_edit(time_table: dict, emp_id: int, year: int, month: int) -> None:
    from sys import stderr
    from core import ui

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
            before_single = list(time_table[date_key][emp_id])
            ui.print_day_card_single(name, date_key, existing)
            while True:
                choice = ui.ask_menu('Выберете пункт меню:', ('1', '2'))
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
                        ui.error(f'Ошибка: неверное время ({e}). Введите снова.')
                        continue
                    come, go = (dt_write, existing) if choice == '1' else (existing, dt_write)
                    err = _validate_pair(come, go)
                    if err is not None:
                        ui.error(f'Ошибка: {err}. Не сохранено. Введите снова или 0 для пропуска.')
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
                        record_edit(emp_id, date_key, 'одиночная метка',
                                    before_single, list(time_table[date_key][emp_id]),
                                    randomized=bool(randomized))
                        ui.info(f'Ввод данных об отметки подтвержден! {dt_write}')
                        break
                    ui.info('Не подтверждено. Введите снова или 0 для пропуска.')
                    continue
    if list_missed != 0:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} не имеет данных за рабочий день!", file=stderr)
        skip_rest = False
        for group in group_consecutive_days(list_missed):
            if skip_rest:
                break
            label = format_range(group)
            multi = len(group) > 1
            ui.print_missed_day_card(name, label)
            if multi:
                ui.info(f'Диапазон {label}: время вводится один раз на все дни. '
                        '[4] разобрать по одному дню  [a] пропустить все оставшиеся')
                valid = ('1', '2', '3', '4', 'a')
            else:
                ui.info('[a] пропустить все оставшиеся')
                valid = ('1', '2', '3', 'a')
            while True:
                switch = ui.ask_menu('Введите пункт меню:', valid)
                if switch in ('0', 'q', 'отмена'):
                    break
                if switch == 'a':
                    skip_rest = True
                    break
                if switch == '4' and multi:
                    for day in group:
                        _edit_one_missed_day(time_table, emp_id, day)
                    break
                if switch == '1':
                    got_begin = _read_valid_time('Время прихода (одно на все дни диапазона)')
                    if got_begin is None:
                        break
                    got_end = _read_valid_time('Время ухода (одно на все дни диапазона)')
                    if got_end is None:
                        break
                    t_begin, rand_begin = got_begin
                    t_end, rand_end = got_end
                    try:
                        dt_b0 = datetime.strptime(f'{group[0]} {t_begin}', '%Y-%m-%d %H %M %S')
                        dt_e0 = datetime.strptime(f'{group[0]} {t_end}', '%Y-%m-%d %H %M %S')
                    except ValueError as e:
                        ui.error(f'Ошибка: неверное время ({e}). Введите заново.')
                        continue
                    err = _validate_pair(dt_b0, dt_e0)
                    if err is not None:
                        ui.error(f'Ошибка: {err}. Не сохранено. Введите заново или 0 для пропуска.')
                        continue
                    preview = (f'Выйдет за {label}: приход {dt_b0.time()} '
                               f'уход {dt_e0.time()} длительность {dt_e0 - dt_b0} '
                               f'x {len(group)} дн.')
                    randomized_fill = bool(rand_begin or rand_end)
                    if randomized_fill:
                        preview += ' (часть времени дополнена случайно — проверьте!)'
                    if _confirm_save(preview):
                        for day in group:
                            dt_begin = datetime.strptime(f'{day} {t_begin}', '%Y-%m-%d %H %M %S')
                            dt_end = datetime.strptime(f'{day} {t_end}', '%Y-%m-%d %H %M %S')
                            _set_mark(time_table, day, emp_id, [dt_end, dt_begin, 'work'])
                        _save_session(time_table)
                        ui.info(f'\nДанные за {label} введены\n')
                        record_edit(emp_id, label, f'рабочие дни x{len(group)}', None,
                                    [dt_e0, dt_b0, 'work'],
                                    randomized=randomized_fill)
                        break
                    ui.info('Не подтверждено. Введите заново или 0 для пропуска.')
                    continue
                elif switch == '2':
                    if _confirm_save(f'Отметить {label} как отпуск?'):
                        for day in group:
                            dt_vac = datetime.strptime(f'{day} 00 00 01', '%Y-%m-%d %H %M %S')
                            _set_mark(time_table, day, emp_id, [dt_vac, dt_vac, 'vacation'])
                        _save_session(time_table)
                        record_edit(emp_id, label, f'отпуск x{len(group)}', None,
                                    [dt_vac, dt_vac, 'vacation'])
                        break
                    continue
                elif switch == '3':
                    if _confirm_save(f'Отметить {label} как прогул?'):
                        for day in group:
                            dt_truancy = datetime.strptime(f'{day} 23 59 59', '%Y-%m-%d %H %M %S')
                            _set_mark(time_table, day, emp_id, [dt_truancy, dt_truancy, 'truancy'])
                        _save_session(time_table)
                        record_edit(emp_id, label, f'прогул x{len(group)}', None,
                                    [dt_truancy, dt_truancy, 'truancy'])
                        break
                    continue


def _edit_one_missed_day(time_table: dict, emp_id: int, day: str) -> str:
    """Разобрать один день диапазона. Возвращает 'done' | 'skip'."""
    from core import ui

    while True:
        sw = ui.ask_menu(f'{day}: [1] рабочий [2] отпуск [3] прогул [0] пропустить день:',
                         ('1', '2', '3'))
        if sw in ('0', 'q', 'отмена'):
            return 'skip'
        if sw == '1':
            got_begin = _read_valid_time('Время прихода')
            if got_begin is None:
                return 'skip'
            got_end = _read_valid_time('Время ухода')
            if got_end is None:
                return 'skip'
            t_begin, rand_begin = got_begin
            t_end, rand_end = got_end
            try:
                dt_begin = datetime.strptime(f'{day} {t_begin}', '%Y-%m-%d %H %M %S')
                dt_end = datetime.strptime(f'{day} {t_end}', '%Y-%m-%d %H %M %S')
            except ValueError as e:
                ui.error(f'Ошибка: неверное время ({e}). Введите день заново.')
                continue
            err = _validate_pair(dt_begin, dt_end)
            if err is not None:
                ui.error(f'Ошибка: {err}. Не сохранено. Введите день заново или 0 для пропуска.')
                continue
            preview = (f'Выйдет за {day}: приход {dt_begin.time()} '
                       f'уход {dt_end.time()} длительность {dt_end - dt_begin}.')
            randomized_fill = bool(rand_begin or rand_end)
            if randomized_fill:
                preview += ' (часть времени дополнена случайно — проверьте!)'
            if _confirm_save(preview):
                _set_mark(time_table, day, emp_id, [dt_end, dt_begin, 'work'])
                _save_session(time_table)
                record_edit(emp_id, day, 'заполнен день', None,
                            list(time_table[day][emp_id]),
                            randomized=randomized_fill)
                return 'done'
            ui.info('Не подтверждено. Введите день заново или 0 для пропуска.')
            continue
        elif sw == '2':
            if _confirm_save(f'Отметить {day} как отпуск?'):
                dt_vac = datetime.strptime(f'{day} 00 00 01', '%Y-%m-%d %H %M %S')
                _set_mark(time_table, day, emp_id, [dt_vac, dt_vac, 'vacation'])
                _save_session(time_table)
                record_edit(emp_id, day, 'отпуск', None,
                            list(time_table[day][emp_id]))
                return 'done'
            continue
        elif sw == '3':
            if _confirm_save(f'Отметить {day} как прогул?'):
                dt_truancy = datetime.strptime(f'{day} 23 59 59', '%Y-%m-%d %H %M %S')
                _set_mark(time_table, day, emp_id, [dt_truancy, dt_truancy, 'truancy'])
                _save_session(time_table)
                record_edit(emp_id, day, 'прогул', None,
                            list(time_table[day][emp_id]))
                return 'done'
            continue
