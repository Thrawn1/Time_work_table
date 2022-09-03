from sys import path
path.append('..')
from build_data_array import determination_period


def test_func_determination_period_true():
    request_year = 2021
    request_month = 3
    request_line = '        4	2021-03-01 06:30:00	1	255	1	0\n'
    calculated_data = determination_period(request_line,request_year,request_month)
    expected_result = True
    assert calculated_data == expected_result

def test_func_determination_period_false():
    request_year = 2022
    request_month = 4
    request_line = '        4	2021-03-01 06:30:00	1	255	1	0\n'
    calculated_data = determination_period(request_line,request_year,request_month)
    expected_result = False
    assert calculated_data == expected_result
