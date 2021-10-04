from calendar import weekday
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

