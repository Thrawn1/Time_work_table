import sys
import os
sys.path.append('..')
from build_data_array import read_file_data


def test_read_file_data_good():
    request_year = 2021
    request_month = 3
    file_name_for_test_data = 'test_file_data.dat'
    calculated_data = read_file_data(file_name_for_test_data,request_year,request_month)
    expected_result = ['        8	2021-03-01 05:55:00	1	255	1	0\n','        4	2021-03-01 06:30:00	1	255	1	0\n','        5	2021-03-01 06:45:15	1	255	1	0\n','        6	2021-03-01 07:00:00	1	255	1	0\n','        9	2021-03-01 07:30:10	1	255	1	0\n','        3	2021-03-01 08:00:00	1	255	1	0\n','        5	2021-03-01 14:00:00	1	255	1	0\n','        6	2021-03-01 15:00:00	1	255	1	0\n','        9	2021-03-01 16:00:00	1	255	1	0\n','        4	2021-03-01 17:00:00	1	255	1	0\n','        3	2021-03-01 18:00:00	1	255	1	0\n']
    assert calculated_data == expected_result

def test_read_file_data_null():
    request_year = 2022
    request_month = 12
    file_name_for_test_data = 'test_file_data.dat'
    calculated_data = read_file_data(file_name_for_test_data,request_year,request_month)
    expected_result = None
    assert calculated_data == expected_result

def test_read_file_data_bad_name_file():
    request_year = 2022
    request_month = 12
    file_name_for_test_data = 'test_file_data_1000.dat'
    calculated_data = read_file_data(file_name_for_test_data,request_year,request_month)
    expected_result = None
    assert calculated_data == expected_result