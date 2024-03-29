from build_data_array import build_data_array, read_file_data
from os import remove
from os.path import exists
from pickle import load
from id_employee import id_employee, detection_id_employee_in_data_array,verification_of_identity_for_permission_to_calculate
from analyze_data import analyze_data_for_print, analyze_data_for_edit, month_name_for_print
from calculation_of_hours_and_wages import calculation_of_exceeding_working_hours_per_month, calculation_of_excess_working_hours_per_day, calculation_wages
from build_file_table_excel import build_file_excel
from html_files_generation import html_builder, build_data_total_for_month_for_employee


def main():
    """Главня функция
    """

    file_name = '1_attlog.dat'
    print('\n\t\tСистема расчета заработной платы и учета рабочего времени работников\n\n')
    print('Если вы хотите сформировать файл с зарплатой - введите секретный ключ. Если нужен файл без зарплаты - введите t\n\n\n')
    key = input('Секретный ключ: ')
    if key == 't':
        secret_key_raw = 0
    else:
        if key.isdigit() == True:
            if len(key) > 2 and len(key) < 123:
                secret_key_raw = int(key)
            else:
                secret_key_raw = 0
        else:
            secret_key_raw = 0
    flag = exists('temporary.pickle')
    if flag == True:
        with open('temporary.pickle', 'rb') as tmp_file:
            data_array = load(tmp_file)
        list_dates = tuple(data_array.keys())
        requested_year = int(list_dates[0][:4])
        requested_month = int(list_dates[0][5:7])
    else:
        requested_year = int(input('Введите год:'))
        requested_month = int(input('Введите месяц:'))
        list_data = read_file_data(file_name, requested_year, requested_month)
        data_array = build_data_array(list_data)
        name_month_for_print = month_name_for_print(requested_month)
        print(name_month_for_print, ' ', requested_year, ' ', 'год')
    id_list = id_employee()
    for id in id_list:
        analyze_data_for_print(data_array, id, requested_year, requested_month)
    for id in id_list:
        analyze_data_for_print(data_array, id, requested_year, requested_month)
        analyze_data_for_edit(data_array, id, requested_year, requested_month)
    for id in id_list:
        analyze_data_for_print(data_array, id, requested_year, requested_month)
    work_time_employees = calculation_of_excess_working_hours_per_day(
        data_array)
    work_time_employees_restructuring = calculation_of_exceeding_working_hours_per_month(
        work_time_employees)
    total_salary = calculation_wages(
        work_time_employees_restructuring[0], secret_key_raw)
    build_file_excel(data_array, work_time_employees,
                     work_time_employees_restructuring[0], total_salary)
    employees_who_worked_for_month = detection_id_employee_in_data_array(
        data_array)
    for id in employees_who_worked_for_month:
        if verification_of_identity_for_permission_to_calculate(id) == True:
            html_builder(id, all_data_dates_and_marks=data_array, data_work_time_all_employees=work_time_employees,
                        all_data_per_month_employees=work_time_employees_restructuring[0], total_salary_employees=total_salary)
    for id in employees_who_worked_for_month:
        if verification_of_identity_for_permission_to_calculate(id) == True:
            data_id = build_data_total_for_month_for_employee(
                id=id, all_data_per_month_employees=work_time_employees_restructuring[0], total_salary_employees=total_salary)
            print('--------------------------------------------------------------------------------------------------------------------------------------------')
            print('\nФамилия работника:  ', data_id['family'])
            print('\n\n\t\t ВСЕГО ЗА МЕСЯЦ:')
            print('\n\n\t')
            print('\n\t\tБудние рабочие дни за месяц:',
                data_id['all_work_weekdays'])
            print('\t\t\t--------------------------')
            print('\n\t\tПереработки за будние рабочие дни в месяце:',
                data_id['weekdays_overtime'])
            print('\t\t\t--------------------------')
            print('\n\t\tРабочие выходные дни за месяц:', data_id['work_weekend'])
            print('\t\t\t--------------------------')
            print('\n\t\tПереработки за рабочие выходные дни в месяце:',
                data_id['overtime_weekend'])
            print('\t\t\t--------------------------')
            print('\n\t\tКоличество дней отпуска:', data_id['vacation'])
            print('\t\t\t--------------------------')
            print('\n\t\tЗарплата(учитвая молоко, но без премий):',
                data_id['salary_whith_milk'])
            print('\t\t\t--------------------------')
    try:
        remove('temporary.pickle')
    except:
        pass


main()
