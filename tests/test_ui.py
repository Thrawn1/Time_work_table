"""Тесты дашборда (шаг 1 console-ui)."""
from datetime import datetime

from core.ui import summarize_employee, build_dashboard_rows, print_dashboard


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
