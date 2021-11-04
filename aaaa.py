import datetime


def data_structure_conversion_for_json(data_structure:dict):
    '''Функция преобразует структуру данных таким обарзом, что бы в ней остались
    только поддерживаемые библиотекой json типы данных. Принимает структуру данных в виде словаря содержащую
    не поддерживаемые json типы данных, возвращает структуру, где неподдерживые типы преобразованы в srt
     '''
    data_array_json = {}
    for date_id in data_structure.keys():
        data_array_json[date_id] = {}
        for id in data_structure[date_id]:
            data_array_json[date_id][id] = []
            cell_0_str = data_structure[date_id][id][0].isoformat()
            cell_1_str = data_structure[date_id][id][1].isoformat()
            data_array_json[date_id][id].append(cell_0_str)
            data_array_json[date_id][id].append(cell_1_str)
            data_array_json[date_id][id].append(data_structure[date_id][id][2])
    return data_array_json


def json_structure_conversion_for_data(data_structure_json:dict):
    '''Функция преобразует структуру данных из json файла так, что бы типы данных сооветствовали приложению.
    Функция принимает структуру в виде словаря, возврщает струткру с не поддерживаемыми json типами '''
    data_array = {}
    for date_id in data_structure_json.keys():
        data_array[date_id] = {}
        for id in data_structure_json[date_id]:
            data_array[date_id][id] = []
            cell_0_str = datetime.datetime.fromisoformat(data_structure_json[date_id][id][0]) 
            cell_1_str = datetime.datetime.fromisoformat(data_structure_json[date_id][id][1])
            data_array[date_id][id].append(cell_0_str)
            data_array[date_id][id].append(cell_1_str)
            data_array[date_id][id].append(data_structure_json[date_id][id][2])
    return data_array

