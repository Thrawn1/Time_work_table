"""Тесты строгого ввода времени (P1 #8)."""
import pytest
from datetime import datetime
from unittest.mock import patch

from randomazer_time_value import (
    parse_time_input,
    parse_and_fill,
    format_time,
)
from core.analysis import _validate_pair, analyze_for_edit


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestParseTimeInput:
    def test_full_valid(self):
        data, missing, err = parse_time_input('08 30 00')
        assert err is None
        assert missing == []
        assert data == {'H': 8, 'M': 30, 'S': 0}

    def test_short_forms_are_missing_not_error(self):
        data, missing, err = parse_time_input('8')
        assert err is None
        assert data['H'] == 8
        assert set(missing) == {'M', 'S'}

        data, missing, err = parse_time_input('8 30')
        assert err is None
        assert missing == ['S']

    @pytest.mark.parametrize('bad', ['08 99 00', '08 30 99', '25 00 00', '24 00 00'])
    def test_out_of_range_is_error_not_random(self, bad):
        _data, _missing, err = parse_time_input(bad)
        assert err is not None

    @pytest.mark.parametrize('bad', ['08 30 00 extra', '1 2 3 4', '08 xx 00', '', '   ', 'ab', '8.5 00 00'])
    def test_garbage_is_error(self, bad):
        _data, _missing, err = parse_time_input(bad)
        assert err is not None

    def test_leading_zeros_length_rejected(self):
        # Раньше '008' проходил isdigit и падал в strptime с ValueError.
        _data, _missing, err = parse_time_input('008 30 00')
        assert err is not None

    def test_missing_never_includes_explicit_typo(self):
        # '99' — это ошибка, а не missing для рандома.
        _data, missing, err = parse_time_input('08 99 00')
        assert err is not None
        assert missing == []

    def test_parse_and_fill_rejects_typo(self):
        with pytest.raises(ValueError):
            parse_and_fill('08 99 00')
        with pytest.raises(ValueError):
            parse_and_fill('08 30 00 extra')
        with pytest.raises(ValueError):
            parse_and_fill('008 30 00')

    def test_parse_and_fill_randomizes_only_missing(self, monkeypatch):
        import randomazer_time_value as rtv
        monkeypatch.setattr(rtv, 'minutes_or_seconds_random', lambda: 17)
        time_str, randomized = parse_and_fill('08')
        assert time_str == '08 17 17'
        assert set(randomized) == {'M', 'S'}
        time_str, randomized = parse_and_fill('08 30 00')
        assert time_str == '08 30 00'
        assert randomized == []

    def test_format_time(self):
        assert format_time({'H': 8, 'M': 5, 'S': 3}) == '08 05 03'


class TestValidatePair:
    def test_equal_rejected(self):
        dt = make_dt('2026-07-06', '08:00:00')
        assert _validate_pair(dt, dt) is not None

    def test_reverse_rejected(self):
        come = make_dt('2026-07-06', '18:00:00')
        go = make_dt('2026-07-06', '17:00:00')
        assert _validate_pair(come, go) is not None

    def test_normal_accepted(self):
        come = make_dt('2026-07-06', '08:00:00')
        go = make_dt('2026-07-06', '17:00:00')
        assert _validate_pair(come, go) is None


class TestAnalyzeForEditValidation:
    def test_reverse_time_not_saved(self, setup_employees):
        """Приход 18:00 при уходе 17:00 не сохраняется."""
        from core import analysis
        date_key = '2026-07-06'
        existing = make_dt(date_key, '17:00:00')
        tt = {date_key: {101: [existing, existing, 'work']}}
        single = [[date_key, existing]]
        with patch.object(analysis, '_get_marks_and_missed', return_value=(single, 0)):
            # 1=приход, 18:00 (невалидно) -> 0 отмена времени -> 0 пропуск дня
            inputs = ['1', '18 00 00', '0', '0']
            with patch('builtins.input', side_effect=inputs):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        assert tt[date_key][101][0] == existing
        assert tt[date_key][101][1] == existing

    def test_equal_time_not_saved(self, setup_employees):
        """Ввод равный второй отметке не сохраняется."""
        from core import analysis
        date_key = '2026-07-06'
        existing = make_dt(date_key, '08:00:00')
        tt = {date_key: {101: [existing, existing, 'work']}}
        single = [[date_key, existing]]
        with patch.object(analysis, '_get_marks_and_missed', return_value=(single, 0)):
            # 2=уход, 08:00 (равно приходу) -> отмена
            inputs = ['2', '08 00 00', '0', '0']
            with patch('builtins.input', side_effect=inputs):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        assert tt[date_key][101][0] == existing
        assert tt[date_key][101][1] == existing

    def test_typo_not_filled_with_random(self, setup_employees):
        """'08 99 00' отклоняется, а не превращается в случайные минуты."""
        from core import analysis
        date_key = '2026-07-06'
        existing = make_dt(date_key, '17:00:00')
        tt = {date_key: {101: [existing, existing, 'work']}}
        single = [[date_key, existing]]
        with patch.object(analysis, '_get_marks_and_missed', return_value=(single, 0)):
            inputs = ['1', '08 99 00', '0', '0']
            with patch('builtins.input', side_effect=inputs):
                with patch.object(analysis, '_save_session', lambda x: None):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        # Ничего не сохранено — опечатка не стала случайными минутами.
        assert tt[date_key][101][1] == existing

    def test_valid_time_saved_after_confirm(self, setup_employees):
        """Валидный приход сохраняется после подтверждения."""
        from core import analysis
        date_key = '2026-07-06'
        existing = make_dt(date_key, '17:00:00')
        tt = {date_key: {101: [existing, existing, 'work']}}
        single = [[date_key, existing]]
        with patch.object(analysis, '_get_marks_and_missed', return_value=(single, 0)):
            inputs = ['1', '08 00 00', 'д']
            saved = []
            with patch('builtins.input', side_effect=inputs):
                with patch.object(analysis, '_save_session', lambda x: saved.append(1)):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        assert tt[date_key][101][1] == make_dt(date_key, '08:00:00')
        assert tt[date_key][101][0] == existing
        assert len(saved) == 1

    def test_decline_does_not_save(self, setup_employees):
        """Отказ на подтверждении не сохраняет, пропуск — выходит."""
        from core import analysis
        date_key = '2026-07-06'
        existing = make_dt(date_key, '17:00:00')
        tt = {date_key: {101: [existing, existing, 'work']}}
        single = [[date_key, existing]]
        with patch.object(analysis, '_get_marks_and_missed', return_value=(single, 0)):
            inputs = ['1', '08 00 00', 'н', '0', '0']
            with patch('builtins.input', side_effect=inputs):
                with patch.object(analysis, '_save_session', lambda x: (_ for _ in ()).throw(AssertionError('save must not be called'))):
                    analysis.analyze_for_edit(tt, 101, 2026, 7)
        assert tt[date_key][101][1] == existing
