from datetime import datetime, timedelta
from calendar import  monthrange,weekday
import os
import sys

from id_employee import id_employee


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

def analyze_data_for_edit(time_table:dict,id:int,year:int,month:int):
    """ Функция анализирует сформированный по файлу данных словарь, ищет, у кого не хватает отметок ухода или прихода, 
        за какие дни нет даных, а затем выводит полученные данные на экран. 
    """
    name_list_tmp = id_employee(type_data = 2)
    name_list = name_list_tmp[1]
    name_employee = name_list[id]
    list_marks = search_for_missed_marks_employee(time_table,id,year,month)
    list_missed_day = search_for_missed_working_days_employee(time_table,id,year,month)
    if list_marks != 0:
        print("ПРЕДУПРЕЖДЕНИЕ! " + name_employee + " имеет только одну отметку в рабочем дне!", file=sys.stderr)
        for cell in list_marks:
            date_key_for_edit =cell[0]
            print('Дата и  время отметки, сохраненной в системе:',time_table[date_key_for_edit][id][0],sep = ' ')
            print('\n\n\tВыберете, какой вариант отметки будет введен:\n\n\t1.Отметка прихода\n\t2.Отметка ухода')
            white_veribal = 0
            while white_veribal!=1:
                user_choice = input('Выберете пункт меню:')
                if user_choice == '1' or user_choice =='2':
                    white_veribal = 1
                    entered_time = input('Введите время в формате час*ПРОБЕЛ*минуты*ПРОБЕЛ*секунды(если есть) --- 00 00 00:  ')
                    data_to_write = datetime.strptime(str(date_key_for_edit + ' ' + entered_time),"%Y-%m-%d %H %M %S")
                    if user_choice == '1':
                        time_table[date_key_for_edit][id][0] = data_to_write
                    else:
                        time_table[date_key_for_edit][id][1] = data_to_write
            print('Ввод данных об отметки подвержден!')
    
    if list_missed_day != 0:
        print("ПРЕДУПРЕЖДЕНИЕ! " + name_employee + " не имеет данных за рабочий день!", file=sys.stderr)
        for missed_day in list_missed_day:
            print('Дата без отметок:',missed_day,sep = ' ')
            print('Введите данные за день\n\n\t1.Рабочий день.Ввести отметку прихода и отметку ухода\n\t2.Отпускной день\n')
            loop_variable = 0
            while loop_variable != 1:
                switch_variable = input('Введите пункт меню:')
                if switch_variable == '1':
                    loop_variable = 1
                    print('Время прихода:\n')
                    entered_time_begin = input('Введите время в формате час*ПРОБЕЛ*минуты*ПРОБЕЛ*секунды(если есть) --- 00 00 00:  ')
                    data_to_write_begin = datetime.strptime(str(missed_day + ' ' + entered_time_begin),"%Y-%m-%d %H %M %S")
                    print('Время ухода:\n')
                    entered_time_end = input('Введите время в формате час*ПРОБЕЛ*минуты*ПРОБЕЛ*секунды(если есть) --- 00 00 00:  ')
                    data_to_write_end = datetime.strptime(str(missed_day + ' ' + entered_time_end),"%Y-%m-%d %H %M %S")
                    time_table[missed_day][id] = [data_to_write_begin,data_to_write_end]
                    
                elif switch_variable == '2':
                    loop_variable =  1
                    entered_time_begin = '00 00 01'
                    entered_time_end = '00 00 02'
                    data_to_write_begin = datetime.strptime(str(missed_day + ' ' + entered_time_begin),"%Y-%m-%d %H %M %S")
                    data_to_write_end = datetime.strptime(str(missed_day + ' ' + entered_time_end),"%Y-%m-%d %H %M %S")
                    time_table[missed_day][id] = [data_to_write_begin,data_to_write_end]
                    time_table[missed_day][id].append('отпуск')
                else:
                    print('Введите правильный пункт меню!')