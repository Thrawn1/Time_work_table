"""TOML-обмен справочниками: шаблон, экспорт, импорт (план roles_rates, §4.3).

Правила импорта:
- сопоставление по постоянным ID и датам действия, а не по ФИО;
- до записи — предпросмотр (добавления / без изменений / ошибки);
- проверки: схема, ссылки, дубли ID/версий, даты, пересекающиеся периоды,
  обязательные поля, диапазоны сумм/коэффициентов/норм;
- ошибки с разделом/записью/полем; синтаксические — с позицией парсера;
- повторный импорт идемпотентен; конфликт значений той же версии —
  ошибка без молчаливой перезаписи и без частичного обновления;
- отсутствие записи в файле удалением не является;
- пакет применяется одной транзакцией.

Денежные значения в TOML — строки (парсер не превращает их в binary float).
"""

from __future__ import annotations

import sqlite3
import tomllib
from datetime import date
from decimal import Decimal, InvalidOperation

from core.money import as_decimal
from core.pay_store import SCHEMA_VERSION, connect, init_db

TEMPLATE = """\
# Шаблон справочников оплаты. schema_version = 1.
# Даты — ISO YYYY-MM-DD. Деньги — СТРОКИ ("60000.00"), иначе float-парсер
# внесёт binary-ошибку. Дата ниже условная и не задаёт дату перехода.
schema_version = 1

[[pay_settings]]
effective_from = "2026-09-01"
monthly_base = "60000.00"
base_day_hours = 8
full_month_bonus = "5000.00"

[[roles]]
id = 1
name = "Работник цеха"

[[role_rules]]
role_id = 1
effective_from = "2026-09-01"
time_mode = "actual"
shift_norm_hours = "8"
check_single_mark = true
participates = true
exclude_reason = ""
overtime_eligible = true
full_month_eligible = true
seniority_eligible = true
overtime_coef = "1.5"

[[employees]]
id = 1
first_name = "Иван"
last_name = "Петров"
hire_date = "2020-01-15"

[[assignments]]
emp_id = 1
role_id = 1
effective_from = "2026-09-01"
# effective_to = "2026-12-31"

[[seniority_scales]]
effective_from = "2026-09-01"
thresholds = [{years = 0, rate = "0"}, {years = 5, rate = "0.10"}]

# [[settlement_exceptions]]
# emp_id = 1
# reason = "подрядчик — не участвует"
"""


def generate_template() -> str:
    """Пустой шаблон: генерируется программой, пригоден для импорта."""
    return TEMPLATE


def _tstr(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def export_toml(db_path: str = 'data/pay_directory.db', section: str | None = None) -> str:
    """Экспорт справочника (целиком или раздел). Результат пригоден для импорта."""
    con = connect(db_path)
    try:
        out = ['schema_version = 1', '']
        if section in (None, 'pay_settings'):
            for r in con.execute('SELECT * FROM pay_settings ORDER BY effective_from'):
                out += ['[[pay_settings]]',
                        f"effective_from = {_tstr(r['effective_from'])}",
                        f"monthly_base = {_tstr(_cents_str(r['monthly_base_cents']))}",
                        f"base_day_hours = {r['base_day_hours']}",
                        f"full_month_bonus = {_tstr(_cents_str(r['full_month_bonus_cents']))}", '']
        if section in (None, 'roles', 'role_rules'):
            for r in con.execute('SELECT * FROM roles ORDER BY id'):
                out += ['[[roles]]', f"id = {r['id']}", f"name = {_tstr(r['name'])}", '']
            for r in con.execute(
                    'SELECT * FROM role_rules ORDER BY role_id, effective_from'):
                out += ['[[role_rules]]',
                        f"role_id = {r['role_id']}",
                        f"effective_from = {_tstr(r['effective_from'])}",
                        f"time_mode = {_tstr(r['time_mode'])}",
                        f"shift_norm_hours = {_tstr(r['shift_norm_hours'])}",
                        f"check_single_mark = {'true' if r['check_single_mark'] else 'false'}",
                        f"participates = {'true' if r['participates'] else 'false'}",
                        f"exclude_reason = {_tstr(r['exclude_reason'] or '')}",
                        f"overtime_eligible = {'true' if r['overtime_eligible'] else 'false'}",
                        f"full_month_eligible = {'true' if r['full_month_eligible'] else 'false'}",
                        f"seniority_eligible = {'true' if r['seniority_eligible'] else 'false'}",
                        f"overtime_coef = {_tstr(r['overtime_coef'])}", '']
        if section in (None, 'employees', 'assignments'):
            for r in con.execute('SELECT * FROM employees ORDER BY id'):
                out += ['[[employees]]', f"id = {r['id']}",
                        f"first_name = {_tstr(r['first_name'])}",
                        f"last_name = {_tstr(r['last_name'])}"]
                if r['hire_date']:
                    out.append(f"hire_date = {_tstr(r['hire_date'])}")
                out.append('')
            for r in con.execute(
                    'SELECT * FROM assignments ORDER BY emp_id, effective_from'):
                out += ['[[assignments]]', f"emp_id = {r['emp_id']}",
                        f"role_id = {r['role_id']}",
                        f"effective_from = {_tstr(r['effective_from'])}"]
                if r['effective_to']:
                    out.append(f"effective_to = {_tstr(r['effective_to'])}")
                out.append('')
        if section in (None, 'seniority_scales'):
            cur: str | None = None
            items: list[str] = []
            rows = con.execute(
                'SELECT * FROM seniority_scale ORDER BY effective_from, threshold_years').fetchall()

            def _flush() -> None:
                if cur is not None:
                    out.extend(['[[seniority_scales]]', f"effective_from = {_tstr(cur)}",
                                f"thresholds = [{', '.join(items)}]", ''])
            for r in rows:
                if r['effective_from'] != cur:
                    _flush()
                    cur, items = r['effective_from'], []
                items.append(f"{{years = {r['threshold_years']}, rate = {_tstr(r['rate'])}}}")
            _flush()
        if section in (None, 'settlement_exceptions'):
            for r in con.execute('SELECT * FROM settlement_exceptions ORDER BY emp_id'):
                out += ['[[settlement_exceptions]]', f"emp_id = {r['emp_id']}",
                        f"reason = {_tstr(r['reason'])}", '']
        return '\n'.join(out).rstrip() + '\n'
    finally:
        con.close()


def _cents_str(cents: int) -> str:
    return f'{Decimal(cents) / Decimal(100):.2f}'


# --- Импорт -------------------------------------------------------------------

def _is_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _is_money(value: object, allow_zero: bool = True) -> bool:
    if not isinstance(value, str):
        return False
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return False
    if amount.is_nan() or amount.is_infinite():
        return False
    return allow_zero or amount > 0


def import_toml(db_path: str, text: str, dry_run: bool = False) -> dict:
    """Импорт пакета. Возвращает {'added': [...], 'unchanged': [...], 'errors': [...]}.

    added/unchanged — (раздел, ключ); errors — строки 'раздел[ключ].поле: причина'.
    При dry_run или при наличии ошибок запись не выполняется.
    """
    added: list[tuple[str, str]] = []
    unchanged: list[tuple[str, str]] = []
    errors: list[str] = []
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        return {'added': [], 'unchanged': [], 'errors': [f'файл: синтаксис TOML: {e}']}

    if data.get('schema_version') != SCHEMA_VERSION:
        return {'added': [], 'unchanged': [],
                'errors': [f"schema_version: нужен {SCHEMA_VERSION}, "
                           f"получен {data.get('schema_version')!r}"]}

    con = init_db(db_path)
    try:
        ops = _plan(con, data, added, unchanged, errors)
        if errors or dry_run:
            return {'added': added, 'unchanged': unchanged, 'errors': errors}
        try:
            con.execute('BEGIN')
            for sql, params in ops:
                con.execute(sql, params)
            con.commit()
        except sqlite3.IntegrityError as e:
            con.rollback()
            errors.append(f'файл: ограничение БД: {e} — пакет не применён')
        return {'added': added, 'unchanged': unchanged, 'errors': errors}
    finally:
        con.close()


def _plan(con: sqlite3.Connection, data: dict, added: list, unchanged: list,
          errors: list) -> list[tuple[str, tuple]]:
    ops: list[tuple[str, tuple]] = []
    db_roles = {r['id'] for r in con.execute('SELECT id FROM roles')}
    db_emps = {r['id'] for r in con.execute('SELECT id FROM employees')}
    file_roles: dict[int, str] = {}
    file_emps: set[int] = set()

    def _same(table: str, where: str, params: tuple, want: dict) -> bool:
        row = con.execute(f'SELECT * FROM {table} WHERE {where}', params).fetchone()
        if row is None:
            return False
        return all(str(row[k]) == str(v) for k, v in want.items())

    # Роли.
    for i, rec in enumerate(data.get('roles', [])):
        tag = f'roles[{rec.get("id", f"#{i}")}]'
        rid, name = rec.get('id'), rec.get('name')
        if not isinstance(rid, int) or rid < 0:
            errors.append(f'{tag}.id: нужен неотрицательный int'); continue
        if not isinstance(name, str) or not name.strip():
            errors.append(f'{tag}.name: пустое название'); continue
        if rid in file_roles:
            errors.append(f'{tag}.id: дубль в файле'); continue
        file_roles[rid] = name.strip()
        want = {'id': rid, 'name': name.strip()}
        if rid in db_roles and not _same('roles', 'id=?', (rid,), {'name': name.strip()}):
            errors.append(f'{tag}: конфликт с БД (перезапись версии запрещена)'); continue
        if rid in db_roles:
            unchanged.append(('roles', str(rid)))
        else:
            added.append(('roles', str(rid)))
            ops.append(('INSERT INTO roles(id, name) VALUES(?,?)', (rid, name.strip())))
    db_roles |= set(file_roles)

    # Правила ролей.
    seen_rules: set[tuple[int, str]] = set()
    for i, rec in enumerate(data.get('role_rules', [])):
        tag = f"role_rules[{rec.get('role_id', '?')}@{rec.get('effective_from', f'#{i}')}]"
        rid, eff = rec.get('role_id'), rec.get('effective_from')
        if rid not in db_roles:
            errors.append(f'{tag}.role_id: нет такой роли'); continue
        if not _is_date(eff):
            errors.append(f'{tag}.effective_from: нужен ISO YYYY-MM-DD'); continue
        if (rid, eff) in seen_rules:
            errors.append(f'{tag}: дубль версии в файле'); continue
        seen_rules.add((rid, eff))
        mode = rec.get('time_mode')
        norm = rec.get('shift_norm_hours')
        coef = rec.get('overtime_coef')
        flags = {k: rec.get(k) for k in ('check_single_mark', 'participates',
                                         'overtime_eligible', 'full_month_eligible',
                                         'seniority_eligible')}
        ok = True
        if mode not in ('actual', 'fixed_shift'):
            errors.append(f'{tag}.time_mode: actual|fixed_shift'); ok = False
        for key, val, low in (('shift_norm_hours', norm, '0'), ('overtime_coef', coef, '0')):
            if not isinstance(val, str) or not _is_money(val, allow_zero=False):
                errors.append(f'{tag}.{key}: положительная Decimal-строка'); ok = False
        for key, val in flags.items():
            if not isinstance(val, bool):
                errors.append(f'{tag}.{key}: true|false'); ok = False
        reason = rec.get('exclude_reason', '')
        if not isinstance(reason, str):
            errors.append(f'{tag}.exclude_reason: строка'); ok = False
        if not ok:
            continue
        want = {'time_mode': mode, 'shift_norm_hours': str(as_decimal(norm)),
                'check_single_mark': int(flags['check_single_mark']),
                'participates': int(flags['participates']),
                'exclude_reason': reason,
                'overtime_eligible': int(flags['overtime_eligible']),
                'full_month_eligible': int(flags['full_month_eligible']),
                'seniority_eligible': int(flags['seniority_eligible']),
                'overtime_coef': str(as_decimal(coef))}
        exists = con.execute(
            'SELECT * FROM role_rules WHERE role_id=? AND effective_from=?', (rid, eff)).fetchone()
        if exists is not None:
            if all(str(exists[k]) == str(v) for k, v in want.items()):
                unchanged.append(('role_rules', f'{rid}@{eff}'))
            else:
                errors.append(f'{tag}: конфликт с БД (перезапись версии запрещена)')
            continue
        added.append(('role_rules', f'{rid}@{eff}'))
        ops.append(('INSERT INTO role_rules(role_id, effective_from, time_mode, shift_norm_hours,'
                    ' check_single_mark, participates, exclude_reason, overtime_eligible,'
                    ' full_month_eligible, seniority_eligible, overtime_coef)'
                    ' VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (rid, eff, mode, str(as_decimal(norm)), int(flags['check_single_mark']),
                     int(flags['participates']), reason, int(flags['overtime_eligible']),
                     int(flags['full_month_eligible']), int(flags['seniority_eligible']),
                     str(as_decimal(coef)))))

    # Сотрудники.
    for i, rec in enumerate(data.get('employees', [])):
        tag = f"employees[{rec.get('id', f'#{i}')}]"
        eid = rec.get('id')
        if not isinstance(eid, int) or eid < 0:
            errors.append(f'{tag}.id: нужен неотрицательный int'); continue
        if eid in file_emps:
            errors.append(f'{tag}.id: дубль в файле'); continue
        file_emps.add(eid)
        first, last = rec.get('first_name'), rec.get('last_name')
        hire = rec.get('hire_date')
        if not isinstance(first, str) or not isinstance(last, str):
            errors.append(f'{tag}: first_name/last_name — строки'); continue
        if hire is not None and not _is_date(hire):
            errors.append(f'{tag}.hire_date: нужен ISO YYYY-MM-DD'); continue
        row = con.execute('SELECT * FROM employees WHERE id=?', (eid,)).fetchone()
        if row is not None:
            same = (row['first_name'], row['last_name'], row['hire_date']) == (first, last, hire)
            if not same:
                errors.append(f'{tag}: конфликт с БД (перезапись запрещена)'); continue
            unchanged.append(('employees', str(eid)))
        else:
            added.append(('employees', str(eid)))
            ops.append(('INSERT INTO employees(id, first_name, last_name, hire_date)'
                        ' VALUES(?,?,?,?)', (eid, first, last, hire)))
    db_emps |= file_emps

    # Назначения.
    file_periods: dict[int, list[tuple[str, str]]] = {}
    for i, rec in enumerate(data.get('assignments', [])):
        tag = (f"assignments[{rec.get('emp_id', '?')}@"
               f"{rec.get('effective_from', f'#{i}')}]")
        eid, rid, eff, end = (rec.get('emp_id'), rec.get('role_id'),
                              rec.get('effective_from'), rec.get('effective_to'))
        if eid not in db_emps:
            errors.append(f'{tag}.emp_id: нет такого сотрудника'); continue
        if rid not in db_roles:
            errors.append(f'{tag}.role_id: нет такой роли'); continue
        if not _is_date(eff):
            errors.append(f'{tag}.effective_from: нужен ISO YYYY-MM-DD'); continue
        if end is not None:
            if not _is_date(end):
                errors.append(f'{tag}.effective_to: нужен ISO YYYY-MM-DD'); continue
            if end < eff:
                errors.append(f'{tag}.effective_to: раньше effective_from'); continue
        periods = file_periods.setdefault(eid, [])
        new_to = end or '9999-12-31'
        if any(not (new_to < f or eff > (t or '9999-12-31')) for f, t in periods):
            errors.append(f'{tag}: пересечение периодов в файле'); continue
        db_overlap = con.execute(
            'SELECT effective_from, effective_to FROM assignments WHERE emp_id=?'
            ' AND (effective_to IS NULL OR effective_to >= ?)'
            ' AND effective_from <= ?',
            (eid, eff, end or '9999-12-31')).fetchall()
        clash = False
        for r in db_overlap:
            other_to = r['effective_to'] or '9999-12-31'
            if not (new_to < r['effective_from'] or eff > other_to):
                # Та же версия с тем же содержимым — идемпотентность, иначе конфликт.
                same = con.execute(
                    'SELECT role_id, effective_to FROM assignments WHERE emp_id=?'
                    ' AND effective_from=?', (eid, eff)).fetchone()
                if same is not None and (same['role_id'], same['effective_to']) == (rid, end):
                    pass
                else:
                    errors.append(f'{tag}: пересечение с БД'); clash = True
                break
        if clash:
            continue
        periods.append((eff, end))
        same = con.execute(
            'SELECT role_id, effective_to FROM assignments WHERE emp_id=? AND effective_from=?',
            (eid, eff)).fetchone()
        if same is not None:
            unchanged.append(('assignments', f'{eid}@{eff}'))
        else:
            added.append(('assignments', f'{eid}@{eff}'))
            ops.append(('INSERT INTO assignments(emp_id, role_id, effective_from, effective_to)'
                        ' VALUES(?,?,?,?)', (eid, rid, eff, end)))

    # Стажевые шкалы.
    seen_scales: set[str] = set()
    for rec in data.get('seniority_scales', []):
        eff = rec.get('effective_from')
        tag = f'seniority_scales[{eff}]'
        if not _is_date(eff):
            errors.append(f'{tag}.effective_from: нужен ISO YYYY-MM-DD'); continue
        if eff in seen_scales:
            errors.append(f'{tag}: дубль версии в файле'); continue
        seen_scales.add(eff)
        thresholds = rec.get('thresholds')
        if not isinstance(thresholds, list) or not thresholds:
            errors.append(f'{tag}.thresholds: непустой список'); continue
        ok, years_seen = True, set()
        for t in thresholds:
            if not isinstance(t, dict) or not isinstance(t.get('years'), int) or t['years'] < 0:
                errors.append(f'{tag}.thresholds.years: неотрицательный int'); ok = False; break
            if t['years'] in years_seen:
                errors.append(f'{tag}.thresholds: дубль порога {t["years"]}'); ok = False; break
            years_seen.add(t['years'])
            if not _is_money(t.get('rate')) or not (Decimal('0') <= Decimal(t['rate']) <= Decimal('1')):
                errors.append(f'{tag}.thresholds.rate: доля 0..1 строкой'); ok = False; break
        if not ok:
            continue
        existing = con.execute(
            'SELECT threshold_years, rate FROM seniority_scale WHERE effective_from=?'
            ' ORDER BY threshold_years', (eff,)).fetchall()
        want = sorted((t['years'], str(as_decimal(t['rate']))) for t in thresholds)
        got = sorted((r['threshold_years'], str(as_decimal(r['rate']))) for r in existing)
        if existing and got != want:
            errors.append(f'{tag}: конфликт с БД (перезапись версии запрещена)'); continue
        if existing:
            unchanged.append(('seniority_scales', eff))
        else:
            added.append(('seniority_scales', eff))
            for years, rate in want:
                ops.append(('INSERT INTO seniority_scale(effective_from, threshold_years, rate)'
                            ' VALUES(?,?,?)', (eff, years, rate)))

    # Общие условия.
    seen_ps: set[str] = set()
    for rec in data.get('pay_settings', []):
        eff = rec.get('effective_from')
        tag = f'pay_settings[{eff}]'
        if not _is_date(eff):
            errors.append(f'{tag}.effective_from: нужен ISO YYYY-MM-DD'); continue
        if eff in seen_ps:
            errors.append(f'{tag}: дубль версии в файле'); continue
        seen_ps.add(eff)
        base, bonus, hours = rec.get('monthly_base'), rec.get('full_month_bonus'), \
            rec.get('base_day_hours')
        if not _is_money(base, allow_zero=False):
            errors.append(f'{tag}.monthly_base: положительная Decimal-строка'); continue
        if not _is_money(bonus):
            errors.append(f'{tag}.full_month_bonus: Decimal-строка ≥ 0'); continue
        if not isinstance(hours, int) or hours <= 0:
            errors.append(f'{tag}.base_day_hours: int > 0'); continue
        row = con.execute('SELECT * FROM pay_settings WHERE effective_from=?', (eff,)).fetchone()
        want = {'monthly_base_cents': int(Decimal(base) * 100),
                'base_day_hours': hours,
                'full_month_bonus_cents': int(Decimal(bonus) * 100)}
        if row is not None:
            if all(row[k] == v for k, v in want.items()):
                unchanged.append(('pay_settings', eff))
            else:
                errors.append(f'{tag}: конфликт с БД (перезапись версии запрещена)')
            continue
        added.append(('pay_settings', eff))
        ops.append(('INSERT INTO pay_settings(effective_from, monthly_base_cents, base_day_hours,'
                    ' full_month_bonus_cents, created_at) VALUES(?,?,?,?,?)',
                    (eff, want['monthly_base_cents'], hours, want['full_month_bonus_cents'],
                     date.today().isoformat())))

    # Исключения.
    seen_exc: set[int] = set()
    for rec in data.get('settlement_exceptions', []):
        eid, reason = rec.get('emp_id'), rec.get('reason')
        tag = f'settlement_exceptions[{eid}]'
        if eid in seen_exc:
            errors.append(f'{tag}: дубль в файле'); continue
        seen_exc.add(eid)
        if eid not in db_emps:
            errors.append(f'{tag}.emp_id: нет такого сотрудника'); continue
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f'{tag}.reason: непустая строка'); continue
        row = con.execute(
            'SELECT reason FROM settlement_exceptions WHERE emp_id=?', (eid,)).fetchone()
        if row is not None:
            if row['reason'] == reason.strip():
                unchanged.append(('settlement_exceptions', str(eid)))
            else:
                errors.append(f'{tag}: конфликт с БД (перезапись запрещена)')
            continue
        added.append(('settlement_exceptions', str(eid)))
        ops.append(('INSERT INTO settlement_exceptions(emp_id, reason) VALUES(?,?)',
                    (eid, reason.strip())))
    return ops
