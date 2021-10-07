from calendar import  monthrange, weekday
from datetime import datetime, timedelta, date
from id_employee import id_employee

def daterange(start,stop,step=timedelta(days = 1),inclusive = False):
    """Функция-генератор 
    """
    if step.days > 0:
        while start < stop:
            yield start
            start = start + step
    elif step.days < 0:
        while start > stop:
            yield start
            start = start + step
    if inclusive and start == stop:
        yield start

def search_missing_mark_employee(A:dict,id:int,requested_year:int,requested_month:int):
    """Функция поиска пропущенных отметок прихода или ухода за месяц.
       Принимает весь словарь целиком, в котором структурированы id работников, даты и временные отметки из файла данных.
       Принимает значения рассматриваемого года и месяца, а так же id сотрудника. 
       Фукнция возвращает список,в котором пара значений - дата и время одиночной отмеки.
    """
    missing_mark_list = []
    jk = [[1,0],]
    last_day_month = monthrange(requested_year,requested_month)[1]
    first_day_month = datetime(requested_year,requested_month,1)
    last_day_month_type = datetime(requested_year,requested_month,last_day_month)
    for day_month in daterange(first_day_month,last_day_month_type,inclusive = True):
        date_day = day_month.strftime("%Y-%m-%d")
        if date_day in A.keys():
            if id in A[date_day].keys():
                if A[date_day][id][0] == A[date_day][id][1]:
                    data_cell = [0,0]
                    data_cell[0] = date_day
                    data_cell[1] = A[date_day][id][1]
                    missing_mark_list.append(data_cell)
            else:
                print('Нет данных за день')
                return 0
    if len(missing_mark_list) != 0:
        return missing_mark_list
    else:
        print('Пропущенных отметок нет')
        return 0

def analyze_employee_work_date(data_dict:dict):
    """Функция анализа всех рабочих дней, который отработал сотрудник"""
    data_employee_work = {}
    employee_list = id_employee()
    for id in employee_list:
        data_employee_work[id] = []
    for data_date in data_dict.keys():
        for id in data_dict[data_date].keys():
            data_employee_work[id].append(data_date)
    for id in data_employee_work.keys():
        name = employee_list[id]
        print(name,":\n" )
        for date in data_employee_work[id]:
            print(date)
    print(data_employee_work)
    print(employee_list)
    return data_employee_work


def analyze_data(A,requested_year:int,requested_month:int,):
    """ Функция анализирует сформированный по файлу данных словарь, ищет, у кого не хватает отметок ухода или прихода, 
        за какие дни нет даных. 
    """
    last_day_month = monthrange(requested_year,requested_month)[1]
    all_day_request_month = list(range(1,last_day_month+1,1))
    
    pass