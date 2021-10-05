from id_employee import*
from datetime import datetime


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
            time_table[key_data][id_employee_data] = [date_and_time, date_and_time]
    return time_table