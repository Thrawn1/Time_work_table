from build_data_array import*
from id_employee import*
from analyze_data_print import*

def month_name_for_print(month_id):
    """Функция возвращает название месяца на русском. Принимает номер месяца"""
    months_names = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}
    name_month = months_names[month_id]
    return name_month

file_name = '1_attlog.dat'
requested_year = int(input('Введите год:'))
requested_month = int(input('Введите месяц:'))
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
id_list = id_employee(type_data=2)
name_month_for_print = month_name_for_print(requested_month)
print(name_month_for_print,' ',requested_year,' ','год')
for id in id_list[1]:
    analyze_data_for_print(data_array,id,requested_year,requested_month)
print('Готово!')