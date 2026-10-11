"""Общие помощники после унификации: правило роли, справочник SQLite, ввод, ремонтники."""

import sqlite3
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

import pytest

from core import ui
from core.config import EmployeeData
from core.data_array import exclusion_reason, repairmen_attendance
from core.day_models import DayMark
from core.roles import DEFAULT_RULES, resolve_rule


def _emp(emp_id, role_id):
    return EmployeeData(emp_id, 'Имя', f'Фамилия{emp_id}', role_id, '')


class TestResolveRule:
    def test_default_matrix_without_sqlite_rules(self):
        assert resolve_rule(1, None) is DEFAULT_RULES[1]
        assert resolve_rule(99, None) is None

    def test_sqlite_rules_replace_default_matrix(self):
        sqlite_rule = replace(DEFAULT_RULES[1], role_id=9, role_name='Новая роль')
        assert resolve_rule(9, {9: sqlite_rule}) is sqlite_rule
        # Переданные правила — единственный источник: умолчание не подставляется.
        assert resolve_rule(1, {9: sqlite_rule}) is None

    def test_role_known_only_in_sqlite_participates(self):
        """Роль 9 есть только в SQLite: участник, а не «неизвестная роль»."""
        staff = {900: _emp(900, 9)}
        rules = {9: replace(DEFAULT_RULES[1], role_id=9)}
        assert exclusion_reason(900, staff) == 'неизвестная роль 9'
        assert exclusion_reason(900, staff, rules_by_role=rules) == ''

    def test_sqlite_rule_can_exclude_role(self):
        staff = {900: _emp(900, 1)}
        rules = {1: replace(DEFAULT_RULES[1], participates=False, exclude_reason='по SQLite')}
        assert exclusion_reason(900, staff, rules_by_role=rules) == 'по SQLite'


class TestOpenDb:
    def test_read_error_wrapped_and_connection_closed(self, tmp_path):
        from core.pay_store import init_db, open_db

        db = str(tmp_path / 'pay.db')
        init_db(db).close()

        class Boom(RuntimeError):
            pass

        with pytest.raises(Boom, match='ошибка чтения справочника'):
            with open_db(db, error=Boom) as con:
                held = con
                con.execute('SELECT * FROM no_such_table')
        with pytest.raises(sqlite3.ProgrammingError):
            held.execute('SELECT 1')  # соединение закрыто

    def test_without_error_class_sqlite_error_passes_through(self, tmp_path):
        from core.pay_store import init_db, open_db

        db = str(tmp_path / 'pay.db')
        init_db(db).close()
        with pytest.raises(sqlite3.OperationalError):
            with open_db(db) as con:
                con.execute('SELECT * FROM no_such_table')


class TestInput:
    @pytest.mark.parametrize('raw', ['0', 'q', 'й', 'отмена', 'Q'])
    def test_ask_menu_any_cancel_token_is_cancel(self, raw):
        with patch('builtins.input', side_effect=[raw]):
            assert ui.ask_menu('Меню:', ('1', '2')) == ui.CANCEL

    def test_read_choice_empty_and_eof_are_none(self):
        with patch('builtins.input', side_effect=['']):
            assert ui.read_choice('> ') is None
        with patch('builtins.input', side_effect=EOFError):
            assert ui.read_choice('> ') is None
        with patch('builtins.input', side_effect=['  X3 ']):
            assert ui.read_choice('> ') == 'x3'

    def test_pick_number_range_and_message(self, capsys):
        assert ui.pick_number('2', 3, 'дня') == 1
        assert ui.pick_number('4', 3, 'дня', shown='x4') is None
        assert "Нет дня с номером 'x4'" in capsys.readouterr().out


def test_repairmen_attendance_lists_days_per_repairman():
    staff = {1: _emp(1, 4), 2: _emp(2, 1), 3: _emp(3, 4)}
    d = datetime(2026, 9, 12, 8)
    table = {
        '2026-09-15': {1: DayMark(d, d, 'work')},
        '2026-09-12': {1: DayMark(d, d, 'weekend'), 2: DayMark(d, d, 'weekend')},
        '2026-10-01': {1: DayMark(d, d, 'work')},
    }
    assert repairmen_attendance(table, staff, 2026, 9) == {
        1: ['2026-09-12', '2026-09-15'],
        3: [],
    }
