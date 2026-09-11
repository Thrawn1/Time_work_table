from datetime import datetime, timedelta
from calendar import monthrange
from core.config import EMPLOYEES
from core.constants import WEEKDAYS_NAME, MONTHS_NAME_GENITIVE, MONTHS_NAME_TO_RUSSIAN
from core.file_parser import definition_of_working_day


def _get_marks_and_missed(time_table: dict, emp_id: int, year: int, month: int) -> tuple:
    from core.roles import TIME_ACTUAL, get_default_rule

    role = EMPLOYEES.get(emp_id)
    if role is None:
        return 0, 0
    try:
        rule = get_default_rule(role.role_id)
    except KeyError:
        return 0, 0
    if not rule.participates:
        return 0, 0
    if rule.time_mode == TIME_ACTUAL and rule.check_single_mark:
        return search_missed_marks(time_table, emp_id, year, month), search_missed_work_days(time_table, emp_id, year, month)
    return 0, search_missed_work_days(time_table, emp_id, year, month)


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


def _dt(day: str, t: str) -> datetime:
    """'2026-07-21' + '08 00 00' -> datetime. Бросает ValueError."""
    return datetime.strptime(f'{day} {t}', '%Y-%m-%d %H %M %S')


def _dt_vac(day: str) -> datetime:
    return _dt(day, '00 00 01')


def _dt_truancy(day: str) -> datetime:
    return _dt(day, '23 59 59')


def _read_work_times(suffix: str = '') -> tuple[str, str, bool] | None:
    """Спросить приход/уход один раз. None — отмена."""
    got_begin = _read_valid_time(f'Время прихода{suffix}')
    if got_begin is None:
        return None
    got_end = _read_valid_time(f'Время ухода{suffix}')
    if got_end is None:
        return None
    (t_begin, rand_begin), (t_end, rand_end) = got_begin, got_end
    return t_begin, t_end, bool(rand_begin or rand_end)


def _apply_work_days(time_table: dict, emp_id: int, days: list[str],
                     t_begin: str, t_end: str, randomized: bool,
                     action: str, date_ref: str) -> bool:
    """Проверить, подтвердить и записать рабочие дни. True — записано."""
    from core import ui

    try:
        dt_b0, dt_e0 = _dt(days[0], t_begin), _dt(days[0], t_end)
    except ValueError as e:
        ui.error(f'Ошибка: неверное время ({e}). Введите заново.')
        return False
    err = _validate_pair(dt_b0, dt_e0)
    if err is not None:
        ui.error(f'Ошибка: {err}. Не сохранено. Введите заново или 0 для пропуска.')
        return False
    count = f' x {len(days)} дн.' if len(days) > 1 else '.'
    preview = (f'Выйдет за {date_ref}: приход {dt_b0.time()} уход {dt_e0.time()} '
               f'длительность {dt_e0 - dt_b0}{count}')
    if randomized:
        preview += ' (часть времени дополнена случайно — проверьте!)'
    if not _confirm_save(preview):
        ui.info('Не подтверждено. Введите заново или 0 для пропуска.')
        return False
    for day in days:
        _set_mark(time_table, day, emp_id, [_dt(day, t_end), _dt(day, t_begin), 'work'])
    _save_session(time_table)
    ui.info(f'\nДанные за {date_ref} введены\n')
    record_edit(emp_id, date_ref, action, None, [dt_e0, dt_b0, 'work'], randomized=randomized)
    return True


def _apply_status_days(time_table: dict, emp_id: int, days: list[str], tag: str,
                       action: str, date_ref: str, confirm_q: str) -> bool:
    """Одно подтверждение на все дни. tag: 'vacation' | 'truancy'."""
    if not _confirm_save(confirm_q):
        return False
    mark_of = _dt_vac if tag == 'vacation' else _dt_truancy
    for day in days:
        mark = mark_of(day)
        _set_mark(time_table, day, emp_id, [mark, mark, tag])
    _save_session(time_table)
    mark0 = mark_of(days[0])
    record_edit(emp_id, date_ref, action, None, [mark0, mark0, tag])
    return True


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
                        dt_write = _dt(date_key, entered_time)
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
                match ui.ask_menu('Введите пункт меню:', valid):
                    case '0' | 'q' | 'отмена':
                        break
                    case 'a':
                        skip_rest = True
                        break
                    case '4' if multi:
                        for day in group:
                            _edit_one_missed_day(time_table, emp_id, day)
                        break
                    case '1':
                        got = _read_work_times(' (одно на все дни диапазона)' if multi else '')
                        if got is None:
                            break
                        t_begin, t_end, randomized = got
                        date_ref = label if multi else group[0]
                        if _apply_work_days(time_table, emp_id, group, t_begin, t_end,
                                            randomized, f'рабочие дни x{len(group)}', date_ref):
                            break
                    case '2':
                        date_ref = label if multi else group[0]
                        if _apply_status_days(time_table, emp_id, group, 'vacation',
                                              f'отпуск x{len(group)}', date_ref,
                                              f'Отметить {date_ref} как отпуск?'):
                            break
                    case '3':
                        date_ref = label if multi else group[0]
                        if _apply_status_days(time_table, emp_id, group, 'truancy',
                                              f'прогул x{len(group)}', date_ref,
                                              f'Отметить {date_ref} как прогул?'):
                            break


def _edit_one_missed_day(time_table: dict, emp_id: int, day: str) -> str:
    """Разобрать один день диапазона. Возвращает 'done' | 'skip'."""
    from core import ui

    while True:
        match ui.ask_menu(f'{day}: [1] рабочий [2] отпуск [3] прогул [0] пропустить день:',
                          ('1', '2', '3')):
            case '0' | 'q' | 'отмена':
                return 'skip'
            case '1':
                got = _read_work_times()
                if got is None:
                    return 'skip'
                t_begin, t_end, randomized = got
                if _apply_work_days(time_table, emp_id, [day], t_begin, t_end,
                                    randomized, 'заполнен день', day):
                    return 'done'
            case '2':
                if _apply_status_days(time_table, emp_id, [day], 'vacation',
                                      'отпуск', day, f'Отметить {day} как отпуск?'):
                    return 'done'
            case '3':
                if _apply_status_days(time_table, emp_id, [day], 'truancy',
                                      'прогул', day, f'Отметить {day} как прогул?'):
                    return 'done'
