from id_employee import id_employee
from datetime import datetime,timedelta

def calculation_of_working_hours(time_table:dict):
    """Функция для рассчета отработанных часов и переработки. Функция принимает отредактированную структуру данных."""
    list_employee = id_employee(type_data=2)
    for cell_date in time_table:
        print(cell_date)
        for cell_id in time_table[cell_date]:
            if cell_id in list_employee[1]:
                print(cell_id)
                time_delta_raw = time_table[cell_date][cell_id][0] - time_table[cell_date][cell_id][1]
                time_delta_sec = time_delta_raw.total_seconds()
                print(time_delta_raw)
                work_time = timedelta(hours = 8)
                yyyy = time_delta_raw - work_time
                zzzz = timedelta(seconds = 1)
                uuu = abs(yyyy)
                if yyyy > zzzz:
                    print('TEST')
                    print(time_table[cell_date][cell_id][0])
                    print(time_table[cell_date][cell_id][1])
                    print(uuu)
                else:
                    print('TEST_22')
                    print(time_table[cell_date][cell_id][0])
                    print(time_table[cell_date][cell_id][1])
                    print(time_delta_raw)
                    print('-',uuu)

    

def calculation_wages(time_table:dict):
    """Функция для рассчета заработной платы. Функция принимает отредактированную структуру данных."""
    pass