from id_employee import id_employee
from analyze_data import definition_of_working_day
from datetime import timedelta

def calculation_of_excess_working_hours_per_day(time_table:dict):
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

def calculation_of_exceeding_working_hours_per_month(work_time_employees:dict):
    """Функция для подсчета всех часов переработки в месяц, по каждому сотруднику. Функция принимает словарь,
    в котором содержиться информация по рабочим дня и переработкам в конкретный день каждого сотрудника.
    Функция возврващает словарь, в котром для каждого сотрудника содержиться кортеж с количеством обычных рабочих дней,
    количество рабочих выходных, переработка в обычне рабочи дни и переработка в выходыне дни"""
    list_employees = id_employee(type_data=2)
    wages_of_employees = {}
    for cell_date in work_time_employees:
        tag_day=definition_of_working_day(cell_date)
        if tag_day[0] == 'work':
            for cell_id in work_time_employees[cell_date]:
                if not cell_id in wages_of_employees:
                    wages_of_employees[cell_id] = [[],[]] 
                    cell_time = (work_time_employees[cell_date][cell_id][0],work_time_employees[cell_date][cell_id][2],cell_date)
                    wages_of_employees[cell_id][0].append(cell_time)
                else:
                    cell_time = (work_time_employees[cell_date][cell_id][0],work_time_employees[cell_date][cell_id][2],cell_date)
                    wages_of_employees[cell_id][0].append(cell_time)
        else:
            for cell_id in work_time_employees[cell_date]:
                if not cell_id in wages_of_employees:
                    wages_of_employees[cell_id] = [[],[]] 
                    cell_time = (work_time_employees[cell_date][cell_id][0],work_time_employees[cell_date][cell_id][2],cell_date)
                    wages_of_employees[cell_id][1].append(cell_time)
                else:
                    cell_time = (work_time_employees[cell_date][cell_id][0],work_time_employees[cell_date][cell_id][2],cell_date)
                    wages_of_employees[cell_id][1].append(cell_time)
    print(wages_of_employees)

def calculation_wages():
    """Функция для рассчета заработной платы. Функция принимает структуру данных, содержаших данные по рабочим часам и переработке.
       Функция возвращает"""