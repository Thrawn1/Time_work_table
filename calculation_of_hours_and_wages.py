import os
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
                if len(time_table[cell_date][cell_id]) != 3:
                    hours_worked = time_table[cell_date][cell_id][0] - time_table[cell_date][cell_id][1]
                    working_day_duration = timedelta(hours = 8)
                    delta_time = hours_worked - working_day_duration
                    abs_delta_time = abs(delta_time)
                    print(cell_date)
                    print(cell_id)
                    print(delta_time)
                    if delta_time > timedelta(seconds = 0):
                        tag = 'переработка'
                    else:
                        tag = 'недоработка'
                    work_time_employees[cell_date][cell_id] = (abs_delta_time,hours_worked,tag)
                else:
                    time_plug = timedelta(seconds = 0)
                    tag = 'отпуск'
                    work_time_employees[cell_date][cell_id] = (time_plug,time_plug,tag)
    print(work_time_employees)
    return work_time_employees

def calculation_of_exceeding_working_hours_per_month(work_time_employees:dict):
    """Функция для подсчета всех часов переработки в месяц, по каждому сотруднику. Функция принимает словарь,
    в котором содержиться информация по рабочим дня и переработкам в конкретный день каждого сотрудника.
    Функция возврващает словарь, в котром для каждого сотрудника содержиться кортеж с количеством обычных рабочих дней,
    количество рабочих выходных, переработка в обычне рабочи дни и переработка в выходные дни"""
    list_employees = id_employee(type_data=2)
    work_time_employees_restructuring = {}
    for cell_date in work_time_employees:
        tag_day=definition_of_working_day(cell_date)
        for cell_id in work_time_employees[cell_date]:
            cell_time = (work_time_employees[cell_date][cell_id][0],work_time_employees[cell_date][cell_id][2],cell_date)
            if tag_day[0] == 'work':
                if not cell_id in work_time_employees_restructuring:
                    work_time_employees_restructuring[cell_id] = [[],[]] 
                    work_time_employees_restructuring[cell_id][0].append(cell_time)
                else:
                    work_time_employees_restructuring[cell_id][0].append(cell_time)
            else:
                if not cell_id in work_time_employees_restructuring:
                    work_time_employees_restructuring[cell_id] = [[],[]] 
                    work_time_employees_restructuring[cell_id][1].append(cell_time)
                else:
                    work_time_employees_restructuring[cell_id][1].append(cell_time)
    working_hours_of_workers_sum_of_all_data = {}
    for id in work_time_employees_restructuring.keys():
        total_work_days = len(work_time_employees_restructuring[id][0])
        total_holiday_days = len(work_time_employees_restructuring[id][1])
        overwork = timedelta(seconds=0)
        for delta_time_day in work_time_employees_restructuring[id][0]:
            if delta_time_day[1] == 'переработка':
                overwork += delta_time_day[0]
            else:
                overwork -= delta_time_day[0]
        overwork_holiday = timedelta(seconds = 0)
        for delta_time_day in work_time_employees_restructuring[id][1]:
                overwork_holiday += delta_time_day[0]
        cell_work_data = ((total_work_days,overwork),(total_holiday_days,overwork_holiday))
        working_hours_of_workers_sum_of_all_data[id] = cell_work_data
    print(working_hours_of_workers_sum_of_all_data)
    return working_hours_of_workers_sum_of_all_data
        
def calculation_wages(working_hours_of_workers_sum_of_all_data:dict):
    """Функция для рассчета заработной платы. Функция принимает структуру данных, содержаших данные по рабочим часам и переработке.
       Функция возвращает"""
    wege_rates_name_file = 'wage_rates.dat'
    wege_rates_file = os.path.join("data",wege_rates_name_file)
    file_wage_rates = open(wege_rates_file, 'r',encoding='utf-8')
    money_rate_all_employes = {}
    for line in file_wage_rates:
        new_line = line.rstrip('\n')
        data = new_line.split(' ')
        secret_key = 3.14
        raw_data = data[1].lstrip('[').rstrip(']')
        raw_data_rate_encrypted = raw_data.split('.')
        raw_data_rate_temporarily = raw_data_rate_encrypted[1] + '.' + raw_data_rate_encrypted[0]
        rate = round(float(raw_data_rate_temporarily)*secret_key)
        money_rate_all_employes[int(data[0])] = rate
    for id in working_hours_of_workers_sum_of_all_data.keys():
        money_rate_employee = money_rate_all_employes[id]
        work_shift_time_in_seconds = 8*3600
        rate_per_second= money_rate_employee/work_shift_time_in_seconds
        salary_for_weekdays =money_rate_employee*working_hours_of_workers_sum_of_all_data[id][0][0] + rate_per_second * working_hours_of_workers_sum_of_all_data[id][0][1].total_seconds()
        salary_for_weekends = money_rate_employee*working_hours_of_workers_sum_of_all_data[id][1][0] + rate_per_second * working_hours_of_workers_sum_of_all_data[id][1][1].total_seconds()
        total_salary = salary_for_weekdays + salary_for_weekends
        
        print(id)
        print(round(total_salary,2))