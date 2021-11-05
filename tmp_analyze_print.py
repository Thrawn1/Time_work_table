import os
import json
from analyze_data import analyze_data_for_print
from supporting_files.data_in_json import json_structure_conversion_for_data

object_file_name = 'test_analyze_data_for_print_version_4'
path_object_file = os.path.join('data','data_for_tests',object_file_name)
with open(path_object_file, encoding="utf-8") as file:
    json_struct = json.loads(file.read())
request_dict = json_structure_conversion_for_data(json_struct)
resquested_id_list = [3,4,5,6,9]
request_id = 3
request_year = 2021
request_month = 3
#for request_id in resquested_id_list:
#    analyze_data_for_print(request_dict,request_id,request_year,request_month)

analyze_data_for_print(request_dict,request_id,request_year,request_month)