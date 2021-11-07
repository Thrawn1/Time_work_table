import openpyxl
from datetime import time
def build_file_excel(time_table:dict,work_time_employees_restructuring:dict,working_hours_of_workers_sum_of_all_data:dict,total_salary_id:dict):

    wb = openpyxl.Workbook()
    ws = wb.active
    topicsList=['Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переботка', 'Примечания']
    topicCounter=1
    for topic in topicsList:
        ws.cell(column = topicCounter, row = 1, value = topic)
        topicCounter+=1
    count = 2
    for date in time_table.keys():
        ws.cell(column = 2, row = count, value = date)
        for id in time_table[date]:
            ws.cell(column = 3,row = count, value=time_table[date][id][1].time())
            ws.cell(column = 4,row = count, value=time_table[date][id][0].time())
        count += 1
    wb.save("TEST_0000.xlsx")
    print('Файл сформирован')