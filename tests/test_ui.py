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
    build_start_info,
    print_start_screen,
    build_preview_rows,
    print_preview,
    print_journal,
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

    def test_two_blocks(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty, capsys):
        """Бывшие (без отметок) — отдельным блоком, а не в общей таблице проблем."""
        dt = make_dt('2026-07-06', '08:00:00')
        tt = {'2026-07-06': {101: [dt, dt, 'work']}}
        rows = build_dashboard_rows(tt, [101, 102], 2026, 7)
        print_dashboard(rows, title='Тест')
        out = capsys.readouterr().out
        assert 'в расчете (1)' in out
        assert 'Без отметок за месяц (1)' in out


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


class TestStartAndPreview:
    def test_start_info_labels(self):
        info = build_start_info('1_attlog.dat', 2026, 7, 10, 5, 'ignored')
        assert info['file'] == '1_attlog.dat'
        assert 'проигнорирована' in info['session_label']

    def test_print_start_screen(self, capsys):
        print_start_screen(build_start_info('f.dat', 2026, 7, 3, 2, 'fresh'))
        assert 'f.dat' in capsys.readouterr().out

    def test_preview_rows_and_print(self, setup_employees, mock_wage_rates, capsys):
        from datetime import timedelta
        summary = {
            101: ((1, timedelta(0), timedelta(0)),
                  (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0),
        }
        wages = {101: (800, 40, 840)}
        rows = build_preview_rows(summary, wages)
        assert rows[0]['name'] == 'Петров Иван'
        assert rows[0]['total'] == 840
        print_preview(rows)
        assert 'Петров' in capsys.readouterr().out

    def test_print_journal_empty_and_filled(self, capsys):
        print_journal([])
        assert 'не вносилось' in capsys.readouterr().out
        print_journal([{'ts': 't', 'name': 'N', 'date': 'd', 'action': 'a',
                        'before': 'b', 'after': 'c', 'randomized': True}])
        out = capsys.readouterr().out
        assert 'N' in out


class TestJournal:
    def test_single_fix_recorded(self, setup_employees):
        from core import analysis
        analysis.clear_journal()
        date_key = '2026-07-06'
        existing = make_dt(date_key, '17:00:00')
        tt = {date_key: {101: [existing, existing, 'work']}}
        single = [[date_key, existing]]
        with patch.object(analysis, '_get_marks_and_missed', return_value=(single, 0)):
            with patch('builtins.input', side_effect=['1', '08 00 00', 'д']):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        entries = analysis.get_journal()
        assert len(entries) == 1
        assert entries[0]['action'] == 'одиночная метка'
        assert entries[0]['date'] == date_key
        analysis.clear_journal()

    def test_missed_day_random_flag(self, setup_employees, monkeypatch):
        import randomazer_time_value as rtv
        monkeypatch.setattr(rtv, 'minutes_or_seconds_random', lambda: 15)
        from core import analysis
        analysis.clear_journal()
        with patch.object(analysis, '_get_marks_and_missed', return_value=(0, ['2026-07-06'])):
            inputs = ['1', '08', '17 00 00', 'д']
            with patch('builtins.input', side_effect=inputs):
                with patch.object(analysis, '_save_session', lambda x: None):
                    tt: dict = {}
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        entries = analysis.get_journal()
        assert len(entries) == 1
        assert entries[0]['action'] == 'заполнен день'
        assert entries[0]['randomized'] is True
        assert '2026-07-06' in tt
        analysis.clear_journal()
