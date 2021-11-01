import openpyxl

def build_file_excel(time_table:dict,work_time_employees_restructuring:dict,working_hours_of_workers_sum_of_all_data:dict,total_salary_id:dict):

    wb = openpyxl.Workbook()
    ws = wb.active
    topicsList=['Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переботка', 'Примечания']
    topicCounter=1
    for topic in topicsList:
        ws.cell(column = topicCounter, row = 1, value = topic)
        topicCounter+=1
    for dt in daterange(a, b, inclusive=True):#Проверить отсюда
        date = dt.strftime("%Y-%m-%d")
        if date in full_info.keys():
            for i in full_info[date].keys():
                name = replace_name(i)
                rec_name = ws.cell(column = 1, row = count, value = name)
                rec_date = ws.cell(column = 2, row = count, value = date)
                if name != 'Рощин':
                    value_for_record = datetime.time(full_info[date][i][0])
                    rec_time_start = ws.cell(column = 3, row = count, value = value_for_record) #3
                    value_for_record = datetime.time(full_info[date][i][1])
                    rec_time_end = ws.cell(column = 4, row = count, value = value_for_record) #4
                    rec_delta = ws.cell(column = 5, row = count, value = full_info[date][i][2])
                    if full_info[date][i][3] >= 0:
                            if full_info[date][i][7]!= 'auto':
                                    info_auto = 'Ручной ввод'
                                    rec_recycling = ws.cell(column = 7, row = count, value = info_auto)
                                    rec_recycling = ws.cell(column = 6, row = count, value = full_info[date][i][6])
                            else:
                                info_auto = 'Автоматика'
                                rec_recycling = ws.cell(column = 7, row = count, value = info_auto)
                                rec_recycling = ws.cell(column = 6, row = count, value = full_info[date][i][6])
                    else:
                            if full_info[date][i][7]!= 'auto':
                                    info_auto = 'Ручной ввод'
                                    info_1 = '- ' + str(full_info[date][i][6])
                                    rec_recycling = ws.cell(column = 7, row = count, value = info_auto)
                                    rec_recycling = ws.cell(column = 6, row = count, value = info_1)
                            else:
                                info_auto = 'Автоматика'
                                info_1 = '- ' + str(full_info[date][i][6])
                                rec_recycling = ws.cell(column = 7, row = count, value = info_auto)
                                rec_recycling = ws.cell(column = 6, row = count, value = info_1)
                else:
                    value_for_record = datetime.time(full_info[date][i][0])
                    rec_time_start = ws.cell(column = 3, row = count, value = value_for_record)
                count += 1
    wb.save("Январь_2019.xlsx")
    print('Файл сформирован')