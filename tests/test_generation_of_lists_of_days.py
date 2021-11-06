from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from analyze_data import generation_of_lists_of_days

def test_generation_of_lists_of_days():
    request_year = 2021
    request_month = 3
    calculated_data = generation_of_lists_of_days(request_year,request_month)
    object_file_name = 'reference_generation_of_lists_of_days'
    path_object_file = gen_path.join('data','data_for_tests','reference_for_tests',object_file_name)
    with open(path_object_file,encoding="utf-8") as file:
        expected_result = loads(file.read())
    assert calculated_data == expected_result