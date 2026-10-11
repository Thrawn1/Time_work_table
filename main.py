"""Запуск расчёта месяца: импорт → контекст → проверка и правки → расчёт → отчёты.

Каждый этап — отдельная функция. Фатальная ошибка этапа — исключение Abort
с готовым текстом для оператора; main() печатает его и завершает запуск с кодом 1.
"""

import os
import sys
from argparse import ArgumentParser, Namespace
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from os.path import exists, join

from core import config
from core.analysis import analyze_for_print, clear_journal, get_journal, restore_journal
from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
from core.cli import build_parser, resolve_period, resolve_secret_key, validate_period
from core.cli import parse_secret_key as parse_secret_key  # совместимость прежнего API main
from core.config import (
    MANUAL_EXCLUSIONS, ConfigError, load_config, preserve_config, set_data_dir, set_secret_key,
)
from core.constants import MONTHS_NAME_TO_RUSSIAN
from core.data_array import (
    build_data_array, display_name, exclusion_reason, get_employees_with_marks,
    repairmen_attendance,
)
from core.day_models import EmployeeMonth, HolidayGroup, WorkGroup
from core.excel_builder import build_excel
from core.file_parser import find_calendar_conflicts, read_file_data
from core.html_builder import build_html
from core.pay_context import (
    PayrollContext, combined_staff_for_import, diagnose_roster_divergence, load_rules_map,
    resolve_context, sqlite_excluded_map,
)
from core.pay_package import (
    build_legacy_package, build_new_package, calendar_detail, file_meta, resolve_dat_path,
    save_package, staff_snapshot,
)
from core.pay_store import get_assignment, open_db
from core.payroll import PayrollError, build_bundle, bundle_to_wages
from core.review import current_settlement_ids, run_review, run_undertime_review
from core.session import (
    SESSION_FILE,
    SessionBackupError,
    _peek_period,
    adopt_cwd_session,
    backup_existing_session,
    load_session_full,
    preserve_session_paths,
    remove_session,
    save_session,
    session_exists,
    set_session_context,
    set_session_dir,
)
from core import ui

__all__ = ['main', 'parse_secret_key', 'resolve_secret_key', 'validate_period']


class Abort(Exception):
    """Запуск прерван: текст — готовое сообщение оператору."""


@contextmanager
def _abort_on(errors, what: str, tail: str = 'Расчет прерван.'):
    """Ошибки errors внутри блока -> Abort('ОШИБКА: <what> (<причина>). <tail>')."""
    try:
        yield
    except errors as e:
        raise Abort(f'ОШИБКА: {what} ({e}). {tail}') from e


@contextmanager
def _reading_sources():
    """Чтение справочников и календаря: понятная причина вместо трейсбека."""
    try:
        yield
    except PayrollError as e:
        raise Abort(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.') from e
    except (ValueError, ConfigError, OSError) as e:
        raise Abort(f'ОШИБКА: календарь/справочник недоступен ({e}). Расчет прерван.') from e


@dataclass
class _Month:
    """Отметки месяца и откуда они взяты (новый импорт или сессия)."""

    year: int
    month: int
    data_array: dict
    list_data: list[str] = field(default_factory=list)
    session_state: str = 'fresh'  # fresh | ignored | resumed
    saved_context: dict | None = None

    @property
    def resumed(self) -> bool:
        return self.session_state == 'resumed'

    @property
    def title(self) -> str:
        return f'{MONTHS_NAME_TO_RUSSIAN[self.month]} {self.year}'


@dataclass
class _Roster:
    """Режим периода, штат, правила и состав участников — один на все этапы."""

    pay_ctx: PayrollContext
    calendar: dict
    staff: dict
    rules_by_role: dict | None
    sqlite_excluded: dict
    candidates: list[int]
    settlement_ids: list[int]

    @property
    def settlement_set(self) -> set[int]:
        return set(self.settlement_ids)


def main(argv: list[str] | None = None) -> None:
    """Точка входа; каждый запуск изолирован от предыдущих вызовов в процессе."""
    parser = build_parser()
    args = parser.parse_args(argv)
    with preserve_config(), preserve_session_paths():
        try:
            _run(args, parser)
        except Abort as e:
            print(e)
            sys.exit(1)


def _run(args: Namespace, parser: ArgumentParser) -> None:
    _prepare_dirs(args)
    try:
        load_config()
    except ConfigError as e:
        raise Abort(f'ОШИБКА: {e}. Расчет прерван до правок и отчётов.') from e

    print('\n\t\tСистема расчета заработной платы и учета рабочего времени работников\n')
    secret_key, salary_mode = resolve_secret_key(args)
    # Ключ — только в памяти запуска (F18): на диск не пишется.
    set_secret_key(secret_key)
    if salary_mode:
        print('Режим: расчет зарплаты (ключ принят).')
    else:
        print('Режим: учет времени БЕЗ зарплаты (оклад = 0, молоко считается).')

    clear_journal()
    month = _resume_month(args, parser) if args.resume else _import_month(args, parser)
    print(f'{month.title} год')

    roster = _resolve_roster(args, month, salary_mode)
    # R08/R10: контекст сессии — до правок, чтобы каждое сохранение несло тот же смысл.
    session_ctx = {
        'db_path': args.pay_dir,
        'mode': roster.pay_ctx.mode,
        'salary_mode': bool(salary_mode),
        'period': {'year': month.year, 'month': month.month},
        'month_start': roster.pay_ctx.month_start,
        'calendar': roster.calendar,
        'participants': sorted(roster.settlement_ids),
        'manual_excluded': _manual_exclusions(),
        'dat_file': _dat_file(args, month),
    }
    set_session_context(session_ctx)

    rows_read = (len(month.list_data) if month.list_data
                 else sum(len(day) for day in month.data_array.values()))
    ui.print_start_screen(ui.build_start_info(
        '(сессия)' if month.resumed else args.file,
        month.year, month.month, rows_read, len(roster.settlement_ids), month.session_state,
        output_dir=args.output_dir, data_dir=args.data_dir,
    ))
    ui.print_header('Проверка')
    # Ремонтники — без начислений и проверок: только дни выходов, сразу на экране.
    ui.print_repairmen(ui.build_repairmen_lines(month.data_array, roster.staff,
                                                month.year, month.month))
    _check_and_edit(args, month, roster, session_ctx)

    ui.print_header('Расчет')
    _calculate_and_report(args, month, roster, salary_mode, secret_key)
    remove_session()
    set_session_context(None)


def _prepare_dirs(args: Namespace) -> None:
    os.makedirs(args.output_dir, exist_ok=True)
    set_data_dir(args.data_dir)
    set_session_dir(args.output_dir)
    adopted = adopt_cwd_session()
    if adopted:
        print(f'Сессия перенесена из текущего каталога в {adopted} '
              f'(теперь сессии живут в --output-dir).')
    # Единый источник пути справочника оплаты на весь запуск (R08 может
    # переключить его при --resume на сохранённый в сессии).
    args.pay_dir = args.pay_dir or join(args.data_dir, 'pay_directory.db')


def _manual_exclusions() -> dict[str, str]:
    return {str(k): v for k, v in MANUAL_EXCLUSIONS.items()}


def _dat_file(args: Namespace, month: _Month) -> str | None:
    if month.resumed:
        return (month.saved_context or {}).get('dat_file')
    return args.file


# --- Этап 1: отметки месяца ---------------------------------------------------

def _resume_month(args: Namespace, parser: ArgumentParser) -> _Month:
    """Продолжить сохранённую сессию: те же отметки, журнал, справочник и исключения."""
    if not session_exists():
        parser.error('сохранённая сессия для --resume не найдена')
    data_array, saved_journal, saved_context = load_session_full()
    if data_array is None:
        raise Abort('Не удалось восстановить сессию!')
    restore_journal(saved_journal)
    if data_array:
        first_date = next(iter(data_array))
        year, month = int(first_date[:4]), int(first_date[5:7])
    else:
        # Пустой месяц, восстановленный по периоду из заголовка сессии.
        period = _peek_period(SESSION_FILE) if exists(SESSION_FILE) else None
        if period is None:
            raise Abort('Не удалось восстановить сессию: пустая сессия без периода!')
        year, month = period
    try:
        year, month = validate_period(year, month)
    except ValueError as e:
        raise Abort(f'ОШИБКА: период восстановленной сессии некорректен ({e}). '
                    f'Расчет прерван.') from e
    if saved_context:
        # R08: продолжение того же расчёта — тот же справочник/календарь.
        saved_db = saved_context.get('db_path')
        if saved_db and saved_db != args.pay_dir:
            print(f'ВНИМАНИЕ: сессия сохранена со справочником {saved_db}, '
                  f'а запрошен {args.pay_dir} — продолжаем расчёт сессии '
                  f'({saved_db}). Для смены источника начните новый расчёт без --resume.')
            args.pay_dir = saved_db
        saved_period = saved_context.get('period')
        if isinstance(saved_period, dict):
            try:
                saved = (int(saved_period.get('year', year)), int(saved_period.get('month', month)))
            except (ValueError, TypeError):
                saved = (year, month)
            if saved != (year, month):
                raise Abort(f'ОШИБКА: период сессии {saved[0]:04d}-{saved[1]:02d} не совпадает '
                            f'с восстановленным {year:04d}-{month:02d}. '
                            f'Начните новый расчёт без --resume.')
        # Исключения сотрудников, выбранные оператором до обрыва, действуют и дальше.
        saved_manual = saved_context.get('manual_excluded')
        if isinstance(saved_manual, dict):
            for key, reason in saved_manual.items():
                try:
                    MANUAL_EXCLUSIONS[int(key)] = str(reason)
                except (TypeError, ValueError):
                    continue
    return _Month(year, month, data_array, session_state='resumed',
                  saved_context=saved_context)


def _import_month(args: Namespace, parser: ArgumentParser) -> _Month:
    """Новый расчёт: прочитать DAT за месяц; прежняя сессия уходит в бэкап."""
    year, month = resolve_period(args, parser)
    session_state = 'fresh'
    if session_exists():
        try:
            saved = backup_existing_session()
        except SessionBackupError as e:
            raise Abort(f'ОШИБКА: не удалось сохранить существующую сессию ({e}). '
                        f'Новый расчёт не начат, исходная сессия сохранена.') from e
        if saved:
            print(f'ВНИМАНИЕ: найден файл сессии. '
                  f'Он сохранён отдельно как {saved} и будет проигнорирован. '
                  f'Используйте --resume для восстановления.')
        else:
            print('ВНИМАНИЕ: найден файл сессии. '
                  'Он будет проигнорирован. Используйте --resume для восстановления.')
        session_state = 'ignored'
    with _abort_on((OSError, UnicodeDecodeError), 'файл данных недоступен'):
        list_data = read_file_data(args.file, year, month, args.data_dir)
    if list_data:
        with _reading_sources():
            data_array = build_data_array(list_data)
    elif args.include_empty and exists(join(args.data_dir, args.file)):
        print('ВНИМАНИЕ: за выбранный месяц отметок нет — '
              'начинаем с пустой таблицы (--include-empty).')
        data_array = {}
    else:
        raise Abort('Нет данных для обработки!')
    return _Month(year, month, data_array, list_data, session_state)


# --- Этап 2: контекст периода и состав ----------------------------------------

def _resolve_roster(args: Namespace, month: _Month, salary_mode: bool) -> _Roster:
    """Единый контекст периода — до анализа и правок (R01–R03, spec §6–§7)."""
    with _reading_sources():
        pay_ctx = resolve_context(args.pay_dir, month.year, month.month, salary_mode)
    # R16: конфликты календаря и его снимок — в контекст до расчёта.
    with _abort_on((OSError, ValueError), 'календарь недоступен'):
        conflicts = find_calendar_conflicts(month.year)
        calendar = calendar_detail(month.year, month.month)
    for day in conflicts:
        print(f'ВНИМАНИЕ (календарь): {day} — праздник и перенесённый рабочий день '
              f'одновременно; применён приоритет праздника (R16).')
    pay_ctx.workdays_D = calendar.get('D')
    pay_ctx.calendar_dates = calendar.get('dates')
    saved = month.saved_context or {}
    # R08: календарь сессии должен совпадать — иначе явный новый пересчёт.
    if month.resumed and isinstance(saved.get('calendar'), dict) and saved['calendar'] != calendar:
        raise Abort('ОШИБКА: производственный календарь изменился после сохранения сессии. '
                    'Норма месяца и классификация отметок разошлись бы. '
                    'Начните новый расчёт без --resume.')
    try:
        pay_ctx.db_meta = file_meta(args.pay_dir)
    except OSError:
        pay_ctx.db_meta = None

    sqlite_excluded: dict = {}
    rules_by_role: dict | None = None
    if pay_ctx.mode == 'new':
        print('Режим модели: новая (SQLite-условия действуют на месяц). Ошибки настройки фатальны.')
        with _reading_sources():
            staff = combined_staff_for_import(config.EMPLOYEES, args.pay_dir, pay_ctx.month_start)
            # Импорт на объединённом штате: SQLite-only отметки не отбрасываются (R01).
            if not month.resumed and month.list_data:
                month.data_array = build_data_array(month.list_data, employees=staff)
            sqlite_excluded = sqlite_excluded_map(args.pay_dir, pay_ctx.month_start)
            # R02: действующие правила — до анализа и редактора; отсутствие — отказ.
            rules_by_role = load_rules_map(args.pay_dir, pay_ctx.month_start, staff)
            pay_ctx.staff = staff
            pay_ctx.rules_by_role = rules_by_role
            for warning in diagnose_roster_divergence(pay_ctx, config.EMPLOYEES, month.data_array):
                print(f'ВНИМАНИЕ (состав): {warning}')
    else:
        print('Режим модели: legacy (действующих SQLite-условий на месяц нет).')
        # R08: сессия сохранена в new-режиме, а текущий справочник даёт legacy —
        # осознанный отказ вместо расчёта по другой модели молча.
        if month.resumed and saved.get('mode') == 'new':
            raise Abort('ОШИБКА: сессия сохранена в новой модели, а текущий справочник даёт legacy. '
                        'Укажите исходный --pay-dir или начните новый расчёт без --resume.')
        staff = config.EMPLOYEES

    if args.include_empty:
        candidates = list(staff)
    else:
        candidates = get_employees_with_marks(month.data_array, staff)
        skipped = len(staff) - len(candidates)
        if skipped:
            print(f'Без отметок за месяц пропущено сотрудников: {skipped} '
                  f'(см. второй блок сводки; для включения — --include-empty).')
    # Единый состав: штат + правила ролей + SQLite-исключения (R01–R03).
    settlement_ids = current_settlement_ids(candidates, staff, sqlite_excluded, rules_by_role)
    roster = _Roster(pay_ctx, calendar, staff, rules_by_role, sqlite_excluded,
                     candidates, settlement_ids)
    if pay_ctx.mode == 'new':
        _require_assignments(args, roster)
    return roster


def _require_assignments(args: Namespace, roster: _Roster) -> None:
    """До правок: отсутствие обязательного назначения — фатально, без silent fallback."""
    month_start = roster.pay_ctx.month_start
    with _abort_on(Exception, 'справочник оплаты недоступен'):
        with open_db(args.pay_dir) as con:
            missing = [e for e in roster.settlement_ids
                       if get_assignment(con, e, month_start) is None]
    if missing:
        names = ', '.join(display_name(e, roster.staff) for e in missing)
        raise Abort(f'ОШИБКА: новая модель должна применяться, но нет назначения SQLite '
                    f'на {month_start} для: {names}. Расчет прерван без fallback.')


# --- Этап 3: проверка и правки ------------------------------------------------

def _dashboard(month: _Month, roster: _Roster, title: str) -> None:
    ui.print_dashboard(
        ui.build_dashboard_rows(month.data_array, list(roster.staff), month.year, month.month,
                                employees=roster.staff,
                                extra_excluded=roster.sqlite_excluded or None,
                                rules_by_role=roster.rules_by_role,
                                included_ids=roster.settlement_set),
        title=title,
    )


def _check_and_edit(args: Namespace, month: _Month, roster: _Roster, session_ctx: dict) -> None:
    title = f'{month.title} — сводка'
    if args.no_edit:
        # Без правок: подробный список проблем каждого участника и сводная таблица.
        for emp_id in roster.settlement_ids:
            analyze_for_print(month.data_array, emp_id, month.year, month.month,
                              employees=roster.staff, rules_by_role=roster.rules_by_role)
        _dashboard(month, roster, title)
        return

    ui.print_header('Правки')

    def update_participants() -> None:
        roster.settlement_ids = current_settlement_ids(
            roster.candidates, roster.staff, roster.sqlite_excluded, roster.rules_by_role)
        session_ctx['participants'] = sorted(roster.settlement_ids)
        session_ctx['manual_excluded'] = _manual_exclusions()
        set_session_context(session_ctx)

    def persist_exclusions() -> None:
        """Ручные исключения и состав участников — в контекст сессии (для --resume)."""
        update_participants()
        try:
            save_session(month.data_array, month.year, month.month, journal=get_journal())
        except (OSError, ValueError) as e:
            print(f'ВНИМАНИЕ: исключение не записано в сессию ({e}); '
                  f'при --resume его придётся выбрать заново.')

    with _abort_on(OSError, 'сессия правок не сохранена',
                   tail='Расчет прерван; повторите запуск с --resume.'):
        run_review(month.data_array, roster.staff, roster.candidates, month.year, month.month,
                   rules_by_role=roster.rules_by_role, extra_excluded=roster.sqlite_excluded,
                   on_exclusion_change=persist_exclusions, title=title)
        # Пропуски закрыты — теперь недоработки (в том числе от автозаполнения):
        # посмотреть все разом и поправить по желанию, до расчёта и Excel.
        run_undertime_review(month.data_array, roster.staff, roster.candidates,
                             month.year, month.month, rules_by_role=roster.rules_by_role,
                             extra_excluded=roster.sqlite_excluded)
    # Состав мог измениться: сотрудников исключили или вернули в расчёт.
    update_participants()
    _dashboard(month, roster, f'{title} (итог перед расчётом)')


# --- Этап 4: расчёт и отчёты --------------------------------------------------

def _empty_month() -> EmployeeMonth:
    zero = timedelta(0)
    return EmployeeMonth(work=WorkGroup(days=0, overtime=zero, undertime=zero),
                         holiday=HolidayGroup(days=0, overtime=zero, undertime=zero, worked=zero),
                         vacation_days=0, truancy_days=0)


def _calculate_and_report(args: Namespace, month: _Month, roster: _Roster,
                          salary_mode: bool, secret_key) -> None:
    staff, settlement_set = roster.staff, roster.settlement_set
    with _abort_on((OSError, ConfigError), 'календарь/справочник недоступен'), \
            _abort_on(ValueError, 'учёт времени невозможен'):
        work_time_all = calculate_hours_per_day(
            month.data_array, employees=staff, rules_by_role=roster.rules_by_role)
    work_time = {}
    for date_key, emps in work_time_all.items():
        day = {emp_id: val for emp_id, val in emps.items() if emp_id in settlement_set}
        if day:
            work_time[date_key] = day
    summary = calculate_hours_per_month(work_time)
    # R07: каждый включённый сотрудник имеет месячную запись — нулевую при
    # отсутствии отметок, а не пропадает из summary/денег.
    for emp_id in roster.settlement_ids:
        summary.setdefault(emp_id, _empty_month())
    sick_days = {e: s.sick_days for e, s in summary.items() if s.sick_days}
    if sick_days:
        print('Больничные дни (программа их не оплачивает — оплата OPEN, spec п.9):')
        for emp_id, days in sorted(sick_days.items()):
            print(f'  {display_name(emp_id, staff)}: {days} дн.')

    pay_bundle, wages, rates = _pay(args, month, roster, work_time, summary,
                                    salary_mode, secret_key)
    preview_rows = ui.build_preview_rows(summary, wages, employees=staff, bundle=pay_bundle)
    ui.print_preview(preview_rows)

    # R10: восстанавливаемый снимок до генерации выходных файлов — повторное
    # завершение действительно возможно даже без правок.
    with _abort_on((OSError, ValueError), 'снимок запуска не сохранён'):
        save_session(month.data_array, month.year, month.month, journal=get_journal())
    # R04: отдельный текстовый список выходов ремонтников (без начислений).
    with _abort_on((OSError, ValueError), 'список ремонтников не записан',
                   tail='Сессия оставлена для --resume.'):
        repairmen_file = _write_repairmen_report(month.data_array, staff, month.year,
                                                 month.month, args.output_dir)

    ui.print_header('Отчеты')
    # R10: весь комплект — в едином обработчике; сбой не оставляет смесь
    # старых и новых отчётов, предыдущий завершённый комплект сохраняется.
    resume_hint = 'Сессия оставлена для --resume.'
    try:
        package_path = _write_reports(args, month, roster, work_time, summary, wages, rates,
                                      pay_bundle, preview_rows, repairmen_file, salary_mode)
    except Abort:
        raise
    except PermissionError as e:
        raise Abort(f'ОШИБКА: файл отчёта недоступен ({e}). Предыдущий комплект сохранён. '
                    f'{resume_hint}') from e
    except (OSError, ValueError, PayrollError) as e:
        raise Abort(f'ОШИБКА: отчёты/пакет не завершены ({e}). {resume_hint}') from e
    except Exception as e:
        raise Abort(f'ОШИБКА: пакет расчёта не сохранён ({e}). {resume_hint}') from e
    print(f'Пакет расчёта сохранён: {package_path}')


def _pay(args: Namespace, month: _Month, roster: _Roster, work_time: dict, summary: dict,
         salary_mode: bool, secret_key):
    """Начисления выбранной до правок модели: (bundle | None, wages, rates legacy).

    new — обязательна и фатальна при ошибках настройки, legacy — старый адаптер.
    Silent fallback запрещён (F05).
    """
    staff = roster.staff
    if roster.pay_ctx.mode == 'new':
        try:
            bundle = build_bundle(month.data_array, work_time, summary, month.year, month.month,
                                  args.pay_dir, salary_mode=salary_mode, employees=staff,
                                  rules_by_role=roster.rules_by_role)
        except PayrollError as e:
            raise Abort(f'ОШИБКА: новая модель должна применяться, но настройка ошибочна ({e}). '
                        f'Расчет прерван без fallback в legacy.') from e
        _warn_if_db_changed(args.pay_dir, roster.pay_ctx.db_meta)
        ui.print_pay_details(bundle)
        versions_file = join(args.output_dir,
                             f'payroll_versions_{month.year}_{month.month:02d}.json')
        bundle.save_versions(versions_file)
        print(f'Версии условий и календарь сохранены: {versions_file}')
        return bundle, bundle_to_wages(bundle), {}
    if not salary_mode:
        # Учёт времени без зарплаты: ставки не нужны, wage_rates.dat может отсутствовать.
        return None, calculate_wages(summary, rates={}, employees=staff), {}
    # Одно чтение ставок за запуск: тот же dict идет в расчет и в предупреждения.
    # Ключ — явно из памяти (F18), ошибки формата — предметно до расчёта.
    try:
        rates = config.load_wage_rates(key=secret_key)
    except ConfigError as e:
        raise Abort(f'ОШИБКА: {e}. Расчет прерван.') from e
    wages = calculate_wages(summary, rates=rates, employees=staff)
    for emp_id in summary:
        if rates.get(emp_id, 0) == 0:
            print(f'ВНИМАНИЕ: {display_name(emp_id, staff)} — ставка 0 '
                  f'(нет в wage_rates.dat или неверный ключ -k). Оклад будет нулевым, только молоко.')
    return None, wages, rates


def _warn_if_db_changed(db_path: str, before: dict | None) -> None:
    """R06/R15: источник не должен меняться за время длительного редактирования."""
    try:
        after = file_meta(db_path)
    except OSError:
        return
    before = before or {}
    if before.get('sha256') and after.get('sha256') and before['sha256'] != after['sha256']:
        print('ВНИМАНИЕ: справочник оплаты изменился за время редактирования — '
              'пакет фиксирует состояние на момент расчёта; проверьте ревизию.')


def _write_reports(args: Namespace, month: _Month, roster: _Roster, work_time: dict,
                   summary: dict, wages: dict, rates: dict, pay_bundle, preview_rows: list,
                   repairmen_file: str, salary_mode: bool) -> str:
    """Excel, персональные HTML, итоги на экране и пакет расчёта. Возвращает путь пакета."""
    staff, settlement_ids = roster.staff, roster.settlement_ids
    excel_file = build_excel(month.data_array, work_time, summary, wages,
                             employees=staff, bundle=pay_bundle,
                             output_dir=args.output_dir, year=month.year, month=month.month)
    html_files = []
    for emp_id in settlement_ids:
        if pay_bundle is not None and emp_id not in pay_bundle.results:
            print(f'Пропущен ID {emp_id}: исключён новой моделью (см. сводку причин).')
            continue
        html_file = build_html(emp_id, month.data_array, work_time, summary, wages,
                               employees=staff, bundle=pay_bundle, output_dir=args.output_dir)
        if html_file:
            html_files.append(html_file)
    if repairmen_file:
        html_files.append(repairmen_file)

    ui.print_salary_report(preview_rows, title=f'{month.title} — зарплата к начислению')
    ui.print_journal(get_journal())

    # R07: участники и результаты сверяются перед завершением.
    paid = pay_bundle.results if pay_bundle is not None else wages
    unpaid = [e for e in settlement_ids if e not in paid]
    if unpaid:
        what = 'без результата новой модели' if pay_bundle is not None else 'без начислений legacy'
        raise Abort(f'ОШИБКА: участники {what}: {unpaid}. Сессия оставлена для --resume.')

    reports = [file_meta(f) for f in ([excel_file] if excel_file else []) + html_files]
    dat_meta = file_meta(resolve_dat_path(args.file, args.data_dir)
                         if not month.resumed else _dat_file(args, month))
    excluded = dict(roster.sqlite_excluded)
    for emp_id in staff:
        if emp_id not in roster.settlement_set and emp_id not in excluded:
            excluded[emp_id] = (exclusion_reason(emp_id, staff, rules_by_role=roster.rules_by_role)
                                or 'без отметок за месяц')
    if pay_bundle is not None:
        snap = staff_snapshot(args.pay_dir, sorted(staff), roster.pay_ctx.month_start, staff)
        package = build_new_package(
            bundle=pay_bundle, data_array=month.data_array, journal=get_journal(),
            participants=list(settlement_ids), excluded=excluded,
            assignments=snap['assignments'], names=snap['names'], hires=snap['hires'],
            dat_meta=dat_meta,
            db_meta={**file_meta(args.pay_dir), 'schema_version': snap['schema_version']},
            reports=reports, prev_package_id=None)
    else:
        package = build_legacy_package(
            year=month.year, month=month.month, salary_mode=salary_mode,
            data_array=month.data_array, journal=get_journal(),
            summary=summary, wages=wages,
            rates_meta=file_meta(config.WAGE_RATES_FILE),
            participants=list(settlement_ids), excluded=excluded,
            names={e: display_name(e, staff) for e in settlement_ids},
            dat_meta=dat_meta, reports=reports, prev_package_id=None,
            rates=rates, roles={e: getattr(staff[e], 'role_id', '?')
                                for e in settlement_ids if e in staff})
    return save_package(package, directory=args.output_dir)


def _write_repairmen_report(data_array: dict, staff: dict, year: int, month: int,
                            output_dir: str) -> str:
    """Отдельный текстовый список выходов ремонтников (R04, spec §2).

    Роль 4 — без начислений и без проверки одиночных: одна отметка = выход.
    Возвращает путь к файлу или '' (нет ремонтников). В общую ведомость
    ремонтники не входят (контролируется правилами participates=False).
    """
    attendance = repairmen_attendance(data_array, staff or {}, year, month)
    if not attendance:
        return ''
    lines = [f'Ремонтники — выходы за {month:02d}.{year} (без начислений, spec §2)', '']
    for emp_id in sorted(attendance):
        days = attendance[emp_id]
        lines.append(f'{display_name(emp_id, staff)} (ID {emp_id}): {len(days)} дн.')
        lines.extend(f'  {d}' for d in days)
        lines.append('')
    os.makedirs(output_dir, exist_ok=True)
    file_name = join(output_dir, f'Ремонтники_{month:02d}_{year}.txt')
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).rstrip() + '\n')
    print(f'Файл {file_name} со списком ремонтников сформирован')
    return file_name


if __name__ == '__main__':
    main()
