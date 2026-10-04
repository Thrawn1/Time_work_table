"""Завершённый пакет расчёта: воспроизводимая ревизия месяца (Этап 6, F08).

Повторный запуск за тот же месяц не перезаписывает предыдущий результат:
каждая ревизия — новый файл ``payroll_ГГГГ_MM_revNN.json`` с уникальным
``package_id`` и ссылкой ``prev_package_id`` на предыдущую ревизию.
Пакет содержит всё нужное для объяснения сумм: период, алгоритм, точные
версии настроек/правил/назначений/шкалы, календарь по датам, отметки после
правок, журнал правок, входы и компоненты результатов, состав участников
и причины исключения, метаданные источников и отчётов.

Excel/HTML остаются файлами «последнего запуска»; их привязка к ревизии —
через контрольные суммы в пакете (по ним видно, какой комплект отчётов
соответствует ревизии).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

PACKAGE_VERSION = 1


def package_filename(year: int, month: int, rev: int) -> str:
    """Имя файла ревизии: payroll_2026_10_rev01.json."""
    return f'payroll_{year:04d}_{month:02d}_rev{rev:02d}.json'


def _rev_from_name(name: str, year: int, month: int) -> int | None:
    prefix, suffix = f'payroll_{year:04d}_{month:02d}_rev', '.json'
    if name.startswith(prefix) and name.endswith(suffix):
        try:
            return int(name[len(prefix):-len(suffix)])
        except ValueError:
            return None
    return None


def list_revisions(year: int, month: int, directory: str = '.') -> list[tuple[int, str]]:
    """Существующие ревизии [(rev, путь)] по возрастанию."""
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    out = []
    for name in names:
        rev = _rev_from_name(name, year, month)
        if rev is not None:
            out.append((rev, str(Path(directory) / name)))
    return sorted(out)


def _latest_package_id(path: str) -> str | None:
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return raw.get('package_id') if isinstance(raw, dict) else None


def next_revision(year: int, month: int, directory: str = '.') -> tuple[int, str | None]:
    """Следующий номер ревизии и package_id предыдущей (связь ревизий)."""
    revs = list_revisions(year, month, directory)
    if not revs:
        return 1, None
    return revs[-1][0] + 1, _latest_package_id(revs[-1][1])


def _sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def file_meta(path: str | None) -> dict:
    """Метаданные источника/отчёта: наличие, размер, mtime, sha256."""
    if not path or not os.path.exists(path):
        return {'path': path, 'exists': False, 'size': None,
                'mtime': None, 'sha256': None}
    try:
        st = os.stat(path)
        size, mtime = st.st_size, datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')
    except OSError:
        return {'path': path, 'exists': False, 'size': None,
                'mtime': None, 'sha256': None}
    return {'path': path, 'exists': True, 'size': size,
            'mtime': mtime, 'sha256': _sha256_file(path)}


def _str(value) -> str:
    return str(value)


def serialize_marks(data_array: dict) -> dict:
    """Отметки после правок: {дата: {id: [уход_iso, приход_iso, тег]}} (как в сессии)."""
    out: dict = {}
    for date_key, employees in (data_array or {}).items():
        day: dict = {}
        for emp_id, marks in employees.items():
            go = getattr(marks, 'go', marks[0])
            come = getattr(marks, 'come', marks[1])
            tag = getattr(marks, 'tag', marks[2])
            day[str(emp_id)] = [go.isoformat(), come.isoformat(), str(tag)]
        out[str(date_key)] = day
    return out


def serialize_rule(rule) -> dict:
    return {
        'role_id': rule.role_id, 'role_name': rule.role_name,
        'time_mode': rule.time_mode, 'shift_norm_hours': _str(rule.shift_norm_hours),
        'check_single_mark': bool(rule.check_single_mark),
        'participates': bool(rule.participates),
        'exclude_reason': rule.exclude_reason or '',
        'overtime_eligible': bool(rule.overtime_eligible),
        'full_month_eligible': bool(rule.full_month_eligible),
        'seniority_eligible': bool(rule.seniority_eligible),
        'overtime_coef': _str(rule.overtime_coef),
    }


def serialize_pay_inputs(inputs) -> dict:
    return {k: (_str(v) if isinstance(v, Decimal) else v)
            for k, v in vars(inputs).items()}


def serialize_pay_result(result) -> dict:
    return {k: (_str(v) if isinstance(v, Decimal) else v)
            for k, v in vars(result).items()}


def calendar_detail(year: int, month: int) -> dict:
    """Календарь месяца по датам (F08.2): D плюс классификация каждой даты."""
    from core.pay_calendar import classify_day, month_date_keys, working_days_in_month

    dates = {key: classify_day(key) for key in month_date_keys(year, month)}
    return {'D': working_days_in_month(year, month), 'dates': dates}


def _timedelta_hours(value) -> str:
    from core.money import timedelta_to_hours

    return _str(timedelta_to_hours(value))


def serialize_summary(summary: dict) -> dict:
    """Агрегаты legacy-пути: дни/часы/отпуск/прогул по сотрудникам."""
    out: dict = {}
    for emp_id, data in (summary or {}).items():
        work = getattr(data, 'work', data[0])
        holiday = getattr(data, 'holiday', data[1])
        out[str(emp_id)] = {
            'work': {'days': work.days if hasattr(work, 'days') else work[0],
                     'overtime_h': _timedelta_hours(work.overtime if hasattr(work, 'overtime') else work[1]),
                     'undertime_h': _timedelta_hours(work.undertime if hasattr(work, 'undertime') else work[2])},
            'holiday': {'days': holiday.days if hasattr(holiday, 'days') else holiday[0],
                        'overtime_h': _timedelta_hours(holiday.overtime if hasattr(holiday, 'overtime') else holiday[1]),
                        'undertime_h': _timedelta_hours(holiday.undertime if hasattr(holiday, 'undertime') else holiday[2])},
            'vacation_days': getattr(data, 'vacation_days', data[2]),
            'truancy_days': getattr(data, 'truancy_days', data[3]),
            'sick_days': getattr(data, 'sick_days', 0),
        }
    return out


def serialize_wages(wages: dict) -> dict:
    return {str(emp_id): {'salary': _str(w[0]), 'milk': _str(w[1]),
                          'total_with_milk': _str(w[2])}
            for emp_id, w in (wages or {}).items()}


SPEC_PAYROLL_VERSION = '1.0'


def _app_version() -> str | None:
    """Идентификатор сборки: git-rev при наличии, иначе None (R11)."""
    try:
        import subprocess

        out = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5)
        rev = (out.stdout or '').strip()
        return rev or None
    except Exception:
        return None


def _base_package(year: int, month: int, algorithm: str, salary_mode: bool,
                  calendar: dict, marks: dict, journal: list,
                  participants: list[int], excluded: dict,
                  sources: dict, reports: list[dict],
                  prev_package_id: str | None) -> dict:
    return {
        'package_version': PACKAGE_VERSION,
        'package_id': uuid.uuid4().hex,
        'prev_package_id': prev_package_id,
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'app': {'name': 'Time_work_table', 'python': platform.python_version(),
                'git_rev': _app_version()},
        'algorithm': algorithm,
        'algorithm_version': f'{algorithm}-v1',
        'spec_payroll': SPEC_PAYROLL_VERSION,
        'salary_mode': bool(salary_mode),
        'period': {'year': year, 'month': month},
        'calendar': calendar,
        'marks': marks,
        'journal': list(journal) if journal else [],
        'participants': sorted(int(e) for e in participants),
        'excluded': {str(k): str(v) for k, v in (excluded or {}).items()},
        'sources': sources,
        'reports': reports,
    }


def resolve_dat_path(file_name: str, data_dir: str = 'data') -> str | None:
    """Путь DAT-источника как в импорте (<data_dir>/<file>), иначе сам аргумент."""
    for candidate in (os.path.join(data_dir, file_name), file_name):
        if os.path.exists(candidate):
            return candidate
    return None


def staff_snapshot(db_path: str, emp_ids: list[int], month_start: str,
                   employees: dict | None = None) -> dict:
    """Снимок штата new-режима на 1-е число (R11): назначения с ОБЕИМИ границами,
    имена, даты приёма, версия схемы.

    R11: ошибки чтения — отказ (PayrollError), а не неполные значения.
    Не пишет в БД; отсутствие БД — пустой снимок.
    """
    from core.data_array import get_name_employee
    from core.payroll import PayrollError
    from core.pay_store import connect

    snap: dict = {'assignments': {}, 'names': {}, 'hires': {}, 'schema_version': None}
    if not os.path.exists(db_path):
        return snap
    import sqlite3 as _sqlite3

    try:
        con = connect(db_path)
    except _sqlite3.Error as e:
        raise PayrollError(f'{db_path}: не удалось открыть справочник ({e}).') from e
    try:
        try:
            row = con.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
            snap['schema_version'] = row['value'] if row else None
        except _sqlite3.Error as e:
            raise PayrollError(f'{db_path}: ошибка чтения версии схемы ({e}).') from e
        try:
            hires = {r['id']: r['hire_date'] for r in con.execute('SELECT id, hire_date FROM employees')}
        except _sqlite3.Error as e:
            raise PayrollError(f'{db_path}: ошибка чтения сотрудников ({e}).') from e
        for emp_id in emp_ids:
            try:
                row = con.execute(
                    'SELECT role_id, effective_from, effective_to FROM assignments'
                    ' WHERE emp_id=? AND effective_from <= ?'
                    ' AND (effective_to IS NULL OR effective_to >= ?)'
                    ' ORDER BY effective_from DESC LIMIT 1',
                    (int(emp_id), month_start, month_start)).fetchone()
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения назначений ({e}).') from e
            if row is None:
                snap['assignments'][str(emp_id)] = None
            else:
                snap['assignments'][str(emp_id)] = {
                    'role_id': row['role_id'],
                    'effective_from': row['effective_from'],
                    'effective_to': row['effective_to'],
                }
            snap['hires'][int(emp_id)] = hires.get(int(emp_id))
            snap['names'][int(emp_id)] = get_name_employee(int(emp_id), employees) or f'ID {emp_id}'
    finally:
        try:
            con.close()
        except Exception:
            pass
    return snap


def build_new_package(*, bundle, data_array: dict, journal: list,
                      participants: list[int], excluded: dict,
                      assignments: dict, names: dict, hires: dict,
                      dat_meta: dict, db_meta: dict, reports: list[dict],
                      prev_package_id: str | None) -> dict:
    """Пакет new-режима: полные PayInputs/PayResult объясняют каждый итог."""
    pkg = _base_package(
        bundle.year, bundle.month, 'new', bundle.salary_mode,
        calendar_detail(bundle.year, bundle.month), serialize_marks(data_array),
        journal, participants, excluded,
        {'dat': dat_meta, 'pay_db': db_meta}, reports, prev_package_id)
    pkg['settings'] = {
        'effective_from': bundle.settings_eff,
        'monthly_base': _str(bundle.monthly_base),
        'base_day_hours': bundle.base_day_hours,
        'full_month_bonus': _str(bundle.full_month_bonus),
    }
    pkg['seniority'] = {
        'effective_from': bundle.seniority_eff,
        'thresholds': [[y, _str(r)] for y, r in bundle.seniority_scale],
    }
    rules: dict = {}
    seen_roles: dict[int, dict] = {}
    for emp_id, res in bundle.results.items():
        seen_roles[res.rule.role_id] = serialize_rule(res.rule)
    for role_id in sorted(set(seen_roles) | set(bundle.rule_versions)):
        rules[str(role_id)] = {
            'effective_from': bundle.rule_versions.get(role_id),
            'rule': seen_roles.get(role_id),
        }
    pkg['rules'] = rules
    pkg['assignments'] = {str(k): v for k, v in assignments.items()}
    pkg['employees'] = {str(k): {'name': names.get(k, f'ID {k}'),
                                 'hire_date': hires.get(k)}
                        for k in participants}
    results: dict = {}
    for emp_id, res in bundle.results.items():
        results[str(emp_id)] = {
            'name': res.name,
            'role_id': res.rule.role_id,
            'inputs': serialize_pay_inputs(res.inputs),
            'result': serialize_pay_result(res.result),
        }
    pkg['results'] = results
    pkg['warnings'] = list(bundle.warnings)
    return pkg


def build_legacy_package(*, year: int, month: int, salary_mode: bool,
                         data_array: dict, journal: list,
                         summary: dict, wages: dict, rates_meta: dict,
                         participants: list[int], excluded: dict, names: dict,
                         dat_meta: dict, reports: list[dict],
                         prev_package_id: str | None,
                         rates: dict | None = None,
                         roles: dict | None = None) -> dict:
    """Пакет legacy-режима: итоги — ведомость wages + агрегаты summary.

    R11: включает фактически применённые ставки и роли сотрудников
    (без них independent replay невозможен); хеш файла ставок — только
    дополнение, а не замена содержимого.
    """
    calendar = calendar_detail(year, month)
    pkg = _base_package(
        year, month, 'legacy', salary_mode,
        calendar, serialize_marks(data_array),
        journal, participants, excluded,
        {'dat': dat_meta, 'rates': rates_meta}, reports, prev_package_id)
    pkg['workdays_D'] = calendar['D']
    pkg['summary'] = serialize_summary(summary)
    pkg['results'] = serialize_wages(wages)
    pkg['employees'] = {str(k): {'name': names.get(k, f'ID {k}')}
                        for k in participants}
    if rates is not None:
        pkg['applied_rates'] = {str(k): str(v) for k, v in rates.items()}
    if roles is not None:
        pkg['applied_roles'] = {str(k): str(v) for k, v in roles.items()}
    return pkg


def save_package(pkg: dict, directory: str = '.') -> str:
    """Атомарно записать ревизию из пакета. Возвращает путь. Не перезаписывает (R12).

    R12: номер выделяется созданием без перезаписи (O_EXCL) с повтором при
    конфликте; prev_package_id пересчитывается на свежий latest перед записью,
    поэтому два одновременных запуска получают разные rev, а цепочка не рвётся.
    Существующий пакет никогда не заменяется.
    """
    import errno as _errno

    year, month = pkg['period']['year'], pkg['period']['month']
    last_err: BaseException | None = None
    for _attempt in range(20):
        revs = list_revisions(year, month, directory)
        rev = (revs[-1][0] + 1) if revs else 1
        fresh_prev = _latest_package_id(revs[-1][1]) if revs else None
        name = package_filename(year, month, rev)
        path = str(Path(directory) / name)
        payload = dict(pkg)
        payload['revision'] = rev
        payload['prev_package_id'] = fresh_prev
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(path, flags, 0o666)
        except FileExistsError as e:
            last_err = e
            continue
        except OSError as e:
            if e.errno == _errno.EEXIST:
                last_err = e
                continue
            raise
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except BaseException as e:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise e
        # Обновить переданный словарь для вызывающего кода (путь/цепочка).
        pkg['revision'] = rev
        pkg['prev_package_id'] = fresh_prev
        pkg['package_id'] = payload['package_id']
        return path
    raise RuntimeError(
        f'не удалось выделить номер ревизии {year}-{month:02d} '
        f'(конфликт параллельных запусков): {last_err}')


def load_package(path: str) -> dict:
    """Прочитать и проверить пакет (версия формата)."""
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    if not isinstance(raw, dict) or raw.get('package_version') != PACKAGE_VERSION:
        raise ValueError(f'{path}: неподдерживаемая версия пакета '
                         f'(нужна {PACKAGE_VERSION})')
    return raw


def verify_package_structure(pkg: dict) -> list[str]:
    """Проверить структуру пакета (R11). Возвращает список ошибок (пусто — ок)."""
    errors: list[str] = []
    if not isinstance(pkg, dict):
        return ['корень пакета должен быть объектом']
    for field in ('package_version', 'package_id', 'period', 'algorithm',
                  'participants', 'results', 'calendar', 'marks', 'journal',
                  'sources', 'reports'):
        if field not in pkg:
            errors.append(f'отсутствует поле {field}')
    period = pkg.get('period', {})
    if not isinstance(period, dict) or 'year' not in period or 'month' not in period:
        errors.append('period должен содержать year/month')
    if pkg.get('algorithm') == 'new':
        for field in ('settings', 'rules', 'assignments', 'employees'):
            if field not in pkg:
                errors.append(f'new-пакет: отсутствует поле {field}')
        results = pkg.get('results', {})
        if isinstance(results, dict):
            for emp_id, entry in results.items():
                if not isinstance(entry, dict) or 'inputs' not in entry or 'result' not in entry:
                    errors.append(f'results[{emp_id}]: нужны inputs/result')
                if not isinstance(entry.get('inputs', None), dict):
                    errors.append(f'results[{emp_id}].inputs должен быть объектом')
    elif pkg.get('algorithm') == 'legacy':
        if 'applied_rates' not in pkg:
            errors.append('legacy-пакет: отсутствует applied_rates (R11)')
        if 'applied_roles' not in pkg:
            errors.append('legacy-пакет: отсутствует applied_roles (R11)')
    participants = pkg.get('participants', [])
    results = pkg.get('results', {})
    if isinstance(participants, list) and isinstance(results, dict):
        missing = [str(e) for e in participants if str(e) not in results]
        if missing:
            errors.append(
                f'участники без результата (нужен результат либо явный статус): '
                f'{", ".join(missing[:10])}')
    return errors


def replay_package(path: str) -> dict:
    """Независимо воспроизвести итог из пакета без текущей БД/DAT (R11).

    Пересчитывает new-результаты из сохранённых PayInputs через calculate_pay
    и сверяет с сохранёнными PayResult; для legacy сверяет суммы ведомости.
    Возвращает {'errors': [...], 'checked': N}. Пустые errors — итог воспроизведён.
    """
    from decimal import Decimal as _Decimal

    from core.pay_calc import PayInputs, calculate_pay

    pkg = load_package(path)
    struct_errors = verify_package_structure(pkg)
    if struct_errors:
        return {'errors': struct_errors, 'checked': 0}
    errors: list[str] = []
    checked = 0
    if pkg.get('algorithm') == 'new':
        for emp_id, entry in pkg['results'].items():
            checked += 1
            try:
                inp_raw = entry['inputs']
                inputs = PayInputs(
                    monthly_base=_Decimal(str(inp_raw['monthly_base'])),
                    base_day_hours=int(inp_raw['base_day_hours']),
                    full_month_bonus=_Decimal(str(inp_raw['full_month_bonus'])),
                    workdays=int(inp_raw['workdays']),
                    shift_norm_hours=_Decimal(str(inp_raw['shift_norm_hours'])),
                    fact_hours=_Decimal(str(inp_raw['fact_hours'])),
                    workdays_present=int(inp_raw['workdays_present']),
                    vacation_days=int(inp_raw.get('vacation_days', 0)),
                    truancy_days=int(inp_raw.get('truancy_days', 0)),
                    single_mark_issue=bool(inp_raw.get('single_mark_issue', False)),
                    employed_whole_month=bool(inp_raw.get('employed_whole_month', True)),
                    overtime_eligible=bool(inp_raw.get('overtime_eligible', False)),
                    full_month_eligible=bool(inp_raw.get('full_month_eligible', False)),
                    seniority_eligible=bool(inp_raw.get('seniority_eligible', False)),
                    overtime_coef=_Decimal(str(inp_raw.get('overtime_coef', '1.5'))),
                    seniority_rate=_Decimal(str(inp_raw.get('seniority_rate', '0'))),
                    milk_amount=_Decimal(str(inp_raw.get('milk_amount', '0'))),
                    sick_days=int(inp_raw.get('sick_days', 0)),
                )
                if pkg.get('salary_mode') is False:
                    # Режим без зарплаты: деньги нулевые, молоко сохранено.
                    want_total = _Decimal('0.00')
                    got_total = _Decimal(str(entry['result']['total']))
                    if got_total != want_total:
                        errors.append(f'results[{emp_id}].total: {got_total} != 0.00 (no-salary)')
                    continue
                recalc = calculate_pay(inputs)
                for key in ('ordinary_pay', 'overtime_bonus', 'full_month_bonus',
                            'seniority_bonus', 'total'):
                    want = _Decimal(str(entry['result'][key]))
                    got = getattr(recalc, key)
                    if want != got:
                        errors.append(
                            f'results[{emp_id}].{key}: в пакете {want}, пересчёт {got}')
            except (KeyError, ValueError, TypeError) as e:
                errors.append(f'results[{emp_id}]: не пересчитывается ({e})')
    else:
        for emp_id, entry in pkg.get('results', {}).items():
            checked += 1
            try:
                salary = _Decimal(str(entry['salary']))
                milk = _Decimal(str(entry['milk']))
                total = _Decimal(str(entry['total_with_milk']))
                if total != salary + milk:
                    errors.append(f'results[{emp_id}]: salary+milk != total')
            except (KeyError, ValueError, TypeError) as e:
                errors.append(f'results[{emp_id}]: не проверяется ({e})')
    return {'errors': errors, 'checked': checked}
