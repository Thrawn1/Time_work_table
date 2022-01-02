from build_data_array import*
from os import remove
from os.path import exists
from pickle import load
from id_employee import id_employee,detection_id_employee_in_data_array
from analyze_data import*
from calculation_of_hours_and_wages import*
from build_file_table_excel import build_file_excel
from gen_html import html_builder


file_name = '2021_12_attlog.dat'
#file_name = 'tmp_data_one_id.dat'
print('Если вы хотите сформировать файл с зарплатой - введите секретный ключ. Если нужен файл без зарплаты - введите t')
key = input('Секретный ключ: ')
if key == 't':
    secret_key_raw = 0
else:
    if key.isdigit() == True:
        if len(key) > 2 and len(key) < 123:
            secret_key_raw = int(key)
        else:
            secret_key_raw = 0
    else:
        secret_key_raw = 0

flag = exists('temporary.pickle')
if flag == True:
    with open('temporary.pickle', 'rb') as tmp_file:
        data_array = load(tmp_file)
    requested_year = int(input('Введите год:'))
    requested_month = int(input('Введите месяц:'))
else:
    requested_year = int(input('Введите год:'))
    requested_month = int(input('Введите месяц:'))
    #requested_year = 2021
    #requested_month = 3
    list_data = read_file_data(file_name,requested_year,requested_month)
    data_array = build_data_array(list_data)
    name_month_for_print = month_name_for_print(requested_month)
    print(name_month_for_print,' ',requested_year,' ','год')

id_list = id_employee(type_data=2)
for id in id_list[1]:
    analyze_data_for_print(data_array,id,requested_year,requested_month)

for id in id_list[1]:
    analyze_data_for_print(data_array,id,requested_year,requested_month)
    analyze_data_for_edit(data_array,id,requested_year,requested_month)

for id in id_list[1]:
    analyze_data_for_print(data_array,id,requested_year,requested_month)

work_time_employees=calculation_of_excess_working_hours_per_day(data_array)
work_time_employees_restructuring = calculation_of_exceeding_working_hours_per_month(work_time_employees)
z = calculation_wages(work_time_employees_restructuring[0],secret_key_raw)
build_file_excel(data_array,work_time_employees,work_time_employees_restructuring[0],z)

employees_who_worked_for_month = detection_id_employee_in_data_array(data_array)

for id in employees_who_worked_for_month:
    html_builder(id,all_data_dates_and_marks=data_array,data_work_time_all_employees=work_time_employees,all_data_per_month_employees=work_time_employees_restructuring[0],total_salary_employees=z)
try:
    remove('temporary.pickle')
except:
    pass