from gen_html import gen_html_file

test_day_1 = {'family':'Иванов','date':'2021-12-24','time_begin':'09:00:12','time_end':'19:00:00','delta_time':'10:00:00','tag_overtime':'Переработка','overtime':'02:00:00','tag_day':'Рабочий день'}
test_day_2 = {'family':'Иванов','date':'2021-12-23','time_begin':'08:00:12','time_end':'18:00:00','delta_time':'10:00:00','tag_overtime':'Переработка','overtime':'02:00:00','tag_day':'Отпуск'}

test_list_days = []
test_list_days.append(test_day_1)
test_list_days.append(test_day_2)

test_month = {'family':'Иванов','all_work_weekdays':22,'weekdays_overtime':'55:44:12','work_weekend':4,'overtime_weekend':'00:30:12','vacation':2,'salary':44343.32}

file_name = 'test_html_Иванов.html'

data_emp =(file_name,test_list_days,test_month)
gen_html_file(data_emp)