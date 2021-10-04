from os import name
from determination_period import*
from build_data_array import*
from read_file_data import*
from id_employer import*
from search_missed_day import generation_of_lists_of_days,analyze_employer_work_date_new,definition_of_working_day,search_for_missed_day_new
from additional_functions import*
file_name = '1_attlog.dat'
requested_year = 2021
requested_month = 3
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
print('Генерация словаря по всем дням:')
p = generation_of_lists_of_days(requested_year,requested_month)
print(p)
print('Генерация завершена\n\n\n')
print('Список всех рабочих дней пользователей')
list_employer = id_employer()
for id in list_employer.keys():
    name = list_employer[id]
    print(name)
    id_list = analyze_employer_work_date_new(data_array,id)
    for date in id_list:
        a = definition_of_working_day(date)
        if a[0] == 'work':
            print(date,a[1],'Рабочий день',sep = ' --- ')
        elif a[0] == 'weekend':
            print(date,a[1],'Выходной',sep = ' --- ')
        elif a[0] == 'holiday':
            print(date,a[1],'Праздничный',sep = ' --- ')
        else:
            print('Ужасная ошибка. Ничего не работает!')
    output_data_employer(data_array,id)
print(analyze_employer_work_date_new(data_array,4))

list_employer_1 = id_employer(type_data = 2)[1]
print(list_employer_1)
for id in list_employer_1.keys():
    name = list_employer_1[id]
    print(name)
    search_for_missed_day_new(data_array,id,requested_year,requested_month)
print('ГОТОВО!')