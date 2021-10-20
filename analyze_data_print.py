from datetime import datetime, timedelta
from calendar import  month_name, monthrange,weekday
import os

from id_employee import id_employee

def month_name_for_print(month_id):
    """Функция возвращает название месяца на русском. Принимает номер месяца"""
    months_names = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}
    name_month = months_names[month_id]
    return name_month

def reading_employee_work_date(data_dict:dict,id:int):
    """Функция получения всех рабочих дней сотрудника по которым есть хотя бы одна метка"""
    data_employer_work = []
    for data_date in data_dict.keys():
        if id in data_dict[data_date].keys():
            data_employer_work.append(data_date)
    return data_employer_work

def definition_of_working_day(date:str):
    """Функция определяет, какого типа день - рабочий, выходной или праздничный. Принимает дату в строковом виде, использует списки исключений(праздников и перенесенных рабочих дней). Возвращает метку - день рабочий, выходной или праздничный """
    year = int(date[0:4])
    month = int(date[6:7])
    day = int(date[8:10])
    name_holiday_file_relative = 'holidays.dat'
    name_postponed_working_days_relative = 'postponed_working_days.dat'
    name_holiday_file = os.path.join("data",name_holiday_file_relative)
    name_postponed_working_days = os.path.join("data",name_postponed_working_days_relative)
    file_holiday = open(name_holiday_file, 'r',encoding='utf-8')
    file_postponed_working_days = open(name_postponed_working_days,'r',encoding='utf-8')
    list_holiday = []
    list_postponed_working_days = []
    for line in file_holiday:
        new_line = line.rstrip('\n')
        line_data=new_line.split('.')
        day_holiday  = line_data[0]
        month_holiday = line_data[1]
        holiday = str(year) + '-' + month_holiday + '-' + day_holiday
        list_holiday.append(holiday) 
    for line in file_postponed_working_days:
        new_line = line.rstrip('\n')
        line_data=new_line.split('.')
        day_postponed_working_days  = line_data[0]
        month_postponed_working_days = line_data[1]
        postponed_working_days = str(year) + '-' + month_postponed_working_days + '-' + day_postponed_working_days
        list_postponed_working_days.append(postponed_working_days)
    month = int(date[6:7])
    day = int(date[8:10])
    number_day = weekday(year,month,day)
    week_day_dic = {0:'Понедельник',1:'Вторник',2:'Среда',3:'Четверг',4:'Пятница',5:'Суббота',6:'Воскресенье'}
    str_weekday = week_day_dic[number_day]
    if date not in list_holiday:
        if date not in list_postponed_working_days:
            if number_day != 5 and number_day !=6:
                return ('work',str_weekday)
            else:
                return ('weekend',str_weekday)
        else:
            return ('weekend',str_weekday)
    else:
        return ('holiday',str_weekday)

def generation_of_lists_of_days(requested_year:int,requested_month:int):
    """Функция принимает значения года и месяца. Функция возвращает список, содержащий списки  - рабочие дни месяца и выходные и праздничные дни месяца """
    last_day_request_month = monthrange(requested_year,requested_month)[1]
    list_day_month = [[],[]]
    for day in range(1,last_day_request_month+1, 1):
        if day in range(1,10,1):
            day_str = '0' +  str(day)
        else:
            day_str = str(day)
        year = str(requested_year)
        if requested_month in range(1,10,1):
            month = '0' + str(requested_month)
        else:
            month = str(requested_month)
        date_str = year + '-' + month + '-' + day_str
        day_mark = definition_of_working_day(date_str)
        if day_mark[0] == 'work':
            list_day_month[0].append(date_str)
        else:
            list_day_month[1].append(date_str)
    return list_day_month

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

def search_for_missed_working_days_employee(time_table:dict,id:int,year:int,month:int):
    """Данная функция анализирует все записи работников за выбранный месяц и возвращает списки дат без отметок для каждого пользователя, а так же списки рабочих выходных и праздников
    """
    missed_days = []
    month_days_work = generation_of_lists_of_days(year,month)
    emoyee_days_work = reading_employee_work_date(time_table,id)
    if len(emoyee_days_work) != 0:
        for day in month_days_work[0]:
            if day not in emoyee_days_work:
                missed_days.append(day)
            else:
                pass
        if len(missed_days) != 0:
            return missed_days
        else:
            return 0
    else: 
        return 0

def search_for_missed_marks_employee(time_table:dict,id:int,requested_year:int,requested_month:int):
    """Функция поиска пропущенных отметок прихода или ухода за месяц.
       Принимает весь словарь целиком, в котором структурированы id работников, даты и временные отметки из файла данных.
       Принимает значения рассматриваемого года и месяца, а так же id сотрудника. 
       Фукнция возвращает список,в котором пара значений - дата и время одиночной отмеки.
    """
    missing_mark_list = []
    last_day_month = monthrange(requested_year,requested_month)[1]
    first_day_month = datetime(requested_year,requested_month,1)
    last_day_month_type = datetime(requested_year,requested_month,last_day_month)
    for day_month in daterange(first_day_month,last_day_month_type,inclusive = True):
        date_day = day_month.strftime("%Y-%m-%d")
        if date_day in time_table.keys():
            if id in time_table[date_day].keys():
                if time_table[date_day][id][0] == time_table[date_day][id][1]:
                    data_cell = [0,0]
                    data_cell[0] = date_day
                    data_cell[1] = time_table[date_day][id][1]
                    missing_mark_list.append(data_cell)
    if len(missing_mark_list) != 0:
        return missing_mark_list
    else:
        return 0

def analyze_data_for_print(time_table:dict,id:int,year:int,month:int):
    """ Функция анализирует сформированный по файлу данных словарь, ищет, у кого не хватает отметок ухода или прихода, 
        за какие дни нет даных, а затем выводит полученные данные на экран. 
    """
    list_employee = id_employee()
    list_marks = search_for_missed_marks_employee(time_table,id,year,month)
    list_missed_day = search_for_missed_working_days_employee(time_table,id,year,month)
    name_employee = list_employee[id]
    if list_marks !=0 or list_missed_day != 0:
        print('\nФамилия работника:  ',name_employee)
        if list_marks != 0:
            print('\n\tЕсть только одна метка:\n')
            for marks in list_marks:
                i = marks[1]
                i_o = i.time()
                i_a = i.date()
                print(i_o,i_a,type(i_o),type(i_a))
                
                print(marks[1])
        if list_missed_day !=0:
            print('\n\tДаты рабочих дней, где нет отметок:\n')
            for missed_day in list_missed_day:
                print(missed_day)