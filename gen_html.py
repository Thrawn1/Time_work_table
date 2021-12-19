

test_date = ['2021-03-01','2021-03-02','2021-03-03']
topicsList=['Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переработка']
space = '  '
new_line = '\n'
name = 'Русаков'
time_1 = '10:00:00'
time_2 = '18:00:00'
timedl = '08:00:00'
tag_time = 'недоработка'
over_time = '00:00:00'
file_name = 'test_html_2.html'
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
file.write(line)
line = 3*space + table_tag_start + new_line
file.write(line)
line = 4*space + thead_tag_start + new_line
file.write(line)
line = 6*space + tr_tag_start + new_line
file.write(line)
for topic in topicsList:
    line = 8*space + th_tag_start + topic + th_tag_end + new_line
    file.write(line)
line = 6*space + tr_tag_end + new_line
file.write(line)
line = 4*space + thead_tag_end + new_line
file.write(line)


def gen_html_line(name,time_1,time_2,timedl,tag_time,over_time):
    """Функция генерирует html блок для таблицы по данным для каждого дня"""
    pass
line = 4*space + tbody_tag_star + new_line
file.write(line)
for i in range(15):
    line = 6*space + tr_tag_start + new_line
    file.write(line)
    line = 8*space + th_tag_start + name  + th_tag_end + new_line
    file.write(line)
    line = 8*space + th_tag_start + time_1 + th_tag_end + new_line
    file.write(line)
    line = 8*space + th_tag_start + time_2 + th_tag_end + new_line
    file.write(line)
    line = 8*space + th_tag_start + timedl + th_tag_end + new_line
    file.write(line)
    line = 8*space + th_tag_start + tag_time + th_tag_end + new_line
    file.write(line)
    line = 8*space + th_tag_start + over_time + th_tag_end + new_line
    file.write(line)
    line = 6*space + tr_tag_end + new_line
    file.write(line)

line = 4*space + tbody_tag_end + new_line
file.write(line)


line = 3*space + table_tag_end + new_line
file.write(line)
line = html_tag_end + new_line
file.write(line)

file.close()
print('Готово')