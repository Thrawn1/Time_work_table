import os
import sys
from argparse import ArgumentParser, Namespace
from datetime import timedelta as _td
from os.path import exists, join as _join

from core.cli import build_parser, resolve_period, resolve_secret_key, validate_period
from core.cli import parse_secret_key as parse_secret_key  # совместимость прежнего API main
from core.config import (
    MANUAL_EXCLUSIONS, ConfigError, load_config, preserve_config, set_secret_key, set_data_dir,
)
from core.file_parser import read_file_data
from core.data_array import (
    build_data_array, get_all_employees_in_data, get_employees_with_marks, is_included_in_settlement,
)
from core.analysis import analyze_for_print, clear_journal, get_journal, restore_journal
from core.review import current_settlement_ids, run_review, run_undertime_review
from core.calculations import calculate_hours_per_day, calculate_hours_per_month, calculate_wages
from core.excel_builder import build_excel
from core.html_builder import build_html
from core.constants import MONTHS_NAME_TO_RUSSIAN
from core.session import (
    SessionBackupError,
    load_session_full,
    session_exists,
    remove_session,
    backup_existing_session,
    set_session_dir,
    adopt_cwd_session,
    preserve_session_paths,
    set_session_context,
)


def main(argv: list[str] | None = None) -> None:
    """Точка входа; каждый запуск изолирован от предыдущих вызовов в процессе."""
    parser = build_parser()
    args = parser.parse_args(argv)
    with preserve_config(), preserve_session_paths():
        _run(args, parser)


def _write_repairmen_report(data_array: dict, staff: dict, year: int, month: int,
                            output_dir: str) -> str:
    """Отдельный текстовый список выходов ремонтников (R04, spec §2).

    Роль 4 — без начислений и без проверки одиночных: одна отметка = выход.
    Возвращает путь к файлу или '' (нет ремонтников/выходов). В общую ведомость
    ремонтники не входят (контролируется правилами participates=False).
    """
    from core.data_array import get_name_employee

    from core.roles import REPAIRMEN_ROLE_ID

    repairmen = [e for e, emp in (staff or {}).items()
                 if getattr(emp, 'role_id', None) == REPAIRMEN_ROLE_ID]
    if not repairmen:
        return ''
    prefix = f'{year:04d}-{month:02d}-'
    lines = [f'Ремонтники — выходы за {month:02d}.{year} (без начислений, spec §2)', '']
    for emp_id in sorted(repairmen):
        name = get_name_employee(emp_id, staff) or f'ID {emp_id}'
        days = sorted(d for d in data_array if d.startswith(prefix) and emp_id in data_array[d])
        lines.append(f'{name} (ID {emp_id}): {len(days)} дн.')
        for d in days:
            lines.append(f'  {d}')
        lines.append('')
    os.makedirs(output_dir, exist_ok=True)
    file_name = _join(output_dir, f'Ремонтники_{month:02d}_{year}.txt')
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).rstrip() + '\n')
    print(f'Файл {file_name} со списком ремонтников сформирован')
    return file_name


def _run(args: Namespace, parser: ArgumentParser) -> None:
    os.makedirs(args.output_dir, exist_ok=True)
    set_data_dir(args.data_dir)
    set_session_dir(args.output_dir)
    adopted = adopt_cwd_session()
    if adopted:
        print(f'Сессия перенесена из текущего каталога в {adopted} '
              f'(теперь сессии живут в --output-dir).')
    # Единый источник пути справочника оплаты на весь запуск (R08 может
    # переключить его при --resume на сохранённый в сессии).
    args.pay_dir = args.pay_dir or _join(args.data_dir, 'pay_directory.db')

    try:
        load_config()
    except ConfigError as e:
        print(f'ОШИБКА: {e}. Расчет прерван до правок и отчётов.')
        sys.exit(1)

    print('\n\t\tСистема расчета заработной платы и учета рабочего времени работников\n')
    secret_key, salary_mode = resolve_secret_key(args)

    # Ключ — только в памяти запуска (F18): на диск не пишется.
    set_secret_key(secret_key)
    if salary_mode:
        print('Режим: расчет зарплаты (ключ принят).')
    else:
        print('Режим: учет времени БЕЗ зарплаты (оклад = 0, молоко считается).')

    clear_journal()

    list_data: list[str] = []
    saved_context: dict | None = None
    if args.resume:
        if not session_exists():
            parser.error('сохранённая сессия для --resume не найдена')
        data_array, _saved_journal, saved_context = load_session_full()
        if data_array is None:
            print('Не удалось восстановить сессию!')
            sys.exit(1)
        restore_journal(_saved_journal)
        if not data_array:
            # Пустой месяц, восстановленный по периоду из заголовка сессии.
            from core.session import SESSION_FILE, _peek_period as _peek_resume_period
            _period = _peek_resume_period(SESSION_FILE) if exists(SESSION_FILE) else None
            if _period is None:
                print('Не удалось восстановить сессию: пустая сессия без периода!')
                sys.exit(1)
            year, month = _period
        else:
            first_date = next(iter(data_array))
            year, month = int(first_date[:4]), int(first_date[5:7])
        try:
            year, month = validate_period(year, month)
        except ValueError as e:
            print(f'ОШИБКА: период восстановленной сессии некорректен ({e}). Расчет прерван.')
            sys.exit(1)
        # R08: продолжение того же расчёта — тот же справочник/календарь.
        if saved_context:
            _saved_db = saved_context.get('db_path')
            if _saved_db and _saved_db != args.pay_dir:
                print(f'ВНИМАНИЕ: сессия сохранена со справочником {_saved_db}, '
                      f'а запрошен {args.pay_dir} — продолжаем расчёт сессии '
                      f'({_saved_db}). Для смены источника начните новый расчёт без --resume.')
                args.pay_dir = _saved_db
            _saved_period = saved_context.get('period')
            if isinstance(_saved_period, dict):
                try:
                    _sy = int(_saved_period.get('year', year))
                    _sm = int(_saved_period.get('month', month))
                    if (_sy, _sm) != (year, month):
                        print(f'ОШИБКА: период сессии {_sy:04d}-{_sm:02d} не совпадает '
                              f'с восстановленным {year:04d}-{month:02d}. '
                              f'Начните новый расчёт без --resume.')
                        sys.exit(1)
                except (ValueError, TypeError):
                    pass
        # Исключения сотрудников, выбранные оператором до обрыва, действуют и дальше.
        _saved_manual = (saved_context or {}).get('manual_excluded')
        if isinstance(_saved_manual, dict):
            for _k, _v in _saved_manual.items():
                try:
                    MANUAL_EXCLUSIONS[int(_k)] = str(_v)
                except (TypeError, ValueError):
                    continue
        session_state = 'resumed'
    else:
        year, month = resolve_period(args, parser)
        session_state = 'fresh'
        if session_exists():
            try:
                saved = backup_existing_session()
            except SessionBackupError as _be:
                print(f'ОШИБКА: не удалось сохранить существующую сессию ({_be}). '
                      f'Новый расчёт не начат, исходная сессия сохранена.')
                sys.exit(1)
            if saved:
                print(f'ВНИМАНИЕ: найден файл сессии. '
                      f'Он сохранён отдельно как {saved} и будет проигнорирован. '
                      f'Используйте --resume для восстановления.')
            else:
                print(f'ВНИМАНИЕ: найден файл сессии. '
                      'Он будет проигнорирован. Используйте --resume для восстановления.')
            session_state = 'ignored'
        try:
            list_data = read_file_data(args.file, year, month, args.data_dir)
        except (OSError, UnicodeDecodeError) as e:
            print(f'ОШИБКА: файл данных недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        if not list_data:
            _missing = not exists(_join(args.data_dir, args.file))
            if _missing:
                print('Нет данных для обработки!')
                sys.exit(1)
            if args.include_empty:
                print('ВНИМАНИЕ: за выбранный месяц отметок нет — '
                      'начинаем с пустой таблицы (--include-empty).')
                data_array = {}
            else:
                print('Нет данных для обработки!')
                sys.exit(1)
        else:
            try:
                data_array = build_data_array(list_data)
            except (ValueError, ConfigError, OSError) as e:
                print(f'ОШИБКА: календарь/справочник недоступен ({e}). Расчет прерван.')
                sys.exit(1)

    print(f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} год')

    # Единый контекст периода — до анализа и правок (R01–R03, spec §6–§7).
    from core.config import EMPLOYEES as _DAT_STAFF
    from core.payroll import PayrollError as _PayrollError
    from core.pay_context import (
        combined_staff_for_import as _combined_staff,
        diagnose_roster_divergence as _diagnose_roster,
        load_rules_map as _load_rules,
        resolve_context as _resolve_context,
        sqlite_excluded_map as _sqlite_excluded,
    )
    try:
        pay_ctx = _resolve_context(args.pay_dir, year, month, salary_mode)
    except _PayrollError as e:
        print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
        sys.exit(1)
    except (ValueError, ConfigError, OSError) as e:
        print(f'ОШИБКА: календарь/справочник недоступен ({e}). Расчет прерван.')
        sys.exit(1)
    # R16: конфликты календаря и его снимок — в контекст до расчёта.
    from core.file_parser import find_calendar_conflicts as _cal_conflicts
    try:
        _conflicts = _cal_conflicts(year)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f'ОШИБКА: календарь недоступен ({e}). Расчет прерван.')
        sys.exit(1)
    for _c in _conflicts:
        print(f'ВНИМАНИЕ (календарь): {_c} — праздник и перенесённый рабочий день '
              f'одновременно; применён приоритет праздника (R16).')
    try:
        from core.pay_package import calendar_detail as _cal_detail

        _cal_snapshot = _cal_detail(year, month)
        pay_ctx.workdays_D = _cal_snapshot.get('D')
        pay_ctx.calendar_dates = _cal_snapshot.get('dates')
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f'ОШИБКА: календарь недоступен ({e}). Расчет прерван.')
        sys.exit(1)
    # R08: календарь сессии должен совпадать — иначе явный новый пересчёт.
    if session_state == 'resumed' and saved_context:
        _saved_cal = saved_context.get('calendar')
        if isinstance(_saved_cal, dict) and _saved_cal != _cal_snapshot:
            print('ОШИБКА: производственный календарь изменился после сохранения сессии. '
                  'Норма месяца и классификация отметок разошлись бы. '
                  'Начните новый расчёт без --resume.')
            sys.exit(1)
    try:
        from core.pay_package import file_meta as _file_meta_ctx

        pay_ctx.db_meta = _file_meta_ctx(args.pay_dir)
    except Exception:
        pay_ctx.db_meta = None
    sqlite_excluded: dict = {}
    rules_by_role: dict | None = None
    if pay_ctx.mode == 'new':
        print('Режим модели: новая (SQLite-условия действуют на месяц). Ошибки настройки фатальны.')
        try:
            active_staff = _combined_staff(_DAT_STAFF, args.pay_dir, pay_ctx.month_start)
        except _PayrollError as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        except (ValueError, ConfigError) as e:
            print(f'ОШИБКА: календарь/справочник недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        # Импорт на объединённом штате: SQLite-only отметки не отбрасываются (R01).
        if session_state != 'resumed' and list_data:
            try:
                data_array = build_data_array(list_data, employees=active_staff)
            except (ValueError, ConfigError, OSError) as e:
                print(f'ОШИБКА: календарь/справочник недоступен ({e}). Расчет прерван.')
                sys.exit(1)
        try:
            sqlite_excluded = _sqlite_excluded(args.pay_dir, pay_ctx.month_start)
        except _PayrollError as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        # R02: действующие правила — до анализа и редактора; отсутствие — отказ.
        try:
            rules_by_role = _load_rules(args.pay_dir, pay_ctx.month_start, active_staff)
        except _PayrollError as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        pay_ctx.staff = active_staff
        pay_ctx.rules_by_role = rules_by_role
        for w in _diagnose_roster(pay_ctx, _DAT_STAFF, data_array):
            print(f'ВНИМАНИЕ (состав): {w}')
        if args.include_empty:
            emp_ids = list(active_staff.keys())
        else:
            _with_marks = {e for day in data_array.values() for e in day}
            emp_ids = [e for e in active_staff if e in _with_marks]
            _skipped = len(active_staff) - len(emp_ids)
            if _skipped:
                print(f'Без отметок за месяц пропущено сотрудников: {_skipped} '
                      f'(см. второй блок сводки; для включения — --include-empty).')
        # Единый состав: объединённый штат + SQLite-исключения (R01–R03).
        settlement_ids = [e for e in emp_ids
                          if is_included_in_settlement(e, active_staff)
                          and e not in sqlite_excluded]
    else:
        print('Режим модели: legacy (действующих SQLite-условий на месяц нет).')
        # R08: сессия сохранена в new-режиме, а текущий справочник даёт legacy —
        # осознанный отказ вместо расчёта по другой модели молча.
        if session_state == 'resumed' and saved_context and saved_context.get('mode') == 'new':
            print('ОШИБКА: сессия сохранена в новой модели, а текущий справочник даёт legacy. '
                  'Укажите исходный --pay-dir или начните новый расчёт без --resume.')
            sys.exit(1)
        active_staff = _DAT_STAFF
        if args.include_empty:
            emp_ids = get_all_employees_in_data(data_array, active_staff)
        else:
            emp_ids = get_employees_with_marks(data_array, active_staff)
            skipped = len(get_all_employees_in_data(data_array, active_staff)) - len(emp_ids)
            if skipped:
                print(f'Без отметок за месяц пропущено сотрудников: {skipped} '
                      f'(см. второй блок сводки; для включения — --include-empty).')
        settlement_ids = [e for e in emp_ids if is_included_in_settlement(e, active_staff)]
    settlement_set = set(settlement_ids)
    if pay_ctx.mode == 'new':
        # До правок: отсутствие обязательного назначения — фатально, без silent fallback.
        from core.pay_store import connect as _connect, get_assignment as _get_assign
        try:
            _con = _connect(args.pay_dir)
            try:
                _missing = []
                for emp_id in settlement_ids:
                    if emp_id in sqlite_excluded:
                        continue
                    if _get_assign(_con, emp_id, pay_ctx.month_start) is None:
                        _missing.append(emp_id)
            finally:
                try:
                    _con.close()
                except Exception:
                    pass
        except Exception as e:
            print(f'ОШИБКА: справочник оплаты недоступен ({e}). Расчет прерван.')
            sys.exit(1)
        if _missing:
            from core.data_array import get_name_employee as _nm
            _names = ', '.join(f'{_nm(e, active_staff) or e}' for e in _missing)
            print(f'ОШИБКА: новая модель должна применяться, но нет назначения SQLite '
                  f'на {pay_ctx.month_start} для: {_names}. Расчет прерван без fallback.')
            sys.exit(1)
    # R08/R10: контекст сессии — до правок, чтобы каждое сохранение несло тот же смысл.
    session_ctx = {
        'db_path': args.pay_dir,
        'mode': pay_ctx.mode,
        'salary_mode': bool(salary_mode),
        'period': {'year': year, 'month': month},
        'month_start': pay_ctx.month_start,
        'calendar': _cal_snapshot,
        'participants': sorted(settlement_ids),
        'manual_excluded': {str(k): v for k, v in MANUAL_EXCLUSIONS.items()},
        'dat_file': args.file if session_state != 'resumed' else (
            (saved_context.get('dat_file') if saved_context else None)),
    }
    set_session_context(session_ctx)

    from core.ui import (
        build_dashboard_rows,
        build_preview_rows,
        build_repairmen_lines,
        build_start_info,
        print_dashboard,
        print_header,
        print_journal,
        print_preview,
        print_repairmen,
        print_salary_report,
        print_start_screen,
    )

    rows_read = len(list_data) if list_data else sum(len(day) for day in data_array.values())
    print_start_screen(build_start_info(
        args.file if session_state != 'resumed' else '(сессия)',
        year, month, rows_read, len(settlement_ids), session_state,
        output_dir=args.output_dir, data_dir=args.data_dir,
    ))

    print_header('Проверка')
    _STAFF = active_staff
    # Ремонтники — без начислений и проверок: только дни выходов, сразу на экране.
    print_repairmen(build_repairmen_lines(data_array, _STAFF, year, month))

    _dashboard_ids = (list(active_staff.keys()) if pay_ctx.mode == 'new'
                      else get_all_employees_in_data(data_array, _STAFF))
    _dashboard_title = f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — сводка'
    if args.no_edit:
        # Без правок: подробный список проблем каждого участника и сводная таблица.
        for emp_id in settlement_ids:
            analyze_for_print(data_array, emp_id, year, month,
                              employees=_STAFF, rules_by_role=rules_by_role)
        print_dashboard(
            build_dashboard_rows(data_array, _dashboard_ids, year, month,
                                 employees=_STAFF, extra_excluded=sqlite_excluded or None,
                                 rules_by_role=rules_by_role, included_ids=settlement_set),
            title=_dashboard_title,
        )
    else:
        print_header('Правки')

        def _persist_exclusions() -> None:
            """Ручные исключения и состав участников — в контекст сессии (для --resume)."""
            session_ctx['manual_excluded'] = {str(k): v for k, v in MANUAL_EXCLUSIONS.items()}
            session_ctx['participants'] = sorted(
                current_settlement_ids(emp_ids, active_staff, sqlite_excluded))
            set_session_context(session_ctx)
            try:
                from core.session import save_session as _save_ctx

                _save_ctx(data_array, year, month, journal=get_journal())
            except (OSError, ValueError) as e:
                print(f'ВНИМАНИЕ: исключение не записано в сессию ({e}); '
                      f'при --resume его придётся выбрать заново.')

        try:
            run_review(data_array, _STAFF, emp_ids, year, month,
                       rules_by_role=rules_by_role, extra_excluded=sqlite_excluded,
                       on_exclusion_change=_persist_exclusions, title=_dashboard_title)
            # Пропуски закрыты — теперь недоработки (в том числе от автозаполнения):
            # посмотреть все разом и поправить по желанию, до расчёта и Excel.
            run_undertime_review(data_array, _STAFF, emp_ids, year, month,
                                 rules_by_role=rules_by_role, extra_excluded=sqlite_excluded)
        except OSError as e:
            print(f'ОШИБКА: сессия правок не сохранена ({e}). Расчет прерван; '
                  f'повторите запуск с --resume.')
            sys.exit(1)
        # Состав мог измениться: сотрудников исключили или вернули в расчёт.
        settlement_ids = current_settlement_ids(emp_ids, active_staff, sqlite_excluded)
        settlement_set = set(settlement_ids)
        session_ctx['participants'] = sorted(settlement_ids)
        session_ctx['manual_excluded'] = {str(k): v for k, v in MANUAL_EXCLUSIONS.items()}
        set_session_context(session_ctx)
        print_dashboard(
            build_dashboard_rows(data_array, _dashboard_ids, year, month,
                                 employees=_STAFF, extra_excluded=sqlite_excluded or None,
                                 rules_by_role=rules_by_role, included_ids=settlement_set),
            title=f'{_dashboard_title} (итог перед расчётом)',
        )

    print_header('Расчет')
    try:
        work_time_all = calculate_hours_per_day(
            data_array, employees=_STAFF, rules_by_role=rules_by_role)
    except ValueError as e:
        print(f'ОШИБКА: учёт времени невозможен ({e}). Расчет прерван.')
        sys.exit(1)
    except (OSError, ConfigError) as e:
        print(f'ОШИБКА: календарь/справочник недоступен ({e}). Расчет прерван.')
        sys.exit(1)
    work_time = {
        date_key: {emp_id: val for emp_id, val in emps.items() if emp_id in settlement_set}
        for date_key, emps in work_time_all.items()
    }
    work_time = {d: e for d, e in work_time.items() if e}
    summary, _restructured = calculate_hours_per_month(work_time)
    # R07: каждый включённый сотрудник имеет месячную запись — нулевую при
    # отсутствии отметок, а не пропадает из summary/денег.
    from core.day_models import EmployeeMonth, HolidayGroup, WorkGroup

    for emp_id in settlement_ids:
        if emp_id not in summary:
            summary[emp_id] = EmployeeMonth(
                work=WorkGroup(days=0, overtime=_td(0), undertime=_td(0)),
                holiday=HolidayGroup(days=0, overtime=_td(0), undertime=_td(0), worked=_td(0)),
                vacation_days=0,
                truancy_days=0,
            )
    _sick_days = {e: s.sick_days for e, s in summary.items() if getattr(s, 'sick_days', 0)}
    if _sick_days:
        from core.data_array import get_name_employee as _sick_name

        print('Больничные дни (программа их не оплачивает — оплата OPEN, spec п.9):')
        for _e, _n in sorted(_sick_days.items()):
            print(f'  {_sick_name(_e, _STAFF) or _e}: {_n} дн.')
    # Режим уже выбран до правок (pay_ctx): new — обязателен и фатален
    # при ошибках настройки, legacy — старый адаптер. Silent fallback запрещён (F05).
    from core.payroll import PayrollError, build_bundle, bundle_to_wages
    pay_bundle = None
    if pay_ctx.mode == 'new':
        try:
            pay_bundle = build_bundle(data_array, work_time, summary, year, month,
                                      args.pay_dir, salary_mode=salary_mode,
                                      employees=active_staff, rules_by_role=rules_by_role)
        except PayrollError as e:
            print(f'ОШИБКА: новая модель должна применяться, но настройка ошибочна ({e}). '
                  f'Расчет прерван без fallback в legacy.')
            sys.exit(1)
        # R06/R15: источник не должен меняться за время длительного редактирования.
        try:
            from core.pay_package import file_meta as _fm_after

            _db_after = _fm_after(args.pay_dir)
            _db_before = pay_ctx.db_meta or {}
            if _db_before.get('sha256') and _db_after.get('sha256') \
                    and _db_before['sha256'] != _db_after['sha256']:
                print('ВНИМАНИЕ: справочник оплаты изменился за время редактирования — '
                      'пакет фиксирует состояние на момент расчёта; проверьте ревизию.')
        except Exception:
            pass
    rates: dict = {}
    if pay_bundle is not None:
        wages = bundle_to_wages(pay_bundle)
        from core.ui import print_pay_details
        print_pay_details(pay_bundle)
        versions_file = _join(args.output_dir, f'payroll_versions_{year}_{month:02d}.json')
        pay_bundle.save_versions(versions_file)
        print(f'Версии условий и календарь сохранены: {versions_file}')
    elif salary_mode:
        from core.config import load_wage_rates as _load_rates
        # Одно чтение ставок за запуск: тот же dict идет в расчет и в предупреждения.
        # Ключ — явно из памяти (F18), ошибки формата — предметно до расчёта.
        try:
            rates = _load_rates(key=secret_key)
        except ConfigError as e:
            print(f'ОШИБКА: {e}. Расчет прерван.')
            sys.exit(1)
        wages = calculate_wages(summary, rates=rates, employees=_STAFF)
    else:
        # Учёт времени без зарплаты: ставки не нужны, wage_rates.dat может отсутствовать.
        wages = calculate_wages(summary, rates=rates, employees=_STAFF)
    from core.data_array import get_name_employee
    if pay_bundle is None and salary_mode:
        zero_rate = [e for e in summary if rates.get(e, 0) == 0]
        for emp_id in zero_rate:
            print(f'ВНИМАНИЕ: {get_name_employee(emp_id, _STAFF) or emp_id} — ставка 0 '
                  f'(нет в wage_rates.dat или неверный ключ -k). Оклад будет нулевым, только молоко.')
    preview_rows = build_preview_rows(summary, wages, employees=_STAFF, bundle=pay_bundle)
    print_preview(preview_rows)

    # R10: восстанавливаемый снимок до генерации выходных файлов — повторное
    # завершение действительно возможно даже без правок.
    try:
        from core.session import save_session as _snapshot_session

        _snapshot_session(data_array, year, month, journal=get_journal())
    except (OSError, ValueError) as e:
        print(f'ОШИБКА: снимок запуска не сохранён ({e}). Расчет прерван.')
        sys.exit(1)

    # R04: отдельный текстовый список выходов ремонтников (без начислений).
    repairmen_file = ''
    try:
        repairmen_file = _write_repairmen_report(data_array, active_staff, year, month,
                                                 args.output_dir)
    except (OSError, ValueError) as e:
        print(f'ОШИБКА: список ремонтников не записан ({e}). Сессия оставлена для --resume.')
        sys.exit(1)

    print_header('Отчеты')
    # R10: весь комплект — в едином обработчике; сбой не оставляет смесь
    # старых и новых отчётов, предыдущий завершённый комплект сохраняется.
    try:
        excel_file = build_excel(data_array, work_time, summary, wages,
                                 employees=_STAFF, bundle=pay_bundle,
                                 output_dir=args.output_dir, year=year, month=month)

        html_files = []
        for emp_id in settlement_ids:
            if emp_id not in summary:
                print(f'Пропущен ID {emp_id}: нет данных расчета (роль не поддерживается?).')
                continue
            if pay_bundle is not None and emp_id not in pay_bundle.results:
                print(f'Пропущен ID {emp_id}: исключён новой моделью (см. сводку причин).')
                continue
            _html = build_html(emp_id, data_array, work_time, summary, wages,
                               employees=_STAFF, bundle=pay_bundle, output_dir=args.output_dir)
            if _html:
                html_files.append(_html)
        if repairmen_file:
            html_files.append(repairmen_file)

        print_salary_report(preview_rows,
                            title=f'{MONTHS_NAME_TO_RUSSIAN[month]} {year} — зарплата к начислению')

        print_journal(get_journal())
        # R07: участники и результаты сверяются перед завершением.
        if pay_bundle is not None:
            _missing_res = [e for e in settlement_ids if e not in pay_bundle.results]
            if _missing_res:
                print(f'ОШИБКА: участники без результата новой модели: {_missing_res}. '
                      f'Сессия оставлена для --resume.')
                sys.exit(1)
        else:
            _missing_w = [e for e in settlement_ids if e not in wages]
            if _missing_w:
                print(f'ОШИБКА: участники без начислений legacy: {_missing_w}. '
                      f'Сессия оставлена для --resume.')
                sys.exit(1)
        from core.pay_package import (
            build_legacy_package, build_new_package, file_meta,
            resolve_dat_path, save_package, staff_snapshot,
        )
        _reports = (([file_meta(excel_file)] if excel_file else [])
                    + [file_meta(f) for f in html_files])
        _dat = resolve_dat_path(args.file, args.data_dir) if session_state != 'resumed' else (
            (saved_context.get('dat_file') if saved_context else None))
        if pay_bundle is not None:
            _snap = staff_snapshot(args.pay_dir, sorted(active_staff),
                                   pay_ctx.month_start, active_staff)
            from core.data_array import exclusion_reason as _excl_reason
            _excluded_all = dict(sqlite_excluded)
            for _e in active_staff:
                if _e not in settlement_set and _e not in _excluded_all:
                    _excluded_all[_e] = _excl_reason(_e, active_staff) or 'без отметок за месяц'
            _pkg = build_new_package(
                bundle=pay_bundle, data_array=data_array, journal=get_journal(),
                participants=list(settlement_ids), excluded=_excluded_all,
                assignments=_snap['assignments'], names=_snap['names'], hires=_snap['hires'],
                dat_meta=file_meta(_dat),
                db_meta={**file_meta(args.pay_dir), 'schema_version': _snap['schema_version']},
                reports=_reports, prev_package_id=None)
        else:
            from core.config import WAGE_RATES_FILE
            from core.data_array import exclusion_reason as _excl_reason
            from core.data_array import get_name_employee as _nm_pkg
            _pkg = build_legacy_package(
                year=year, month=month, salary_mode=salary_mode,
                data_array=data_array, journal=get_journal(),
                summary=summary, wages=wages,
                rates_meta=file_meta(WAGE_RATES_FILE),
                participants=list(settlement_ids),
                excluded={_e: (_excl_reason(_e, _STAFF) or 'без отметок за месяц')
                          for _e in get_all_employees_in_data(data_array, _STAFF)
                          if _e not in settlement_set},
                names={_e: (_nm_pkg(_e, _STAFF) or f'ID {_e}') for _e in settlement_ids},
                dat_meta=file_meta(_dat),
                reports=_reports, prev_package_id=None,
                rates=rates, roles={e: getattr(_STAFF[e], 'role_id', '?')
                                    for e in settlement_ids if e in _STAFF})
        package_path = save_package(_pkg, directory=args.output_dir)
    except PermissionError as e:
        print(f'ОШИБКА: файл отчёта недоступен ({e}). Предыдущий комплект сохранён. '
              f'Сессия оставлена для --resume.')
        sys.exit(1)
    except (OSError, ValueError, _PayrollError) as e:
        print(f'ОШИБКА: отчёты/пакет не завершены ({e}). Сессия оставлена для --resume.')
        sys.exit(1)
    except Exception as e:
        print(f'ОШИБКА: пакет расчёта не сохранён ({e}). '
              f'Сессия оставлена для --resume.')
        sys.exit(1)
    print(f'Пакет расчёта сохранён: {package_path}')
    remove_session()
    set_session_context(None)


if __name__ == '__main__':
    main()
