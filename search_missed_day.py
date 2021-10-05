from calendar import  calendar, month, monthrange, weekday
from id_employer import id_employer

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
    name_holiday_file = 'holidays.dat'
    name_postponed_working_days = 'postponed_working_days.dat'
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
    """Функция принимает значения года и месяца. Функция возвращает Список, содержащий списки - рабочие будние дни, выходные дни и праздники """
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

def search_for_missed_day_new(data_dict:dict,id:int,requested_year:int,requested_month:int):
    """Данная функция анализирует все записи работников за выбранный месяц и возвращает списки дат без отметок для каждого пользователя, а так же списки рабочих выходных и праздников"""
    missed_days = []
    month_days_work = generation_of_lists_of_days(requested_year,requested_month)
    emoyee_days_work = reading_employee_work_date(data_dict,id)
    if len(emoyee_days_work) != 0:
        for day in month_days_work[0]:
            if day not in emoyee_days_work:
                missed_days.append(day)
            else:
                pass
        if len(missed_days) != 0:
            return missed_days
        else:
            pass
    else: 
        return 0