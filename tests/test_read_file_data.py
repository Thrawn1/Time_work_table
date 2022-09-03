from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from build_data_array import read_file_data


def test_read_file_data_good():
    request_year = 2021
    request_month = 3
    file_name_for_test_data = 'test_read_file.dat'
    calculated_data = read_file_data(file_name_for_test_data,request_year,request_month)
    object_file_name = 'reference_read_file_data_good'
    path_object_file = gen_path.join('data','test_data','reference_result',object_file_name)
    with open(path_object_file,encoding="utf-8") as file:
        expected_result = loads(file.read())
    assert calculated_data == expected_result

def test_read_file_data_null():
    request_year = 2022
    request_month = 12
    file_name_for_test_data = 'test_read_file.dat'
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