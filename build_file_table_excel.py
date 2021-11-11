import openpyxl
from openpyxl.styles import Border, Side
from id_employee import id_employee




def build_file_excel(time_table:dict,work_time_employees:dict,working_hours_of_workers_sum_of_all_data:dict,total_salary_id:dict):

    wb = openpyxl.Workbook()
    list_employee = id_employee(type_data=2)
    ws = wb.active
    ws.column_dimensions['A'].width = 16.44
    ws.column_dimensions['B'].width = 13.48
    ws.column_dimensions['C'].width = 14.3
    ws.column_dimensions['D'].width = 16.43
    ws.column_dimensions['E'].width = 14.3
    ws.column_dimensions['F'].width = 12.26
    ws.column_dimensions['G'].width = 13.23
    ws.column_dimensions['H'].width = 16.44
    ws.column_dimensions['I'].width = 23.21
    ws.column_dimensions['J'].width = 12.46
    ws.column_dimensions['K'].width = 17.93
    ws.column_dimensions['L'].width = 21.96
    ws.column_dimensions['M'].width = 28.09
    ws.column_dimensions['N'].width = 10.27 
    border_style='thick'
    color='FF000000'
    top = Side(border_style,color)
    right = Side(border_style,color)
    bottom = Side(border_style,color)
    left = Side(border_style,color)
    #ws.cell(1,1).border = Border(left,right,top,bottom)
    topicsList=['Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода', 'Общее время работы', 'Переработка', 'Метка']
    topicCounter=1
    for topic in topicsList:
        ws.cell(column = topicCounter, row = 1, value = topic)
        ws.cell(1,topicCounter).border = Border(left,right,top,bottom)
        topicCounter+=1
    count = 2
    list_date = []
    for date in time_table.keys():
        list_date.append(date)
    list_date.sort()
    for date in list_date:
        ws.cell(column = 2, row = count, value = date)
        ws.cell(count,2).border = Border(left,right,top,bottom)
        for id in time_table[date]:
            ws.cell(column = 1,row = count, value=list_employee[1][id])
            ws.cell(count,1).border = Border(left,right,top,bottom)
            if time_table[date][id][2] != 'vacation':
                ws.cell(column = 3,row = count, value=time_table[date][id][1].time())
                ws.cell(count,3).border = Border(left,right,top,bottom)
                ws.cell(column = 4,row = count, value=time_table[date][id][0].time())
                ws.cell(count,4).border = Border(left,right,top,bottom)
                ws.cell(column = 5,row = count, value=work_time_employees[date][id][1])
                ws.cell(count,5).border = Border(left,right,top,bottom)
                ws.cell(column = 6,row = count, value=work_time_employees[date][id][0])
                ws.cell(count,6).border = Border(left,right,top,bottom)
                if work_time_employees[date][id][2] == 'недоработка':
                    ws.cell(column = 7,row = count, value=work_time_employees[date][id][2])
                    ws.cell(count,7).border = Border(left,right,top,bottom)
                else:
                    ws.cell(column = 7,row = count, value=work_time_employees[date][id][2])
                    ws.cell(count,7).border = Border(left,right,top,bottom)
            else:
                ws.cell(column = 3,row = count, value='Отпуск')
                for cell in range(3,8):
                    ws.cell(count,cell).border = Border(left,right,top,bottom)
        count += 1
    count += 3
    topicsList=['Фамилия', 'Отработано будних день', 'Переработка', 'Рабочих выходных','Переработка выходных', 'Количество дней дней отпуска', 'Зарплата']
    topicCounter=8
    for topic in topicsList:
        ws.cell(column = topicCounter, row = count, value = topic)
        topicCounter+=1
    count += 1
    for id in working_hours_of_workers_sum_of_all_data.keys():
        ws.cell(column = 8,row = count, value=list_employee[1][id])
        number_worked_day = working_hours_of_workers_sum_of_all_data[id][0][0]
        ws.cell(column = 9,row = count, value=number_worked_day)
        overwork_hours_weekday = working_hours_of_workers_sum_of_all_data[id][0][1]
        ws.cell(column = 10,row = count, value=overwork_hours_weekday)
        number_holiday_day = working_hours_of_workers_sum_of_all_data[id][1][0]
        ws.cell(column = 11,row = count, value=number_holiday_day)
        overwork_hours_weekend = number_holiday_day = working_hours_of_workers_sum_of_all_data[id][1][1]
        ws.cell(column = 12,row = count, value=overwork_hours_weekend)
        ws.cell(column = 13,row = count, value=working_hours_of_workers_sum_of_all_data[id][2])
        ws.cell(column = 14,row = count, value=total_salary_id[id])
        count += 1
    wb.save("TEST_0000.xlsx")
    print('Файл сформирован')