from build_data_array import*
from id_employee import*
from analyze_data import*
from calculation_of_hours_and_wages import*

file_name = '3-2021.dat'
#requested_year = int(input('Введите год:'))
#requested_month = int(input('Введите месяц:'))
requested_year = 2021
requested_month = 3
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
id_list = id_employee(type_data=2)
name_month_for_print = month_name_for_print(requested_month)
print(name_month_for_print,' ',requested_year,' ','год')
for id in id_list[1]:
    analyze_data_for_print(data_array,id,requested_year,requested_month)
    analyze_data_for_edit(data_array,id,requested_year,requested_month)

for id in id_list[1]:
    analyze_data_for_print(data_array,id,requested_year,requested_month)

work_time_employees=calculation_of_excess_working_hours_per_day(data_array)
work_time_employees_restructuring = calculation_of_exceeding_working_hours_per_month(work_time_employees)
z=calculation_wages(work_time_employees_restructuring)
print('Готово!!!')