"""Тесты разбора ключа и режима зарплаты."""
import argparse
import sys
import types
from decimal import Decimal

import pytest

from main import parse_secret_key, resolve_secret_key


def _ns(key):
    return argparse.Namespace(key=key)


def _tty(monkeypatch, is_tty: bool):
    monkeypatch.setattr(sys, 'stdin', types.SimpleNamespace(isatty=lambda: is_tty))


class TestParseSecretKey:
    def test_time_only_t(self):
        secret, mode, warn = parse_secret_key('t')
        assert secret == Decimal('0.00') and mode is False and warn is None

    def test_time_only_zero(self):
        secret, mode, warn = parse_secret_key('0')
        assert secret == Decimal('0.00') and mode is False and warn is None

    def test_valid_key(self):
        secret, mode, warn = parse_secret_key('12345')
        assert secret == Decimal('123.45') and mode is True and warn is None

    def test_garbage_warns(self):
        secret, mode, warn = parse_secret_key('abc')
        assert secret == Decimal('0.00') and mode is False and warn is not None

    def test_short_key_warns(self):
        # длина <= 2 старым правилом отбрасывалась молча — теперь с предупреждением
        secret, mode, warn = parse_secret_key('42')
        assert secret == Decimal('0.00') and mode is False and warn is not None

    def test_key_exact_decimal(self):
        # Ключ делится на 100 точно: Decimal('123.45'), а не float 123.4499...
        secret, _, _ = parse_secret_key('12345')
        assert isinstance(secret, Decimal)
        assert secret == Decimal('12345') / Decimal('100')

    def test_long_key_preserves_all_digits(self):
        raw = '1234567890' * 12 + '12'
        secret, mode, warning = parse_secret_key(raw)
        assert secret == Decimal(raw[:-2] + '.' + raw[-2:])
        assert mode is True and warning is None

    @pytest.mark.parametrize('raw', ['²²²', '１２３', 'abc12345'])
    def test_invalid_key_does_not_raise_or_echo(self, raw):
        secret, mode, warning = parse_secret_key(raw)
        assert secret == Decimal('0.00') and mode is False
        assert warning and raw not in warning


class TestResolveSecretKey:
    def test_explicit_key_passthrough(self, capsys):
        assert resolve_secret_key(_ns('t')) == (Decimal('0.00'), False)
        assert resolve_secret_key(_ns('12345')) == (Decimal('123.45'), True)

    def test_explicit_garbage_warns_time_only(self, capsys):
        secret, mode = resolve_secret_key(_ns('abc'))
        assert (secret, mode) == (Decimal('0.00'), False)
        assert 'ВНИМАНИЕ' in capsys.readouterr().out

    def test_no_key_non_tty_time_only(self, monkeypatch, capsys):
        _tty(monkeypatch, False)
        assert resolve_secret_key(_ns(None)) == (Decimal('0.00'), False)
        assert 'неинтерактивный' in capsys.readouterr().out

    def test_menu_time_only(self, monkeypatch):
        _tty(monkeypatch, True)
        monkeypatch.setattr('core.ui.info', lambda *a, **k: None)
        monkeypatch.setattr('core.ui.ask_menu', lambda *a, **k: '1')
        assert resolve_secret_key(_ns(None)) == (Decimal('0.00'), False)

    def test_menu_salary_hidden_input(self, monkeypatch, capsys):
        _tty(monkeypatch, True)
        monkeypatch.setattr('core.ui.info', lambda *a, **k: None)
        monkeypatch.setattr('core.ui.ask_menu', lambda *a, **k: '2')
        monkeypatch.setattr('getpass.getpass', lambda *a, **k: '12345')
        secret, mode = resolve_secret_key(_ns(None))
        assert (secret, mode) == (Decimal('123.45'), True)
        assert '12345' not in capsys.readouterr().out  # ключ нигде не печатается

    def test_menu_empty_key_back_to_menu(self, monkeypatch):
        _tty(monkeypatch, True)
        monkeypatch.setattr('core.ui.info', lambda *a, **k: None)
        answers = iter(['2', '1'])
        monkeypatch.setattr('core.ui.ask_menu', lambda *a, **k: next(answers))
        monkeypatch.setattr('getpass.getpass', lambda *a, **k: '  ')
        assert resolve_secret_key(_ns(None)) == (Decimal('0.00'), False)

    def test_menu_garbage_thrice_exits_1(self, monkeypatch, capsys):
        import pytest
        _tty(monkeypatch, True)
        monkeypatch.setattr('core.ui.info', lambda *a, **k: None)
        monkeypatch.setattr('core.ui.ask_menu', lambda *a, **k: '2')
        monkeypatch.setattr('getpass.getpass', lambda *a, **k: 'abc')
        with pytest.raises(SystemExit) as e:
            resolve_secret_key(_ns(None))
        assert e.value.code == 1
        assert 'abc' not in capsys.readouterr().out

    def test_menu_cancel_exits_0(self, monkeypatch):
        import pytest
        _tty(monkeypatch, True)
        monkeypatch.setattr('core.ui.info', lambda *a, **k: None)
        monkeypatch.setattr('core.ui.ask_menu', lambda *a, **k: '0')
        with pytest.raises(SystemExit) as e:
            resolve_secret_key(_ns(None))
        assert e.value.code == 0

    def test_menu_eof_falls_back_time_only(self, monkeypatch, capsys):
        # < NUL в Windows: isatty() == True, но input() сразу EOF
        _tty(monkeypatch, True)
        monkeypatch.setattr('core.ui.info', lambda *a, **k: None)

        def _eof(*a, **k):
            raise EOFError

        monkeypatch.setattr('core.ui.ask_menu', _eof)
        assert resolve_secret_key(_ns(None)) == (Decimal('0.00'), False)
        assert 'Ввод недоступен' in capsys.readouterr().out


class TestPeriodValidation:
    @pytest.mark.parametrize('flag,value', [
        ('-m', '0'), ('-m', '13'), ('-m', 'abc'),
        ('-y', '0'), ('-y', '-1'), ('-y', '10000'),
    ])
    def test_invalid_argument_fails_before_creating_output(self, flag, value, tmp_path, capsys):
        from main import main
        output = tmp_path / 'out'
        with pytest.raises(SystemExit) as exc:
            main([flag, value, '--output-dir', str(output)])
        assert exc.value.code == 2
        assert not output.exists()
        assert 'должен быть' in capsys.readouterr().err

    def test_invalid_interactive_month_has_diagnostic(self, monkeypatch, capsys):
        from core.cli import build_parser, resolve_period
        parser = build_parser()
        args = parser.parse_args(['-y', '2026'])
        monkeypatch.setattr('builtins.input', lambda _: '13')
        with pytest.raises(SystemExit) as exc:
            resolve_period(args, parser)
        assert exc.value.code == 2
        assert 'месяц должен быть' in capsys.readouterr().err

    def test_closed_input_has_diagnostic(self, monkeypatch, capsys):
        from core.cli import build_parser, resolve_period
        parser = build_parser()

        def closed_input(_):
            raise EOFError

        monkeypatch.setattr('builtins.input', closed_input)
        with pytest.raises(SystemExit) as exc:
            resolve_period(parser.parse_args([]), parser)
        assert exc.value.code == 2
        assert '-y и -m' in capsys.readouterr().err
