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

def analyze_employer_work_date_new(data_dict:dict,id:int):
    """Функция анализа всех рабочих дней, который отработал сотрудник"""
    data_employer_work = []
    for data_date in data_dict.keys():
        if id in data_dict[data_date].keys():
            data_employer_work.append(data_date)
    return data_employer_work


def output_data_employer(data_dict:dict,id:int):
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
def definition_of_working_day(date:str):
    year = int(date[0:4])
    month = int(date[6:7])
    day = int(date[8:10])
    name_holiday_file = 'holidays.dat'
    name_postponed_working_days = ' 7  '
    file_holiday = open(name_holiday_file, 'r',encoding='utf-8')
    file_postponed_working_days = open(name_postponed_working_days,'r',encoding='utf-8')
    list_holiday = []
    for line in file_holiday:
        new_line = line.rstrip('\n')
        line_data=new_line.split('.')
        day_holiday  = line_data[0]
        month_holiday = line_data[1]
        holiday = str(year) + '-' + month_holiday + '-' + day_holiday
        list_holiday.append(holiday) 
    month = int(date[6:7])
    day = int(date[8:10])
    number_day = weekday(year,month,day)
    week_day_dic = {0:'Понедельник',1:'Вторник',2:'Среда',3:'Четверг',4:'Пятница',5:'Суббота',6:'Воскресенье'}
    str_weekday = week_day_dic[number_day]
    if date not in list_holiday:
        if number_day != 5 and number_day !=6:
            return ('work',str_weekday)
        else:
            return ('weekend',str_weekday)
    else:
        return ('holiday',str_weekday)


def search_for_missed_day_new():
    """Данная функция анализирует все записи работников за выбранный месяц и возвращает списки дат без отметок для каждого пользователя, а так же списки рабочих выходных и праздников"""
    pass