from sys import path
path.append('..')
from analyze_data import definition_of_working_day


def test_definition_of_working_day_workday():
    request_date = '2021-03-01'
    calculated_data = definition_of_working_day(request_date)
    expected_result = ('work','Понедельник')
    assert calculated_data == expected_result

def test_definition_of_working_day_weekend():
    request_date = '2021-03-20'
    calculated_data = definition_of_working_day(request_date)
    expected_result = ('weekend','Суббота')
    assert calculated_data == expected_result

def test_definition_of_working_day_holiday():
    request_date = '2021-03-08'
    calculated_data = definition_of_working_day(request_date)
    expected_result = ('holiday','Понедельник')
    assert calculated_data == expected_result

def test_definition_of_working_day_postponed_working_days():
    request_date = '2021-02-20'
    calculated_data = definition_of_working_day(request_date)
    expected_result = ('work','Суббота')
    assert calculated_data == expected_result