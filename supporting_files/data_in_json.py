from datetime import datetime


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
            id_int = int(id)
            data_array[date_id][id_int] = []
            cell_0_str = datetime.fromisoformat(data_structure_json[date_id][id][0]) 
            cell_1_str = datetime.fromisoformat(data_structure_json[date_id][id][1])
            data_array[date_id][id_int].append(cell_0_str)
            data_array[date_id][id_int].append(cell_1_str)
            data_array[date_id][id_int].append(data_structure_json[date_id][id][2])
    return data_array

def data_structure_conversion_for_json_for_search_miss_mark(data_structure:dict):
    '''Функция преобразует структуру данных возвращаемую поиском пропущенных меток таким обарзом, что бы в ней остались
    только поддерживаемые библиотекой json типы данных. Принимает структуру данных в виде списка, содеращего другие списки с результами
     в которых есть не поддерживаемые json типы данных, возвращает структуру, где неподдерживые типы преобразованы в srt
     '''
    data_array_json = []
    for cell_obj in data_structure:
        cell = []
        date_struct_str = cell_obj[1].isoformat()
        cell.append(cell_obj[0])
        cell.append(date_struct_str)
        data_array_json.append(cell)

    return data_array_json


def json_structure_conversion_for_data__for_search_miss_mark(data_structure_json:dict):
    '''Функция преобразует структуру данных из json файла так, что бы типы данных сооветствовали возвращаемым из поиска пропущеных меток.
    Функция принимает структуру в виде словаря, возврщает струткру с не поддерживаемыми json типами '''
    data_array = []
    for cell_str in data_structure_json:
        cell = []
        data_struct_obj = datetime.fromisoformat(cell_str[1])
        cell.append(cell_str[0])
        cell.append(data_struct_obj)
        data_array.append(cell)

    return data_array
