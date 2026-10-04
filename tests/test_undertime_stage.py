"""Этап «Недоработки»: после разбора пропусков и до расчёта/Excel.

Все дни участников расчёта, отработанные меньше нормы смены (в том числе после
автозаполнения), — одним списком; по номеру строки день правится. Enter — к расчёту.
"""
import json
from datetime import datetime
from unittest.mock import patch

import pytest

from core import analysis, config
from core.day_models import DayMark


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


def day(date_key, come, go, tag='work'):
    return DayMark(go=make_dt(date_key, go), come=make_dt(date_key, come), tag=tag)


@pytest.fixture(autouse=True)
def _clean_state():
    analysis.clear_journal()
    config.MANUAL_EXCLUSIONS.clear()
    yield
    analysis.clear_journal()
    config.MANUAL_EXCLUSIONS.clear()


@pytest.fixture
def saves(monkeypatch):
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


def staff_with_second_worker(setup_employees):
    from core.config import EmployeeData

    staff = dict(setup_employees)
    staff[104] = EmployeeData(id=104, first_name='Пётр', last_name='Сидоров',
                              role_id=1, role_name='Работник цеха')
    return staff


def table():
    """101: 07.07 — 6 ч; 104: 08.07 — на секунду меньше нормы; 06.07 у обоих полный."""
    return {
        '2026-07-06': {101: day('2026-07-06', '08:00:00', '17:00:00'),
                       104: day('2026-07-06', '08:00:00', '17:00:00')},
        '2026-07-07': {101: day('2026-07-07', '08:00:00', '14:00:00')},
        '2026-07-08': {104: day('2026-07-08', '08:00:00', '15:59:59')},
    }


class TestUndertimeStage:
    def test_rows_follow_staff_order_then_dates(self, setup_employees):
        from core.review import build_undertime_rows

        rows = build_undertime_rows(table(), staff_with_second_worker(setup_employees),
                                    [104, 101], 2026, 7)
        assert [(r['name'], r['item'].date) for r in rows] == [
            ('Сидоров Пётр', '2026-07-08'), ('Петров Иван', '2026-07-07')]

    def test_nothing_to_show_asks_nothing(self, setup_employees, capsys):
        from core.review import run_undertime_review

        def boom(prompt=''):
            raise AssertionError('этап без недоработок не должен ничего спрашивать')

        full = {d: {101: day(d, '08:00:00', '17:00:00')} for d in ('2026-07-06', '2026-07-07')}
        with patch('builtins.input', boom):
            run_undertime_review(full, setup_employees, [101], 2026, 7)
        assert 'Недоработок нет.' in capsys.readouterr().out

    def test_overview_lists_every_employee_and_enter_changes_nothing(
            self, setup_employees, capsys, saves):
        from core.review import run_undertime_review

        with patch('builtins.input', feed('')):
            run_undertime_review(table(), staff_with_second_worker(setup_employees),
                                 [101, 104], 2026, 7)
        out = capsys.readouterr().out
        assert 'Петров' in out and 'Сидоров' in out
        assert 'Дней: 2, сотрудников: 2' in out
        assert analysis.get_journal() == [] and saves == []

    def test_row_number_is_global_across_employees(self, setup_employees, saves):
        from core.review import run_undertime_review

        tt = table()
        with patch('builtins.input', feed('2', '2', 'д', '')):  # строка 2 — день Сидорова
            run_undertime_review(tt, staff_with_second_worker(setup_employees),
                                 [101, 104], 2026, 7)
        assert tt['2026-07-08'][104].tag == 'vacation'
        assert tt['2026-07-07'][101].tag == 'work'
        (entry,) = analysis.get_journal()
        assert entry['name'] == 'Сидоров Пётр' and entry['emp_id'] == 104

    def test_list_refreshes_and_still_short_day_stays(self, setup_employees, saves, capsys):
        from core.review import run_undertime_review

        tt = table()
        # день Петрова доводим до 7 ч — всё ещё недоработка, остаётся в списке
        with patch('builtins.input', feed('1', '1', '8 0 0', '15 0 0', 'д', '')):
            run_undertime_review(tt, staff_with_second_worker(setup_employees),
                                 [101, 104], 2026, 7)
        assert tt['2026-07-07'][101].go == make_dt('2026-07-07', '15:00:00')
        assert capsys.readouterr().out.count('Дней: 2, сотрудников: 2') == 2  # до и после

    def test_fixed_day_leaves_the_list(self, setup_employees, saves, capsys):
        from core.review import run_undertime_review

        tt = table()
        with patch('builtins.input', feed('1', '1', '8 0 0', '17 0 0', 'д', '')):
            run_undertime_review(tt, staff_with_second_worker(setup_employees),
                                 [101, 104], 2026, 7)
        out = capsys.readouterr().out
        assert 'Дней: 2, сотрудников: 2' in out and 'Дней: 1, сотрудников: 1' in out

    def test_excluded_employee_is_not_shown(self, setup_employees, capsys):
        from core.review import run_undertime_review

        config.MANUAL_EXCLUSIONS[104] = config.MANUAL_EXCLUSION_REASON
        with patch('builtins.input', feed('2', '')):  # строки 2 уже нет
            run_undertime_review(table(), staff_with_second_worker(setup_employees),
                                 [101, 104], 2026, 7)
        out = capsys.readouterr().out
        assert 'Сидоров' not in out and 'Нет строки с номером' in out

    def test_bad_number_reprompts_and_eof_leaves(self, setup_employees, capsys):
        from core.review import run_undertime_review

        with patch('builtins.input', feed('99', 'abc')):  # затем EOF — выход без трейсбека
            run_undertime_review(table(), staff_with_second_worker(setup_employees),
                                 [101, 104], 2026, 7)
        assert capsys.readouterr().out.count('Нет строки с номером') == 2

    def test_plain_fallback_without_rich(self, setup_employees, capsys, monkeypatch):
        from core import ui
        from core.review import build_undertime_rows

        monkeypatch.setattr(ui, 'HAS_RICH', False)
        rows = build_undertime_rows(table(), staff_with_second_worker(setup_employees),
                                    [101, 104], 2026, 7)
        ui.print_undertime_overview(rows)
        out = capsys.readouterr().out
        assert '1. Петров Иван | 07.07 Вт | 08:00:00–14:00:00 | ' \
               'отработано 06:00:00 | недоработка 02:00:00' in out
        assert '2. Сидоров Пётр | 08.07 Ср' in out


@pytest.fixture
def september_with_short_day(tmp_path):
    """Сентябрь 2026: у 101 день 09.09 — 4 часа вместо 9; у 102 всё полное."""
    root = tmp_path / 'input'
    var = root / 'variable_data_for_app'
    var.mkdir(parents=True)
    (var / 'roles_employee.dat').write_text('[1] Работник цеха\n', encoding='utf-8')
    (var / 'id_employee.dat').write_text(
        '101 [1] Иванов Иван\n102 [1] Петров Пётр\n', encoding='utf-8')
    for name in ('settlement_exceptions.dat', 'holidays.dat', 'postponed_working_days.dat'):
        (var / name).write_text('', encoding='utf-8')
    lines = []
    for d in range(1, 31):
        date = datetime(2026, 9, d)
        if date.weekday() >= 5:
            continue
        for emp in (101, 102):
            leave = '12:00:00' if (emp, d) == (101, 9) else '17:00:00'
            lines += [f'{emp} {date:%Y-%m-%d} 08:00:00 1', f'{emp} {date:%Y-%m-%d} {leave} 1']
    (root / 'marks.dat').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return root


def _argv(root, out, *extra):
    return ['--data-dir', str(root), '--output-dir', str(out), '-f', 'marks.dat',
            '-y', '2026', '-m', '9', '-k', 't', *extra]


def test_main_offers_undertime_before_reports(september_with_short_day, tmp_path,
                                              monkeypatch, capsys):
    """Хаб → Enter → этап «Недоработки» → день 1 в отпуск → расчёт и Excel."""
    from main import main

    monkeypatch.chdir(tmp_path)
    out = tmp_path / 'out'
    prompts: list[str] = []
    monkeypatch.setattr('builtins.input', feed('', '1', '2', 'д', prompts=prompts))
    main(_argv(september_with_short_day, out))
    text = capsys.readouterr().out
    assert any('Номер строки — править день' in p for p in prompts)
    assert text.index('Недоработки') < text.index('Отчеты')
    assert list(out.glob('*.xlsx'))  # расчёт и Excel состоялись после правки
    package = json.loads(next(out.glob('payroll_2026_09_rev*.json')).read_text(encoding='utf-8'))
    (entry,) = package['journal']
    assert entry['action'] == 'правка недоработки: отпуск' and entry['date'] == '2026-09-09'
    assert entry['before'] == '08:00:00 -> 12:00:00 [work]'


def test_main_no_edit_skips_undertime_stage(september_with_short_day, tmp_path,
                                            monkeypatch, capsys):
    from main import main

    def boom(prompt=''):
        raise AssertionError('--no-edit не должен ничего спрашивать')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('builtins.input', boom)
    main(_argv(september_with_short_day, tmp_path / 'out', '--no-edit'))
    text = capsys.readouterr().out
    assert 'Дни с недоработкой' in text  # печатный список остаётся
    assert 'Номер строки' not in text
