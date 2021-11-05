import sys
import os
import json
sys.path.append('..')
from analyze_data import analyze_data_for_print
from supporting_files.data_in_json import json_structure_conversion_for_data

def test_analyze_data_for_print_one_employee_loss_data(capsys):
    object_file_name = 'test_analyze_data_for_print_version_1'
    path_object_file = os.path.join('data','data_for_tests',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = json.loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 3
    request_year = 2021
    request_month = 3
    analyze_data_for_print(request_dict,request_id,request_year,request_month)
    calc,err = capsys.readouterr()
    file_name_whith_reference_result = 'reference_result_analyze_data_for_print_one_employee_loss_data'
    path_file_with_reference_result = os.path.join('data','data_for_tests','reference_for_tests',file_name_whith_reference_result)
    file_ecpected_result = open(path_file_with_reference_result, 'r',encoding='utf-8')
    expected_result = ''
    for line in file_ecpected_result:
        expected_result += line
    assert calc == expected_result

def test_analyze_data_for_print_id_no_data(capsys):
    object_file_name = 'test_analyze_data_for_print_version_1'
    path_object_file = os.path.join('data','data_for_tests',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = json.loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 5
    request_year = 2021
    request_month = 3
    analyze_data_for_print(request_dict,request_id,request_year,request_month)
    calc,err = capsys.readouterr()
    expected_result = ''
    assert calc == expected_result

def test_analyze_data_for_print_id_all_data_month(capsys):
    object_file_name = 'test_analyze_data_for_print_version_2'
    path_object_file = os.path.join('data','data_for_tests',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = json.loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 3
    request_year = 2021
    request_month = 3
    analyze_data_for_print(request_dict,request_id,request_year,request_month)
    calc,err = capsys.readouterr()
    expected_result = ''
    assert calc == expected_result

def test_analyze_data_for_print_id_all_data_month_all_id(capsys):
    object_file_name = 'test_analyze_data_for_print_version_3'
    path_object_file = os.path.join('data','data_for_tests',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = json.loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 3
    request_year = 2021
    request_month = 3
    analyze_data_for_print(request_dict,request_id,request_year,request_month)
    calc,err = capsys.readouterr()
    expected_result = ''
    assert calc == expected_result

def test_analyze_data_for_print_all_id_loss_data(capsys):
    object_file_name = 'test_analyze_data_for_print_version_4'
    path_object_file = os.path.join('data','data_for_tests',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = json.loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    resquested_id_list = [3,4,5,6,9]
    request_year = 2021
    request_month = 3
    for request_id in resquested_id_list:
        analyze_data_for_print(request_dict,request_id,request_year,request_month)
    calc,err = capsys.readouterr()
    file_name_whith_reference_result = 'reference_result_analyze_data_for_print_all_id_loss_data'
    path_file_with_reference_result = os.path.join('data','data_for_tests','reference_for_tests',file_name_whith_reference_result)
    file_ecpected_result = open(path_file_with_reference_result, 'r',encoding='utf-8')
    expected_result = ''
    for line in file_ecpected_result:
        expected_result += line
    assert calc == expected_result



def test_analyze_data_for_print_one_id_loss_data_all_id_month(capsys):
    object_file_name = 'test_analyze_data_for_print_version_4'
    path_object_file = os.path.join('data','data_for_tests',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = json.loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    resquested_id_list = [3,4,5,6,9]
    request_year = 2021
    request_month = 3
    request_id = 3
    analyze_data_for_print(request_dict,request_id,request_year,request_month)
    calc,err = capsys.readouterr()
    file_name_whith_reference_result = 'reference_result_analyze_data_for_print_one_id_loss_data_all_id_month'
    path_file_with_reference_result = os.path.join('data','data_for_tests','reference_for_tests',file_name_whith_reference_result)
    file_ecpected_result = open(path_file_with_reference_result, 'r',encoding='utf-8')
    expected_result = ''
    for line in file_ecpected_result:
        expected_result += line
    assert calc == expected_result