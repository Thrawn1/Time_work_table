from build_data_array import*
from id_employee import*
from analyze_data import*
from calculation_of_hours_and_wages import*
from build_file_table_excel import build_file_excel
from generation_pdf_file import generation_pdf_file

#file_name = 'tmp_data_one_id.dat'
file_name = '2_attlog.dat'
#file_name = 'n_1_attlog.dat'
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
#file_name = '3-2021.dat'
#file_name = '3-2021-v2.dat'
#requested_year = int(input('Введите год:'))
#requested_month = int(input('Введите месяц:'))
requested_year = 2021
requested_month = 12
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
id_list = id_employee(type_data=2)
name_month_for_print = month_name_for_print(requested_month)
print(name_month_for_print,' ',requested_year,' ','год')


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
#generation_pdf_file(0,'test')