from datetime import date,time
from lable import Lable
from employee import Employee
from work_month import Work_month
import sys
from os import path
directory = 'data'
name_row_file = '1_attlog_b.dat'
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
print(test_month)
print(test_month.__sizeof__())
print(test_month.work_employees)
print(test_month.month_data)

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