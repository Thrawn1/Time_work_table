from calendar import monthrange
from datetime import date,time
from lable import Lable
from employee import Employee
from work_month import Work_month
import sys
from os import path
directory = 'data'
name_row_file = '1_attlog_c.dat'
file = open(path.join(directory,name_row_file),'r',encoding='utf-8')
list_lines = []
for line in file:
    list_lines.append(line)
file.close()
tmp_line = list_lines[0]
tmp_line = tmp_line.rstrip('\n')
year = int(tmp_line[10:14])
month = int(tmp_line[15:17])
test_month = Work_month(year,month,list_lines)
test_month.build_day_object()

# test_month.check_loss_lable()
# print('LABLE',test_month.loss_lable_days)

# test_month.check_loss_days_in_work_month()
# print('LOSS_DAYS',test_month.loss_all_data_days)


test_month.display_info_loss_data()


#print(test_month.work_employees[5].get_role(),test_month.work_employees[5].role_name)






# print('----------------------------------------------------------------------------------------------------')
# month_test = 1
# year_test = 2023
# name_file_holiday = 'holidays.dat'
# name_file_postponed_works_days = 'postponed_working_days.dat'
# directory_1 = 'data'
# directory_2 = 'variable_data_for_app'
# path_file_holiday = path.join(directory_1,directory_2,name_file_holiday)
# path_file_postponed_works_days = path.join(directory_1,directory_2,name_file_postponed_works_days)
# list_obj_holiday = []
# list_obj_postponed_works_days = []
# all_work_days_months_ideally = []

# with open(path_file_holiday,'r',encoding='utf-8') as file:
#     for line in file:
#         line = line.rstrip('\n')
#         str_line = line.split('.')
#         srt_line_1 = [int(i) for i in str_line]
#         if srt_line_1[1] == month_test:
#             list_obj_holiday.append(srt_line_1[0])
# print('Выходные',list_obj_holiday)

# with open(path_file_postponed_works_days,'r',encoding='utf-8') as file:
#     for line in file:
#         line = line.rstrip('\n')
#         str_line = line.split('.')
#         srt_line_1 = [int(i) for i in str_line]
#         if srt_line_1[1] == month_test:
#             list_obj_postponed_works_days.append(srt_line_1[0])
# print('Дополнительные рабочие дни',list_obj_postponed_works_days)

# last_day_month = monthrange(year,month_test)[1]

# for i in range(1,last_day_month+1):
#     day_obj = date(year_test,month_test,i)
#     if day_obj.weekday() != 5 and day_obj.weekday() != 6:
#         if i not in list_obj_holiday:
#             all_work_days_months_ideally.append(i)
# if len(list_obj_postponed_works_days) != 0:
#     all_work_days_months_ideally = all_work_days_months_ideally + list_obj_postponed_works_days
#     all_work_days_months_ideally.sort()
# print('Все рабочие дни',all_work_days_months_ideally)

# for id in test_month.work_employees:
#     print('\n')
#     print('ID: ',test_month.work_employees[id].id)
#     print('Имя: ',test_month.work_employees[id].name)
#     print('Фамилия: ',test_month.work_employees[id].family)
#     print('Роль: ',test_month.work_employees[id].role_name)
#     print('Ставка: ',test_month.work_employees[id].rate)

# print(test_month.month_data)
# for id in test_month.month_data:
#     print('ID: ',id)
#     print('Метка прихода: ',test_month.month_data[id][0].get_come())
#     print('Метка ухода: ',test_month.month_data[id][0].get_go())
#     print('Тестовая_метка_прихода:', type(test_month.month_data[id][0].get_come()))
#     print('Тестовая_метка_ухода:',type(test_month.month_data[id][0].get_go()))
#     print('Тестовая_метка_прихода:',test_month.month_data[id][0].get_come().time)
#     print('Тестовая_метка_ухода:',test_month.month_data[id][0].get_go().time)

# tmp_dict = {1:'Ааа',2:'Ббб',3:'Ввв'}
# tmp_list = [1,2,7]
# for i in tmp_list:
#     if i in tmp_dict:
#         print(tmp_dict[i])
#     else:
#         print('Нет такого ключа',i)