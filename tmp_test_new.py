from os import name
from determination_period import*
from build_data_array import*
from read_file_data import*
from id_employer import*
from search_missed_day import generation_of_lists_of_days,analyze_employer_work_date_new,output_data_employer
file_name = '1_attlog.dat'
requested_year = 2021
requested_month = 3
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
print('Генерация словаря по всем дням:')
generation_of_lists_of_days(requested_year,requested_month)
print('Генерация завершена\n\n\n')
print('Список всех рабочих дней пользователей')
list_employer = id_employer()
for id in list_employer.keys():
    name = list_employer[id]
    print(name)
    output_data_employer(data_array,id)
print(analyze_employer_work_date_new(data_array,4))
print('ГОТОВО!')