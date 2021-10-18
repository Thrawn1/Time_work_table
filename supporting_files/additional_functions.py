from calendar import weekday
from datetime import*
from id_employee import*
from analyze_data import *
import sys
from id_employee import id_employee
def output_data_employee(data_dict:dict,id:int):
    """Функция анализа всех рабочих дней, которые отработали сотрудники"""
    id_data= []
    for data_date in data_dict.keys():
        if id in data_dict[data_date].keys():
            id_data.append(data_date)
    for date in id_data:
        year = int(date[0:4])
        month = int(date[6:7])
        day = int(date[8:10])
        number_day = weekday(year,month,day)
        if number_day == 0:
            print('\n')
        week_day_dic = {0:'Понедельник',1:'Вторник',2:'Среда',3:'Четверг',4:'Пятница',5:'Суббота',6:'Воскресенье'}
        str_weekday = week_day_dic[number_day]
        print(date,str_weekday,sep=' - ')
        if number_day == 4:
            print('\n')

def editing_missing_mark(A:dict,last_day_month,requested_year:int,requested_month:int):
    """Функция поиска пропущенных отметок прихода или ухода в словаре
       Принимает весь словарь целиком, в котором структурированы id работников, даты и временные отметки из файла данных.
       Принимает значения рассматриваемого года и месяца
       Фукнция ничего не возвращает
    """
    first_day_month = datetime(requested_year,requested_month,1)
    last_day_month_type = datetime(requested_year,requested_month,last_day_month)
    name_list_tmp = id_employee(type_data = 2)
    name_list = name_list_tmp[1]
    for day_month in daterange(first_day_month,last_day_month_type,inclusive = True):
        date_day = day_month.strftime("%Y-%m-%d")
        if date_day in A.keys():
            for id in A[date_day].keys():
                if id in name_list:
                    if A[date_day][id][0] == A[date_day][id][1]:
                        name_employer = name_list[id]
                        print(name_employer)
                        print("ПРЕДУПРЕЖДЕНИЕ! " + name_employer + " имеет только одну отметку в рабочем дне!", file=sys.stderr)
                        print('Дата и  время отметки, сохраненной в системе:',A[date_day][id][0],sep = ' ')
                        print('\n\n\tВыберете, какой вариант отметки будет введен:\n\n\t1.Отметка прихода\n\t2.Отметка ухода')
                        white_veribal = 0
                        while white_veribal!=1:
                            user_choice = input('Выберете пункт меню:')
                            if user_choice == '1' or user_choice =='2':
                                white_veribal = 1
                                entered_time = input('Введите время в формате час*ПРОБЕЛ*минуты*ПРОБЕЛ*секунды(если есть) --- 00 00 00:  ')
                                data_to_write = datetime.strptime(str(date_day + ' ' + entered_time),"%Y-%m-%d %H %M %S")
                                if user_choice == '1':
                                    A[date_day][id][0] = data_to_write
                                else:
                                    A[date_day][id][1] = data_to_write
                                print('Ввод данных об отметки подвержден!')
                                print("Данные в системе\n\n\n")
                                print("Время прихода:",A[date_day][id][0],"Время ухода:",A[date_day][id][1],sep=' ')
                            else:
                                print('Введите цифру, соответсвующую пункту меню!')

                else:
                    pass
        else:
            pass



def search_missing_mark(A:dict,requested_year:int,requested_month:int):
    """Функция поиска пропущенных отметок прихода или ухода в словаре
       Принимает весь словарь целиком, в котором структурированы id работников, даты и временные отметки из файла данных.
       Принимает значения рассматриваемого года и месяца
       Фукнция ничего не возвращает
    """
    missing_mark_dict = {}
    last_day_month = monthrange(requested_year,requested_month)[1]
    first_day_month = datetime(requested_year,requested_month,1)
    last_day_month_type = datetime(requested_year,requested_month,last_day_month)
    name_list_tmp = id_employee(type_data = 2)
    name_list = name_list_tmp[1]
    for id in name_list:
        missing_mark_dict[id] = []
    for day_month in daterange(first_day_month,last_day_month_type,inclusive = True):
        date_day = day_month.strftime("%Y-%m-%d")
        if date_day in A.keys():
            for id in A[date_day].keys():
                if id in name_list:
                    if A[date_day][id][0] == A[date_day][id][1]:
                        # name_employer = name_list[id]
                        # print(name_employer)
                        # print("ПРЕДУПРЕЖДЕНИЕ! " + name_employer + " имеет только одну отметку в рабочем дне!", file=sys.stderr)
                        # print('Дата и  время отметки, сохраненной в системе:',A[date_day][id][0],sep = ' ')
                        missing_mark_dict[id].append(date_day)
    for id in list(missing_mark_dict):
        a = missing_mark_dict[id]
        if len(a) == 0:
            missing_mark_dict.pop(id)
        else:
            pass
        pass
    return missing_mark_dict



    # def search_for_missed_day(A:dict,all_day_month:list,requested_year:int,requested_month:int):
#     """Функция поиска пропущенных рабочих дней в месяце.
#        Принимает весь структурированный словарь целиком.
#        Возвращет список рабочих дней, которые были пропущены
#     """
#     list_work_date = []
#     work_days_without_data = []
#     for work_date in A.keys():
#         # print(work_date)
#         # print(A[work_date])
#         list_work_date.append(work_date)
#     print('Рабочие дни месяца:')
#     print(list_work_date)
#     for day in list_work_date:
#         a = weekday(requested_year,requested_month,int(day[8:]))
#         week_day_dic = {0:'Понедельник',1:'Вторник',2:'Среда',3:'Четверг',4:'Пятница',5:'Суббота',6:'Воскресенье'}
#         b = week_day_dic.get(a)
#         #print(day,b, sep = '|||')
#     for day_month_number in all_day_month:
#         day_month_data = date(requested_year,requested_month,day_month_number)
#         day_month = day_month_data.strftime("%Y-%m-%d") + ' '
#         mark_day=list_work_date.count(day_month)
#         if mark_day == 0:
#             week_day_work = weekday(requested_year,requested_month,day_month_number)
#             if week_day_work != 5 and week_day_work != 6:
#                 work_days_without_data.append(day_month)
#     print('Дней без отметок: \n',work_days_without_data)

#     pass

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