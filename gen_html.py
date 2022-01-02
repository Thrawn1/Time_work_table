from id_employee import id_employee
from datetime import timedelta


def html_builder(id:int,all_data_dates_and_marks:dict,data_work_time_all_employees:dict,all_data_per_month_employees:dict,total_salary_employees:dict):
    """Функция вызывает функции, которые формируют структуры необходимые для построения html, а так же функцию построения html файла 
    Принимает id работника, всю структуру данных, в которой есть данные о всех пользователях за месяц, их отметках прихода и ухода. Кроме того, функция принимает структуру данных,
    которая содержит информацию об отработанных часах всех сотрудников. Кроме того, структуру данных, содержащую информацию о зарплатах всех сотрудников(при условии ввода корректного секретного ключа).
    Функция выводит сообщение, о том, что файл с данными сформирован. """
    

    list_id = id_employee(type_data=2)
    family = list_id[1][id]
    all_data_per_month_for_marks_employee_for_html = build_data_days_per_month_for_month(id,all_data_dates_and_marks,data_work_time_all_employees)
    total_data_for_employee_month = build_data_total_for_month_for_employee(id,all_data_per_month_employees,total_salary_employees)
    str_month = all_data_per_month_for_marks_employee_for_html[0]['date'][5:7]
    str_year = all_data_per_month_for_marks_employee_for_html[0]['date'][:4]
    name_html_file = family + '_' + str_month + '_' + str_year + '.html'
    data_employee = (name_html_file,all_data_per_month_for_marks_employee_for_html,total_data_for_employee_month)
    gen_html_file(data_employee)
    print('Файл готов:', name_html_file)


def build_data_days_per_month_for_month(id:int,all_data_dates_and_marks:dict,data_work_time_all_employees:dict):
    """Функция создает структуру данных, содержащую информацию о дате, отметки прихода и отметки ухода сотрудника. Функция принимает id сотрудника,
    структуру данных, которая содержит информацию о датах и отметках всех пользователей. Функция возвращает список, состоящий из словарей и информацией
    о каждом рабочем дне конктретного работника. """


    list_id = id_employee(type_data=2)
    list_date = []
    for date in all_data_dates_and_marks.keys():
        list_date.append(date)
    list_date.sort()
    all_data_per_month_for_marks_employee_for_html = []
    for date in list_date:
        if id in list_id[1] and id in all_data_dates_and_marks[date]:
            cell_data_dict = {}
            cell_data_dict['family'] = list_id[1][id]
            cell_data_dict['date'] = date
            cell_data_dict['time_begin'] = all_data_dates_and_marks[date][id][1].time().isoformat(timespec = 'auto')
            cell_data_dict['time_end'] = all_data_dates_and_marks[date][id][0].time().isoformat(timespec = 'auto')
            cell_data_dict['delta_time'] = str(data_work_time_all_employees[date][id][1])
            cell_data_dict['tag_overtime'] = data_work_time_all_employees[date][id][2]
            cell_data_dict['overtime'] = str(data_work_time_all_employees[date][id][0])
            if data_work_time_all_employees[date][id][3] == 'vacation':
                cell_data_dict['tag_day'] = 'Отпуск'
            elif data_work_time_all_employees[date][id][3] == 'truancy':
                cell_data_dict['tag_day'] = 'Прогул'
            else:
                cell_data_dict['tag_day'] = data_work_time_all_employees[date][id][3]
            all_data_per_month_for_marks_employee_for_html.append(cell_data_dict)
    return all_data_per_month_for_marks_employee_for_html


def build_data_total_for_month_for_employee(id:int,all_data_per_month_employees:dict,total_salary_employees:dict):
    """Функция создает структуру данных, содержащий суммарную информацию за месяц для одного работника. Функция принимает id  работника,
    структуру, содержащую суммарную информацию за месяц для каждого работника, а так же структуру, содержащую информацию о зарплатах всех 
    сотрудников(при условии ввода корректного секретного ключа).Функция возвращает словарь, содержаший всю суммарную информацию для конктреного работника,
    который нужен для построения html файла"""


    total_data_for_employee_month = {}
    list_id = id_employee(type_data=2)
    data_per_month_employee = all_data_per_month_employees[id]
    total_data_for_employee_month['family'] = list_id[1][id]
    total_data_for_employee_month['all_work_weekdays'] = data_per_month_employee[0][0]
    total_data_for_employee_month['weekdays_overtime'] = str_time_overwork(data_per_month_employee[0][1])
    total_data_for_employee_month['work_weekend'] = data_per_month_employee[1][0]
    total_data_for_employee_month['overtime_weekend'] = str_time_overwork(data_per_month_employee[1][1])
    total_data_for_employee_month['vacation'] = data_per_month_employee[2]
    total_data_for_employee_month['salary'] = total_salary_employees[id]
    return total_data_for_employee_month


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
        th_tag_merge_cell = '<th colspan="2" align="center">'
        topicsList=('Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переработка')
    else:
        topicsList = ('Фамилия', 'Отработано будних дней', 'Переработка в будние дни', 'Рабочих выходных', 'Переработка в выходные дни', 'Количество дней отпуска','Зарплата')
    lines_block = []
    line = 4*space + thead_tag_start + new_line
    lines_block.append(line)
    line = 6*space + tr_tag_start + new_line
    lines_block.append(line)
    for topic in topicsList:
        if topic != 'Переработка':
            line = 8*space + th_tag_start + topic + th_tag_end + new_line
            lines_block.append(line)
        else:
            line = 8*space + th_tag_merge_cell + topic + th_tag_end + new_line
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
    elif data_day['tag_day'] == 'weekend':
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


def str_time_overwork(time:timedelta):
    """Функция преобразует общее время переработки в строковый стиль вида часы:минуты:секунды. 
    Функция принимает объект типа timedetla. Возвращает строку"""
    
    
    time_in_seconds = time.total_seconds()
    hours = int(time_in_seconds//3600)
    minutes = int((time_in_seconds - hours*3600)//60)
    seconds = int(time_in_seconds - hours*3600 - minutes*60)
    if len(str(hours)) == 1:
        str_hours = '0' + str(hours)
    else:
        str_hours = str(hours)
    if len(str(minutes)) == 1:
        str_minutes = '0' + str(minutes)
    else:
        str_minutes = str(minutes)
    if len(str(seconds)) == 1:
        str_seconds = '0' + str(seconds)
    else:
        str_seconds = str(seconds)
    str_time_overwork = str_hours + ':' + str_minutes + ':' + str_seconds
    return str_time_overwork