from os import name
from determination_period import*
from build_data_array import*
from read_file_data import*
from id_employee import*
from search_missed_day import*
from additional_functions import*
from analyze_data import*
file_name = '1_attlog.dat'
requested_year = 2021
requested_month = 9
last_day_month = 30
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
# print('Генерация словаря по всем дням:')
# p = generation_of_lists_of_days(requested_year,requested_month)
# print(p)
# print('Генерация завершена\n\n\n')
# print('Список всех рабочих дней пользователей')
# list_employee = id_employee()
# for id in list_employee.keys():
#     name = list_employee[id]
#     print(name)
#     id_list = analyze_employee_work_date_new(data_array,id)
#     for date in id_list:
#         a = definition_of_working_day(date)
#         if a[0] == 'work':
#             print(date,a[1],'Рабочий день',sep = ' --- ')
#         elif a[0] == 'weekend':
#             print(date,a[1],'Выходной',sep = ' --- ')
#         elif a[0] == 'holiday':
#             print(date,a[1],'Праздничный',sep = ' --- ')
#         else:
#             print('Ужасная ошибка. Ничего не работает!')
#     output_data_employee(data_array,id)
# print(analyze_employee_work_date_new(data_array,4))

# list_employee = id_employee(type_data = 2)[1]
# for id in list_employee.keys():
#     name = list_employee[id]
#     print(name)
#     search_for_missed_day_new(data_array,id,requested_year,requested_month)
# print('ГОТОВО!')

# a = search_missing_mark(data_array,last_day_month,requested_year,requested_month)
z1 = id_employee(type_data=2)
z = z1[1]
# for i in a.keys():
#     name = z[i]
#     print(name)
#     for d in a[i]:
#         print(d)
# print(a)
for id in z.keys():
    ji = search_missing_mark_employee(data_array,id,requested_year,requested_month)
    if ji == 0:
        pass
    else:
        pass
        name = z[id]
        print('Фамилия работника: ',name)
        for data_cell in ji:
            data_date = data_cell[0]
            data_time = data_cell[1]
            print('Дата отметки: ',data_date,'  Время отметки: ',data_time)


