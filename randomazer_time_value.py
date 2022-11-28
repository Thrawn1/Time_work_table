import random

def minutes_or_seconds_random():
    '''Функция возращает случайное значение минут или секунд  в диапазоне от 0 до 59'''
    return random.randint(0, 59)

def analize_input_time(time_value: str):
    """Функция принимает строку с временем и возвращает кортеж, в котором есть словарь с корректными значениями времени и список ключей времени с ошибками"""    
    data_time = {'H': None, 'M': None, 'S': None}
    error_time_value = []
    time_value = time_value.split()
    count = 0
    if len (time_value) <= 3:
        for i in time_value:
            if count == 0:
                data_time['H'] = i
                count += 1
            elif count == 1:
                data_time['M'] = i
                count += 1
            elif count == 2:
                data_time['S'] = i
                count += 1
    for key in data_time.keys():
        if data_time[key] == None:
            error_time_value.append(key)
    for key in data_time.keys():
        if data_time[key] != None:
            if data_time[key].isdigit() == True:
                if key == 'H':
                    if int(data_time[key]) > 23:
                        data_time[key] = None
                        error_time_value.append(key)
                elif key == 'M' or key == 'S':
                    if int(data_time[key]) > 59:
                        data_time[key] = None
                        error_time_value.append(key)
            else:
                data_time[key] = None
                error_time_value.append(key)
    return (data_time,error_time_value)

def updating_missing_values(data_time: dict, error_time_value: list):
    """Функция принимает словарь с временем и список ключей времени с ошибками, возвращает словарь с обновленными значениями времени"""
    for miss_key in error_time_value:
        if miss_key == 'H':
            while data_time['H'] == None:
                print('Нужно ввести правильное значение часов')
                hours_row = input('Введите значение часов: ')
                if hours_row.isdigit() == True:
                    if int(hours_row) <= 23:
                        data_time['H'] = hours_row
                    else:
                        print('Введено некорректное значение часов')
        elif miss_key == 'M' or miss_key == 'S':
            data_time[miss_key] = minutes_or_seconds_random()
    return data_time

def get_str_time(data_time: dict):
    """Функция принимает словарь с временем и возвращает строку с временем"""
    H = str(data_time['H'])
    M = str(data_time['M'])
    S = str(data_time['S'])
    if len(H) == 1:
        H = '0' + H
    if len(M) == 1:
        M = '0' + M
    if len(S) == 1:
        S = '0' + S
    str_time = H +' ' + M + ' ' + S
    return str_time


def time_data_generation(time_value: str):
    """Функция принимает строку с временем и возвращает строку с временем после проверки и обработки ошибок"""
    result_analize = analize_input_time(time_value)
    result_update = updating_missing_values(result_analize[0], result_analize[1])
    final_result = get_str_time(result_update)
    return final_result

