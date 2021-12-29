from id_employee import id_employee

def gen_html_file(data_employee:tuple):
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
    for day in data_employee[1]:
        data_block_data_day = gen_block_data_day(day)
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
    data_block_month_employee = gen_block_data_month_employee(data_employee[2])
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
    file = open(data_employee[0],'w',encoding='utf-8')
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


def gen_block_data_day(data_day:dict):
    """Функция генерирует блок строк описывающих один день месяца. Дата, время прихода, время ухода, общее время работы,
    тэг(переработка/недоработка), велечина переработки/недоработки. Функция принимает словарь, с данными за день.
    Возврщает кортеж с строками блока."""
    
    space = '  '
    new_line = '\n'
    td_tag_start = '<td>'
    td_tag_end =  '</td>'
    td_tag_merge_cell = '<td colspan="5" align="center">'
    tr_tag_start = '<tr>'
    tr_tag_end = '</tr>'
    line_1 = 6*space + tr_tag_start + new_line
    line_2 = 8*space + td_tag_start + data_day['family']  + td_tag_end + new_line
    line_3 = 8*space + td_tag_start + data_day['date']  + td_tag_end + new_line
    if data_day['tag_day'] == 'work':
        line_4 = 8*space + td_tag_start + data_day['time_begin'] + td_tag_end + new_line
        line_5 = 8*space + td_tag_start + data_day['time_end'] + td_tag_end + new_line
        line_6 = 8*space + td_tag_start + data_day['delta_time'] + td_tag_end + new_line
        line_7 = 8*space + td_tag_start + data_day['tag_overtime'] + td_tag_end + new_line
        line_8 = 8*space + td_tag_start + data_day['overtime'] + td_tag_end + new_line
        line_9 = 6*space + tr_tag_end + new_line
        return (line_1,line_2,line_3,line_4,line_5,line_6,line_7,line_8,line_9)
    else:
        line_4 = 8*space + td_tag_merge_cell + data_day['tag_day'] + td_tag_end + new_line
        line_5 = 6*space + tr_tag_end + new_line
        return (line_1,line_2,line_3,line_4,line_5)


def gen_block_data_month_employee(data_month_dict:dict):
    """Функция генерирует блок строк описывающий месяц работы сотрудника. Фамилия, Отработано будних денй, Переработка, Отработанные выходные дни, 
    Переработка в выходные дни,Количесто дней отпуска, Зарплата. Функция принимает словарь с данными за месяц для работника.Возвращет кортеж с 
    строками блока"""


    space = '  '
    new_line = '\n'
    th_tag_start = '<th>'
    th_tag_family_start = '<th align="center">'
    th_tag_end =  '</th>'
    tr_tag_start = '<tr>'
    tr_tag_end = '</tr>'
    line_1 = 6*space + tr_tag_start + new_line
    line_2 = 8*space + th_tag_family_start + data_month_dict['family']  + th_tag_end + new_line
    line_3 = 8*space + th_tag_start + str(data_month_dict['all_work_weekdays']) + th_tag_end + new_line
    line_4 = 8*space + th_tag_start + data_month_dict['weekdays_overtime'] + th_tag_end + new_line
    line_5 = 8*space + th_tag_start + str(data_month_dict['work_weekend']) + th_tag_end + new_line
    line_6 = 8*space + th_tag_start + data_month_dict['overtime_weekend'] + th_tag_end + new_line
    line_7 = 8*space + th_tag_start + str(data_month_dict['vacation']) + th_tag_end + new_line
    line_8 = 8*space + th_tag_start + str(data_month_dict['salary']) + th_tag_end + new_line
    line_9 = 6*space + tr_tag_end + new_line
    return (line_1,line_2,line_3,line_4,line_5,line_6,line_7,line_8,line_9)


def build_html(time_table:dict,work_time_employees:dict):
    """Функция принимает структуру данных за месяц для всех работников. Она преобразует структуру в кортежи с данными
    для построения по кортежам html файлов для каждого из работников. Функция не возвраещет ничего, только выводит сообщение на экран """

    list_id = id_employee(type_data=2)
    list_date = []
    for date in time_table.keys():
        list_date.append(date)
    list_date.sort()
    for date in list_date:
        for id in time_table[date]:
            family = list_id[1][id]
            month_data_employee_for_html = []
            file_name = family + '_' + date[5:7] + '_' + date[:4] + '.html'
            print(file_name)
            if id in list_id[1]:
                cell_data_dict = {}
                date_str = date 
                time_begin = time_table[date][id][1].time().isoformat(timespec = 'auto')
                time_end = time_table[date][id][0].time().isoformat(timespec = 'auto')
                delta_time = str(work_time_employees[date][id][1])
                tag_overtime = work_time_employees[date][id][2]
                overtime = str(work_time_employees[date][id][0])
                tag_day = work_time_employees[date][id][3]
                cell_data_dict['family'] = family
                cell_data_dict['date'] = date_str
                cell_data_dict['time_begin'] = time_begin
                cell_data_dict['time_end'] = time_end
                cell_data_dict['delta_time'] = delta_time
                cell_data_dict['tag_overtime'] = tag_overtime
                cell_data_dict['overtime'] = overtime
                cell_data_dict['tag_day'] = tag_day
                month_data_employee_for_html.append(cell_data_dict)
            all_data_employee = (file_name,month_data_employee_for_html)
            return all_data_employee

def build_data_per_month():
    """Функция ..."""
    pass
