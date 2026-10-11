"""Проверка отметок месяца и интерактивные правки оператора.

Поиск проблем (одиночные отметки, пустые рабочие дни, недоработка) — чистые
функции над TimeTable. Правки идут через один путь: журнал (R09) → отметки →
атомарное сохранение сессии, с откатом журнала при сбое записи (_commit).
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from core import ui
from core.config import full_name, staff_or_default
from core.constants import MONTHS_NAME_GENITIVE, WEEKDAYS_NAME
from core.day_models import (
    ATTENDANCE_TAGS, TAG_SICK, TAG_TRUANCY, TAG_VACATION, TAG_WORK, DayMark,
)
from core.pay_calendar import month_date_keys, workday_keys_in_month
from core.roles import TIME_ACTUAL, RoleRule, resolve_rule

#: Статусы дня без работы: пункт меню -> (тег, подпись).
STATUS_CHOICES: dict[str, tuple[str, str]] = {
    '2': (TAG_VACATION, 'отпуск'),
    '3': (TAG_TRUANCY, 'прогул'),
    '5': (TAG_SICK, 'больничный'),
}

#: Время условной отметки статуса (приход = уход): различимо в JSON и Excel.
_STATUS_MARK_TIME: dict[str, str] = {
    TAG_VACATION: '00 00 01',
    TAG_TRUANCY: '23 59 59',
    TAG_SICK: '00 00 02',
}


def _participating_rule(emp_id: int, staff: dict,
                        rules_by_role: dict | None) -> RoleRule | None:
    """Правило роли сотрудника, если он есть в штате и участвует в расчёте."""
    emp = staff.get(emp_id)
    if emp is None:
        return None
    rule = resolve_rule(getattr(emp, 'role_id', None), rules_by_role)
    if rule is None or not rule.participates:
        return None
    return rule


def _get_marks_and_missed(time_table: dict, emp_id: int, year: int, month: int,
                          employees: dict | None = None,
                          rules_by_role: dict | None = None
                          ) -> tuple[list[tuple[str, datetime]], list[str]]:
    """Одиночные отметки и пустые рабочие дни по действующему штату и правилам (R01–R02).

    employees — объединённый DAT+SQLite штат (SQLite-only сотрудник виден,
    его одиночная отметка блокирует бонус). rules_by_role — действующие
    SQLite-правила; без них — DAT-умолчание (legacy). Нет карточки, правила
    или сотрудник не участвует — оба списка пустые (дашборд покажет причину
    через exclusion_reason).
    """
    staff = staff_or_default(employees)
    rule = _participating_rule(emp_id, staff, rules_by_role)
    if rule is None:
        return [], []
    singles = (search_missed_marks(time_table, emp_id, year, month)
               if rule.time_mode == TIME_ACTUAL and rule.check_single_mark else [])
    return singles, search_missed_work_days(time_table, emp_id, year, month, employees=staff)


def search_missed_work_days(time_table: dict, emp_id: int, year: int, month: int,
                            employees: dict | None = None) -> list[str]:
    """Рабочие дни месяца, в которых у сотрудника нет ни одной отметки."""
    if emp_id not in staff_or_default(employees):
        return []
    return [d for d in workday_keys_in_month(year, month)
            if emp_id not in time_table.get(d, {})]


def search_missed_marks(time_table: dict, emp_id: int, year: int,
                        month: int) -> list[tuple[str, datetime]]:
    """Дни выхода с единственной отметкой: [(дата, время отметки)]."""
    result: list[tuple[str, datetime]] = []
    for date_key in month_date_keys(year, month):
        marks = time_table.get(date_key, {}).get(emp_id)
        if marks is not None and marks.go == marks.come and marks.tag in ATTENDANCE_TAGS:
            result.append((date_key, marks.come))
    return result


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
    result: list[UndertimeDay] = []
    for date_key in month_date_keys(year, month):
        marks = time_table.get(date_key, {}).get(emp_id)
        if marks is None or marks.tag != TAG_WORK:
            continue
        if skip_single and marks.go == marks.come:
            continue
        worked = marks.go - marks.come
        if worked < norm:
            result.append(UndertimeDay(date_key, marks.come, marks.go, worked, norm))
    return result


def _get_undertime_days(time_table: dict, emp_id: int, year: int, month: int,
                        employees: dict | None = None,
                        rules_by_role: dict | None = None) -> list[UndertimeDay]:
    """Дни с недоработкой по действующим штату и правилам (как в расчёте времени).

    Только роли с учётом по факту (time_mode 'actual'): у фиксированной смены
    недоработки нет. Нет карточки, правила или неучастие — пустой список.
    """
    rule = _participating_rule(emp_id, staff_or_default(employees), rules_by_role)
    if rule is None or rule.time_mode != TIME_ACTUAL:
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
    return (f"{_day_label(day)} | {format_datetime_russian(day, '%A')} | "
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
    come_sum = go_sum = count = 0
    for date_key, day in time_table.items():
        if date_key in skip_dates or emp_id not in day:
            continue
        marks = day[emp_id]
        if marks.tag != TAG_WORK or marks.go - marks.come < MIN_SHIFT_FOR_AVERAGE:
            continue
        come_sum += _seconds_of_day(marks.come)
        go_sum += _seconds_of_day(marks.go)
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
    if fmt == '%B':
        return MONTHS_NAME_GENITIVE.get(dt_obj.month, dt_obj.strftime(fmt))
    if fmt == '%A':
        return WEEKDAYS_NAME.get(dt_obj.weekday(), dt_obj.strftime(fmt))
    return dt_obj.strftime(fmt)


def _day_label(dt_obj: datetime) -> str:
    """'09 июля'."""
    return f"{dt_obj:%d} {format_datetime_russian(dt_obj, '%B')}"


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


_SEPARATOR = '-' * 140


def analyze_for_print(time_table: dict, emp_id: int, year: int, month: int,
                      employees: dict | None = None,
                      rules_by_role: dict | None = None) -> None:
    staff = staff_or_default(employees)
    emp = staff.get(emp_id)
    if emp is None:
        return
    singles, missed = _get_marks_and_missed(
        time_table, emp_id, year, month, employees=staff, rules_by_role=rules_by_role)
    undertime = _get_undertime_days(time_table, emp_id, year, month,
                                    employees=staff, rules_by_role=rules_by_role)
    if not (singles or missed or undertime):
        return
    print(_SEPARATOR)
    print(f'\nФамилия работника:  {full_name(emp)}')
    if singles:
        print('\n\t\tЕсть только одна метка:\n')
        print('\t\t\t--------------------')
        for _date_key, mark_dt in singles:
            print(f"\t\t\t{_day_label(mark_dt)} | {mark_dt:%H:%M:%S} | "
                  f"{format_datetime_russian(mark_dt, '%A')}")
            print('\t\t\t---------------------')
    if missed:
        print('\n\n\n\t\tДаты рабочих дней, где нет отметок:\n')
        print('\t\t\t------------------')
        for group in group_consecutive_days(missed):
            if len(group) == 1:
                dt_obj = datetime.strptime(group[0], '%Y-%m-%d')
                print(f"\t\t\t{_day_label(dt_obj)} | {format_datetime_russian(dt_obj, '%A')}")
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
    return None


def _read_valid_time(prompt: str) -> tuple[str, list] | None:
    """Запросить время до валидного ввода. None — пользователь отменил (0, EOF)."""
    from randomazer_time_value import parse_and_fill

    while True:
        try:
            raw = input(prompt + ' (формат "Ч М С", 0 — пропустить): ')
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if raw.strip().lower() in ui.CANCEL_TOKENS:
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
    return ui.confirm_save(preview)


def _pair_preview(come: datetime, go: datetime, randomized) -> str:
    preview = f'Выйдет: приход {come.time()} уход {go.time()} длительность {go - come}.'
    if randomized:
        preview += ' (часть времени дополнена случайно — проверьте!)'
    return preview


# --- Журнал правок -------------------------------------------------------------

_JOURNAL: list[dict] = []


def _marks_repr(marks: DayMark) -> str:
    """Кратко: 'приход -> уход [тег]'."""
    return f'{marks.come.time()} -> {marks.go.time()} [{marks.tag}]'


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
                before: DayMark | None, after: DayMark, randomized: bool = False,
                employees: dict | None = None, dates: list[str] | None = None) -> None:
    """Записать правку в журнал запуска (R09: структурированный набор дат)."""
    from core.data_array import display_name

    entry: dict = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'emp_id': emp_id,
        'name': display_name(emp_id, employees),
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


def _commit(time_table: dict, emp_id: int, changes: list[tuple[str, DayMark]],
            action: str, *, randomized: bool = False,
            employees: dict | None = None) -> None:
    """Единственный путь записи правок.

    R09: журнал — до атомарного сохранения, по каждому дню отдельно; при сбое
    записи журнал откатывается, чтобы отметки и журнал описывали один набор.
    """
    for day, mark in changes:
        record_edit(emp_id, day, action, time_table.get(day, {}).get(emp_id), mark,
                    randomized=randomized, employees=employees)
    for day, mark in changes:
        time_table.setdefault(day, {})[emp_id] = mark
    try:
        _save_session(time_table)
    except BaseException:
        del _JOURNAL[-len(changes):]
        raise


def _dt(day: str, t: str) -> datetime:
    """'2026-07-21' + '08 00 00' -> datetime. Бросает ValueError."""
    return datetime.strptime(f'{day} {t}', '%Y-%m-%d %H %M %S')


def _status_mark(day: str, tag: str) -> DayMark:
    moment = _dt(day, _STATUS_MARK_TIME[tag])
    return DayMark(go=moment, come=moment, tag=tag)


# --- Правки дней ---------------------------------------------------------------

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
    _commit(time_table, emp_id,
            [(day, DayMark(go=_dt(day, t_end), come=_dt(day, t_begin), tag=TAG_WORK))
             for day in days],
            action, randomized=randomized, employees=employees)
    ui.info(f'\nДанные за {date_ref} введены\n')
    return True


def _apply_auto_work_days(time_table: dict, emp_id: int, days: list[str],
                          avg: AverageTimes | None, date_ref: str, rng=None,
                          employees: dict | None = None) -> bool:
    """Заполнить рабочие дни по средним (± 5 минут, для каждого дня своё время).

    Одно подтверждение на все дни. True — записано. Без средних (нет полных
    рабочих дней у сотрудника) автозаполнение недоступно.
    """
    if avg is None:
        ui.error('Автозаполнение недоступно: у сотрудника нет полных рабочих дней '
                 'для среднего. Введите время вручную.')
        return False
    plan: list[tuple[str, DayMark]] = []
    for day in days:
        pair = auto_complete_day(day, avg, rng=rng)
        if pair is None:
            ui.error(f'Не удалось подобрать время для {day} по средним. Введите вручную.')
            return False
        plan.append((day, DayMark(go=pair[1], come=pair[0], tag=TAG_WORK)))
    lines = [f'{day}: приход {m.come.time()} уход {m.go.time()}' for day, m in plan[:7]]
    if len(plan) > 7:
        lines.append(f'... и ещё {len(plan) - 7} дн.')
    preview = (f'Автозаполнение за {date_ref} по среднему ({avg.come_text} / {avg.go_text}'
               f' ± 5 мин):\n' + '\n'.join(lines))
    if not _confirm_save(preview):
        ui.info('Не подтверждено.')
        return False
    _commit(time_table, emp_id, plan, f'рабочие дни x{len(days)} (авто по среднему)',
            randomized=True, employees=employees)
    ui.info(f'\nДанные за {date_ref} заполнены по среднему\n')
    return True


def _apply_status_days(time_table: dict, emp_id: int, days: list[str], tag: str,
                       action: str, confirm_q: str,
                       employees: dict | None = None) -> bool:
    """Одно подтверждение на все дни. tag: TAG_VACATION | TAG_TRUANCY | TAG_SICK."""
    if not _confirm_save(confirm_q):
        return False
    _commit(time_table, emp_id, [(day, _status_mark(day, tag)) for day in days],
            action, employees=employees)
    return True


def _edit_single_mark(time_table: dict, emp_id: int, date_key: str, name: str,
                      avg: AverageTimes | None, staff: dict) -> None:
    """Карточка дня с одной отметкой: дописать приход [1], уход [2] или авто [3]."""
    marks = time_table[date_key][emp_id]
    existing = marks.go
    ui.print_day_card_single(name, date_key, existing, avg_hint=format_average(avg))
    while True:
        choice = ui.ask_menu('Выберете пункт меню:', ('1', '2', '3'))
        if choice == ui.CANCEL:
            return
        if choice == '3':
            # Автозаполнение: недостающая сторона — среднее ± 5 минут.
            auto = auto_complete_single(existing, avg) if avg is not None else None
            if auto is None:
                ui.error('Автозаполнение недоступно: нет средних времён или '
                         'отметка не подходит к ним. Введите время вручную.')
                continue
            come, go, side = auto
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
                return  # пропуск этого дня
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
            action = 'одиночная метка'
            preview = _pair_preview(come, go, randomized)
        if _confirm_save(preview):
            _commit(time_table, emp_id, [(date_key, DayMark(go=go, come=come, tag=marks.tag))],
                    action, randomized=bool(randomized), employees=staff)
            ui.info(f'Ввод данных об отметки подтвержден! {dt_write}')
            return
        ui.info('Не подтверждено. Введите снова или 0 для пропуска.')


def _edit_missed_group(time_table: dict, emp_id: int, group: list[str], name: str,
                       avg: AverageTimes | None, staff: dict) -> bool:
    """Диапазон пустых рабочих дней. False — оператор выбрал «пропустить все оставшиеся»."""
    label = format_range(group)
    multi = len(group) > 1
    date_ref = label if multi else group[0]
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
            case ui.CANCEL:
                return True
            case 'a':
                return False
            case '4':
                for day in group:
                    _edit_one_missed_day(time_table, emp_id, day, staff)
                return True
            case '1':
                got = _read_work_times(' (одно на все дни диапазона)' if multi else '')
                if got is None:
                    return True
                t_begin, t_end, randomized = got
                if _apply_work_days(time_table, emp_id, group, t_begin, t_end, randomized,
                                    f'рабочие дни x{len(group)}', date_ref, employees=staff):
                    return True
            case '2' | '3' | '5' as choice:
                tag, status = STATUS_CHOICES[choice]
                if _apply_status_days(time_table, emp_id, group, tag,
                                      f'{status} x{len(group)}',
                                      f'Отметить {date_ref} как {status}?', employees=staff):
                    return True
            case '6':
                if _apply_auto_work_days(time_table, emp_id, group, avg, date_ref,
                                         employees=staff):
                    return True


def analyze_for_edit(time_table: dict, emp_id: int, year: int, month: int,
                     employees: dict | None = None,
                     rules_by_role: dict | None = None) -> None:
    from sys import stderr

    staff = staff_or_default(employees)
    emp = staff.get(emp_id)
    if emp is None:
        return
    singles, missed = _get_marks_and_missed(
        time_table, emp_id, year, month, employees=staff, rules_by_role=rules_by_role)
    name = full_name(emp)
    avg = _current_average(time_table, emp_id)
    if singles:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} имеет только одну отметку в рабочем дне!", file=stderr)
        for date_key, _mark in singles:
            _edit_single_mark(time_table, emp_id, date_key, name, avg, staff)
    if missed:
        print(f"ПРЕДУПРЕЖДЕНИЕ! {name} не имеет данных за рабочий день!", file=stderr)
        for group in group_consecutive_days(missed):
            if not _edit_missed_group(time_table, emp_id, group, name, avg, staff):
                break


def _edit_one_missed_day(time_table: dict, emp_id: int, day: str,
                         employees: dict | None = None) -> bool:
    """Разобрать один день диапазона. True — день заполнен, False — пропущен."""
    while True:
        match ui.ask_menu(f'{day}: [1] рабочий [2] отпуск [3] прогул [5] больничный '
                          f'[6] авто по среднему [0] пропустить день:',
                          ('1', '2', '3', '5', '6')):
            case ui.CANCEL:
                return False
            case '1':
                got = _read_work_times()
                if got is None:
                    return False
                t_begin, t_end, randomized = got
                if _apply_work_days(time_table, emp_id, [day], t_begin, t_end,
                                    randomized, 'заполнен день', day, employees=employees):
                    return True
            case '2' | '3' | '5' as choice:
                tag, status = STATUS_CHOICES[choice]
                if _apply_status_days(time_table, emp_id, [day], tag, status,
                                      f'Отметить {day} как {status}?', employees=employees):
                    return True
            case '6':
                if _apply_auto_work_days(time_table, emp_id, [day],
                                         _current_average(time_table, emp_id), day,
                                         employees=employees):
                    return True


def _apply_one_side(time_table: dict, emp_id: int, day: str, side: str,
                    employees: dict | None = None) -> bool:
    """Поменять у существующего дня только приход ('come') или только уход ('go').

    Вторая отметка остаётся как есть. True — записано.
    """
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
    come, go = (dt_write, marks.go) if side == 'come' else (marks.come, dt_write)
    err = _validate_pair(come, go)
    if err is not None:
        ui.error(f'Ошибка: {err}. Не сохранено.')
        return False
    if not _confirm_save(_pair_preview(come, go, randomized)):
        ui.info('Не подтверждено.')
        return False
    _commit(time_table, emp_id, [(day, DayMark(go=go, come=come, tag=marks.tag))],
            f'правка недоработки: {"приход" if side == "come" else "уход"}',
            randomized=bool(randomized), employees=employees)
    ui.info(f'Данные за {day} изменены.')
    return True


def _edit_undertime_day(time_table: dict, emp_id: int, item: UndertimeDay, name: str,
                        employees: dict | None = None) -> bool:
    """Карточка дня с недоработкой и выбор правки. True — день изменён."""
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
            case ui.CANCEL:
                return False
            case '1':
                got = _read_work_times()
                if got is None:
                    return False
                t_begin, t_end, randomized = got
                if _apply_work_days(time_table, emp_id, [day], t_begin, t_end, randomized,
                                    'правка недоработки: время', day, employees=employees):
                    return True
            case '2' | '3' | '5' as choice:
                tag, status = STATUS_CHOICES[choice]
                if _apply_status_days(time_table, emp_id, [day], tag,
                                      f'правка недоработки: {status}',
                                      f'Заменить {day} ({was}) на «{status}»?',
                                      employees=employees):
                    return True
            case '6':
                if _apply_auto_work_days(time_table, emp_id, [day], avg, day,
                                         employees=employees):
                    return True
            case '7' | '8' as choice:
                if _apply_one_side(time_table, emp_id, day,
                                   'come' if choice == '7' else 'go', employees=employees):
                    return True


def edit_undertime_days(time_table: dict, emp_id: int, year: int, month: int,
                        employees: dict | None = None,
                        rules_by_role: dict | None = None) -> None:
    """Список дней сотрудника с недоработкой (любой) и правка выбранного по номеру.

    Недоработку нельзя «закрыть» навсегда: день, который после правки всё ещё
    короче нормы, остаётся в списке. Выход — 0, пустой ввод или закрытый ввод.
    """
    staff = staff_or_default(employees)
    emp = staff.get(emp_id)
    if emp is None:
        return
    name = full_name(emp)
    while True:
        items = _get_undertime_days(time_table, emp_id, year, month,
                                    employees=staff, rules_by_role=rules_by_role)
        if not items:
            ui.info('Дней с недоработкой нет.')
            return
        ui.print_undertime_list(
            name, [format_undertime_line(i) for i in items], total_shortfall(items))
        raw = ui.read_choice('Номер дня — править | 0 или Enter — назад: ')
        if raw is None:
            return
        index = ui.pick_number(raw, len(items), 'дня')
        if index is not None:
            _edit_undertime_day(time_table, emp_id, items[index], name, employees=staff)


def auto_fill_singles(time_table: dict, emp_id: int, year: int, month: int,
                      employees: dict | None = None,
                      rules_by_role: dict | None = None, rng=None) -> int:
    """Достроить ВСЕ одиночные отметки сотрудника по его средним (± 5 минут).

    Одно подтверждение на весь список. Для каждой отметки недостающая сторона
    берётся у среднего времени ухода/прихода (см. auto_complete_single). Отметки,
    к которым подобрать пару не удалось, остаются как есть — их можно разобрать
    вручную. Возвращает число заполненных отметок.
    """
    staff = staff_or_default(employees)
    emp = staff.get(emp_id)
    if emp is None:
        return 0
    singles, _missed = _get_marks_and_missed(
        time_table, emp_id, year, month, employees=staff, rules_by_role=rules_by_role)
    if not singles:
        ui.info('Одиночных отметок нет.')
        return 0
    avg = _current_average(time_table, emp_id)
    if avg is None:
        ui.error('Автозаполнение недоступно: у сотрудника нет полных рабочих дней '
                 'для среднего. Разберите отметки вручную.')
        return 0
    plan: list[tuple[str, DayMark]] = []
    lines: list[str] = []
    skipped: list[str] = []
    for date_key, _mark in singles:
        marks = time_table[date_key][emp_id]
        auto = auto_complete_single(marks.go, avg, rng=rng)
        if auto is None:
            skipped.append(date_key)
            continue
        come, go, side = auto
        plan.append((date_key, DayMark(go=go, come=come, tag=marks.tag)))
        lines.append(f'{date_key}: приход {come.time()} уход {go.time()} (дополнен {side})')
    if not plan:
        ui.error('Ни к одной отметке не удалось подобрать пару по средним. '
                 'Разберите отметки вручную.')
        return 0
    preview = (f'{full_name(emp)}: автозаполнение {len(plan)} одиночных отметок по среднему '
               f'({avg.come_text} / {avg.go_text} ± 5 мин):\n' + '\n'.join(lines))
    if skipped:
        preview += f'\nБез изменений (подобрать не удалось): {", ".join(skipped)}'
    if not _confirm_save(preview):
        ui.info('Не подтверждено.')
        return 0
    _commit(time_table, emp_id, plan, 'одиночная метка (авто по среднему)',
            randomized=True, employees=staff)
    ui.info(f'Заполнено отметок: {len(plan)}.')
    return len(plan)
