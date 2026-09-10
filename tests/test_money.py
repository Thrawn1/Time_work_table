"""Деньги: Decimal, HALF_UP, ставка за смену, формат 2 знака."""
from datetime import timedelta
from decimal import Decimal

from core.money import (
    as_decimal,
    format_money,
    quantize_money,
    quantize_rate,
    timedelta_to_hours,
    timedelta_to_seconds,
)


class TestQuantizeHalfUp:
    def test_half_up_not_bankers(self):
        # Бухгалтерское: .005 вверх; у round() было бы HALF_EVEN
        assert quantize_money(Decimal('2.345')) == Decimal('2.35')
        assert quantize_money(Decimal('2.335')) == Decimal('2.34')
        assert quantize_money(Decimal('2.355')) == Decimal('2.36')

    def test_rate_keeps_kopecks(self):
        # Раньше round(float*key) резал до целых рублей
        assert quantize_rate(Decimal('100.005')) == Decimal('100.01')
        assert quantize_rate(Decimal('425.867508')) == Decimal('425.87')

    def test_no_float_dust(self):
        assert as_decimal(0.1) + as_decimal(0.2) == Decimal('0.3')
        assert as_decimal(800) == Decimal('800')
        assert as_decimal('40.00') == Decimal('40.00')


class TestTimedeltaExact:
    def test_seconds_exact(self):
        assert timedelta_to_seconds(timedelta(hours=8)) == Decimal('28800')
        assert timedelta_to_seconds(timedelta(seconds=1)) == Decimal('1')

    def test_hours_exact(self):
        assert timedelta_to_hours(timedelta(hours=8)) == Decimal('8')
        assert timedelta_to_hours(timedelta(seconds=1)) == Decimal('1') / Decimal('3600')
        # float дал бы 0.0002777777777777778 с мусором — у нас точный Decimal
        assert timedelta_to_hours(timedelta(hours=2)) == Decimal('2')


class TestFormatMoney:
    def test_always_two_decimals(self):
        assert format_money(Decimal('800')) == '800.00'
        assert format_money(Decimal('6400.00')) == '6400.00'
        assert format_money(0) == '0.00'
        assert format_money(Decimal('2.345')) == '2.35'


class TestDailyWagesDecimal:
    def test_standard_day(self, setup_employees, mock_wage_rates):
        from core.calculations import calculate_wages
        summary = {101: ((1, timedelta(0), timedelta(0)),
                         (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)}
        total, milk, with_milk = calculate_wages(summary)[101]
        assert isinstance(total, Decimal)
        assert total == Decimal('800.00')  # 800 руб/смена
        assert milk == Decimal('40.00')
        assert with_milk == Decimal('840.00')

    def test_one_second_overtime_quantized_once(self, setup_employees, mock_wage_rates):
        from core.calculations import calculate_wages
        summary = {101: ((1, timedelta(seconds=1), timedelta(0)),
                         (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)}
        total, _, _ = calculate_wages(summary)[101]
        # 800 + 1.5*(800/8)/3600 = 800.0416... -> 800.04 (HALF_UP, один раз в конце)
        assert total == Decimal('800.04')

    def test_frac_rate_overtime_half_up(self, setup_employees, monkeypatch):
        from core import calculations
        monkeypatch.setattr(calculations, 'load_wage_rates', lambda: {101: Decimal('100.005')})
        summary = {101: ((1, timedelta(0), timedelta(0)),
                         (0, timedelta(0), timedelta(0), timedelta(0)), 0, 0)}
        total, _, _ = calculations.calculate_wages(summary)[101]
        # ставка 100.005 руб/смена за 1 день -> 100.01 (HALF_UP, без float-хвостов)
        assert total == Decimal('100.01')

    def test_load_wage_rates_keeps_kopecks(self, tmp_path, monkeypatch):
        import os
        from core import config
        monkeypatch.chdir(tmp_path)
        os.makedirs('data/variable_data_for_app', exist_ok=True)
        # decrypted = '425.867508' (запись '867508.425' наоборот); key = 1.00
        with open('data/variable_data_for_app/wage_rates.dat', 'w', encoding='utf-8') as f:
            f.write('101 [867508.425]\n')
        with open('_secret_key.tmp', 'w', encoding='utf-8') as f:
            f.write('1.00')
        rates = config.load_wage_rates()
        assert rates[101] == Decimal('425.87')
        assert isinstance(rates[101], Decimal)
