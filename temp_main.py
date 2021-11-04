import datetime
import json
import pickle
from build_data_array import read_file_data,build_data_array
from id_employee import id_employee
from analyze_data import analyze_data_for_print,analyze_data_for_edit
from calculation_of_hours_and_wages import calculation_wages
from supporting_files.data_in_json import data_structure_conversion_for_json


file_name = 'test_file_data_part_2_1.dat'
requested_year = 2021
requested_month = 3
request_id = 3
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
data_array_str = data_structure_conversion_for_json(data_array)


with open('test_jsons', "w", encoding="utf-8") as fh:
    fh.write(json.dumps(data_array_str, ensure_ascii=False, indent=4))
with open('test_pickle', "wb") as fh:
    pickle.dump(data_array, fh)

request_dict = {'2021-03-01': {3: [datetime.datetime(2021, 3, 1, 18, 29, 25), datetime.datetime(2021, 3, 1, 9, 36, 12), 'work']}, '2021-03-02': {3: [datetime.datetime(2021, 3, 2, 7, 3, 32), datetime.datetime(2021, 3, 2, 7, 3, 32), 'work']}, '2021-03-03': {3: [datetime.datetime(2021, 3, 3, 17, 1, 5), datetime.datetime(2021, 3, 3, 5, 9, 57), 'work']}, '2021-03-04': {3: [datetime.datetime(2021, 3, 4, 20, 22, 45), datetime.datetime(2021, 3, 4, 10, 22, 6), 'work']}, '2021-03-05': {3: [datetime.datetime(2021, 3, 5, 17, 59, 25), datetime.datetime(2021, 3, 5, 9, 8, 47), 'work']}, '2021-03-07': {3: [datetime.datetime(2021, 3, 7, 18, 12, 35), datetime.datetime(2021, 3, 7, 7, 41, 30), 'weekend']}, '2021-03-08': {3: [datetime.datetime(2021, 3, 8, 15, 49, 7), datetime.datetime(2021, 3, 8, 8, 29, 47), 'holiday']}, '2021-03-09': {3: [datetime.datetime(2021, 3, 9, 18, 18, 50), datetime.datetime(2021, 3, 9, 9, 26, 7), 'work']}, '2021-03-10': {3: [datetime.datetime(2021, 3, 10, 11, 1, 10), datetime.datetime(2021, 3, 10, 6, 21, 6), 'work']}, '2021-03-11': {3: [datetime.datetime(2021, 3, 11, 19, 56, 59), datetime.datetime(2021, 3, 11, 10, 5, 6), 'work']}, '2021-03-12': {3: [datetime.datetime(2021, 3, 12, 16, 22, 34), datetime.datetime(2021, 3, 12, 7, 35, 4), 'work']}, '2021-03-16': {3: [datetime.datetime(2021, 3, 16, 19, 18, 29), datetime.datetime(2021, 3, 16, 8, 9, 52), 'work']}, '2021-03-17': {3: [datetime.datetime(2021, 3, 17, 22, 17, 58), datetime.datetime(2021, 3, 17, 6, 11, 37), 'work']}, '2021-03-18': {3: [datetime.datetime(2021, 3, 18, 20, 7, 18), datetime.datetime(2021, 3, 18, 9, 51, 5), 'work']}, '2021-03-19': {3: [datetime.datetime(2021, 3, 19, 18, 31, 50), datetime.datetime(2021, 3, 19, 9, 50, 22), 'work']}, '2021-03-22': {3: [datetime.datetime(2021, 3, 22, 17, 39, 19), datetime.datetime(2021, 3, 22, 7, 13, 18), 'work']}, '2021-03-23': {3: [datetime.datetime(2021, 3, 23, 19, 20, 1), datetime.datetime(2021, 3, 23, 8, 32, 45), 'work']}, '2021-03-24': {3: [datetime.datetime(2021, 3, 24, 20, 8, 4), datetime.datetime(2021, 3, 24, 7, 51, 41), 'work']}, '2021-03-25': {3: [datetime.datetime(2021, 3, 25, 18, 21, 14), datetime.datetime(2021, 3, 25, 10, 52, 25), 'work']}, '2021-03-26': {3: [datetime.datetime(2021, 3, 26, 21, 1, 54), datetime.datetime(2021, 3, 26, 10, 29, 9), 'work']}, '2021-03-27': {3: [datetime.datetime(2021, 3, 27, 21, 45, 20), datetime.datetime(2021, 3, 27, 11, 10, 15), 'weekend']}, '2021-03-28': {3: [datetime.datetime(2021, 3, 28, 15, 41, 51), datetime.datetime(2021, 3, 28, 7, 23, 30), 'weekend']}, '2021-03-29': {3: [datetime.datetime(2021, 3, 29, 18, 55, 39), datetime.datetime(2021, 3, 29, 18, 55, 39), 'work']}, '2021-03-30': {3: [datetime.datetime(2021, 3, 30, 17, 35, 21), datetime.datetime(2021, 3, 30, 8, 2, 4), 'work']}, '2021-03-31': {3: [datetime.datetime(2021, 3, 31, 15, 39, 11), datetime.datetime(2021, 3, 31, 6, 2, 22), 'work']}}

analyze_data_for_print(request_dict,request_id,requested_year,requested_month)

#print('\n\n\n\nГотово!!!')