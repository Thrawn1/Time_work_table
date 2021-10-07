from calendar import month
from os import name
from id_employee import*
from read_file_data import*
from analyze_data import*
from build_data_array import*
from search_missed_day import*
file_name_data = '1_attlog.dat'
year_request = int(input())
month_request = int(input())
file_read = read_file_data(file_name_data,year_request,month_request)
array = build_data_array(file_read)
id_list = id_employee(type_data=2)
for id in id_list.keys():
    name = id_list[id]
    search_for_missed_day(array,id,year_request,month_request)
    search_missing_mark_employee(array,year_request,month_request)
print('Главная функция!')