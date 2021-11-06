from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from supporting_files.data_in_json import json_structure_conversion_for_data
from analyze_data import reading_employee_work_date


def test_reading_employee_work_date_null():
    request_dict = {}
    request_id = 5
    calculated_data = reading_employee_work_date(request_dict,request_id)
    expected_result = []
    assert calculated_data == expected_result

def test_reading_employee_work_date_good():
    test_data_file_name = 'test_data_reading_employee_work_date_good'
    path_object_file = gen_path.join('data','data_for_tests',test_data_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id_list = [4,5,6,9,3]
    for request_id in request_id_list:
        calculated_data = reading_employee_work_date(request_dict,request_id)
        expected_result = ['2021-03-01']
        assert calculated_data == expected_result