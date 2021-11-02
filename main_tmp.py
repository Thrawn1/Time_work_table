from build_data_array import*
from id_employee import*
from analyze_data import*
from calculation_of_hours_and_wages import*

file_name = '1_attlog.dat'
#file_name = '3-2021.dat'
#file_name = '3-2021-v2.dat'
#requested_year = int(input('Введите год:'))
#requested_month = int(input('Введите месяц:'))
requested_year = 2021
requested_month = 10
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
#print(data_array)
work_time_employees_restructuring = calculation_of_exceeding_working_hours_per_month(work_time_employees)


list_employee = id_employee(type_data=2)
for id in work_time_employees_restructuring[1].keys():
    name = list_employee[1][id]
    work = work_time_employees_restructuring[1][id][0]
    holiday = work_time_employees_restructuring[1][id][1]
    vacation = work_time_employees_restructuring[1][id][2]
    print('--------------------------------------------------------------------------------------------------------------------------------------------')
    print('\nФамилия работника:  ',name)
    print('\n\t\tБудние рабочие дни:')
    for day in work:
        print('\t\t\t--------------------')
        print('\t\t\tДата:', day[2],day[1],":",day[0])
        print('\t\t\t--------------------')
    print('\n\t\tВыходные и праздинки')
    for day in holiday:
        print('\t\t\t--------------------')
        print('\t\t\tДата:', day[2],day[1],":",day[0])
        print('\t\t\t--------------------')
    print('\n\t\tОтпуск')
    for day in vacation:
        print('\t\t\t--------------------')
        print('\t\t\tДата:', day[2])
        print('\t\t\t--------------------')
    print('\n\n\t\t ВСЕГО ЗА МЕСЯЦ:')
    print('\t\t\t--------------------')
    print('\n\t\tБудние рабочие дни за месяц:', work_time_employees_restructuring[0][id][0][0])
    print('\t\t\t--------------------')
    print('\n\t\tПереработки за будниче рабочие дни в месяце:', work_time_employees_restructuring[0][id][0][1])
    print('\t\t\t--------------------')
    print('\n\t\tРабочие выходные дни за месяц:', work_time_employees_restructuring[0][id][1][0])
    print('\t\t\t--------------------')
    print('\n\t\tПереработки за будниче рабочие дни в месяце:', work_time_employees_restructuring[0][id][1][1])
    print('\t\t\t--------------------')
    print('\n\t\tКоличество дней отпуска:', work_time_employees_restructuring[0][id][2])
    print('\t\t\t--------------------')
    
print(work_time_employees_restructuring[0])
z = calculation_wages(work_time_employees_restructuring[0])
print(z)
print('\n\n\nПРЕДПОЛАГАЕМАЯ ЗАРПЛАТА\n\n\n')
for id in z.keys():
    name = list_employee[1][id]
    print('--------------------------------------------------------------------------------------------------------------------------------------------')
    print('\nФамилия работника:  ',name,'Зарплата: ',z[id],' рублей' )
#print(data_array)
print('\n\n\n\nГотово!!!')