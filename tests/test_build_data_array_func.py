from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from supporting_files.data_in_json import json_structure_conversion_for_data
from build_data_array import build_data_array


def test_build_array_good():
    test_data_file_name = 'test_data_build_array_good'
    request_list = []
    path_file_data_test = gen_path.join('data','data_for_tests',test_data_file_name)
    with open(path_file_data_test,'r',encoding="utf-8") as data_file:
        for line in data_file:
            request_list.append(line)
    calculated_data = build_data_array(request_list)
    name_file_object_reference = 'reference_block_build_data_array'
    path_file_object_reference = gen_path.join('data','data_for_tests','reference_for_tests',name_file_object_reference)
    with open(path_file_object_reference, encoding="utf-8") as file:
        json_struct = loads(file.read())
    expected_result = json_structure_conversion_for_data(json_struct)
    assert calculated_data == expected_result


def test_build_array_duplicate_marks():
    test_data_file_name = 'test_data_build_array_duplicate_marks'
    request_list = []
    path_file_data_test = gen_path.join('data','data_for_tests',test_data_file_name)
    with open(path_file_data_test,'r',encoding="utf-8") as data_file:
        for line in data_file:
            request_list.append(line)
    calculated_data = build_data_array(request_list)
    name_file_object_reference = 'reference_block_build_data_array_duplicate_marks'
    path_file_object_reference = gen_path.join('data','data_for_tests','reference_for_tests',name_file_object_reference)
    with open(path_file_object_reference, encoding="utf-8") as file:
        json_struct = loads(file.read())
    expected_result = json_structure_conversion_for_data(json_struct)
    assert calculated_data == expected_result
