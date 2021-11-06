from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from supporting_files.data_in_json import json_structure_conversion_for_data,json_structure_conversion_for_data__for_search_miss_mark
from analyze_data import search_for_missed_marks_employee

def test_search_for_missed_marks_employee_id_no_data():
    data_test_file_name = 'test_data_search_for_missed_marks_employee_one_id_all_marks'
    path_object_file = gen_path.join('data','data_for_tests',data_test_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 4
    request_year = 2021
    request_month = 3
    calculated_data = search_for_missed_marks_employee(request_dict,request_id,request_year,request_month)
    expected_result = 0
    assert calculated_data == expected_result

def test_search_for_missed_marks_employee_id_all_marks():
    data_test_file_name = 'test_data_search_for_missed_marks_employee_one_id_all_marks'
    path_object_file = gen_path.join('data','data_for_tests',data_test_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 3
    request_year = 2021
    request_month = 3
    calculated_data = search_for_missed_marks_employee(request_dict,request_id,request_year,request_month)
    expected_result = 0
    assert calculated_data == expected_result

def test_search_for_missed_marks_employee_id_loss_marks():
    data_test_file_name = 'test_data_search_for_missed_marks_employee_one_id_missed_marks'
    path_object_file = gen_path.join('data','data_for_tests',data_test_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 3
    request_year = 2021
    request_month = 3
    calculated_data = search_for_missed_marks_employee(request_dict,request_id,request_year,request_month)
    object_file_name = 'reference_search_for_missed_marks_employee_id_loss_marks'
    path_object_file = gen_path.join('data','data_for_tests','reference_for_tests',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct_ref = loads(file.read())
    expected_result = json_structure_conversion_for_data__for_search_miss_mark(json_struct_ref)
    assert calculated_data == expected_result