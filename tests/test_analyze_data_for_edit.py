from sys import path
from os import path as gen_path 
from json import loads
path.append('..')
from analyze_data import analyze_data_for_edit
from supporting_files.data_in_json import json_structure_conversion_for_data

def test_analyze_data_for_edit_good(capsys):
    object_file_name = 'test_analyze_data_for_print_loss_data_one_id'
    path_object_file = gen_path.join('data','test_data',object_file_name)
    with open(path_object_file, encoding="utf-8") as file:
        json_struct = loads(file.read())
    request_dict = json_structure_conversion_for_data(json_struct)
    request_id = 3
    request_year = 2021
    request_month = 3
    analyze_data_for_edit(request_dict,request_id,request_year,request_month)
    calc,err = capsys.readouterr()