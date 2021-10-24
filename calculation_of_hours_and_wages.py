from id_employee import id_employee
from datetime import datetime,timedelta

def calculation_of_working_hours(time_table:dict):
    """Функция для рассчета отработанных часов и переработки. Функция принимает отредактированную структуру данных.
       Функция возвращает структуру данных, содержащих рабочие часы за дату, переработку или недоработку и метку переработка или недоработка"""
    list_employee = id_employee(type_data=2)
    work_time_employees = {}
    for cell_date in time_table:
        work_time_employees[cell_date] = {}
        for cell_id in time_table[cell_date]:
            if cell_id in list_employee[1]:
                hours_worked = time_table[cell_date][cell_id][0] - time_table[cell_date][cell_id][1]
                working_day_duration = timedelta(hours = 8)
                delta_time = hours_worked - working_day_duration
                abs_delta_time = abs(delta_time)
                if delta_time > timedelta(seconds = 0):
                    tag = 'переработка'
                else:
                    tag = 'недоработка'
                work_time_employees[cell_date][cell_id] = (abs_delta_time,hours_worked,tag)
    return work_time_employees

    

def calculation_wages(work_time_employees:dict):
    """Функция для рассчета заработной платы. Функция принимает структуру данных, содержаших данные по рабочим часам и переработке.
       Функция возвращает"""
    pass
    list_employees = id_employee(type_data=2)
    wages_of_employees = {}
    for cell_date in work_time_employees:
        for cell_id in wages_of_employees[cell_date]:
            if not cell_id in wages_of_employees:
                wages_of_employees[cell_id] = [] 
                cell_time = (wages_of_employees[cell_date][cell_id][0],wages_of_employees[cell_date][cell_id][2])
                wages_of_employees[cell_id].append(cell_time)
            else:
                for cell_id in wages_of_employees[cell_date]:
                    cell_time = (wages_of_employees[cell_date][cell_id][0],wages_of_employees[cell_date][cell_id][2])
                    wages_of_employees[cell_id].append(cell_time)
    print(wages_of_employees)