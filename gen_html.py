
def gen_html_line_data_time(name,time_1,time_2,timedl,tag_time,over_time):
    """Функция генерирует html блок для таблицы по данным для каждого дня"""
    space = '  '
    new_line = '\n'
    th_tag_start = '<th>'
    th_tag_end =  '</th>'
    tr_tag_start = '<tr>'
    tr_tag_end = '</tr>'
    line_1 = 6*space + tr_tag_start + new_line
    line_2 = 8*space + th_tag_start + name  + th_tag_end + new_line
    line_3 = 8*space + th_tag_start + time_1 + th_tag_end + new_line
    line_4 = 8*space + th_tag_start + time_2 + th_tag_end + new_line
    line_5 = 8*space + th_tag_start + timedl + th_tag_end + new_line
    line_6 = 8*space + th_tag_start + tag_time + th_tag_end + new_line
    line_7 = 8*space + th_tag_start + over_time + th_tag_end + new_line
    line_8 = 6*space + tr_tag_end + new_line
    return (line_1,line_2,line_3,line_4,line_5,line_6,line_7,line_8)


def gen_html_line_data_per_month(name:str,work_day_per_month:int, holiday_work_per_month:int, overtime_work_days:int, overtime_holiday_days:int, money:int ):
    """Функция генерирует табличкку работника за месяц, где укзано сколько дней отработал работник, сколько часов у него переработки и какая зарплата"""
    pass


def gen_html_file_body(name,time_1,time_2,timedl,tag_time,over_time,request_year:int, request_month:int):
    """Функция генерирует html файл, содержаший информацию по одному конктреному работнику. Даты, когда он был, время, когда была отметка, переработка
    Так же есть сводная таблица, где указано, сколько дней отработал человек, сколько у него всего часов переработки и зарплата. """
    
    
    all_data_html = []
    topicsList=('Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переработка')
    space = '  '
    new_line = '\n'
    file_name = request_year + '_'+ request_month  + '_' + name + '.html'
    file = open(file_name,'w',encoding='utf-8')
    html_tag_start = '<html>'
    html_tag_end = '</html>'
    table_tag_start  = '<table border="5" class="dataframe" style="width:100%">'
    table_tag_end = '</table>'
    thead_tag_start = '<thead>'
    thead_tag_end = '</thead>'
    tr_tag_start = '<tr style="text-align: right;">'
    tr_tag_end = '</tr>'
    th_tag_start = '<th>'
    th_tag_end =  '</th>'
    tbody_tag_star = '<tbody>'
    tbody_tag_end = '</tbody>'
    td_tag_start = '<td>'
    td_tag_end = '</td>'

    line = html_tag_start + new_line
    all_data_html.append(line)
    line = 3*space + table_tag_start + new_line
    all_data_html.append(line)
    line = 4*space + thead_tag_start + new_line
    all_data_html.append(line)
    line = 6*space + tr_tag_start + new_line
    all_data_html.append(line)
    for topic in topicsList:
        line = 8*space + th_tag_start + topic + th_tag_end + new_line
        all_data_html.append(line)
    line = 6*space + tr_tag_end + new_line
    file.write(line)
    line = 4*space + thead_tag_end + new_line
    file.write(line)



    line = 4*space + tbody_tag_star + new_line
    file.write(line)
    for i in range(100):
        gen_html_line_data_time(name,time_1,time_2,timedl,tag_time,over_time)

    line = 4*space + tbody_tag_end + new_line
    file.write(line)
    line = 3*space + table_tag_end + new_line
    file.write(line)
    line = html_tag_end + new_line
    file.write(line)
    file.close()
    print('Готово')





test_date = ['2021-03-01','2021-03-02','2021-03-03']
name = 'Иванов '
time_1 = '10:00:00'
time_2 = '18:00:00'
timedl = '08:00:00'
tag_time = 'недоработка'
over_time = '00:00:00'