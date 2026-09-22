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
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from core.money import as_decimal
from core.pay_validate import money_to_cents as _validate_cents
from core.pay_validate import normalize_date
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


class SchemaVersionError(sqlite3.Error, RuntimeError):
    """Неподдерживаемая/неопознанная версия схемы БД (F07).

    Подкласс обоих, чтобы её ловили и старые ``except RuntimeError``, и
    предметные ``except sqlite3.Error`` → ``PayrollError`` обработчики (F05).
    """


def _read_schema_version(con: sqlite3.Connection) -> str | None:
    """Версия схемы без её изменения; None — пустая БД без своих таблиц.

    БД с таблицами справочника, но без метки версии — отказ без изменений (R15).
    Таблица ``schema_meta`` без строки версии — тоже отказ: пустую БД отличаем
    от существующей без надёжной версии и чужую структуру версией 1 не подписываем.
    """
    tables = {r[0] for r in
              con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'schema_meta' not in tables:
        known = {'pay_settings', 'roles', 'role_rules', 'employees', 'assignments',
                 'seniority_scale', 'settlement_exceptions'}
        if tables & known:
            raise SchemaVersionError(
                'БД без метки версии схемы, но с таблицами справочника: '
                'отказываемся менять схему. Перенос не выполняем.')
        return None
    row = con.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    if row is None:
        raise SchemaVersionError(
            'БД содержит schema_meta без строки schema_version: версия ненадёжна, '
            'отказываемся менять схему. Нужна явная миграция.')
    return row['value']


def connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Открыть справочник с проверкой версии схемы до любых изменений (F07)."""
    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys = ON')
        existing = _read_schema_version(con)
        if existing is not None and existing != str(SCHEMA_VERSION):
            raise SchemaVersionError(
                f'Неизвестная версия схемы БД {existing}: '
                f'поддерживается {SCHEMA_VERSION}. Перенос не выполняем.')
    except Exception:
        con.close()
        raise
    return con


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Создать схему (безопасный повторный вызов).

    Версия существующей схемы проверяется ДО любого DDL: чужую версию
    и БД без метки не трогаем (F07).
    """
    if db_path != ':memory:':
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
    except Exception:
        con.close()
        raise
    return con


def _check_date(value: str) -> str:
    """Строгая каноническая дата YYYY-MM-DD (единый контракт, F13)."""
    return normalize_date(value)


def _cents(amount: Decimal | int | str, field: str) -> int:
    """Единый перевод денег в копейки HALF_UP (F12): см. pay_validate."""
    return _validate_cents(amount, field, allow_zero=True)


def _cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal('100')).quantize(Decimal('0.01'))


# --- Общие условия оплаты ----------------------------------------------------

def set_pay_settings(con: sqlite3.Connection, effective_from: str,
                     monthly_base: Decimal | str = Decimal('60000.00'),
                     base_day_hours: int = 8,
                      full_month_bonus: Decimal | str = Decimal('5000.00')) -> None:
    from core.pay_validate import require_month_start

    effective_from = require_month_start(_check_date(effective_from))
    if isinstance(base_day_hours, bool) or type(base_day_hours) is not int:
        raise ValueError('base_day_hours должен быть целым int > 0')
    if int(base_day_hours) <= 0:
        raise ValueError('base_day_hours должен быть > 0')
    try:
        con.execute(
            'INSERT INTO pay_settings(effective_from, monthly_base_cents, base_day_hours,'
            ' full_month_bonus_cents, created_at) VALUES(?,?,?,?,?)',
            (effective_from, _validate_cents(monthly_base, 'monthly_base', allow_zero=False),
             int(base_day_hours),
             _cents(full_month_bonus, 'full_month_bonus'),
             datetime.now().isoformat(timespec='seconds')),
    )
    except sqlite3.IntegrityError:
        raise ValueError(
            f'Условия на {effective_from} уже заданы: конфликт версий молча не перезаписываем. '
            f'Введите новую дату действия или исправьте запись явно.') from None
    con.commit()


def get_pay_settings(con: sqlite3.Connection, on_date: str) -> PaySettings | None:
    on_date = _check_date(on_date)
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
    from core.pay_validate import parse_finite_decimal, require_int_id, require_month_start

    effective_from = require_month_start(_check_date(effective_from))
    require_int_id(rule.role_id, f'Роль {rule.role_id}.role_id')
    if rule.time_mode not in ('actual', 'fixed_shift'):
        raise ValueError(f'Роль {rule.role_id}: неизвестный time_mode {rule.time_mode!r}')
    parse_finite_decimal(rule.shift_norm_hours, f'Роль {rule.role_id}.shift_norm_hours')
    parse_finite_decimal(rule.overtime_coef, f'Роль {rule.role_id}.overtime_coef')
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


def get_role_rule_version(con: sqlite3.Connection, role_id: int,
                          on_date: str) -> tuple[str, RoleRule] | None:
    """Версия правил роли на дату с датой её действия (F08): (effective_from, правило)."""
    on_date = _check_date(on_date)
    row = con.execute(
        'SELECT r.*, roles.name AS name FROM role_rules r JOIN roles ON roles.id=r.role_id'
        ' WHERE r.role_id=? AND r.effective_from <= ? ORDER BY r.effective_from DESC LIMIT 1',
        (role_id, on_date),
    ).fetchone()
    return (row['effective_from'], _row_to_rule(row)) if row else None


def get_role_rule(con: sqlite3.Connection, role_id: int, on_date: str) -> RoleRule | None:
    found = get_role_rule_version(con, role_id, on_date)
    return found[1] if found else None


def role_rule_versions(con: sqlite3.Connection, role_id: int) -> list[tuple[str, RoleRule]]:
    """Все версии правил роли с датами действия [(effective_from, правило)] (F17)."""
    rows = con.execute(
        'SELECT r.*, roles.name AS name FROM role_rules r JOIN roles ON roles.id=r.role_id'
        ' WHERE r.role_id=? ORDER BY r.effective_from', (role_id,),
    ).fetchall()
    return [(r['effective_from'], _row_to_rule(r)) for r in rows]


def role_rule_history(con: sqlite3.Connection, role_id: int) -> list[RoleRule]:
    return [rule for _, rule in role_rule_versions(con, role_id)]


# --- Сотрудники и назначения ---------------------------------------------------

def upsert_employee(con: sqlite3.Connection, emp_id: int, first_name: str,
                    last_name: str, hire_date: str | None = None) -> None:
    from core.pay_validate import require_int_id

    require_int_id(emp_id, 'employees.id')
    if hire_date is not None:
        hire_date = _check_date(hire_date)
    con.execute(
        'INSERT INTO employees(id, first_name, last_name, hire_date) VALUES(?,?,?,?)'
        ' ON CONFLICT(id) DO UPDATE SET first_name=excluded.first_name,'
        ' last_name=excluded.last_name, hire_date=excluded.hire_date',
        (int(emp_id), first_name.strip(), last_name.strip(), hire_date),
    )
    con.commit()


def update_employee(con: sqlite3.Connection, emp_id: int,
                    first_name: str | None = None, last_name: str | None = None,
                    hire_date: str | None = None, change_hire: bool = False) -> bool:
    """Явное исправление карточки сотрудника (F17).

    В отличие от ``upsert_employee`` требует существующую карточку и меняет
    только переданные поля (``hire_date`` — только при ``change_hire=True``;
    ``hire_date=None`` с ``change_hire=True`` очищает дату в NULL).
    Возвращает True при изменении, False при совпадении (no-op).
    """
    row = con.execute('SELECT * FROM employees WHERE id=?', (emp_id,)).fetchone()
    if row is None:
        raise ValueError(f'Сотрудник {emp_id}: карточка не найдена')
    new_first = row['first_name'] if first_name is None else first_name.strip()
    new_last = row['last_name'] if last_name is None else last_name.strip()
    if not new_first or not new_last:
        raise ValueError(f'Сотрудник {emp_id}: пустые ФИО недопустимы')
    if change_hire:
        new_hire = normalize_date(hire_date) if hire_date is not None else None
    else:
        new_hire = row['hire_date']
    if (row['first_name'], row['last_name'], row['hire_date']) == (new_first, new_last, new_hire):
        return False
    con.execute(
        'UPDATE employees SET first_name=?, last_name=?, hire_date=? WHERE id=?',
        (new_first, new_last, new_hire, emp_id),
    )
    con.commit()
    return True


def assign_role(con: sqlite3.Connection, emp_id: int, role_id: int,
                effective_from: str, effective_to: str | None = None) -> None:
    from core.pay_validate import require_int_id, require_month_end_or_none, require_month_start

    require_int_id(emp_id, 'assignments.emp_id')
    require_int_id(role_id, 'assignments.role_id')
    effective_from = require_month_start(_check_date(effective_from))
    if effective_to is not None:
        effective_to = require_month_end_or_none(_check_date(effective_to))
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
    on_date = _check_date(on_date)
    row = con.execute(
        'SELECT role_id, effective_to FROM assignments WHERE emp_id=?'
        ' AND effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?)'
        ' ORDER BY effective_from DESC LIMIT 1',
        (emp_id, on_date, on_date),
    ).fetchone()
    return (row['role_id'], row['effective_to']) if row else None


def change_assignment(con: sqlite3.Connection, emp_id: int, new_role_id: int,
                      effective_from: str) -> str:
    """Атомарная смена роли с даты (F17): закрыть действующее назначение днём
    раньше и открыть новое бессрочное. Возвращает дату закрытия (день раньше).

    Требует действующее назначение на день раньше новой даты; версия на саму
    новую дату уже существовать не должна. Пересечение с будущими периодами —
    ошибка с полным откатом (закрытие тоже отменяется).
    """
    from core.pay_validate import require_month_start

    effective_from = require_month_start(_check_date(effective_from))
    if con.execute('SELECT 1 FROM employees WHERE id=?', (emp_id,)).fetchone() is None:
        raise ValueError(f'Сотрудник {emp_id}: сначала заведите карточку (upsert_employee)')
    if con.execute('SELECT 1 FROM roles WHERE id=?', (new_role_id,)).fetchone() is None:
        raise ValueError(f'Роль {new_role_id}: сначала заведите роль (upsert_role)')
    prev_day = (date.fromisoformat(effective_from) - timedelta(days=1)).isoformat()
    with con:
        if con.execute(
                'SELECT 1 FROM assignments WHERE emp_id=? AND effective_from=?',
                (emp_id, effective_from)).fetchone() is not None:
            raise ValueError(
                f'Сотрудник {emp_id}: версия на {effective_from} уже существует — '
                f'исправьте запись явно')
        prev = con.execute(
            'SELECT effective_from, effective_to, role_id FROM assignments WHERE emp_id=?'
            ' AND effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?)'
            ' ORDER BY effective_from DESC LIMIT 1',
            (emp_id, prev_day, prev_day)).fetchone()
        if prev is None:
            raise ValueError(
                f'Сотрудник {emp_id}: нет действующего назначения на {prev_day} — '
                f'нечего закрывать; используйте assign_role для нового периода')
        if prev['effective_to'] != prev_day:
            con.execute(
                'UPDATE assignments SET effective_to=? WHERE emp_id=? AND effective_from=?',
                (prev_day, emp_id, prev['effective_from']))
        clash = con.execute(
            'SELECT effective_from, effective_to FROM assignments WHERE emp_id=?'
            ' AND (effective_to IS NULL OR effective_to >= ?)'
            ' AND effective_from <= ?',
            (emp_id, effective_from, '9999-12-31')).fetchall()
        if clash:
            r = clash[0]
            raise ValueError(
                f'Сотрудник {emp_id}: пересечение нового периода '
                f'[{effective_from}...] ∩ '
                f'[{r["effective_from"]}..{r["effective_to"] or "..."}]')
        con.execute(
            'INSERT INTO assignments(emp_id, role_id, effective_from, effective_to)'
            ' VALUES(?,?,?,?)', (emp_id, new_role_id, effective_from, None))
    return prev_day


# --- Стажевая шкала ------------------------------------------------------------

def set_seniority_scale(con: sqlite3.Connection, effective_from: str,
                        scale: list[tuple[int, Decimal | str]]) -> None:
    """Шкала [(порог_лет, доля)]; версия целиком, пустая запрещена.

    Существующая версия на дату неизменна: повтор с тем же содержимым —
    идемпотентный no-op, любое отличие — конфликт без частичной записи (F07).
    """
    from core.pay_validate import require_month_start

    effective_from = require_month_start(_check_date(effective_from))
    if not scale:
        raise ValueError('Стажевая шкала: пустой набор порогов')
    seen = set()
    want: list[tuple[int, str]] = []
    for years, rate in scale:
        if int(years) < 0 or int(years) in seen:
            raise ValueError(f'Стажевая шкала: некорректный порог {years}')
        seen.add(int(years))
        try:
            value = as_decimal(rate)
        except Exception:
            raise ValueError(f'Стажевая шкала: доля {rate} вне [0..1]') from None
        if value < 0 or value > 1:
            raise ValueError(f'Стажевая шкала: доля {rate} вне [0..1]')
        want.append((int(years), str(value)))
    want.sort()
    existing = con.execute(
        'SELECT threshold_years, rate FROM seniority_scale WHERE effective_from=?'
        ' ORDER BY threshold_years', (effective_from,)).fetchall()
    if existing:
        got = sorted((r['threshold_years'], str(as_decimal(r['rate']))) for r in existing)
        if got == want:
            return
        raise ValueError(
            f'Стажевая шкала на {effective_from} уже задана: '
            f'конфликт версий молча не перезаписываем.')
    with con:
        for years, rate in want:
            try:
                con.execute(
                    'INSERT INTO seniority_scale(effective_from, threshold_years, rate)'
                    ' VALUES(?,?,?)',
                    (effective_from, years, rate),
                )
            except sqlite3.IntegrityError:
                raise ValueError(
                    f'Стажевая шкала на {effective_from} уже задана: '
                    f'конфликт версий молча не перезаписываем.') from None


def get_seniority_version(con: sqlite3.Connection,
                          on_date: str) -> tuple[str | None, list[tuple[int, Decimal]]]:
    """Шкала стажа на дату с датой её версии (F08): (effective_from|None, шкала)."""
    on_date = _check_date(on_date)
    row = con.execute(
        'SELECT effective_from FROM seniority_scale WHERE effective_from <= ?'
        ' ORDER BY effective_from DESC LIMIT 1', (on_date,),
    ).fetchone()
    if row is None:
        return None, []
    rows = con.execute(
        'SELECT threshold_years, rate FROM seniority_scale WHERE effective_from=? ORDER BY threshold_years',
        (row['effective_from'],),
    ).fetchall()
    return row['effective_from'], [(r['threshold_years'], Decimal(r['rate'])) for r in rows]


def get_seniority_scale(con: sqlite3.Connection, on_date: str) -> list[tuple[int, Decimal]]:
    return get_seniority_version(con, on_date)[1]


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

    R04: существующие БД со старой ролью 4 (почасовая с бонусами) явно
    обновляются до spec §2 (без начислений): одного ``INSERT OR IGNORE``
    недостаточно, молчаливое наследие старой матрицы недопустимо.
    """
    effective_from = _check_date(effective_from)
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
        # Явное исправление наследия R04 на ту же дату действия.
        want4 = DEFAULT_RULES[4]
        row4 = con.execute(
            'SELECT time_mode, shift_norm_hours, check_single_mark, participates,'
            ' exclude_reason, overtime_eligible, full_month_eligible,'
            ' seniority_eligible, overtime_coef FROM role_rules'
            ' WHERE role_id=4 AND effective_from=?', (effective_from,)).fetchone()
        if row4 is not None:
            got4 = (row4['time_mode'], str(row4['shift_norm_hours']),
                    int(row4['check_single_mark']), int(row4['participates']),
                    row4['exclude_reason'] or '',
                    int(row4['overtime_eligible']), int(row4['full_month_eligible']),
                    int(row4['seniority_eligible']), str(row4['overtime_coef']))
            want4t = (want4.time_mode, str(want4.shift_norm_hours),
                      int(want4.check_single_mark), int(want4.participates),
                      want4.exclude_reason,
                      int(want4.overtime_eligible), int(want4.full_month_eligible),
                      int(want4.seniority_eligible), str(want4.overtime_coef))
            if got4 != want4t:
                con.execute(
                    'UPDATE role_rules SET time_mode=?, shift_norm_hours=?,'
                    ' check_single_mark=?, participates=?, exclude_reason=?,'
                    ' overtime_eligible=?, full_month_eligible=?,'
                    ' seniority_eligible=?, overtime_coef=?'
                    ' WHERE role_id=4 AND effective_from=?',
                    (*want4t, effective_from))


def find_midmonth_violations(con: sqlite3.Connection) -> list[str]:
    """Аудит версий/назначений не с 1-го числа и окончаний не в конец месяца (R06).

    Возвращает описания нарушений; пустой список — границы корректны.
    Проверяются pay_settings, role_rules, assignments (обе границы),
    seniority_scale. Отсутствующие таблицы пропускаются (частичная БД —
    забота R15/проверки структуры).
    """
    import calendar as _cal

    problems: list[str] = []

    def _is_first(val: str | None) -> bool:
        return isinstance(val, str) and len(val) == 10 and val[8:10] == '01'

    def _is_month_end(val: str | None) -> bool:
        if not isinstance(val, str) or len(val) != 10:
            return False
        try:
            y, m, d = int(val[:4]), int(val[5:7]), int(val[8:10])
            return d == _cal.monthrange(y, m)[1]
        except (ValueError, TypeError):
            return False

    queries = [
        ('SELECT effective_from AS v FROM pay_settings', 'pay_settings.effective_from', 'first'),
        ('SELECT role_id || "@" || effective_from AS k, effective_from AS v FROM role_rules',
         'role_rules', 'first'),
        ('SELECT emp_id || "@" || effective_from AS k, effective_from AS v FROM assignments',
         'assignments.effective_from', 'first'),
        ('SELECT emp_id || "@" || effective_from AS k, effective_to AS v FROM assignments'
         ' WHERE effective_to IS NOT NULL', 'assignments.effective_to', 'end'),
        ('SELECT effective_from AS v FROM seniority_scale', 'seniority_scale.effective_from', 'first'),
    ]
    for sql, label, kind in queries:
        try:
            rows = con.execute(sql).fetchall()
        except Exception:
            continue
        for row in rows:
            try:
                val = row['v']
            except (KeyError, IndexError, TypeError):
                continue
            key = None
            try:
                key = row['k']
            except (KeyError, IndexError, TypeError):
                key = val
            ok = _is_first(val) if kind == 'first' else _is_month_end(val)
            if not ok:
                problems.append(f'{label}[{key}] = {val!r}: дата не на границе месяца')
    return problems


def migrate_from_dat(con: sqlite3.Connection, variable_data_dir: str = 'data/variable_data_for_app',
                     effective_from: str = DEFAULT_TRANSITION) -> dict:
    """Перенос сотрудников, ролей и исключений из .dat с сохранением ID.

    Перед переносом копии исходников сохраните вручную. Старые индивидуальные
    ставки wage_rates.dat НЕ превращаются в общую базу — общие условия вносятся
    отдельно через seed_defaults/set_pay_settings. Повторный вызов идемпотентен:
    совпадающие записи пропускаются, конфликт значений — ошибка без частичной записи.
    """
    effective_from = _check_date(effective_from)
    base = Path(variable_data_dir)
    report: dict = {'roles': 0, 'employees': 0, 'exceptions': 0,
                    'skipped': 0, 'conflicts': []}

    def _read_lines(name: str) -> list[str]:
        return (base / name).read_text(encoding='utf-8-sig').splitlines()

    # Роли: '[id] name' — те же строгие правила, что в config (F19):
    # любые пробельные разделители вокруг, ошибки — с файлом и строкой.
    dat_roles: dict[int, str] = {}
    for lineno, raw in enumerate(_read_lines('roles_employee.dat'), 1):
        line = raw.strip()
        if not line:
            continue
        if ']' not in line:
            raise ValueError(
                f'roles_employee.dat:{lineno}: нужен формат "[id] название": {raw.strip()!r}')
        head, _, tail = line.partition(']')
        head = head.strip()
        if not head.startswith('['):
            raise ValueError(
                f'roles_employee.dat:{lineno}: нужен формат "[id] название": {raw.strip()!r}')
        try:
            role_id = int(head[1:].strip())
        except ValueError:
            raise ValueError(
                f'roles_employee.dat:{lineno}: некорректный id роли: {raw.strip()!r}'
            ) from None
        dat_roles[role_id] = tail.strip()
    # Сотрудники: 'id [role_id] last first' — split() по любым пробелам (F19).
    dat_emps: dict[int, tuple[int, str, str]] = {}
    for lineno, raw in enumerate(_read_lines('id_employee.dat'), 1):
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) < 2:
            raise ValueError(
                f'id_employee.dat:{lineno}: нужен формат "id [role] фамилия имя": '
                f'{raw.strip()!r}')
        try:
            emp_id = int(parts[0])
        except ValueError:
            raise ValueError(
                f'id_employee.dat:{lineno}: некорректный id сотрудника {parts[0]!r}'
            ) from None
        tok = parts[1].strip()
        if not (tok.startswith('[') and tok.endswith(']')):
            raise ValueError(
                f'id_employee.dat:{lineno}: роль должна быть "[id]": {parts[1]!r}')
        try:
            role_id = int(tok[1:-1].strip())
        except ValueError:
            raise ValueError(
                f'id_employee.dat:{lineno}: некорректный id роли {parts[1]!r}'
            ) from None
        last = parts[2] if len(parts) > 2 else ''
        first = parts[3] if len(parts) > 3 else ''
        dat_emps[emp_id] = (role_id, first, last)
    dat_exceptions: list[int] = []
    for lineno, raw in enumerate(_read_lines('settlement_exceptions.dat'), 1):
        line = raw.strip()
        if not line:
            continue
        tok = line.split()[0]
        try:
            dat_exceptions.append(int(tok))
        except ValueError:
            raise ValueError(
                f'settlement_exceptions.dat:{lineno}: некорректный id {line!r}'
            ) from None

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
                'SELECT role_id, effective_to FROM assignments'
                ' WHERE emp_id=? AND effective_from=?',
                (emp_id, effective_from)).fetchone()
            if already is not None:
                if already['role_id'] != role_id or already['effective_to'] is not None:
                    report['conflicts'].append(
                        f'assignments[{emp_id}]: БД=[{already["role_id"]}@'
                        f'{effective_from}..{already["effective_to"] or "..."}] '
                        f'DAT=[{role_id}@{effective_from}.....]: '
                        f'конфликт версии молча не перезаписываем')
                    continue
                report['skipped'] += 1
                continue
            if con.execute('SELECT 1 FROM roles WHERE id=?', (role_id,)).fetchone() is None:
                report['conflicts'].append(f'assignments[{emp_id}]: роль {role_id} вне справочника')
                continue
            overlap = con.execute(
                'SELECT effective_from, effective_to FROM assignments WHERE emp_id=?'
                ' AND (effective_to IS NULL OR effective_to >= ?)'
                ' AND effective_from <= ?',
                (emp_id, effective_from, '9999-12-31')).fetchall()
            clash = False
            for row in overlap:
                other_to = row['effective_to'] or '9999-12-31'
                if not ('9999-12-31' < row['effective_from'] or effective_from > other_to):
                    report['conflicts'].append(
                        f'assignments[{emp_id}]: пересечение '
                        f'[{effective_from}..{"..."}] ∩ '
                        f'[{row["effective_from"]}..{row["effective_to"] or "..."}]')
                    clash = True
                    break
            if clash:
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
