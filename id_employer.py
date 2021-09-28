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
        name = (line[2:].lstrip(' ')).rstrip('\n')
        id = int(line[0:2])
        id_employer_list[id] = name
    return id_employer_list


def id_employer_new(name_id_file = 'id_employer_new_v2.dat',name_roles_file = 'roles_employer.dat' ):
    """ Функция создания словаря id-фамилия из файла-хранилища
        Принимает имя файла - хранилища, возвращает - словарь. Ключ - id, значение - фамилия
        В процессе исполения печатает список на экран
    """
#     file_id_name = open(name_id_file, 'r')
#     roules_file = open(name_roles_file,'r')
#     id_employer_list = []
#     roles_employer_list = {}
#     all_employer = {}
#     print('\n\n\n')
#     for line in roules_file:
#         rules_data = line.split(' ')
#         if len(rules_data) > 2:
#             rules_data[1] = rules_data[1] + ' ' + rules_data[len(rules_data)-1]
#         print(rules_data)
#         roles_employer_list[rules_data[0]] = rules_data[1].rstrip('\n')
#     for line in file_id_name:
#         data_id = line.split(' ')
#         id = int(data_id[0])
#         print('ID',id, sep = ':')
#         role = (data_id[1])
# #       for line_role in roules_file:
# #            if line_role == role:

#         print('ROLE',role, sep = ':')
#         name = (data_id[2].rstrip('\n'))
#         print('NAME',name, sep = ':')
# #        if role == 1
#         id_employer_list_dict[id] = name
#     print(id_employer_list_dict)
#     return id_employer_list


    id_employer_list = []
    number_roles = 0
    roles_file = open(name_roles_file,'r')
    for line in roles_file:
        number_roles += 1 
    print(number_roles)
    for role in range(1,(number_roles+1)):
        role_dict = []
        id_employer_list.append(role_dict)
    print(id_employer_list)
    file_id_name = open(name_id_file, 'r')
    for line in file_id_name:
        new_line = line.rstrip('\n')
        line_data=new_line.split(' ')
        role_id = line_data[1].rstrip(']')
        role_id = role_id.lstrip('[')
        line_data[1] = int(role_id)
        line_data[0] = int(line_data[0])
        #print(line_data)
        for i in range(0,(number_roles+1)):
            if line_data[1] == i:
         #       print(line_data[1])
          #      print(line_data[2])
                id_employer_data = {}
                id = line_data[0]
                name = line_data[2]
                id_employer_data[id] = name
                id_employer_list[i].append(id_employer_data)
    print(id_employer_list)