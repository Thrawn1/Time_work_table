from sys import path
path.append('..')
from analyze_data import translation_into_russian_names,month_name_for_print


def test_translation_into_russian_names_month_good():
    request_name = 'March'
    request_type = 'month'
    calculated_data = translation_into_russian_names(request_name,request_type)
    expected_result = 'Марта'
    assert calculated_data == expected_result


def test_translation_into_russian_names_weekday_good():
    request_name = 'Tuesday'
    request_type = 'weekday'
    calculated_data = translation_into_russian_names(request_name,request_type)
    expected_result = 'Вторник'
    assert calculated_data == expected_result

def test_month_name_for_print():
    request_id_month = 5
    calculated_data = month_name_for_print(request_id_month)
    expected_result = 'Май'
    assert calculated_data == expected_result