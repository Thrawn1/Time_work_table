from id_employer import*
from datetime import datetime


def build_data_array(list_month: list):
    """Функция получения структуры данных. Получает на вход список строк, которые относятся к необходимому месяцу.
       В процессе делает сложный словарь, который учитывает конкретные даты и сотрудников.
       Возвращает словарь словарей 
    """
    time_table = {}
    list_employer = id_employer()
    for line in list_month:
        id_employer_data = int(line[7:10])
        date_and_time = datetime.strptime(line[10:29], "%Y-%m-%d %H:%M:%S")
        key_data = line[10:21]
        family_employer = list_employer.get(id_employer_data)
        if family_employer == None:
            print('Ошибка! Не указан id пользователя в файле!')
        if not key_data in time_table.keys():
            time_table[key_data] = {}
        if id_employer_data in time_table[key_data].keys():
            if time_table[key_data][id_employer_data][0] < date_and_time:
                time_table[key_data][id_employer_data][0] = date_and_time
            if time_table[key_data][id_employer_data][1] > date_and_time:
                time_table[key_data][id_employer_data][1] = date_and_time
        else:
            time_table[key_data][id_employer_data] = [date_and_time, date_and_time]
    return time_table