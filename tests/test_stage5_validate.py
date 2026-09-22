"""Этап 5 задачи 1–2: валидаторы/даты (F12-част, F13) + неизменность версий (F07)."""

from decimal import Decimal
from pathlib import Path

import pytest

from core.pay_store import (
    assign_role, change_assignment, get_assignment, get_pay_settings,
    get_seniority_scale, init_db, migrate_from_dat, set_pay_settings,
    set_seniority_scale, upsert_employee, upsert_role, update_employee,
)
from core.pay_toml import import_toml
from core.pay_validate import (
    find_noncanonical_dates, is_valid_date, money_to_cents, normalize_date,
)


@pytest.fixture
def db():
    con = init_db(':memory:')
    yield con
    con.close()


def test_strict_dates_reject_compact_and_short(db):
    for bad in ('20261001', '2026-1-1', '2026/10/01', '09-2026', '2026-02-30', '', None, 20261001):
        with pytest.raises(ValueError, match='ISO YYYY-MM-DD'):
            set_pay_settings(db, bad)  # type: ignore[arg-type]
    # Каноническая проходит.
    set_pay_settings(db, '2026-09-01')
    assert get_pay_settings(db, '2026-09-01') is not None


def test_query_with_compact_date_raises_not_silent_none(db):
    set_pay_settings(db, '2026-09-01')
    with pytest.raises(ValueError, match='ISO YYYY-MM-DD'):
        get_pay_settings(db, '20261001')


def test_assign_and_hire_strict_dates(db):
    upsert_role(db, 1, 'A')
    with pytest.raises(ValueError, match='ISO YYYY-MM-DD'):
        upsert_employee(db, 1, 'Иван', 'Петров', '20260101')
    with pytest.raises(ValueError, match='ISO YYYY-MM-DD'):
        upsert_employee(db, 1, 'Иван', 'Петров', '2026-13-01')
    upsert_employee(db, 1, 'Иван', 'Петров', '2020-01-15')
    with pytest.raises(ValueError, match='ISO YYYY-MM-DD'):
        assign_role(db, 1, 1, '20261001')
    with pytest.raises(ValueError, match='ISO YYYY-MM-DD'):
        assign_role(db, 1, 1, '2026-09-01', '20260930')


def test_is_valid_date_and_normalize():
    assert is_valid_date('2026-09-01') is True
    assert is_valid_date('20261001') is False
    assert is_valid_date('2026-1-1') is False
    assert is_valid_date('2026-02-30') is False
    assert is_valid_date(None) is False
    assert normalize_date('2026-09-01') == '2026-09-01'


def test_toml_structure_errors_not_exceptions(tmp_path):
    db = str(tmp_path / 'pay.db')
    init_db(db)
    for bad in ('schema_version = 1\nroles = 1\n',
                'schema_version = 1\nroles = [1]\n',
                'schema_version = 1\n[employees]\nid = 1\n',
                'schema_version = 1\n[[roles]]\nid = 1\nname = "A"\n[[roles]]\nid = "x"\nname = "B"\n'):
        report = import_toml(db, bad)
        assert report['errors'], bad  # предметная ошибка, а не TypeError


def test_toml_compact_date_is_error(tmp_path):
    db = str(tmp_path / 'pay.db')
    init_db(db)
    text = ('schema_version = 1\n[[pay_settings]]\neffective_from = "20261001"\n'
            'monthly_base = "60000.00"\nbase_day_hours = 8\nfull_month_bonus = "5000.00"\n')
    report = import_toml(db, text, dry_run=True)
    assert report['errors']
    assert 'YYYY-MM-DD' in report['errors'][0]


def test_negative_money_rejected_same_in_dry_run_and_apply(tmp_path):
    db = str(tmp_path / 'pay.db')
    init_db(db)
    text = ('schema_version = 1\n[[pay_settings]]\neffective_from = "2026-09-01"\n'
            'monthly_base = "60000.00"\nbase_day_hours = 8\nfull_month_bonus = "-1"\n')
    dry = import_toml(db, text, dry_run=True)
    assert dry['errors']  # раньше dry-run пропускал, запись падала в SQLite
    real = import_toml(db, text)
    assert real['errors']
    assert get_pay_settings(__import__('core.pay_store', fromlist=['connect']).connect(db),
                            '2026-09-01') is None


def test_fractional_kopecks_unified_half_up(tmp_path, db):
    # API: HALF_UP.
    set_pay_settings(db, '2026-09-01', monthly_base=Decimal('60000.005'))
    assert get_pay_settings(db, '2026-09-01').monthly_base == Decimal('60000.01')
    # TOML: тот же HALF_UP, а не int(x*100).
    db2 = str(tmp_path / 'pay2.db')
    init_db(db2)
    text = ('schema_version = 1\n[[pay_settings]]\neffective_from = "2026-09-01"\n'
            'monthly_base = "60000.005"\nbase_day_hours = 8\nfull_month_bonus = "5000.00"\n')
    report = import_toml(db2, text)
    assert report['errors'] == []
    from core.pay_store import connect
    con = connect(db2)
    try:
        assert get_pay_settings(con, '2026-09-01').monthly_base == Decimal('60000.01')
    finally:
        con.close()
    # Общий хелпер тоже HALF_UP.
    assert money_to_cents('60000.005', 'monthly_base', allow_zero=False) == 6000001


def test_find_noncanonical_dates_audit(db):
    db.execute(
        "INSERT INTO pay_settings(effective_from, monthly_base_cents, base_day_hours,"
        " full_month_bonus_cents, created_at) VALUES('20261001', 6000000, 8, 500000, 'x')")
    problems = find_noncanonical_dates(db)
    assert any('20261001' in p for p in problems)


def _write_dat_dir(path: Path, roles: dict[int, str],
                   emps: dict[int, tuple[int, str, str]],
                   exceptions: list[int] | None = None) -> str:
    path.mkdir(parents=True, exist_ok=True)
    (path / 'roles_employee.dat').write_text(
        ''.join(f'[{rid}] {name}\n' for rid, name in roles.items()), encoding='utf-8-sig')
    (path / 'id_employee.dat').write_text(
        ''.join(f'{eid} [{role}] {last} {first}\n' for eid, (role, first, last) in emps.items()),
        encoding='utf-8-sig')
    (path / 'settlement_exceptions.dat').write_text(
        ''.join(f'{e}\n' for e in (exceptions or [])), encoding='utf-8-sig')
    return str(path)


def test_seniority_append_rejected_no_partial(db):
    set_seniority_scale(db, '2026-01-01', [(0, Decimal('0'))])
    with pytest.raises(ValueError, match='уже задана'):
        set_seniority_scale(db, '2026-01-01', [(5, Decimal('0.10'))])
    assert get_seniority_scale(db, '2026-06-01') == [(0, Decimal('0'))]


def test_seniority_identical_reset_is_idempotent(db):
    set_seniority_scale(db, '2026-01-01', [(0, Decimal('0')), (5, Decimal('0.10'))])
    set_seniority_scale(db, '2026-01-01', [(5, Decimal('0.10')), (0, Decimal('0'))])
    assert get_seniority_scale(db, '2026-06-01') == [(0, Decimal('0')), (5, Decimal('0.10'))]


def test_seniority_conflict_keeps_history(db):
    set_seniority_scale(db, '2026-01-01', [(0, Decimal('0')), (5, Decimal('0.10'))])
    with pytest.raises(ValueError, match='уже задана'):
        set_seniority_scale(db, '2026-01-01', [(0, Decimal('0')), (5, Decimal('0.20'))])
    assert get_seniority_scale(db, '2026-06-01') == [(0, Decimal('0')), (5, Decimal('0.10'))]


def test_migrate_same_date_role_mismatch_conflicts_and_rolls_back(tmp_path):
    con = init_db(':memory:')
    upsert_role(con, 1, 'A')
    upsert_role(con, 2, 'B')
    upsert_employee(con, 10, 'Иван', 'Петров')
    assign_role(con, 10, 1, '2026-01-01')
    dat = _write_dat_dir(tmp_path / 'dat', {1: 'A', 2: 'B'}, {10: (2, 'Иван', 'Петров')})
    with pytest.raises(ValueError, match='Конфликты переноса'):
        migrate_from_dat(con, dat, '2026-01-01')
    from core.pay_store import get_assignment
    assert get_assignment(con, 10, '2026-06-01') == (1, None)
    assert con.execute('SELECT COUNT(*) c FROM assignments').fetchone()['c'] == 1
    con.close()


def test_migrate_overlap_different_date_conflicts(tmp_path):
    con = init_db(':memory:')
    upsert_role(con, 1, 'A')
    upsert_employee(con, 10, 'Иван', 'Петров')
    assign_role(con, 10, 1, '2026-01-01')  # бессрочное
    dat = _write_dat_dir(tmp_path / 'dat', {1: 'A'}, {10: (1, 'Иван', 'Петров')})
    with pytest.raises(ValueError, match='пересечение'):
        migrate_from_dat(con, dat, '2026-02-01')
    assert con.execute('SELECT COUNT(*) c FROM assignments').fetchone()['c'] == 1
    con.close()


def test_migrate_idempotent_same_content(tmp_path):
    con = init_db(':memory:')
    dat = _write_dat_dir(tmp_path / 'dat', {1: 'A'}, {10: (1, 'Иван', 'Петров')})
    upsert_role(con, 1, 'A')
    first = migrate_from_dat(con, dat, '2026-01-01')
    assert first['conflicts'] == []
    second = migrate_from_dat(con, dat, '2026-01-01')
    assert second['conflicts'] == []
    assert second['roles'] == 0 and second['employees'] == 0
    con.close()


def test_tstr_newline_roundtrip(tmp_path):
    import tomllib

    from core.pay_store import add_exception, connect
    from core.pay_toml import _tstr, export_toml

    assert '\n' not in _tstr('First\nSecond')[1:-1].replace('\\n', '')
    # Экспорт через файл.
    db1 = str(tmp_path / 'a.db')
    c1 = init_db(db1)
    upsert_role(c1, 9, 'First\nSecond')
    upsert_employee(c1, 99, 'Иван', 'Петров')
    add_exception(c1, 99, 'причина с "кавычкой" и\nпереводом')
    c1.close()
    text = export_toml(db1)
    assert 'First\\nSecond' in text
    parsed = tomllib.loads(text)  # невалидный TOML раньше падал здесь
    assert parsed['roles'][0]['name'] == 'First\nSecond'
    db2 = str(tmp_path / 'b.db')
    report = import_toml(db2, text)
    assert report['errors'] == []
    con2 = connect(db2)
    try:
        row = con2.execute('SELECT name FROM roles WHERE id=9').fetchone()
        assert row['name'] == 'First\nSecond'
        row = con2.execute(
            'SELECT reason FROM settlement_exceptions WHERE emp_id=99').fetchone()
        assert row['reason'] == 'причина с "кавычкой" и\nпереводом'
    finally:
        con2.close()


def test_dry_run_creates_no_file(tmp_path):
    from pathlib import Path as _Path

    db = str(tmp_path / 'newdir' / 'pay.db')
    assert not _Path(db).exists()
    from core.pay_toml import generate_template
    report = import_toml(db, generate_template(), dry_run=True)
    assert report['errors'] == []
    assert report['added']
    assert not _Path(db).exists()


def test_dry_run_does_not_modify_existing(tmp_path):
    from core.pay_toml import export_toml, generate_template

    db = str(tmp_path / 'pay.db')
    init_db(db)
    before = export_toml(db)
    report = import_toml(db, generate_template(), dry_run=True)
    assert report['errors'] == []
    assert export_toml(db) == before


def test_change_assignment_ok(db):
    upsert_role(db, 1, 'A')
    upsert_role(db, 2, 'B')
    upsert_employee(db, 10, 'Иван', 'Петров')
    assign_role(db, 10, 1, '2026-01-01')
    closed = change_assignment(db, 10, 2, '2026-06-01')
    assert closed == '2026-05-31'
    assert get_assignment(db, 10, '2026-05-31') == (1, '2026-05-31')
    assert get_assignment(db, 10, '2026-06-01') == (2, None)


def test_change_assignment_no_active(db):
    upsert_role(db, 1, 'A')
    upsert_employee(db, 10, 'Иван', 'Петров')
    with pytest.raises(ValueError, match='нечего закрывать'):
        change_assignment(db, 10, 1, '2026-06-01')


def test_change_assignment_same_day_rejected(db):
    upsert_role(db, 1, 'A')
    upsert_role(db, 2, 'B')
    upsert_employee(db, 10, 'Иван', 'Петров')
    assign_role(db, 10, 1, '2026-06-01')
    with pytest.raises(ValueError, match='уже существует'):
        change_assignment(db, 10, 2, '2026-06-01')


def test_change_assignment_future_overlap_rolls_back(db):
    upsert_role(db, 1, 'A')
    upsert_role(db, 2, 'B')
    upsert_employee(db, 10, 'Иван', 'Петров')
    db.execute(
        "INSERT INTO assignments(emp_id, role_id, effective_from, effective_to)"
        " VALUES(10, 1, '2026-01-01', NULL)")
    db.execute(
        "INSERT INTO assignments(emp_id, role_id, effective_from, effective_to)"
        " VALUES(10, 2, '2026-09-01', NULL)")
    db.commit()
    with pytest.raises(ValueError, match='пересечение'):
        change_assignment(db, 10, 1, '2026-06-01')
    assert get_assignment(db, 10, '2026-05-01') == (1, None)
    assert db.execute('SELECT COUNT(*) c FROM assignments').fetchone()['c'] == 2


def test_update_employee(db):
    upsert_employee(db, 10, 'Иван', 'Петров')
    assert update_employee(db, 10, 'Иван', 'Петров') is False
    assert update_employee(db, 10, last_name='Сидоров') is True
    assert update_employee(db, 10, hire_date='2020-01-15', change_hire=True) is True
    row = db.execute('SELECT * FROM employees WHERE id=10').fetchone()
    assert (row['last_name'], row['hire_date']) == ('Сидоров', '2020-01-15')
    assert update_employee(db, 10, hire_date=None, change_hire=True) is True
    assert db.execute('SELECT hire_date h FROM employees WHERE id=10').fetchone()['h'] is None
    with pytest.raises(ValueError, match='не найдена'):
        update_employee(db, 99, last_name='X')
    with pytest.raises(ValueError, match='ISO YYYY-MM-DD'):
        update_employee(db, 10, hire_date='20200101', change_hire=True)
    with pytest.raises(ValueError, match='ФИО'):
        update_employee(db, 10, first_name='  ')


def test_toml_hire_fill_and_conflicts(tmp_path):
    db = str(tmp_path / 'pay.db')
    con = init_db(db)
    upsert_role(con, 1, 'A')
    upsert_employee(con, 10, 'Иван', 'Петров')
    con.close()
    fill = ('schema_version = 1\n[[roles]]\nid = 1\nname = "A"\n'
            '[[employees]]\nid = 10\nfirst_name = "Иван"\nlast_name = "Петров"\n'
            'hire_date = "2020-01-15"\n')
    report = import_toml(db, fill)
    assert report['errors'] == []
    from core.pay_store import connect
    con = connect(db)
    try:
        assert con.execute('SELECT hire_date h FROM employees WHERE id=10').fetchone()['h'] == '2020-01-15'
    finally:
        con.close()
    again = import_toml(db, fill)
    assert again['errors'] == [] and again['added'] == []
    rename = fill.replace('last_name = "Петров"', 'last_name = "Сидоров"')
    assert import_toml(db, rename)['errors']
    rehire = fill.replace('2020-01-15', '2021-05-01')
    assert import_toml(db, rehire)['errors']


def test_cli_management_commands(tmp_path, capsys):
    from core.pay_cli import main as pay_cli
    from core.pay_store import connect
    from tests.synth_data import write_synth_dat_dir

    synth = write_synth_dat_dir(tmp_path / 'synth')
    db = str(tmp_path / 'pay.db')
    assert pay_cli(['init', '--db', db]) == 0
    assert pay_cli(['migrate', '--db', db, '--dat-dir', synth]) == 0
    capsys.readouterr()
    assert pay_cli(['update-employee', '--db', db, '--emp', '1', '--hire', '2020-01-15']) == 0
    assert 'обновлена' in capsys.readouterr().out
    con = connect(db)
    try:
        assert con.execute('SELECT hire_date h FROM employees WHERE id=1').fetchone()['h'] == '2020-01-15'
    finally:
        con.close()
    assert pay_cli(['change-assignment', '--db', db, '--emp', '1',
                    '--role', '2', '--from', '2026-06-01']) == 0
    out = capsys.readouterr().out
    assert '2026-05-31' in out and '2026-06-01' in out
    assert pay_cli(['rules-history', '--db', db, '1']) == 0
    assert '2026-01-01' in capsys.readouterr().out
    assert pay_cli(['show', '--db', db, '--date', '2026-10-01']) == 0
    assert 'правила с 2026-01-01' in capsys.readouterr().out


def test_schema_version_checked_before_ddl(tmp_path):
    import sqlite3

    from core.pay_store import SchemaVersionError, connect, init_db

    db = str(tmp_path / 'future.db')
    raw = sqlite3.connect(db)
    raw.execute("CREATE TABLE schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    raw.execute("INSERT INTO schema_meta(key, value) VALUES('schema_version','999')")
    raw.commit()
    raw.close()
    with pytest.raises(SchemaVersionError):
        init_db(db)
    with pytest.raises(SchemaVersionError):
        connect(db)
    # DDL не выполнялся: чужих таблиц не появилось.
    raw = sqlite3.connect(db)
    try:
        tables = {r[0] for r in
                  raw.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert tables == {'schema_meta'}
    finally:
        raw.close()


def test_partial_db_without_version_refused(tmp_path):
    import sqlite3

    from core.pay_store import SchemaVersionError, connect, init_db

    db = str(tmp_path / 'partial.db')
    raw = sqlite3.connect(db)
    raw.execute('CREATE TABLE employees(id INTEGER PRIMARY KEY, first_name TEXT NOT NULL,'
                ' last_name TEXT NOT NULL, hire_date TEXT)')
    raw.commit()
    raw.close()
    with pytest.raises(SchemaVersionError):
        connect(db)
    with pytest.raises(SchemaVersionError):
        init_db(db)
    raw = sqlite3.connect(db)
    try:
        tables = {r[0] for r in
                  raw.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert 'schema_meta' not in tables
    finally:
        raw.close()


def test_version_mismatch_keeps_data_and_diagnoses(tmp_path):
    import sqlite3

    from core.pay_store import SchemaVersionError, connect, init_db

    db = str(tmp_path / 'pay.db')
    con = init_db(db)
    upsert_role(con, 1, 'A')
    con.close()
    raw = sqlite3.connect(db)
    raw.execute("UPDATE schema_meta SET value='999' WHERE key='schema_version'")
    raw.commit()
    raw.close()
    with pytest.raises(SchemaVersionError, match='999'):
        connect(db)
    # Данные целы: сырым чтением роль на месте.
    raw = sqlite3.connect(db)
    try:
        assert raw.execute('SELECT name FROM roles WHERE id=1').fetchone()[0] == 'A'
    finally:
        raw.close()
