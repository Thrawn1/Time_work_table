def gen_html_file(name_file:str,data_days_list:list,data_month_dict:dict):
    """Функция создает начальные тэги html файла. Создает список, в который
    добавляются все строки. После генерации всех строк они из списка записываются разом в файл
    Функция принимает имя html файла"""
    

    all_line_html = []
    space = '  '
    new_line = '\n'
    html_tag_start = '<html>'
    html_tag_end = '</html>'
    table_tag_start  = '<table border="5" class="dataframe" style="width:100%">'
    table_tag_end = '</table>'
    tbody_tag_start = '<tbody>'
    tbody_tag_end = '</tbody>'
    tr_tag_start = '<tr>'
    tr_tag_end = '</tr>'
    line = html_tag_start + new_line
    all_line_html.append(line)
    line = 3*space + table_tag_start + new_line
    all_line_html.append(line)
    data_block_topic_table_data_days = gen_block_topic_table(type_table=1)
    for line in data_block_topic_table_data_days:
        all_line_html.append(line)
    line = 4*space + tbody_tag_start + new_line
    all_line_html.append(line)
    line = 6*space + tr_tag_start + new_line
    all_line_html.append(line)
    #Надо придумать как итерировать все записи за месяц, что бы потом вытащить нужные данные
    #Придумать логику, по которой буду отделяться обычные дни от Отпусков и Прогулов
    for day in  data_days_list:
        if day['tag_day'] == 'Рабочий день':
            data_block_data_day = gen_block_data_day(family=day['family'],date=day['date'],time_begin=day['time_begin'],time_end=day['time_end'],delta_time=day['delta_time'],tag_overtime=day['tag_overtime'],overtime=day['overtime'])
        else:
            data_block_data_day = gen_block_data_day(family=day['family'],date=day['date'],time_begin=day['time_begin'],time_end=day['time_end'],delta_time=day['delta_time'],tag_overtime=day['tag_overtime'],overtime=day['overtime'],tag_day=day['tag_day'],type_block=2)
        for line in data_block_data_day:
            all_line_html.append(line)
    line = 6*space + tr_tag_end + new_line
    all_line_html.append(line)
    line = 4*space + tbody_tag_end + new_line
    all_line_html.append(line)
    
    line = 3*space + table_tag_end + new_line
    all_line_html.append(line)
    line = 3*space + table_tag_start + new_line
    all_line_html.append(line)
    data_block_topic_table_data_month = gen_block_topic_table(type_table=2)
    for line in data_block_topic_table_data_month:
        all_line_html.append(line)
    line = 4*space + tbody_tag_start + new_line
    all_line_html.append(line)
    line = 6*space + tr_tag_start + new_line
    all_line_html.append(line)
    data_block_month_employee = gen_block_data_month_employee(family=data_month_dict['family'],all_work_weekdays=data_month_dict['all_work_weekdays'],weekdays_overtime=data_month_dict['weekdays_overtime'],work_weekend=data_month_dict['work_weekend'],overtime_weekend=data_month_dict['overtime_weekend'],vacation=data_month_dict['vacation'],salary=data_month_dict['salary'])
    for line in data_block_month_employee:
        all_line_html.append(line)
    line = 6*space + tr_tag_end + new_line
    all_line_html.append(line)
    line = 4*space + tbody_tag_end + new_line
    all_line_html.append(line)
    line = 3*space + table_tag_end + new_line
    all_line_html.append(line)
    line = html_tag_end + new_line
    all_line_html.append(line)
    file = open(name_file,'w',encoding='utf-8')
    for line in all_line_html:
        file.write(line)
    file.close()
    print('Готово')
    


def gen_block_topic_table(type_table:int):
    """Функция создает заголовок таблицы. В случае, если передан тип таблицы 1 - генерируется блок шапки таблицы рабочих дней.
    В любом другом случае - генерируется шапка таблицы сводных данных за месяц.
    Возвращает список со строками html-файла """
    
    
    th_tag_start = '<th>'
    th_tag_end =  '</th>'
    thead_tag_start = '<thead>'
    thead_tag_end = '</thead>'
    tr_tag_start = '<tr style="text-align: right;">'
    tr_tag_end = '</tr>'
    new_line = '\n'
    space = '  '
    if type_table == 1:
        topicsList=('Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переработка')
    else:
        topicsList = ('Фамилия', 'Отработано будних дней', 'Перерабокта', 'Рабочих выходных', 'Переработка в выходные дни', 'Количество дней отпуска','Зарплата')
    lines_block = []
    line = 4*space + thead_tag_start + new_line
    lines_block.append(line)
    line = 6*space + tr_tag_start + new_line
    lines_block.append(line)
    for topic in topicsList:
        line = 8*space + th_tag_start + topic + th_tag_end + new_line
        lines_block.append(line)
    line = 6*space + tr_tag_end + new_line
    lines_block.append(line)
    line = 4*space + thead_tag_end + new_line
    lines_block.append(line)
    return lines_block


def gen_block_data_day(family:str,date:str,time_begin:str,time_end:str,delta_time:str,tag_overtime:str,overtime:str,type_block = 1,tag_day = 'Рабочий день'):
    """Функция генерирует блок строк описывающих один день месяца. Дата, время прихода, время ухода, общее время работы,
    тэг(переработка/недоработка), велечина переработки/недоработки. Функция принимает аргументы в строковом
    формате - Фамилию, дату, время прихода, время ухода, общее рабочее время, тэг переработки/недоработки, величина переработки/недоработки.
    Возврщает кортеж с строками блока."""
    space = '  '
    new_line = '\n'
    td_tag_start = '<td>'
    td_tag_end =  '</td>'
    td_tag_merge_cell = '<td colspan="5" align="center">'
    tr_tag_start = '<tr>'
    tr_tag_end = '</tr>'
    line_1 = 6*space + tr_tag_start + new_line
    line_2 = 8*space + td_tag_start + family  + td_tag_end + new_line
    line_3 = 8*space + td_tag_start + date  + td_tag_end + new_line
    if type_block == 1:
        line_4 = 8*space + td_tag_start + time_begin + td_tag_end + new_line
        line_5 = 8*space + td_tag_start + time_end + td_tag_end + new_line
        line_6 = 8*space + td_tag_start + delta_time + td_tag_end + new_line
        line_7 = 8*space + td_tag_start + tag_overtime + td_tag_end + new_line
        line_8 = 8*space + td_tag_start + overtime + td_tag_end + new_line
        line_9 = 6*space + tr_tag_end + new_line
        return (line_1,line_2,line_3,line_4,line_5,line_6,line_7,line_8,line_9)
    else:
        line_4 = 8*space + td_tag_merge_cell + tag_day + td_tag_end + new_line
        line_5 = 6*space + tr_tag_end + new_line
        return (line_1,line_2,line_3,line_4,line_5)


def gen_block_data_month_employee(family:str,all_work_weekdays:int,weekdays_overtime:str,work_weekend:int,overtime_weekend:str,vacation:int,salary:float):
    """Функция генерирует блок строк описывающий месяц работы сотрудника. Фамилия, Отработано будних денй, Переработка, Отработанные выходные дни, 
    Переработка в выходные дни,Количесто дней отпуска, Зарплата. Функция принимает фамилию, полное время переработки в будние дни и полное время 
    переаботки в выходные в строковом виде, зарплату в формате вещественных чисел, все остальное - формате целых чисел.Возвращет кортеж с 
    строками блока"""
    space = '  '
    new_line = '\n'
    td_tag_start = '<td>'
    td_tag_end =  '</td>'
    tr_tag_start = '<tr>'
    tr_tag_end = '</tr>'
    line_1 = 6*space + tr_tag_start + new_line
    line_2 = 8*space + td_tag_start + family  + td_tag_end + new_line
    line_3 = 8*space + td_tag_start + str(all_work_weekdays) + td_tag_end + new_line
    line_4 = 8*space + td_tag_start + weekdays_overtime + td_tag_end + new_line
    line_5 = 8*space + td_tag_start + str(work_weekend) + td_tag_end + new_line
    line_6 = 8*space + td_tag_start + overtime_weekend + td_tag_end + new_line
    line_7 = 8*space + td_tag_start + str(vacation) + td_tag_end + new_line
    line_8 = 8*space + td_tag_start + str(salary) + td_tag_end + new_line
    line_9 = 6*space + tr_tag_end + new_line
    return (line_1,line_2,line_3,line_4,line_5,line_6,line_7,line_8,line_9)

