"""Тесты новой расчётной модели: ставки, бонусы, границы (§7 плана)."""

from decimal import Decimal

import pytest

from core.pay_calc import (
    PayInputs, calculate_pay, check_full_month, monthly_rates,
    seniority_rate_for_service,
)


def _base_inputs(**over):
    kw = dict(
        monthly_base=Decimal('60000.00'), base_day_hours=8,
        full_month_bonus=Decimal('5000.00'), workdays=20,
        shift_norm_hours=Decimal('8'), fact_hours=Decimal('160'),
        workdays_present=20,
        overtime_eligible=True, full_month_eligible=True,
        seniority_eligible=True, overtime_coef=Decimal('1.5'),
        seniority_rate=Decimal('0.10'),
    )
    kw.update(over)
    return PayInputs(**kw)


def test_rates_20_22_23_days():
    rd, rh = monthly_rates(Decimal('60000.00'), 20)
    assert rd == Decimal('3000')
    assert rh == Decimal('375')
    rd22, rh22 = monthly_rates(Decimal('60000.00'), 22)
    assert rd22 == Decimal('60000') / Decimal('22')
    assert rh22 == Decimal('60000') / (Decimal('22') * Decimal('8'))
    # Производные не квантованы: точное значение, а не 2727.27
    assert rd22 != Decimal('2727.27')
    rd23, rh23 = monthly_rates(Decimal('60000.00'), 23)
    assert rh23 == Decimal('60000') / (Decimal('23') * Decimal('8'))


def test_full_month_gives_base_without_kopeck_loss():
    # Полная норма будней по 8 часов → обычная оплата ровно 60 000 ₽
    # даже когда дневная ставка некруглая (22 дня).
    res = calculate_pay(_base_inputs(
        workdays=22, fact_hours=Decimal('176'), workdays_present=22,
        overtime_eligible=False, full_month_eligible=False,
        seniority_eligible=False, seniority_rate=Decimal('0'),
    ))
    assert res.ordinary_pay == Decimal('60000.00')
    assert res.total == Decimal('60000.00')


def test_section_2_5_illustration():
    # 20 раб. дней, +10 ч сверх нормы, все бонусы, стаж 10%:
    # 60000 + 5625 + 5000 + 7062.50 = 77687.50
    res = calculate_pay(_base_inputs(fact_hours=Decimal('170')))
    assert res.rate_hour == Decimal('375')
    assert res.overtime_hours == Decimal('10')
    assert res.overtime_bonus == Decimal('5625.00')
    assert res.full_month_bonus == Decimal('5000.00')
    assert res.seniority_basis_exact == Decimal('70625.00')
    assert res.seniority_bonus == Decimal('7062.50')
    assert res.total == Decimal('77687.50')


def test_no_double_overtime_payment():
    # Обычная оплата capped нормой: сверхурочные часы не сидят в ordinary.
    res = calculate_pay(_base_inputs(fact_hours=Decimal('170')))
    assert res.ordinary_hours == Decimal('160')
    assert res.ordinary_pay == Decimal('60000.00')


def test_overtime_ineligible_is_zero():
    res = calculate_pay(_base_inputs(fact_hours=Decimal('170'), overtime_eligible=False))
    assert res.overtime_hours == Decimal('0')
    assert res.overtime_bonus == Decimal('0.00')


def test_full_month_strict_reasons():
    ok, reason = check_full_month(20, 20, Decimal('160'), Decimal('160'), 0, 0, False, True, True)
    assert ok
    bad_cases = [
        dict(vacation_days=1),
        dict(truancy_days=1),
        dict(workdays_present=19),
        dict(fact_hours=Decimal('159')),
        dict(single_mark_issue=True),
        dict(employed_whole_month=False),
    ]
    for patch in bad_cases:
        inp = _base_inputs(**patch)
        res = calculate_pay(inp)
        assert res.full_month_ok is False
        assert res.full_month_bonus == Decimal('0.00')


def test_full_month_ineligible_role():
    res = calculate_pay(_base_inputs(full_month_eligible=False))
    assert res.full_month_ok is False
    assert res.full_month_reason == 'роль не имеет права на бонус'


def test_seniority_basis_uses_full_base_for_partial_month():
    # Неполный месяц: основа стажа — вся база 60 000 (решение шага 0),
    # а не фактическая обычная оплата.
    res = calculate_pay(_base_inputs(
        fact_hours=Decimal('80'), workdays_present=10,
        overtime_eligible=False, full_month_eligible=False,
    ))
    assert res.ordinary_pay == Decimal('30000.00')
    assert res.seniority_basis_exact == Decimal('60000.00')
    assert res.seniority_bonus == Decimal('6000.00')


def test_total_is_sum_of_quantized_components():
    res = calculate_pay(_base_inputs(fact_hours=Decimal('170')))
    assert res.total == res.ordinary_pay + res.overtime_bonus + res.full_month_bonus + res.seniority_bonus
    assert res.total_with_milk == res.total + res.milk_amount


def test_zero_workdays_is_explicit_error():
    with pytest.raises(ValueError, match='D=0'):
        monthly_rates(Decimal('60000.00'), 0)


def test_seniority_scale_lookup():
    scale = [(0, Decimal('0')), (5, Decimal('0.10')), (10, Decimal('0.15'))]
    assert seniority_rate_for_service(scale, 0) == Decimal('0')
    assert seniority_rate_for_service(scale, 4.9) == Decimal('0')
    assert seniority_rate_for_service(scale, 5) == Decimal('0.10')
    assert seniority_rate_for_service(scale, 12) == Decimal('0.15')


def test_overtime_monthly_compensates_undertime():
    # Месячная схема: недоработка одного дня компенсируется переработкой
    # другого — важен итог месяца, а не превышение каждого дня.
    # Факт 160 при норме 160 → переработки нет, хотя внутри месяца дни разные.
    res = calculate_pay(_base_inputs(fact_hours=Decimal('160')))
    assert res.overtime_hours == Decimal('0')
    assert res.full_month_ok is True
