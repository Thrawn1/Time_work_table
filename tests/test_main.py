"""Тесты разбора ключа и режима зарплаты."""
from decimal import Decimal

from main import parse_secret_key


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
