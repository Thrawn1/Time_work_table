from build_data_array import*
from id_employee import*
from analyze_data_print import*
file_name = '1_attlog.dat'
requested_year = int(input('Введите год:'))
requested_month = int(input('Введите месяц:'))
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
id_list = id_employee(type_data=2)
for id in id_list:
    analyze_data_for_print(data_array,id,requested_year,requested_month)
print('Готово!')