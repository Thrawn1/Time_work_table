"""Тесты дашборда (шаг 1-2 console-ui)."""
from datetime import datetime
from unittest.mock import patch

from core.ui import (
    summarize_employee,
    build_dashboard_rows,
    print_dashboard,
    ask_menu,
    confirm_save,
    print_day_card_single,
    print_missed_day_card,
)


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestSummarize:
    def test_ok(self):
        assert summarize_employee(0, 0, True) == {'status': 'OK', 'style': 'green'}

    def test_needs_fix_single(self):
        assert summarize_employee(1, 0, True)['status'] == 'Править'

    def test_needs_fix_missed(self):
        assert summarize_employee(0, 3, True)['status'] == 'Править'

    def test_no_data(self):
        assert summarize_employee(0, 0, False) == {'status': 'Нет данных', 'style': 'red'}


class TestBuildRows:
    def test_statuses(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        from core import analysis

        # 101: одна одиночная метка 06.07 + есть отметки; 102/103: пусто
        dt = make_dt('2026-07-06', '08:00:00')
        tt = {'2026-07-06': {101: [dt, dt, 'work']}}
        rows = build_dashboard_rows(tt, [101, 102, 103], 2026, 7)
        by_id = {r['emp_id']: r for r in rows}
        assert by_id[101]['single'] == 1
        assert by_id[101]['status'] == 'Править'
        assert by_id[102]['has_marks'] is False
        assert by_id[102]['status'] == 'Нет данных'

    def test_print_does_not_raise(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty, capsys):
        rows = build_dashboard_rows({}, [101], 2026, 7)
        print_dashboard(rows, title='Тест')
        out = capsys.readouterr().out
        # rich печатает таблицу в stdout — проверяем, что имя/статус есть
        assert 'Нет данных' in out or 'Петров' in out


class TestMenuAndConfirm:
    def test_ask_menu_valid(self):
        with patch('builtins.input', return_value='2'):
            assert ask_menu('Меню:', ('1', '2')) == '2'

    def test_ask_menu_reprompts_then_accepts(self):
        with patch('builtins.input', side_effect=['9', 'мусор', '1']):
            assert ask_menu('Меню:', ('1', '2')) == '1'

    def test_ask_menu_cancel(self):
        with patch('builtins.input', return_value='0'):
            assert ask_menu('Меню:', ('1', '2')) == '0'

    def test_confirm_yes_no(self):
        with patch('builtins.input', return_value='д'):
            assert confirm_save('Сохранить?') is True
        with patch('builtins.input', return_value='н'):
            assert confirm_save('Сохранить?') is False

    def test_confirm_reprompts(self):
        with patch('builtins.input', side_effect=['мусор', 'y']):
            assert confirm_save('Сохранить?') is True


class TestCards:
    def test_cards_do_not_raise(self, capsys):
        print_day_card_single('Петров Иван', '2026-07-06', make_dt('2026-07-06', '17:00:00'))
        print_missed_day_card('Петров Иван', '2026-07-07')
        out = capsys.readouterr().out
        assert '2026-07-06' in out
        assert '2026-07-07' in out
