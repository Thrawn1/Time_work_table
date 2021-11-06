from os import path
from id_employee import id_employee
from datetime import datetime
from analyze_data import definition_of_working_day

def determination_period(line, year, month):
    """Функция будет определять, какие записи относятся к определенному периоду
       Что бы не хранить словарь на несколько десятков тысяч записей - нужно отсечь ненужные по дате. 
       Сначала проверяется год, потом месяц. 
       Функция принимает строку файла данных, год, месяц
       Возвращает Истину - если строка относиться к выбранному году и месяцу, Ложь - во всех прочих
    """
    data_year = int(line[10:14])
    data_month = int(line[15:17])
    if data_year == year and data_month == month:
        return True
    else:
        return False

def read_file_data(file_name_data_relative, requested_year, requested_month):
    """ Функция служит для прочтения файла данных, его информация переводится в вид словаря.
        Возвращается словарь, содержащий все записи из файла с данными, 
        относящимся к нужному периоду - определенный месяца определенного года
        Функция принимает имя файла данных, год и месяц. 
        Если словарь пуст - скорее всего данные запрашиваются за декабрь, вывести поздравление с НГ и рекомендацию
        ввести вручную дату и месяц
    """
    file_name_data = path.join("data",file_name_data_relative)
    try:
        file_data = open(file_name_data, 'r')
    except FileNotFoundError:
        print('В каталоге программы нет указанного файла с данными! Пожалуйста укажите корретный файл')
        return None
    list_month = []
    for line in file_data:
        arbiter = determination_period(line, requested_year, requested_month)
        if arbiter == True:
            list_month.append(line)
    if len(list_month) != 0:
        return list_month
    else:
        print('Данных нет!\n\n\tСкорее всего не корректно определился месяц, за который строится выборка. \n\nУкажите явно год и месяц')



def build_data_array(list_month: list):
    """Функция получения структуры данных. Получает на вход список строк, которые относятся к необходимому месяцу.
       В процессе делает сложный словарь, который учитывает конкретные даты и сотрудников.
       Возвращает словарь словарей 
    """
    time_table = {}
    list_employee = id_employee()
    for line in list_month:
        id_employee_data = int(line[7:10])
        date_and_time = datetime.strptime(line[10:29], "%Y-%m-%d %H:%M:%S")
        key_data = line[10:20]
        family_employee = list_employee.get(id_employee_data)
        if family_employee == None:
            print('Ошибка! Не указан id пользователя в файле!')
        if not key_data in time_table.keys():
            time_table[key_data] = {}
        if id_employee_data in time_table[key_data].keys():
            if time_table[key_data][id_employee_data][0] < date_and_time:
                time_table[key_data][id_employee_data][0] = date_and_time
            if time_table[key_data][id_employee_data][1] > date_and_time:
                time_table[key_data][id_employee_data][1] = date_and_time
        else:
            tag_day = definition_of_working_day(key_data)[0]
            time_table[key_data][id_employee_data] = [date_and_time, date_and_time,tag_day]
    return time_table