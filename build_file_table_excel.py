import openpyxl
from id_employee import id_employee
def build_file_excel(time_table:dict,work_time_employees:dict,work_time_employees_restructuring:dict,working_hours_of_workers_sum_of_all_data:dict,total_salary_id:dict):

    wb = openpyxl.Workbook()
    list_employee = id_employee(type_data=2)
    ws = wb.active
    topicsList=['Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переботка', 'Зарплата']
    topicCounter=1
    for topic in topicsList:
        ws.cell(column = topicCounter, row = 1, value = topic)
        topicCounter+=1
    count = 2
    for date in time_table.keys():
        ws.cell(column = 2, row = count, value = date)
        for id in time_table[date]:
            ws.cell(column = 1,row = count, value=list_employee[1][id])
            ws.cell(column = 3,row = count, value=time_table[date][id][1].time())
            ws.cell(column = 4,row = count, value=time_table[date][id][0].time())
            if work_time_employees[date][id][2] == 'недоработка':
                ws.cell(column = 5,row = count, value=work_time_employees[date][id][1])
                write_value = '-' + str(work_time_employees[date][id][0])
                ws.cell(column = 6,row = count, value= write_value)
            else:
                ws.cell(column = 5,row = count, value=work_time_employees[date][id][1])
                ws.cell(column = 6,row = count, value=work_time_employees[date][id][0])
        count += 1
    wb.save("TEST_0000.xlsx")
    print('Файл сформирован')