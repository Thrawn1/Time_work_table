"""Тесты TOML-обмена и консольного управления (план roles_rates, шаг 2, §7)."""

import tomllib
from decimal import Decimal

from core.pay_cli import main as pay_cli
from core.pay_store import (
    connect, get_pay_settings, init_db, migrate_from_dat, seed_defaults,
)
from core.pay_toml import export_toml, generate_template, import_toml


def _seeded_db(tmp_path):
    db = str(tmp_path / 'pay.db')
    con = init_db(db)
    seed_defaults(con)
    migrate_from_dat(con)
    con.close()
    return db


def test_template_is_importable(tmp_path):
    db = str(tmp_path / 'pay.db')
    init_db(db)
    text = generate_template()
    tomllib.loads(text)  # синтаксис валиден
    dry = import_toml(db, text, dry_run=True)
    assert dry['errors'] == []
    assert dry['added']
    # dry-run не пишет
    assert get_pay_settings(connect(db), '2026-09-01') is None
    real = import_toml(db, text)
    assert real['errors'] == []
    assert get_pay_settings(connect(db), '2026-09-01').monthly_base == Decimal('60000.00')


def test_reimport_idempotent(tmp_path):
    db = str(tmp_path / 'pay.db')
    init_db(db)
    import_toml(db, generate_template())
    again = import_toml(db, generate_template())
    assert again['errors'] == []
    assert again['added'] == []
    assert again['unchanged']


def test_export_import_roundtrip(tmp_path):
    db1 = _seeded_db(tmp_path / 'a')
    (tmp_path / 'a').mkdir(exist_ok=True)
    text1 = export_toml(db1)
    db2 = str(tmp_path / 'b' / 'pay.db')
    (tmp_path / 'b').mkdir(exist_ok=True)
    report = import_toml(db2, text1)
    assert report['errors'] == []
    assert export_toml(db2) == text1


def test_conflict_no_silent_overwrite_no_partial(tmp_path):
    db = _seeded_db(tmp_path)
    text = export_toml(db).replace('monthly_base = "60000.00"', 'monthly_base = "70000.00"')
    report = import_toml(db, text)
    assert report['errors']
    assert 'pay_settings' in report['errors'][0]
    con = connect(db)
    try:
        assert get_pay_settings(con, '2026-12-01').monthly_base == Decimal('60000.00')
    finally:
        con.close()


def test_validation_errors(tmp_path):
    db = str(tmp_path / 'pay.db')
    init_db(db)
    bad_version = 'schema_version = 2\n'
    assert import_toml(db, bad_version)['errors']
    bad_syntax = '[[pay_settings\n'
    assert import_toml(db, bad_syntax)['errors']
    bad_ref = ('schema_version = 1\n[[role_rules]]\nrole_id = 99\n'
               'effective_from = "2026-09-01"\ntime_mode = "actual"\n'
               'shift_norm_hours = "8"\ncheck_single_mark = true\nparticipates = true\n'
               'exclude_reason = ""\novertime_eligible = true\nfull_month_eligible = true\n'
               'seniority_eligible = true\novertime_coef = "1.5"\n')
    assert import_toml(db, bad_ref)['errors']
    bad_money = ('schema_version = 1\n[[pay_settings]]\neffective_from = "2026-09-01"\n'
                 'monthly_base = "nan"\nbase_day_hours = 8\nfull_month_bonus = "5000.00"\n')
    assert import_toml(db, bad_money)['errors']


def test_assignment_overlap_rejected(tmp_path):
    db = _seeded_db(tmp_path)
    dup = ('schema_version = 1\n[[assignments]]\nemp_id = 1\nrole_id = 2\n'
           'effective_from = "2026-10-01"\n')
    report = import_toml(db, dup)
    assert report['errors']
    assert 'пересечение' in report['errors'][0]


def test_missing_records_are_not_deletions(tmp_path):
    db = _seeded_db(tmp_path)
    tiny = ('schema_version = 1\n[[pay_settings]]\neffective_from = "2030-01-01"\n'
            'monthly_base = "60000.00"\nbase_day_hours = 8\nfull_month_bonus = "5000.00"\n')
    report = import_toml(db, tiny)
    assert report['errors'] == []
    con = connect(db)
    try:
        assert get_pay_settings(con, '2026-10-01').monthly_base == Decimal('60000.00')
    finally:
        con.close()


def test_cli_template_init_show(tmp_path, capsys):
    db = str(tmp_path / 'pay.db')
    assert pay_cli(['template']) == 0
    assert 'schema_version = 1' in capsys.readouterr().out
    assert pay_cli(['init', '--db', db]) == 0
    assert pay_cli(['show', '--db', db, '--date', '2026-10-01']) == 0
    out = capsys.readouterr().out
    assert '60000' in out and 'руководство' in out
