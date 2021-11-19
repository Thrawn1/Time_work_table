

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
file_name = 'test_html.html'
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
line = 3*space + table_tag_end + new_line
file.write(line)
line = html_tag_end + new_line
file.write(line)

file.close()
print('Готово')