"""Тесты разбора ключа и режима зарплаты."""
from main import parse_secret_key


class TestParseSecretKey:
    def test_time_only_t(self):
        secret, mode, warn = parse_secret_key('t')
        assert secret == 0.0 and mode is False and warn is None

    def test_time_only_zero(self):
        secret, mode, warn = parse_secret_key('0')
        assert secret == 0.0 and mode is False and warn is None

    def test_valid_key(self):
        secret, mode, warn = parse_secret_key('12345')
        assert secret == 123.45 and mode is True and warn is None

    def test_garbage_warns(self):
        secret, mode, warn = parse_secret_key('abc')
        assert secret == 0.0 and mode is False and warn is not None

    def test_short_key_warns(self):
        # длина <= 2 старым правилом отбрасывалась молча — теперь с предупреждением
        secret, mode, warn = parse_secret_key('42')
        assert secret == 0.0 and mode is False and warn is not None
