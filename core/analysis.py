from dataclasses import dataclass
from datetime import datetime, time, timedelta
from calendar import monthrange
from core.config import EMPLOYEES
from core.constants import WEEKDAYS_NAME, MONTHS_NAME_GENITIVE, MONTHS_NAME_TO_RUSSIAN
from core.file_parser import definition_of_working_day


def _resolve_staff(employees: dict | None):
    """Действующий штат: переданный объединённый (R01) или DAT-глобал (legacy)."""
    if employees is not None:
        return employees
    return EMPLOYEES


def _resolve_rule(role_id, rules_by_role: dict | None):
    """Действующее правило роли: SQLite-версия (R01–R02) или DAT-умолчание."""
    from core.roles import get_default_rule

    if rules_by_role is not None and role_id in rules_by_role:
        return rules_by_role[role_id]
    if rules_by_role is not None:
        return None
    try:
        return get_default_rule(role_id)
    except KeyError:
        return None


def _get_marks_and_missed(time_table: dict, emp_id: int, year: int, month: int,
                          employees: dict | None = None,
                          rules_by_role: dict | None = None) -> tuple:
    """Проверка отметок по действующему штату и правилам (R01–R02).

    employees — объединённый DAT+SQLite штат (SQLite-only сотрудник виден,
    его одиночная отметка блокирует бонус). rules_by_role — действующие
    SQLite-правила; без них — DAT-умолчание (legacy). Отсутствие карточки
    или правила — «нет ошибок» здесь не возвращается молча: вызывающий код
    (дашборд/бонус) получает 0,0 только для действительно неучаствующих;
    неизвестный сотрудник без карточки — тоже 0,0, но дашборд покажет
    «нет в справочнике» через exclusion_reason.
    """
    from core.roles import TIME_ACTUAL

    staff = _resolve_staff(employees)
    role = staff.get(emp_id) if hasattr(staff, 'get') else None
    if role is None:
        return 0, 0
    rule = _resolve_rule(getattr(role, 'role_id', None), rules_by_role)
    if rule is None:
        return 0, 0
    if not rule.participates:
        return 0, 0
    if rule.time_mode == TIME_ACTUAL and rule.check_single_mark:
        return (search_missed_marks(time_table, emp_id, year, month),
                search_missed_work_days(time_table, emp_id, year, month,
                                        employees=staff))
    return 0, search_missed_work_days(time_table, emp_id, year, month,
                                      employees=staff)


def generation_of_lists_of_days(year: int, month: int) -> list[list[str]]:
    from core.day_models import TAG_WORK

    last_day = monthrange(year, month)[1]
    work_days: list[str] = []
    non_work_days: list[str] = []
    for day in range(1, last_day + 1):
        day_str = f'{day:02d}'
        month_str = f'{month:02d}'
        date_str = f'{year}-{month_str}-{day_str}'
        tag, _ = definition_of_working_day(date_str)
        if tag == TAG_WORK:
            work_days.append(date_str)
        else:
            non_work_days.append(date_str)
    return [work_days, non_work_days]


def search_missed_work_days(time_table: dict, emp_id: int, year: int, month: int,
                            employees: dict | None = None) -> list[str] | int:
    staff = _resolve_staff(employees)
    if emp_id not in staff:
        return 0
    month_days = generation_of_lists_of_days(year, month)
    employee_dates = [d for d in time_table if emp_id in time_table[d]]
    if not employee_dates:
        return month_days[0] if month_days[0] else 0
    missed = [d for d in month_days[0] if d not in employee_dates]
    return missed if missed else 0


def _mark_go(marks):
    return getattr(marks, 'go', marks[0])


def _mark_come(marks):
    return getattr(marks, 'come', marks[1])


def _mark_tag(marks):
    return getattr(marks, 'tag', marks[2])


def _set_mark_come(marks, value) -> None:
    if hasattr(marks, 'come'):
        marks.come = value
    else:
        marks[1] = value


def _set_mark_go(marks, value) -> None:
    if hasattr(marks, 'go'):
        marks.go = value
    else:
        marks[0] = value


def search_missed_marks(time_table: dict, emp_id: int, year: int, month: int) -> list[list] | int:
    from core.day_models import ATTENDANCE_TAGS

    result: list[list] = []
    last_day = monthrange(year, month)[1]
    first = datetime(year, month, 1)
    last = datetime(year, month, last_day)
    current = first
    while current <= last:
        date_str = current.strftime('%Y-%m-%d')
        if date_str in time_table and emp_id in time_table[date_str]:
            cell = time_table[date_str][emp_id]
            if _mark_go(cell) == _mark_come(cell) and _mark_tag(cell) in ATTENDANCE_TAGS:
                result.append([date_str, _mark_come(cell)])
        current += timedelta(days=1)
    return result if result else 0


@dataclass(frozen=True)
class UndertimeDay:
    """Будний день с парой «приход–уход», отработанный меньше нормы смены."""

    date: str
    come: datetime
    go: datetime
    worked: timedelta
    norm: timedelta

    @property
    def shortfall(self) -> timedelta:
        return self.norm - self.worked


def search_undertime_days(time_table: dict, emp_id: int, year: int, month: int,
                          norm: timedelta, skip_single: bool = True) -> list[UndertimeDay]:
    """Будние дни месяца, где отработано строго меньше нормы смены (любая недоработка).

    Выходные и праздники не проверяются: их оплата идёт по факту, нормы там нет.
    skip_single — не включать дни с совпадающими отметками: их уже показывает
    проверка одиночных отметок (если для роли она выключена, такой день — недоработка).
    """
    from core.day_models import TAG_WORK

    prefix = f'{year:04d}-{month:02d}-'
    result: list[UndertimeDay] = []
    for date_key in sorted(time_table):
        if not date_key.startswith(prefix) or emp_id not in time_table[date_key]:
            continue
        marks = time_table[date_key][emp_id]
        if _mark_tag(marks) != TAG_WORK:
            continue
        come, go = _mark_come(marks), _mark_go(marks)
        if skip_single and go == come:
            continue
        worked = go - come
        if worked < norm:
            result.append(UndertimeDay(date_key, come, go, worked, norm))
    return result


def _get_undertime_days(time_table: dict, emp_id: int, year: int, month: int,
                        employees: dict | None = None,
                        rules_by_role: dict | None = None) -> list[UndertimeDay]:
    """Дни с недоработкой по действующим штату и правилам (как в расчёте времени).

    Только роли с учётом по факту (time_mode 'actual'): у фиксированной смены
    недоработки нет. Нет карточки, правила или неучастие — пустой список.
    """
    from core.roles import TIME_ACTUAL

    staff = _resolve_staff(employees)
    role = staff.get(emp_id) if hasattr(staff, 'get') else None
    if role is None:
        return []
    rule = _resolve_rule(getattr(role, 'role_id', None), rules_by_role)
    if rule is None or not rule.participates or rule.time_mode != TIME_ACTUAL:
        return []
    try:
        norm = timedelta(hours=float(rule.shift_norm_hours))
    except (ValueError, TypeError):
        return []  # некорректную норму назовёт расчёт времени, а не сводка
    return search_undertime_days(time_table, emp_id, year, month, norm,
                                 skip_single=bool(rule.check_single_mark))


def format_undertime_line(item: UndertimeDay) -> str:
    """'09 июля | чт | 08:00:00–14:30:00 | отработано 06:30:00 | недоработка 01:30:00'."""
    from core.calculations import str_timedelta

    day = datetime.strptime(item.date, '%Y-%m-%d')
    return (f"{day:%d} {format_datetime_russian(day, '%B')} | "
            f"{format_datetime_russian(day, '%A')} | "
            f'{item.come.time()}–{item.go.time()} | '
            f'отработано {str_timedelta(item.worked)} | '
            f'недоработка {str_timedelta(item.shortfall)}')


def total_shortfall(items: list[UndertimeDay]) -> timedelta:
    return sum((i.shortfall for i in items), timedelta(0))


#: Пара «приход–уход» короче этого в среднее не берётся: это двойное касание
#: терминала, а не смена, и она исказила бы среднее время ухода.
MIN_SHIFT_FOR_AVERAGE = timedelta(hours=1)


@dataclass(frozen=True)
class AverageTimes:
    """Среднее время начала и конца рабочего дня сотрудника за месяц."""

    come: int  # секунды от полуночи
    go: int
    days: int  # по скольким полным будним дням посчитано

    @property
    def come_text(self) -> str:
        return format_seconds(self.come)

    @property
    def go_text(self) -> str:
        return format_seconds(self.go)


def format_seconds(seconds: int) -> str:
    """Секунды от полуночи -> 'ЧЧ:ММ:СС'."""
    seconds = max(0, min(86399, int(seconds)))
    return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'


def _seconds_of_day(moment: datetime) -> int:
    return moment.hour * 3600 + moment.minute * 60 + moment.second


def _at_seconds(day: datetime | str, seconds: int) -> datetime:
    """Дата `day` (datetime или 'YYYY-MM-DD') в момент `seconds` от полуночи."""
    if isinstance(day, str):
        day = datetime.strptime(day, '%Y-%m-%d')
    seconds = max(0, min(86399, int(seconds)))
    return datetime.combine(day.date(), time(seconds // 3600, seconds % 3600 // 60,
                                             seconds % 60))


def compute_average_times(time_table: dict, emp_id: int,
                          skip_dates: frozenset[str] | set[str] = frozenset()
                          ) -> AverageTimes | None:
    """Среднее время прихода/ухода по полным будним дням сотрудника.

    Берутся только настоящие данные: будни с двумя разными отметками и сменой не
    короче MIN_SHIFT_FOR_AVERAGE. Даты из ``skip_dates`` (правки оператора,
    автозаполнение) пропускаются, чтобы собственные правки не сдвигали среднее.
    None — нет ни одного подходящего дня.
    """
    from core.day_models import TAG_WORK

    come_sum = go_sum = count = 0
    for date_key, day in time_table.items():
        if date_key in skip_dates or emp_id not in day:
            continue
        marks = day[emp_id]
        if _mark_tag(marks) != TAG_WORK:
            continue
        come, go = _mark_come(marks), _mark_go(marks)
        if go - come < MIN_SHIFT_FOR_AVERAGE:
            continue
        come_sum += _seconds_of_day(come)
        go_sum += _seconds_of_day(go)
        count += 1
    if count == 0:
        return None
    return AverageTimes(come=come_sum // count, go=go_sum // count, days=count)


def format_average(avg: AverageTimes | None) -> str:
    """Короткая строка для карточек: «Среднее по 18 дн.: приход 08:03:12, уход 17:01:40»."""
    if avg is None:
        return 'Среднее время: нет данных (нет полных рабочих дней)'
    return f'Среднее по {avg.days} дн.: приход {avg.come_text}, уход {avg.go_text}'


def _current_average(time_table: dict, emp_id: int) -> AverageTimes | None:
    """Среднее по данным без дней, которые оператор уже правил в этом запуске."""
    return compute_average_times(time_table, emp_id, skip_dates=_edited_dates(emp_id))


def _edited_dates(emp_id: int) -> set[str]:
    return {str(e.get('date')) for e in _JOURNAL if e.get('emp_id') == emp_id}


def auto_complete_single(existing: datetime, avg: AverageTimes,
                         rng=None) -> tuple[datetime, datetime, str] | None:
    """Достроить одиночную отметку по среднему времени.

    Отметка, которая ближе к среднему приходу, считается приходом (дополняем уход
    средним временем ухода ± 5 минут), иначе — уходом (дополняем приход).
    Возвращает (приход, уход, какая сторона дополнена: 'приход'|'уход') или None,
    если подходящую пару подобрать не удалось (например, отметка позже среднего ухода).
    """
    from randomazer_time_value import random_time_near

    seconds = _seconds_of_day(existing)
    fill_go = abs(seconds - avg.come) <= abs(seconds - avg.go)
    for _ in range(30):
        if fill_go:
            go = _at_seconds(existing, random_time_near(avg.go, rng=rng))
            if _validate_pair(existing, go) is None:
                return existing, go, 'уход'
        else:
            come = _at_seconds(existing, random_time_near(avg.come, rng=rng))
            if _validate_pair(come, existing) is None:
                return come, existing, 'приход'
    return None


def auto_complete_day(day: str, avg: AverageTimes, rng=None) -> tuple[datetime, datetime] | None:
    """Рабочий день целиком по средним: (приход, уход), оба ± 5 минут от среднего."""
    from randomazer_time_value import random_time_near

    for _ in range(30):
        come = _at_seconds(day, random_time_near(avg.come, rng=rng))
        go = _at_seconds(day, random_time_near(avg.go, rng=rng))
        if _validate_pair(come, go) is None:
            return come, go
    return None


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


def analyze_for_print(time_table: dict, emp_id: int, year: int, month: int,
                      employees: dict | None = None,
                      rules_by_role: dict | None = None) -> None:
    staff = _resolve_staff(employees)
    role = staff.get(emp_id) if hasattr(staff, 'get') else None
    if role is None:
        return
    list_marks, list_missed = _get_marks_and_missed(
        time_table, emp_id, year, month,
        employees=staff, rules_by_role=rules_by_role)
    undertime = _get_undertime_days(time_table, emp_id, year, month,
                                    employees=staff, rules_by_role=rules_by_role)
    name = f'{role.last_name} {role.first_name}'.strip()
    if list_marks != 0 or list_missed != 0 or undertime:
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
        if undertime:
            print('\n\n\n\t\tДни с недоработкой (отработано меньше нормы смены):\n')
            print('\t\t\t------------------')
            for item in undertime:
                print(f'\t\t\t{format_undertime_line(item)}')
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


def _preview_mark(current, choice: str, dt_write):
    """Будущее значение отметки для журнала ДО записи (R09)."""
    from copy import copy

    try:
        preview = copy(current)
    except Exception:
        return current
    if choice == '1':
        try:
            if hasattr(preview, 'come'):
                preview.come = dt_write
            else:
                preview[1] = dt_write
        except (IndexError, TypeError):
            pass
    else:
        try:
            if hasattr(preview, 'go'):
                preview.go = dt_write
            else:
                preview[0] = dt_write
        except (IndexError, TypeError):
            pass
    return preview


_JOURNAL: list[dict] = []


def _marks_repr(marks: list) -> str:
    """Кратко: 'приход -> уход [тег]'."""
    try:
        return f'{_mark_come(marks).time()} -> {_mark_go(marks).time()} [{_mark_tag(marks)}]'
    except (IndexError, AttributeError):
        return str(marks)


JOURNAL_REQUIRED_FIELDS = frozenset(
    {'ts', 'emp_id', 'name', 'date', 'action', 'before', 'after'})


def validate_journal_entry(entry: object) -> list[str]:
    """Проверить запись журнала: словарь с обязательными полями (R09)."""
    if not isinstance(entry, dict):
        return ['запись журнала должна быть словарём']
    missing = [f for f in sorted(JOURNAL_REQUIRED_FIELDS) if f not in entry]
    if missing:
        return [f'в записи журнала нет полей: {", ".join(missing)}']
    return []


def record_edit(emp_id: int, date_key: str, action: str,
                before: list | None, after: list, randomized: bool = False,
                employees: dict | None = None, dates: list[str] | None = None) -> None:
    """Записать правку в журнал запуска (R09: структурированный набор дат)."""
    staff = _resolve_staff(employees)
    role = staff.get(emp_id) if hasattr(staff, 'get') else None
    name = f'{role.last_name} {role.first_name}'.strip() if role else f'ID {emp_id}'
    entry: dict = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'emp_id': emp_id,
        'name': name,
        'date': date_key,
        'action': action,
        'before': _marks_repr(before) if before is not None else '—',
        'after': _marks_repr(after),
        'randomized': bool(randomized),
    }
    if dates is not None:
        entry['dates'] = list(dates)
    _JOURNAL.append(entry)


def get_journal() -> list[dict]:
    """Копия журнала правок за запуск."""
    return list(_JOURNAL)


def clear_journal() -> None:
    """Очистить журнал (начало запуска / изоляция тестов)."""
    _JOURNAL.clear()


def restore_journal(entries: list[dict]) -> None:
    """Восстановить журнал из сессии при --resume (F08): замена содержимого."""
    _JOURNAL.clear()
    _JOURNAL.extend([dict(e) for e in entries if isinstance(e, dict)])


def _save_session(time_table: dict) -> None:
    from core.session import save_session
    save_session(time_table, journal=list(_JOURNAL))


def _dt(day: str, t: str) -> datetime:
    """'2026-07-21' + '08 00 00' -> datetime. Бросает ValueError."""
    return datetime.strptime(f'{day} {t}', '%Y-%m-%d %H %M %S')


def _dt_vac(day: str) -> datetime:
    return _dt(day, '00 00 01')


def _dt_truancy(day: str) -> datetime:
    return _dt(day, '23 59 59')


def _dt_sick(day: str) -> datetime:
    return _dt(day, '00 00 02')


def _existing_mark(time_table: dict, day: str, emp_id: int):
    """Отметка дня до правки (для журнала) или None, если дня нет."""
    return time_table.get(day, {}).get(emp_id)


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
                     action: str, date_ref: str, employees: dict | None = None) -> bool:
    """Проверить, подтвердить и записать рабочие дни. True — записано."""
    from core import ui
    from core.day_models import DayMark, TAG_WORK

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
    # R09: запись журнала — ДО атомарного сохранения, по каждому дню отдельно.
    for day in days:
        record_edit(emp_id, day, action, _existing_mark(time_table, day, emp_id),
                    DayMark(go=_dt(day, t_end), come=_dt(day, t_begin), tag=TAG_WORK),
                    randomized=randomized, employees=employees)
    for day in days:
        _set_mark(time_table, day, emp_id, DayMark(go=_dt(day, t_end), come=_dt(day, t_begin), tag=TAG_WORK))
    try:
        _save_session(time_table)
    except BaseException:
        # Откат журнала при ошибке записи: отметки и журнал описывают один набор.
        del _JOURNAL[-len(days):]
        raise
    ui.info(f'\nДанные за {date_ref} введены\n')
    return True


def _apply_auto_work_days(time_table: dict, emp_id: int, days: list[str],
                          avg: AverageTimes | None, date_ref: str, rng=None,
                          employees: dict | None = None) -> bool:
    """Заполнить рабочие дни по средним (± 5 минут, для каждого дня своё время).

    Одно подтверждение на все дни. True — записано. Без средних (нет полных
    рабочих дней у сотрудника) автозаполнение недоступно.
    """
    from core import ui
    from core.day_models import DayMark, TAG_WORK

    if avg is None:
        ui.error('Автозаполнение недоступно: у сотрудника нет полных рабочих дней '
                 'для среднего. Введите время вручную.')
        return False
    plan: list[tuple[str, datetime, datetime]] = []
    for day in days:
        pair = auto_complete_day(day, avg, rng=rng)
        if pair is None:
            ui.error(f'Не удалось подобрать время для {day} по средним. Введите вручную.')
            return False
        plan.append((day, pair[0], pair[1]))
    lines = [f'{day}: приход {come.time()} уход {go.time()}' for day, come, go in plan[:7]]
    if len(plan) > 7:
        lines.append(f'... и ещё {len(plan) - 7} дн.')
    preview = (f'Автозаполнение за {date_ref} по среднему ({avg.come_text} / {avg.go_text}'
               f' ± 5 мин):\n' + '\n'.join(lines))
    if not _confirm_save(preview):
        ui.info('Не подтверждено.')
        return False
    action = f'рабочие дни x{len(days)} (авто по среднему)'
    for day, come, go in plan:
        record_edit(emp_id, day, action, _existing_mark(time_table, day, emp_id),
                    DayMark(go=go, come=come, tag=TAG_WORK), randomized=True,
                    employees=employees)
    for day, come, go in plan:
        _set_mark(time_table, day, emp_id, DayMark(go=go, come=come, tag=TAG_WORK))
    try:
        _save_session(time_table)
    except BaseException:
        del _JOURNAL[-len(plan):]
        raise
    ui.info(f'\nДанные за {date_ref} заполнены по среднему\n')
    return True


def _apply_status_days(time_table: dict, emp_id: int, days: list[str], tag: str,
                       action: str, date_ref: str, confirm_q: str,
                       employees: dict | None = None) -> bool:
    """Одно подтверждение на все дни. tag: TAG_VACATION | TAG_TRUANCY | TAG_SICK."""
    from core.day_models import DayMark, TAG_SICK, TAG_TRUANCY, TAG_VACATION, TAG_WORK

    if not _confirm_save(confirm_q):
        return False
    mark_of = {TAG_VACATION: _dt_vac, TAG_TRUANCY: _dt_truancy, TAG_SICK: _dt_sick}[tag]
    # R09: журнал до сохранения, точные даты и значения до/после по каждому дню.
    for day in days:
        mark = mark_of(day)
        record_edit(emp_id, day, action, _existing_mark(time_table, day, emp_id),
                    DayMark(go=mark, come=mark, tag=tag), employees=employees)
    for day in days:
        mark = mark_of(day)
        _set_mark(time_table, day, emp_id, DayMark(go=mark, come=mark, tag=tag))
    try:
        _save_session(time_table)
    except BaseException:
        del _JOURNAL[-len(days):]
        raise
    return True


def analyze_for_edit(time_table: dict, emp_id: int, year: int, month: int,
                     employees: dict | None = None,
                     rules_by_role: dict | None = None) -> None:
    from sys import stderr
    from core import ui

    staff = _resolve_staff(employees)
    role = staff.get(emp_id) if hasattr(staff, 'get') else None
    if role is None:
        return
    list_marks, list_missed = _get_marks_and_missed(
        time_table, emp_id, year, month,
        employees=staff, rules_by_role=rules_by_role)
    name = f'{role.last_name} {role.first_name}'.strip()
    avg = _current_average(time_table, emp_id)
    if list_marks != 0:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} имеет только одну отметку в рабочем дне!", file=stderr)
        for cell in list_marks:
            date_key = cell[0]
            existing = _mark_go(time_table[date_key][emp_id])
            before_single = time_table[date_key][emp_id]
            try:
                before_snapshot = list(before_single)
            except TypeError:
                before_snapshot = before_single
            ui.print_day_card_single(name, date_key, existing, avg_hint=format_average(avg))
            while True:
                choice = ui.ask_menu('Выберете пункт меню:', ('1', '2', '3'))
                if choice in ('0', 'q', 'отмена'):
                    break
                if choice in ('1', '2', '3'):
                    action = 'одиночная метка'
                    if choice == '3':
                        # Автозаполнение: недостающая сторона — среднее ± 5 минут.
                        auto = auto_complete_single(existing, avg) if avg is not None else None
                        if auto is None:
                            ui.error('Автозаполнение недоступно: нет средних времён или '
                                     'отметка не подходит к ним. Введите время вручную.')
                            continue
                        come, go, side = auto
                        choice = '2' if side == 'уход' else '1'
                        dt_write = go if side == 'уход' else come
                        randomized = True
                        action = 'одиночная метка (авто по среднему)'
                        preview = (f'Выйдет: приход {come.time()} уход {go.time()} '
                                   f'длительность {go - come}. '
                                   f'(авто: {side} по среднему {avg.come_text} / '
                                   f'{avg.go_text} ± 5 мин)')
                    else:
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
                        # R09: журнал до сохранения; откат при ошибке записи.
                        record_edit(emp_id, date_key, action,
                                    before_snapshot,
                                    _preview_mark(time_table[date_key][emp_id],
                                                  choice, dt_write),
                                    randomized=bool(randomized),
                                    employees=_resolve_staff(employees))
                        if choice == '1':
                            _set_mark_come(time_table[date_key][emp_id], dt_write)
                        else:
                            _set_mark_go(time_table[date_key][emp_id], dt_write)
                        try:
                            _save_session(time_table)
                        except BaseException:
                            del _JOURNAL[-1:]
                            raise
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
            ui.print_missed_day_card(name, label, avg_hint=format_average(avg))
            if multi:
                ui.info(f'Диапазон {label}: время вводится один раз на все дни. '
                        '[4] разобрать по одному дню  [a] пропустить все оставшиеся',
                        markup=False)
                valid = ('1', '2', '3', '4', '5', '6', 'a')
            else:
                ui.info('[a] пропустить все оставшиеся', markup=False)
                valid = ('1', '2', '3', '5', '6', 'a')
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
                        from core.day_models import TAG_VACATION

                        if _apply_status_days(time_table, emp_id, group, TAG_VACATION,
                                              f'отпуск x{len(group)}', date_ref,
                                              f'Отметить {date_ref} как отпуск?'):
                            break
                    case '3':
                        date_ref = label if multi else group[0]
                        from core.day_models import TAG_TRUANCY

                        if _apply_status_days(time_table, emp_id, group, TAG_TRUANCY,
                                              f'прогул x{len(group)}', date_ref,
                                              f'Отметить {date_ref} как прогул?'):
                            break
                    case '5':
                        date_ref = label if multi else group[0]
                        from core.day_models import TAG_SICK

                        if _apply_status_days(time_table, emp_id, group, TAG_SICK,
                                              f'больничный x{len(group)}', date_ref,
                                              f'Отметить {date_ref} как больничный?'):
                            break
                    case '6':
                        date_ref = label if multi else group[0]
                        if _apply_auto_work_days(time_table, emp_id, group, avg, date_ref):
                            break


def _edit_one_missed_day(time_table: dict, emp_id: int, day: str) -> str:
    """Разобрать один день диапазона. Возвращает 'done' | 'skip'."""
    from core import ui
    from core.day_models import TAG_SICK, TAG_TRUANCY, TAG_VACATION

    while True:
        match ui.ask_menu(f'{day}: [1] рабочий [2] отпуск [3] прогул [5] больничный '
                          f'[6] авто по среднему [0] пропустить день:',
                          ('1', '2', '3', '5', '6')):
            case '5':
                if _apply_status_days(time_table, emp_id, [day], TAG_SICK,
                                      'больничный', day, f'Отметить {day} как больничный?'):
                    return 'done'
            case '6':
                if _apply_auto_work_days(time_table, emp_id, [day],
                                         _current_average(time_table, emp_id), day):
                    return 'done'
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
                if _apply_status_days(time_table, emp_id, [day], TAG_VACATION,
                                      'отпуск', day, f'Отметить {day} как отпуск?'):
                    return 'done'
            case '3':
                if _apply_status_days(time_table, emp_id, [day], TAG_TRUANCY,
                                      'прогул', day, f'Отметить {day} как прогул?'):
                    return 'done'


def _apply_one_side(time_table: dict, emp_id: int, day: str, side: str,
                    employees: dict | None = None) -> bool:
    """Поменять у существующего дня только приход ('come') или только уход ('go').

    Вторая отметка остаётся как есть. True — записано.
    """
    from core import ui

    marks = time_table[day][emp_id]
    title = 'прихода' if side == 'come' else 'ухода'
    got = _read_valid_time(f'Новое время {title}')
    if got is None:
        return False
    entered, randomized = got
    try:
        dt_write = _dt(day, entered)
    except ValueError as e:
        ui.error(f'Ошибка: неверное время ({e}). Введите снова.')
        return False
    come, go = (dt_write, _mark_go(marks)) if side == 'come' else (_mark_come(marks), dt_write)
    err = _validate_pair(come, go)
    if err is not None:
        ui.error(f'Ошибка: {err}. Не сохранено.')
        return False
    preview = f'Выйдет: приход {come.time()} уход {go.time()} длительность {go - come}.'
    if randomized:
        preview += ' (часть времени дополнена случайно — проверьте!)'
    if not _confirm_save(preview):
        ui.info('Не подтверждено.')
        return False
    choice = '1' if side == 'come' else '2'
    # R09: журнал до записи (строки до/после формируются сразу), откат при сбое сохранения.
    record_edit(emp_id, day, f'правка недоработки: {"приход" if side == "come" else "уход"}',
                marks, _preview_mark(marks, choice, dt_write),
                randomized=bool(randomized), employees=employees)
    if side == 'come':
        _set_mark_come(marks, dt_write)
    else:
        _set_mark_go(marks, dt_write)
    try:
        _save_session(time_table)
    except BaseException:
        del _JOURNAL[-1:]
        raise
    ui.info(f'Данные за {day} изменены.')
    return True


def _edit_undertime_day(time_table: dict, emp_id: int, item: UndertimeDay, name: str,
                        employees: dict | None = None) -> str:
    """Карточка дня с недоработкой и выбор правки. Возвращает 'done' | 'skip'."""
    from core import ui
    from core.day_models import TAG_SICK, TAG_TRUANCY, TAG_VACATION

    day = item.date
    # Сам правимый день в среднее не входит: «авто по среднему» не должно целиться в себя.
    avg = compute_average_times(time_table, emp_id,
                                skip_dates=_edited_dates(emp_id) | {day})
    ui.print_undertime_card(name, format_undertime_line(item), format_average(avg))
    was = _marks_repr(time_table[day][emp_id])
    while True:
        match ui.ask_menu(f'{day}: [1] приход и уход [2] отпуск [3] прогул [5] больничный '
                          f'[6] авто по среднему [7] только приход [8] только уход '
                          f'[0] назад:', ('1', '2', '3', '5', '6', '7', '8')):
            case '0' | 'q' | 'отмена':
                return 'skip'
            case '1':
                got = _read_work_times()
                if got is None:
                    return 'skip'
                t_begin, t_end, randomized = got
                if _apply_work_days(time_table, emp_id, [day], t_begin, t_end, randomized,
                                    'правка недоработки: время', day, employees=employees):
                    return 'done'
            case '2' | '3' | '5' as choice:
                tag, label = {'2': (TAG_VACATION, 'отпуск'), '3': (TAG_TRUANCY, 'прогул'),
                              '5': (TAG_SICK, 'больничный')}[choice]
                if _apply_status_days(time_table, emp_id, [day], tag,
                                      f'правка недоработки: {label}', day,
                                      f'Заменить {day} ({was}) на «{label}»?',
                                      employees=employees):
                    return 'done'
            case '6':
                if _apply_auto_work_days(time_table, emp_id, [day], avg, day,
                                         employees=employees):
                    return 'done'
            case '7' | '8' as choice:
                if _apply_one_side(time_table, emp_id, day,
                                   'come' if choice == '7' else 'go', employees=employees):
                    return 'done'


def edit_undertime_days(time_table: dict, emp_id: int, year: int, month: int,
                        employees: dict | None = None,
                        rules_by_role: dict | None = None) -> None:
    """Список дней сотрудника с недоработкой (любой) и правка выбранного по номеру.

    Недоработку нельзя «закрыть» навсегда: день, который после правки всё ещё
    короче нормы, остаётся в списке. Выход — 0, пустой ввод или закрытый ввод.
    """
    from core import ui

    staff = _resolve_staff(employees)
    role = staff.get(emp_id) if hasattr(staff, 'get') else None
    if role is None:
        return
    name = f'{role.last_name} {role.first_name}'.strip()
    while True:
        items = _get_undertime_days(time_table, emp_id, year, month,
                                    employees=staff, rules_by_role=rules_by_role)
        if not items:
            ui.info('Дней с недоработкой нет.')
            return
        ui.print_undertime_list(
            name, [format_undertime_line(i) for i in items], total_shortfall(items))
        try:
            raw = input('Номер дня — править | 0 или Enter — назад: ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw in ('', '0', 'q', 'й', 'отмена'):
            return
        if not raw.isdigit() or not 1 <= int(raw) <= len(items):
            ui.error(f'Нет дня с номером {raw!r}: введите число от 1 до {len(items)}.')
            continue
        _edit_undertime_day(time_table, emp_id, items[int(raw) - 1], name, employees=staff)


def auto_fill_singles(time_table: dict, emp_id: int, year: int, month: int,
                      employees: dict | None = None,
                      rules_by_role: dict | None = None, rng=None) -> int:
    """Достроить ВСЕ одиночные отметки сотрудника по его средним (± 5 минут).

    Одно подтверждение на весь список. Для каждой отметки недостающая сторона
    берётся у среднего времени ухода/прихода (см. auto_complete_single). Отметки,
    к которым подобрать пару не удалось, остаются как есть — их можно разобрать
    вручную. Возвращает число заполненных отметок.
    """
    from core import ui

    staff = _resolve_staff(employees)
    role = staff.get(emp_id) if hasattr(staff, 'get') else None
    if role is None:
        return 0
    list_marks, _missed = _get_marks_and_missed(
        time_table, emp_id, year, month, employees=staff, rules_by_role=rules_by_role)
    if list_marks == 0:
        ui.info('Одиночных отметок нет.')
        return 0
    avg = _current_average(time_table, emp_id)
    if avg is None:
        ui.error('Автозаполнение недоступно: у сотрудника нет полных рабочих дней '
                 'для среднего. Разберите отметки вручную.')
        return 0
    plan: list[tuple[str, str, datetime, datetime, str]] = []
    skipped: list[str] = []
    for cell in list_marks:
        date_key = cell[0]
        existing = _mark_go(time_table[date_key][emp_id])
        auto = auto_complete_single(existing, avg, rng=rng)
        if auto is None:
            skipped.append(date_key)
            continue
        come, go, side = auto
        plan.append((date_key, '2' if side == 'уход' else '1', come, go, side))
    if not plan:
        ui.error('Ни к одной отметке не удалось подобрать пару по средним. '
                 'Разберите отметки вручную.')
        return 0
    name = f'{role.last_name} {role.first_name}'.strip()
    lines = [f'{date_key}: приход {come.time()} уход {go.time()} (дополнен {side})'
             for date_key, _choice, come, go, side in plan]
    preview = (f'{name}: автозаполнение {len(plan)} одиночных отметок по среднему '
               f'({avg.come_text} / {avg.go_text} ± 5 мин):\n' + '\n'.join(lines))
    if skipped:
        preview += f'\nБез изменений (подобрать не удалось): {", ".join(skipped)}'
    if not _confirm_save(preview):
        ui.info('Не подтверждено.')
        return 0
    action = 'одиночная метка (авто по среднему)'
    for date_key, choice, come, go, _side in plan:
        dt_write = go if choice == '2' else come
        marks = time_table[date_key][emp_id]
        try:
            before_snapshot = list(marks)
        except TypeError:
            before_snapshot = marks
        record_edit(emp_id, date_key, action, before_snapshot,
                    _preview_mark(marks, choice, dt_write), randomized=True,
                    employees=staff)
        if choice == '1':
            _set_mark_come(marks, dt_write)
        else:
            _set_mark_go(marks, dt_write)
    try:
        _save_session(time_table)
    except BaseException:
        del _JOURNAL[-len(plan):]
        raise
    ui.info(f'Заполнено отметок: {len(plan)}.')
    return len(plan)
