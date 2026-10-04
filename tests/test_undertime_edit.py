"""Правка дней с недоработкой: поиск, сводка, список по номерам, карточка дня.

Недоработка — будний день с двумя разными отметками, где отработано строго меньше
нормы смены роли; ни порога, ни минимума нет (даже секунда). Такой день оператор
может переписать (приход/уход, только одну сторону, отпуск/прогул/больничный, авто).
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from core import analysis, config
from core.analysis import (
    UndertimeDay,
    _get_undertime_days,
    edit_undertime_days,
    format_undertime_line,
    search_undertime_days,
)
from core.day_models import DayMark

NORM = timedelta(hours=8)


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


def day(date_key, come, go, tag='work'):
    return DayMark(go=make_dt(date_key, go), come=make_dt(date_key, come), tag=tag)


def full_days(*dates, come='08:00:00', go='17:00:00'):
    return {d: {101: day(d, come, go)} for d in dates}


@pytest.fixture(autouse=True)
def _clean_state():
    analysis.clear_journal()
    config.MANUAL_EXCLUSIONS.clear()
    yield
    analysis.clear_journal()
    config.MANUAL_EXCLUSIONS.clear()


@pytest.fixture
def saves(monkeypatch):
    """Сессия не пишется на диск; считаем, сколько раз её сохраняли."""
    calls = []
    monkeypatch.setattr(analysis, '_save_session', lambda table: calls.append(1))
    return calls


def feed(*answers, prompts=None):
    """input(): ответы по очереди, затем EOFError; prompts — куда складывать приглашения."""
    it = iter(answers)

    def _input(prompt=''):
        if prompts is not None:
            prompts.append(prompt)
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return _input


class TestSearch:
    def test_any_shortfall_counts_even_one_second(self):
        tt = {
            '2026-07-06': {101: day('2026-07-06', '08:00:00', '15:59:59')},  # -1 с
            '2026-07-07': {101: day('2026-07-07', '08:00:00', '16:00:00')},  # ровно норма
            '2026-07-08': {101: day('2026-07-08', '08:00:00', '17:00:00')},  # переработка
            '2026-07-09': {101: day('2026-07-09', '08:00:00', '14:30:00')},  # -1:30
        }
        found = search_undertime_days(tt, 101, 2026, 7, NORM)
        assert [(i.date, i.shortfall) for i in found] == [
            ('2026-07-06', timedelta(seconds=1)),
            ('2026-07-09', timedelta(hours=1, minutes=30)),
        ]

    def test_weekend_other_status_and_other_month_ignored(self):
        tt = {
            '2026-07-11': {101: day('2026-07-11', '10:00:00', '12:00:00', tag='weekend')},
            '2026-07-13': {101: day('2026-07-13', '00:00:01', '00:00:01', tag='vacation')},
            '2026-08-03': {101: day('2026-08-03', '08:00:00', '10:00:00')},
        }
        assert search_undertime_days(tt, 101, 2026, 7, NORM) == []

    def test_single_mark_left_to_single_check(self):
        tt = {'2026-07-06': {101: day('2026-07-06', '08:00:00', '08:00:00')}}
        assert search_undertime_days(tt, 101, 2026, 7, NORM, skip_single=True) == []
        # если для роли одиночные отметки не проверяются, нулевой день — недоработка
        assert len(search_undertime_days(tt, 101, 2026, 7, NORM, skip_single=False)) == 1

    def test_legacy_list_marks_are_supported(self):
        come, go = make_dt('2026-07-06', '08:00:00'), make_dt('2026-07-06', '12:00:00')
        tt = {'2026-07-06': {101: [go, come, 'work']}}
        assert search_undertime_days(tt, 101, 2026, 7, NORM)[0].worked == timedelta(hours=4)

    def test_only_actual_time_roles_have_undertime(self, setup_employees):
        short = {d: {e: day(d, '08:00:00', '12:00:00') for e in (101, 102, 103)}
                 for d in ('2026-07-06',)}
        assert len(_get_undertime_days(short, 101, 2026, 7)) == 1  # цеховой: по факту
        assert _get_undertime_days(short, 102, 2026, 7) == []  # фикс. смена: нормы по факту нет
        assert _get_undertime_days(short, 103, 2026, 7) == []  # роль не участвует
        assert _get_undertime_days(short, 999, 2026, 7) == []  # нет в справочнике

    def test_line_is_readable(self):
        item = UndertimeDay('2026-07-09', make_dt('2026-07-09', '08:00:00'),
                            make_dt('2026-07-09', '14:30:00'), timedelta(hours=6, minutes=30), NORM)
        assert format_undertime_line(item) == (
            '09 Июля | Четверг | 08:00:00–14:30:00 | отработано 06:30:00 | недоработка 01:30:00')


class TestDashboard:
    def test_status_and_columns(self, setup_employees, mock_holidays_jan2026, mock_postponed_empty):
        from core.ui import build_dashboard_rows, summarize_employee

        tt = {
            '2026-07-06': {101: day('2026-07-06', '08:00:00', '14:30:00'),
                           102: day('2026-07-06', '08:00:00', '17:00:00')},
            '2026-07-07': {101: day('2026-07-07', '08:00:00', '15:59:59')},
        }
        by_id = {r['emp_id']: r for r in build_dashboard_rows(
            tt, [101, 102], 2026, 7, employees=setup_employees)}
        assert by_id[101]['under'] == 2
        assert by_id[101]['status'] == 'Править'  # пустые рабочие дни главнее
        assert by_id[102]['under'] == 0
        assert summarize_employee(0, 0, True, undertime_count=2)['status'] == 'Проверить'
        assert summarize_employee(1, 0, True, undertime_count=2)['status'] == 'Править'
        assert summarize_employee(0, 0, True)['status'] == 'OK'

    def test_table_shows_undertime(self, setup_employees, mock_holidays_jan2026,
                                   mock_postponed_empty, capsys):
        from core.ui import build_dashboard_rows, print_dashboard

        tt = full_days('2026-07-06')
        tt['2026-07-07'] = {101: day('2026-07-07', '08:00:00', '14:30:00')}
        rows = build_dashboard_rows(tt, [101], 2026, 7, employees=setup_employees)
        print_dashboard(rows, title='Тест', numbered=True)
        out = capsys.readouterr().out
        assert 'Недоработка' in out and '1 дн.' in out


class TestEditDay:
    def _table(self):
        tt = full_days('2026-07-06', '2026-07-07')
        tt['2026-07-09'] = {101: day('2026-07-09', '08:00:00', '14:30:00')}
        return tt

    def run(self, tt, *answers, employees=None):
        with patch('builtins.input', feed(*answers)):
            edit_undertime_days(tt, 101, 2026, 7, employees=employees)

    def test_new_times_replace_day_and_journal_keeps_old_value(self, setup_employees, saves):
        tt = self._table()
        self.run(tt, '1', '1', '8 0 0', '17 0 0', 'д')
        mark = tt['2026-07-09'][101]
        assert (mark.come, mark.go, mark.tag) == (
            make_dt('2026-07-09', '08:00:00'), make_dt('2026-07-09', '17:00:00'), 'work')
        (entry,) = analysis.get_journal()
        assert entry['action'] == 'правка недоработки: время'
        assert entry['before'] == '08:00:00 -> 14:30:00 [work]'
        assert entry['after'] == '08:00:00 -> 17:00:00 [work]'
        assert saves == [1]

    def test_only_departure_keeps_arrival(self, setup_employees, saves):
        tt = self._table()
        self.run(tt, '1', '8', '16 30 0', 'д')
        mark = tt['2026-07-09'][101]
        assert mark.come == make_dt('2026-07-09', '08:00:00')
        assert mark.go == make_dt('2026-07-09', '16:30:00')
        assert analysis.get_journal()[0]['action'] == 'правка недоработки: уход'

    def test_only_arrival_keeps_departure(self, setup_employees, saves):
        tt = full_days('2026-07-06')
        tt['2026-07-09'] = {101: day('2026-07-09', '11:00:00', '17:00:00')}
        self.run(tt, '1', '7', '8 0 0', 'д')
        mark = tt['2026-07-09'][101]
        assert mark.come == make_dt('2026-07-09', '08:00:00')
        assert mark.go == make_dt('2026-07-09', '17:00:00')
        assert analysis.get_journal()[0]['action'] == 'правка недоработки: приход'

    def test_impossible_pair_is_rejected_and_nothing_changes(self, setup_employees, saves, capsys):
        tt = self._table()
        before = _snapshot(tt)
        self.run(tt, '1', '7', '15 0 0', '0', '0')  # приход позже ухода → ошибка, назад
        assert _snapshot(tt) == before
        assert analysis.get_journal() == [] and saves == []
        assert 'позже ухода' in capsys.readouterr().out

    def test_declined_confirmation_changes_nothing(self, setup_employees, saves):
        tt = self._table()
        before = _snapshot(tt)
        self.run(tt, '1', '1', '8 0 0', '17 0 0', 'н', '0', '0')
        assert _snapshot(tt) == before
        assert analysis.get_journal() == [] and saves == []

    @pytest.mark.parametrize('key, tag, action', [
        ('2', 'vacation', 'правка недоработки: отпуск'),
        ('3', 'truancy', 'правка недоработки: прогул'),
        ('5', 'sick', 'правка недоработки: больничный'),
    ])
    def test_status_replaces_day(self, setup_employees, saves, key, tag, action):
        tt = self._table()
        self.run(tt, '1', key, 'д')
        assert tt['2026-07-09'][101].tag == tag
        (entry,) = analysis.get_journal()
        assert entry['action'] == action
        assert entry['before'] == '08:00:00 -> 14:30:00 [work]'

    def test_auto_fills_by_average_without_counting_the_day_itself(self, setup_employees, saves):
        tt = full_days('2026-07-06', '2026-07-07')
        tt['2026-07-09'] = {101: day('2026-07-09', '10:00:00', '12:00:00')}  # 2 ч — не в среднем
        self.run(tt, '1', '6', 'д')
        mark = tt['2026-07-09'][101]
        assert abs((mark.come - make_dt('2026-07-09', '08:00:00')).total_seconds()) <= 300
        assert abs((mark.go - make_dt('2026-07-09', '17:00:00')).total_seconds()) <= 300
        (entry,) = analysis.get_journal()
        assert entry['randomized'] is True and entry['before'] == '10:00:00 -> 12:00:00 [work]'

    def test_auto_unavailable_without_other_full_days(self, setup_employees, saves, capsys):
        tt = {'2026-07-09': {101: day('2026-07-09', '08:00:00', '14:30:00')}}
        self.run(tt, '1', '6', '0', '0')
        assert tt['2026-07-09'][101].go == make_dt('2026-07-09', '14:30:00')
        assert analysis.get_journal() == []
        assert 'Автозаполнение недоступно' in capsys.readouterr().out

    def test_day_still_short_after_edit_stays_in_list(self, setup_employees, saves):
        tt = self._table()
        self.run(tt, '1', '1', '8 0 0', '15 0 0', 'д', '0')
        assert tt['2026-07-09'][101].go == make_dt('2026-07-09', '15:00:00')
        assert [i.date for i in _get_undertime_days(tt, 101, 2026, 7)] == ['2026-07-09']

    def test_day_is_chosen_by_number(self, setup_employees, saves):
        tt = full_days('2026-07-06')
        tt['2026-07-07'] = {101: day('2026-07-07', '08:00:00', '12:00:00')}
        tt['2026-07-08'] = {101: day('2026-07-08', '08:00:00', '13:00:00')}
        self.run(tt, '2', '2', 'д')  # второй в списке — 08.07 — в отпуск
        assert tt['2026-07-08'][101].tag == 'vacation'
        assert tt['2026-07-07'][101].tag == 'work'

    def test_bad_number_reprompts_and_enter_leaves(self, setup_employees, saves, capsys):
        tt = self._table()
        self.run(tt, '99', 'abc', '')
        assert capsys.readouterr().out.count('Нет дня с номером') == 2

    def test_no_undertime_says_so(self, setup_employees, saves, capsys):
        self.run(full_days('2026-07-06'))
        assert 'Дней с недоработкой нет' in capsys.readouterr().out

    def test_journal_name_comes_from_passed_staff(self, setup_employees, saves):
        """Сотрудник есть только в переданном штате (напр. SQLite) — имя, а не «ID»."""
        from core.config import EmployeeData

        staff = {999: EmployeeData(id=999, first_name='Олег', last_name='Новый',
                                   role_id=1, role_name='Работник цеха')}
        tt = {'2026-07-09': {999: day('2026-07-09', '08:00:00', '12:00:00')}}
        with patch('builtins.input', feed('1', '2', 'д')):
            edit_undertime_days(tt, 999, 2026, 7, employees=staff)
        assert analysis.get_journal()[0]['name'] == 'Новый Олег'


def _snapshot(tt):
    return {d: {e: (m.come, m.go, m.tag) for e, m in emps.items()} for d, emps in tt.items()}


class TestReviewFlow:
    def test_print_lists_undertime_days(self, setup_employees, mock_holidays_jan2026,
                                        mock_postponed_empty, capsys):
        tt = full_days('2026-07-06')
        tt['2026-07-07'] = {101: day('2026-07-07', '08:00:00', '15:59:59')}
        analysis.analyze_for_print(tt, 101, 2026, 7)
        out = capsys.readouterr().out
        assert 'Дни с недоработкой' in out and 'недоработка 00:00:01' in out

    def test_menu_offers_only_applicable_items(self, setup_employees, saves):
        from core.review import review_employee

        tt = full_days('2026-07-06')
        tt['2026-07-07'] = {101: day('2026-07-07', '08:00:00', '14:30:00')}
        prompts: list[str] = []
        with patch.object(analysis, '_get_marks_and_missed', return_value=(0, 0)), \
                patch('builtins.input', feed('0', prompts=prompts)):
            review_employee(tt, setup_employees, 101, 2026, 7)
        assert '[3] править дни с недоработкой' in prompts[0]
        assert '[1]' not in prompts[0] and '[2]' not in prompts[0]

    def test_review_to_edit_and_back(self, setup_employees, saves, capsys):
        """Сводка → сотрудник → [3] → день 1 → новое время → «Проблем нет» → к расчёту."""
        from core.review import run_review

        tt = {'2026-07-06': {101: day('2026-07-06', '08:00:00', '17:00:00')},
              '2026-07-07': {101: day('2026-07-07', '08:00:00', '14:30:00')}}
        with patch.object(analysis, '_get_marks_and_missed', return_value=(0, 0)), \
                patch('builtins.input', feed('1', '3', '1', '1', '8 0 0', '17 0 0', 'д', '')):
            run_review(tt, {101: setup_employees[101]}, [101], 2026, 7)
        assert tt['2026-07-07'][101].go == make_dt('2026-07-07', '17:00:00')
        assert 'Проблем нет' in capsys.readouterr().out
        assert [e['action'] for e in analysis.get_journal()] == ['правка недоработки: время']
