"""SQLite-хранилище справочников новой модели оплаты (план roles_rates, §4/шаг 1).

Целевой файл — data/pay_directory.db (новый). Существующие company.db
(оргструктура), line.db/line_new.db (сырые строки) НЕ трогаем и не
перезаписываем. Суммы — целые копейки, коэффициенты/проценты — TEXT Decimal,
даты действия — ISO 'YYYY-MM-DD'. История сохраняется версиями: новая дата
действия добавляет запись, а не перезаписывает прошлое.

Сущности: общие условия оплаты, сотрудники, роли, версии правил ролей,
назначения ролей, стажевая шкала, персональные исключения.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from core.money import as_decimal, quantize_money
from core.roles import DEFAULT_RULES, RoleRule

SCHEMA_VERSION = 1

DEFAULT_DB_PATH = 'data/pay_directory.db'

#: Дата перехода на новую схему: январь 2026 (решение 2026-09-11).
#: Периоды раньше неё считает старый режим (legacy-адаптер).
DEFAULT_TRANSITION = '2026-01-01'

_DDL = """
CREATE TABLE IF NOT EXISTS schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pay_settings(
    effective_from TEXT PRIMARY KEY,
    monthly_base_cents INTEGER NOT NULL CHECK(monthly_base_cents > 0),
    base_day_hours INTEGER NOT NULL CHECK(base_day_hours > 0),
    full_month_bonus_cents INTEGER NOT NULL CHECK(full_month_bonus_cents >= 0),
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS roles(
    id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS role_rules(
    role_id INTEGER NOT NULL REFERENCES roles(id),
    effective_from TEXT NOT NULL,
    time_mode TEXT NOT NULL CHECK(time_mode IN ('actual','fixed_shift')),
    shift_norm_hours TEXT NOT NULL,
    check_single_mark INTEGER NOT NULL CHECK(check_single_mark IN (0,1)),
    participates INTEGER NOT NULL CHECK(participates IN (0,1)),
    exclude_reason TEXT NOT NULL DEFAULT '',
    overtime_eligible INTEGER NOT NULL CHECK(overtime_eligible IN (0,1)),
    full_month_eligible INTEGER NOT NULL CHECK(full_month_eligible IN (0,1)),
    seniority_eligible INTEGER NOT NULL CHECK(seniority_eligible IN (0,1)),
    overtime_coef TEXT NOT NULL,
    PRIMARY KEY(role_id, effective_from));
CREATE TABLE IF NOT EXISTS employees(
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL, last_name TEXT NOT NULL, hire_date TEXT);
CREATE TABLE IF NOT EXISTS assignments(
    emp_id INTEGER NOT NULL REFERENCES employees(id),
    role_id INTEGER NOT NULL REFERENCES roles(id),
    effective_from TEXT NOT NULL, effective_to TEXT,
    PRIMARY KEY(emp_id, effective_from));
CREATE TABLE IF NOT EXISTS seniority_scale(
    effective_from TEXT NOT NULL,
    threshold_years INTEGER NOT NULL CHECK(threshold_years >= 0),
    rate TEXT NOT NULL,
    PRIMARY KEY(effective_from, threshold_years));
CREATE TABLE IF NOT EXISTS settlement_exceptions(
    emp_id INTEGER PRIMARY KEY, reason TEXT NOT NULL);
"""


@dataclass(frozen=True)
class PaySettings:
    effective_from: str
    monthly_base: Decimal
    base_day_hours: int
    full_month_bonus: Decimal


def connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Создать схему (безопасный повторный вызов). Версия схемы проверяется."""
    parent = Path(db_path).parent
    if str(parent) not in ('', '.'):
        parent.mkdir(parents=True, exist_ok=True)
    con = connect(db_path)
    try:
        con.executescript(_DDL)
        row = con.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        if row is None:
            con.execute("INSERT INTO schema_meta(key, value) VALUES('schema_version','1')")
            con.commit()
        elif row['value'] != str(SCHEMA_VERSION):
            raise RuntimeError(
                f'Неизвестная версия схемы БД {row["value"]}: '
                f'поддерживается {SCHEMA_VERSION}. Перенос не выполняем.'
            )
    except Exception:
        con.close()
        raise
    return con


def _check_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'Некорректная дата действия {value!r}: нужен ISO YYYY-MM-DD') from None
    return value


def _cents(amount: Decimal | int | str, field: str) -> int:
    value = quantize_money(as_decimal(amount))
    if value < 0:
        raise ValueError(f'{field}: отрицательная сумма {value}')
    return int(value * 100)


def _cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal('100')).quantize(Decimal('0.01'))


# --- Общие условия оплаты ----------------------------------------------------

def set_pay_settings(con: sqlite3.Connection, effective_from: str,
                     monthly_base: Decimal | str = Decimal('60000.00'),
                     base_day_hours: int = 8,
                     full_month_bonus: Decimal | str = Decimal('5000.00')) -> None:
    _check_date(effective_from)
    if int(base_day_hours) <= 0:
        raise ValueError('base_day_hours должен быть > 0')
    try:
        con.execute(
            'INSERT INTO pay_settings(effective_from, monthly_base_cents, base_day_hours,'
            ' full_month_bonus_cents, created_at) VALUES(?,?,?,?,?)',
            (effective_from, _cents(monthly_base, 'monthly_base'), int(base_day_hours),
             _cents(full_month_bonus, 'full_month_bonus'),
             datetime.now().isoformat(timespec='seconds')),
    )
    except sqlite3.IntegrityError:
        raise ValueError(
            f'Условия на {effective_from} уже заданы: конфликт версий молча не перезаписываем. '
            f'Введите новую дату действия или исправьте запись явно.') from None
    con.commit()


def get_pay_settings(con: sqlite3.Connection, on_date: str) -> PaySettings | None:
    _check_date(on_date)
    row = con.execute(
        'SELECT * FROM pay_settings WHERE effective_from <= ? ORDER BY effective_from DESC LIMIT 1',
        (on_date,),
    ).fetchone()
    if row is None:
        return None
    return PaySettings(
        effective_from=row['effective_from'],
        monthly_base=_cents_to_decimal(row['monthly_base_cents']),
        base_day_hours=row['base_day_hours'],
        full_month_bonus=_cents_to_decimal(row['full_month_bonus_cents']),
    )


# --- Роли и версии правил -----------------------------------------------------

def upsert_role(con: sqlite3.Connection, role_id: int, name: str) -> None:
    if not name.strip():
        raise ValueError(f'Роль {role_id}: пустое название')
    con.execute(
        'INSERT INTO roles(id, name) VALUES(?,?)'
        ' ON CONFLICT(id) DO UPDATE SET name=excluded.name',
        (int(role_id), name.strip()),
    )
    con.commit()


def set_role_rule(con: sqlite3.Connection, rule: RoleRule, effective_from: str) -> None:
    _check_date(effective_from)
    if rule.time_mode not in ('actual', 'fixed_shift'):
        raise ValueError(f'Роль {rule.role_id}: неизвестный time_mode {rule.time_mode!r}')
    if as_decimal(rule.shift_norm_hours) <= 0:
        raise ValueError(f'Роль {rule.role_id}: норма смены должна быть > 0')
    if as_decimal(rule.overtime_coef) <= 0:
        raise ValueError(f'Роль {rule.role_id}: коэффициент переработки должен быть > 0')
    if con.execute('SELECT 1 FROM roles WHERE id=?', (rule.role_id,)).fetchone() is None:
        raise ValueError(f'Роль {rule.role_id}: сначала заведите роль (upsert_role)')
    try:
        con.execute(
            'INSERT INTO role_rules(role_id, effective_from, time_mode, shift_norm_hours,'
            ' check_single_mark, participates, exclude_reason, overtime_eligible,'
            ' full_month_eligible, seniority_eligible, overtime_coef)'
            ' VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (rule.role_id, effective_from, rule.time_mode, str(rule.shift_norm_hours),
             int(rule.check_single_mark), int(rule.participates), rule.exclude_reason,
             int(rule.overtime_eligible), int(rule.full_month_eligible),
             int(rule.seniority_eligible), str(rule.overtime_coef)),
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f'Правило роли {rule.role_id} на {effective_from} уже задано: '
            f'конфликт версий молча не перезаписываем.') from None
    con.commit()


def _row_to_rule(row: sqlite3.Row, fallback_name: str = '') -> RoleRule:
    return RoleRule(
        role_id=row['role_id'], role_name=row['name'] or fallback_name,
        time_mode=row['time_mode'], shift_norm_hours=Decimal(row['shift_norm_hours']),
        check_single_mark=bool(row['check_single_mark']),
        participates=bool(row['participates']),
        exclude_reason=row['exclude_reason'] or '',
        overtime_eligible=bool(row['overtime_eligible']),
        full_month_eligible=bool(row['full_month_eligible']),
        seniority_eligible=bool(row['seniority_eligible']),
        overtime_coef=Decimal(row['overtime_coef']),
    )


def get_role_rule(con: sqlite3.Connection, role_id: int, on_date: str) -> RoleRule | None:
    _check_date(on_date)
    row = con.execute(
        'SELECT r.*, roles.name AS name FROM role_rules r JOIN roles ON roles.id=r.role_id'
        ' WHERE r.role_id=? AND r.effective_from <= ? ORDER BY r.effective_from DESC LIMIT 1',
        (role_id, on_date),
    ).fetchone()
    return _row_to_rule(row) if row else None


def role_rule_history(con: sqlite3.Connection, role_id: int) -> list[RoleRule]:
    rows = con.execute(
        'SELECT r.*, roles.name AS name FROM role_rules r JOIN roles ON roles.id=r.role_id'
        ' WHERE r.role_id=? ORDER BY r.effective_from', (role_id,),
    ).fetchall()
    return [_row_to_rule(r) for r in rows]


# --- Сотрудники и назначения ---------------------------------------------------

def upsert_employee(con: sqlite3.Connection, emp_id: int, first_name: str,
                    last_name: str, hire_date: str | None = None) -> None:
    if hire_date is not None:
        _check_date(hire_date)
    con.execute(
        'INSERT INTO employees(id, first_name, last_name, hire_date) VALUES(?,?,?,?)'
        ' ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name,'
        ' last_name=excluded.last_name, hire_date=excluded.hire_date',
        (int(emp_id), first_name.strip(), last_name.strip(), hire_date),
    )
    con.commit()


def assign_role(con: sqlite3.Connection, emp_id: int, role_id: int,
                effective_from: str, effective_to: str | None = None) -> None:
    _check_date(effective_from)
    if effective_to is not None:
        _check_date(effective_to)
        if effective_to < effective_from:
            raise ValueError('effective_to раньше effective_from')
    if con.execute('SELECT 1 FROM employees WHERE id=?', (emp_id,)).fetchone() is None:
        raise ValueError(f'Сотрудник {emp_id}: сначала заведите карточку (upsert_employee)')
    overlap = con.execute(
        'SELECT effective_from, effective_to FROM assignments WHERE emp_id=?'
        ' AND (effective_to IS NULL OR effective_to >= ?)'
        ' AND (effective_to IS NULL OR ? IS NULL OR effective_from <= ?)',
        (emp_id, effective_from, effective_to, effective_to or '9999-12-31'),
    ).fetchall()
    # Точная проверка пересечений периодов.
    for row in overlap:
        other_from, other_to = row['effective_from'], row['effective_to']
        new_to = effective_to or '9999-12-31'
        other_to = other_to or '9999-12-31'
        if not (new_to < other_from or effective_from > other_to):
            raise ValueError(
                f'Сотрудник {emp_id}: пересекающееся назначение '
                f'[{effective_from}..{effective_to or "..."}] ∩ [{other_from}..{row["effective_to"] or "..."}]'
            )
    con.execute(
        'INSERT INTO assignments(emp_id, role_id, effective_from, effective_to) VALUES(?,?,?,?)',
        (emp_id, role_id, effective_from, effective_to),
    )
    con.commit()


def get_assignment(con: sqlite3.Connection, emp_id: int, on_date: str) -> tuple[int, str | None] | None:
    """Назначение (role_id, effective_to) на дату или None."""
    _check_date(on_date)
    row = con.execute(
        'SELECT role_id, effective_to FROM assignments WHERE emp_id=?'
        ' AND effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?)'
        ' ORDER BY effective_from DESC LIMIT 1',
        (emp_id, on_date, on_date),
    ).fetchone()
    return (row['role_id'], row['effective_to']) if row else None


# --- Стажевая шкала ------------------------------------------------------------

def set_seniority_scale(con: sqlite3.Connection, effective_from: str,
                        scale: list[tuple[int, Decimal | str]]) -> None:
    """Шкала [(порог_лет, доля)]; версия целиком, пустая запрещена."""
    _check_date(effective_from)
    if not scale:
        raise ValueError('Стажевая шкала: пустой набор порогов')
    seen = set()
    for years, rate in scale:
        if int(years) < 0 or int(years) in seen:
            raise ValueError(f'Стажевая шкала: некорректный порог {years}')
        seen.add(int(years))
        value = as_decimal(rate)
        if value < 0 or value > 1:
            raise ValueError(f'Стажевая шкала: доля {rate} вне [0..1]')
    with con:
        for years, rate in scale:
            try:
                con.execute(
                    'INSERT INTO seniority_scale(effective_from, threshold_years, rate)'
                    ' VALUES(?,?,?)',
                    (effective_from, int(years), str(as_decimal(rate))),
                )
            except sqlite3.IntegrityError:
                raise ValueError(
                    f'Стажевая шкала на {effective_from} уже задана: '
                    f'конфликт версий молча не перезаписываем.') from None


def get_seniority_scale(con: sqlite3.Connection, on_date: str) -> list[tuple[int, Decimal]]:
    _check_date(on_date)
    row = con.execute(
        'SELECT effective_from FROM seniority_scale WHERE effective_from <= ?'
        ' ORDER BY effective_from DESC LIMIT 1', (on_date,),
    ).fetchone()
    if row is None:
        return []
    rows = con.execute(
        'SELECT threshold_years, rate FROM seniority_scale WHERE effective_from=? ORDER BY threshold_years',
        (row['effective_from'],),
    ).fetchall()
    return [(r['threshold_years'], Decimal(r['rate'])) for r in rows]


# --- Персональные исключения ----------------------------------------------------

def add_exception(con: sqlite3.Connection, emp_id: int, reason: str) -> None:
    if not reason.strip():
        raise ValueError('Исключение: пустая причина')
    con.execute(
        'INSERT INTO settlement_exceptions(emp_id, reason) VALUES(?,?)'
        ' ON CONFLICT(emp_id) DO UPDATE SET reason=excluded.reason',
        (emp_id, reason.strip()),
    )
    con.commit()


def remove_exception(con: sqlite3.Connection, emp_id: int) -> None:
    con.execute('DELETE FROM settlement_exceptions WHERE emp_id=?', (emp_id,))
    con.commit()


def list_exceptions(con: sqlite3.Connection) -> dict[int, str]:
    return {r['emp_id']: r['reason'] for r in con.execute('SELECT * FROM settlement_exceptions')}


def is_excluded(con: sqlite3.Connection, emp_id: int) -> bool:
    return con.execute(
        'SELECT 1 FROM settlement_exceptions WHERE emp_id=?', (emp_id,)).fetchone() is not None


# --- Первичный перенос и стартовые значения -------------------------------------

def seed_defaults(con: sqlite3.Connection,
                  effective_from: str = DEFAULT_TRANSITION) -> None:
    """Стартовые условия: база 60 000, H_base 8, бонус 5 000, матрица ролей.

    Стажевая шкала НЕ вносится: данные по стажу будут даны позже, до этого
    бонус стажа равен 0 (пустая шкала). См. set_seniority_scale / TOML-импорт.
    """
    with con:
        con.execute(
            'INSERT OR IGNORE INTO pay_settings(effective_from, monthly_base_cents,'
            ' base_day_hours, full_month_bonus_cents, created_at) VALUES(?,?,?,?,?)',
            (effective_from, 60000 * 100, 8, 5000 * 100,
             datetime.now().isoformat(timespec='seconds')),
        )
        for role_id, rule in DEFAULT_RULES.items():
            con.execute('INSERT OR IGNORE INTO roles(id, name) VALUES(?,?)',
                        (role_id, rule.role_name))
            con.execute(
                'INSERT OR IGNORE INTO role_rules(role_id, effective_from, time_mode,'
                ' shift_norm_hours, check_single_mark, participates, exclude_reason,'
                ' overtime_eligible, full_month_eligible, seniority_eligible, overtime_coef)'
                ' VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (role_id, effective_from, rule.time_mode, str(rule.shift_norm_hours),
                 int(rule.check_single_mark), int(rule.participates), rule.exclude_reason,
                 int(rule.overtime_eligible), int(rule.full_month_eligible),
                 int(rule.seniority_eligible), str(rule.overtime_coef)),
            )


def migrate_from_dat(con: sqlite3.Connection, variable_data_dir: str = 'data/variable_data_for_app',
                     effective_from: str = DEFAULT_TRANSITION) -> dict:
    """Перенос сотрудников, ролей и исключений из .dat с сохранением ID.

    Перед переносом копии исходников сохраните вручную. Старые индивидуальные
    ставки wage_rates.dat НЕ превращаются в общую базу — общие условия вносятся
    отдельно через seed_defaults/set_pay_settings. Повторный вызов идемпотентен:
    совпадающие записи пропускаются, конфликт значений — ошибка без частичной записи.
    """
    base = Path(variable_data_dir)
    report: dict = {'roles': 0, 'employees': 0, 'exceptions': 0,
                    'skipped': 0, 'conflicts': []}

    def _read_lines(name: str) -> list[str]:
        return (base / name).read_text(encoding='utf-8-sig').splitlines()

    # Роли: '[id] name'.
    dat_roles: dict[int, str] = {}
    for line in _read_lines('roles_employee.dat'):
        line = line.strip()
        if not line:
            continue
        head, _, tail = line.partition(']')
        dat_roles[int(head.strip('['))] = tail.strip()
    # Сотрудники: 'id [role_id] last first'.
    dat_emps: dict[int, tuple[int, str, str]] = {}
    for line in _read_lines('id_employee.dat'):
        parts = line.split()
        if len(parts) < 2:
            continue
        emp_id = int(parts[0])
        role_id = int(parts[1].strip('[]'))
        last = parts[2] if len(parts) > 2 else ''
        first = parts[3] if len(parts) > 3 else ''
        dat_emps[emp_id] = (role_id, first, last)
    dat_exceptions: list[int] = []
    for line in _read_lines('settlement_exceptions.dat'):
        line = line.strip()
        if line:
            dat_exceptions.append(int(line))

    with con:
        for role_id, name in dat_roles.items():
            existing = con.execute('SELECT name FROM roles WHERE id=?', (role_id,)).fetchone()
            if existing is None:
                con.execute('INSERT INTO roles(id, name) VALUES(?,?)', (role_id, name))
                report['roles'] += 1
            elif existing['name'] != name:
                report['conflicts'].append(f'roles[{role_id}]: БД={existing["name"]!r} DAT={name!r}')
        for emp_id, (role_id, first, last) in dat_emps.items():
            existing = con.execute('SELECT * FROM employees WHERE id=?', (emp_id,)).fetchone()
            if existing is None:
                con.execute(
                    'INSERT INTO employees(id, first_name, last_name, hire_date) VALUES(?,?,?,?)',
                    (emp_id, first, last, None),
                )
                report['employees'] += 1
            elif (existing['first_name'], existing['last_name']) != (first, last):
                report['conflicts'].append(f'employees[{emp_id}]: БД conflict DAT')
                continue
            else:
                report['skipped'] += 1
            already = con.execute(
                'SELECT 1 FROM assignments WHERE emp_id=? AND effective_from=?',
                (emp_id, effective_from)).fetchone()
            if already is None:
                if con.execute('SELECT 1 FROM roles WHERE id=?', (role_id,)).fetchone() is None:
                    report['conflicts'].append(f'assignments[{emp_id}]: роль {role_id} вне справочника')
                    continue
                try:
                    con.execute(
                        'INSERT INTO assignments(emp_id, role_id, effective_from, effective_to)'
                        ' VALUES(?,?,?,?)', (emp_id, role_id, effective_from, None))
                except sqlite3.IntegrityError as e:
                    report['conflicts'].append(f'assignments[{emp_id}]: {e}')
        for emp_id in dat_exceptions:
            existing = con.execute(
                'SELECT reason FROM settlement_exceptions WHERE emp_id=?', (emp_id,)).fetchone()
            if existing is None:
                con.execute(
                    'INSERT INTO settlement_exceptions(emp_id, reason) VALUES(?,?)',
                    (emp_id, 'перенесено из settlement_exceptions.dat: причина уточняется'))
                report['exceptions'] += 1
            else:
                report['skipped'] += 1
        if report['conflicts']:
            # Внутри транзакции: rollback, частичных записей нет.
            raise ValueError('Конфликты переноса (транзакция отменена): '
                             + '; '.join(report['conflicts']))
    return report
