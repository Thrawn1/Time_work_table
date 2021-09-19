from os import sep


def id_employer(name_id_file = 'id_employer_new.dat'):
    """ Функция создания словаря id-фамилия из файла-хранилища
        Принимает имя файла - хранилища, возвращает - словарь. Ключ - id, значение - фамилия
        В процессе исполения печатает список на экран
    """
    file_id_name = open(name_id_file, 'r')
    id_employer_list = {}
    print('\n\n\n')
    for line in file_id_name:
        id = int(line[0:2])
        name = (line[2:].lstrip(' ')).rstrip('\n')
        id_employer_list[id] = name
    return id_employer_list
