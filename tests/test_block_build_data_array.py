from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from supporting_files.data_in_json import json_structure_conversion_for_data
from build_data_array import build_data_array,read_file_data



def test_bloc_buil_data_array_all():
    name_file_for_test = 'test_read_file.dat'
    requested_year = 2021 
    requested_month = 3
    list_data = read_file_data(name_file_for_test,requested_year,requested_month)
    calculated_data = build_data_array(list_data)
    object_file_name = 'reference_block_build_data_array'
    path_object_file = gen_path.join('data','test_data','reference_result',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = loads(file.read())
    expected_result = json_structure_conversion_for_data(json_struct)
    assert calculated_data == expected_result