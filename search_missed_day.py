from calendar import  calendar, monthrange, weekday
from id_employer import id_employer
def generation_of_lists_of_days(requested_year:int,requested_month:int):
    """Функция принимает значения года и месяца. Функция возвращает Список, содержащий списки - рабочие будние дни, выходные дни и праздники """
    last_day_request_month = monthrange(requested_year,requested_month)[1]
    list_day_month = {}
    for day in range(1,last_day_request_month+1, 1):
        day_week = weekday(requested_year,requested_month,day)
        key_date = str(requested_year) + '-' + str(requested_month) + '-' + str(day)
        if day_week != 5 and day_week !=6:
            list_day_month[key_date] = 'Будний день'
        else:
            list_day_month[key_date] = 'Выходной'
    return list_day_month

def analyze_employers_work_date_new(data_dict:dict):
    """Функция анализа всех рабочих дней, которые отработали сотрудники"""
    data_employer_work = {}
    employer_list = id_employer()
    for id in employer_list:
        data_employer_work[id] = []
    for data_date in data_dict.keys():
        for id in data_dict[data_date].keys():
            data_employer_work[id].append(data_date)
    for id in data_employer_work.keys():
        name = employer_list[id]
        print(name,":\n" )
        for date in data_employer_work[id]:
            print(date)
    print(data_employer_work)
    return data_employer_work

def analyze_employer_work_date_new(data_dict:dict,id:int):
    """Функция анализа всех рабочих дней, который отработал сотрудник"""
    data_employer_work = []
    for data_date in data_dict.keys():
        if id in data_dict[data_date].keys():
            data_employer_work.append(data_date)
    return data_employer_work

def search_for_missed_day_new():
    """Данная функция анализирует все записи работников за выбранный месяц и возвращает списки дат без отметок для каждого пользователя, а так же списки рабочих выходных и праздников"""
    pass