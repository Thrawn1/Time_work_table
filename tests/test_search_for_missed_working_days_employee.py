from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from supporting_files.data_in_json import json_structure_conversion_for_data
from analyze_data import search_for_missed_working_days_employee

def test_search_for_missed_working_days_employee_null():
    test_data_file_name = 'test_data_search_for_missed_working_days_employee_null'
    path_test_data_file = gen_path.join('data','data_for_tests',test_data_file_name)
    with open(path_test_data_file,encoding='utf-8') as file:
      request_dict_str = loads(file.read())
    request_dict = json_structure_conversion_for_data(request_dict_str)
    request_id = 3
    request_year = 2021
    request_month = 3
    calculated_data = search_for_missed_working_days_employee(request_dict,request_id,request_year,request_month)
    expected_result = 0
    assert calculated_data == expected_result

def test_search_for_missed_working_days_employee_search_results():
    test_data_file_name = 'test_data_search_for_missed_working_days_employee_search_results_one_id'
    path_test_data_file = gen_path.join('data','data_for_tests',test_data_file_name)
    with open(path_test_data_file,encoding='utf-8') as file:
      request_dict_str = loads(file.read())
    request_dict = json_structure_conversion_for_data(request_dict_str)
    request_id = 3
    request_year = 2021
    request_month = 3
    calculated_data = search_for_missed_working_days_employee(request_dict,request_id,request_year,request_month)
    reference_file_name = 'reference_search_for_missed_working_days_employee_search_results'
    path_reference_file = gen_path.join('data','data_for_tests','reference_for_tests',reference_file_name)
    with open(path_reference_file,encoding='utf-8') as file:
      expected_result = loads(file.read())
    assert calculated_data == expected_result

def test_search_for_missed_working_days_employee_no_data_id():

  test_data_file_name = 'test_data_search_for_missed_working_days_employee_search_results_one_id'
  path_test_data_file = gen_path.join('data','data_for_tests',test_data_file_name)
  with open(path_test_data_file,encoding='utf-8') as file:
      request_dict_str = loads(file.read())
  request_dict = json_structure_conversion_for_data(request_dict_str)
  request_id = 6
  request_year = 2021
  request_month = 3
  calculated_data = search_for_missed_working_days_employee(request_dict,request_id,request_year,request_month)
  expected_result = 0
  assert calculated_data == expected_result