import os
import datetime
import json
import pickle
from build_data_array import read_file_data,build_data_array
from id_employee import id_employee
from analyze_data import analyze_data_for_print,analyze_data_for_edit, generation_of_lists_of_days
from calculation_of_hours_and_wages import calculation_wages
from supporting_files.data_in_json import data_structure_conversion_for_json,data_structure_conversion_for_json_for_search_miss_mark


file_name = 'test_file_data_part_3.dat'
requested_year = 2021
requested_month = 3
request_id = 3
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
data_array_str = data_structure_conversion_for_json(data_array)
#expected_result ={'2021-03-01': {8: [datetime.datetime(2021, 3, 1, 5, 55), datetime.datetime(2021, 3, 1, 5, 55), 'work'], 4: [datetime.datetime(2021, 3, 1, 17, 0), datetime.datetime(2021, 3, 1, 6, 30), 'work'], 5: [datetime.datetime(2021, 3, 1, 14, 0), datetime.datetime(2021, 3, 1, 6, 45, 15), 'work'], 6: [datetime.datetime(2021, 3, 1, 15, 0), datetime.datetime(2021, 3, 1, 7, 0), 'work'], 9: [datetime.datetime(2021, 3, 1, 16, 0), datetime.datetime(2021, 3, 1, 7, 30, 10), 'work'], 3: [datetime.datetime(2021, 3, 1, 18, 0), datetime.datetime(2021, 3, 1, 8, 0), 'work']}}
#expected_result ={'2021-03-01': {8: [datetime.datetime(2021, 3, 1, 5, 55), datetime.datetime(2021, 3, 1, 5, 55), 'work'], 4: [datetime.datetime(2021, 3, 1, 17, 0), datetime.datetime(2021, 3, 1, 6, 30), 'work'], 5: [datetime.datetime(2021, 3, 1, 14, 0), datetime.datetime(2021, 3, 1, 6, 45, 15), 'work'], 6: [datetime.datetime(2021, 3, 1, 15, 0), datetime.datetime(2021, 3, 1, 7, 0), 'work'], 9: [datetime.datetime(2021, 3, 1, 16, 0), datetime.datetime(2021, 3, 1, 7, 29, 59), 'work'], 3: [datetime.datetime(2021, 3, 1, 18, 0), datetime.datetime(2021, 3, 1, 8, 0), 'work']}}
#expected_result_str = data_structure_conversion_for_json(expected_result)
#request_dict = {'2021-03-01': {8: [datetime.datetime(2021, 3, 1, 5, 55), datetime.datetime(2021, 3, 1, 5, 55), 'work'], 4: [datetime.datetime(2021, 3, 1, 17, 0), datetime.datetime(2021, 3, 1, 6, 30), 'work'], 5: [datetime.datetime(2021, 3, 1, 14, 0), datetime.datetime(2021, 3, 1, 6, 45, 15), 'work'], 6: [datetime.datetime(2021, 3, 1, 15, 0), datetime.datetime(2021, 3, 1, 7, 0), 'work'], 9: [datetime.datetime(2021, 3, 1, 16, 0), datetime.datetime(2021, 3, 1, 7, 30, 10), 'work'], 3: [datetime.datetime(2021, 3, 1, 18, 0), datetime.datetime(2021, 3, 1, 8, 0), 'work']}}
expected_result = [['2021-03-04',datetime.datetime(2021, 3, 4, 20, 22, 45)],['2021-03-31',datetime.datetime(2021, 3, 31, 6, 2, 22)]]



request_dict_json = data_structure_conversion_for_json_for_search_miss_mark(expected_result)
with open('reference_search_for_missed_marks_employee_id_loss_marks', "w", encoding="utf-8") as fh:
    fh.write(json.dumps(request_dict_json, ensure_ascii=False, indent=4))


file_name_for_test_data = 'test_read_file.dat'
tmp = read_file_data(file_name_for_test_data,requested_year,requested_month)


#tmp = generation_of_lists_of_days(requested_year,requested_month)
with open('reference_read_file_data_good', "w", encoding="utf-8") as fh:
    fh.write(json.dumps(tmp, ensure_ascii=False, indent=4))


#with open('test_pickle', "wb") as fh:
#    pickle.dump(data_array, fh)

#analyze_data_for_print(request_dict,request_id,requested_year,requested_month)

print('\n\n\n\nГотово!!!')