import os

def id_employee(name_id_file_relative = 'id_employer_new.dat',name_roles_file_relative = 'roles_employer.dat', type_data = 1):
    """ Функция создания структуры данных(список списков, состящих из словарей id-фамилия)
        или создания списка словарей(id - фамилия) для необходимых случаев. В случае использования структуры
        используется ролевая модель. Функция принимает имена файлов - список работников, их роль и id и файл описвающий роли и id - роли.
        Так же принимает параметр, который определяет, что функция возвращает - простой список, или структуру по ролям.
    """
    name_id_file = os.path.join("data",name_id_file_relative)
    name_roles_file = os.path.join("data",name_roles_file_relative)
    if type_data == 1:
        file_id_name = open(name_id_file, 'r',encoding='utf-8')
        id_employee_list = {}
        for line in file_id_name:
            new_line = line.rstrip('\n')
            line_data=new_line.split(' ')
            id  = int(line_data[0])
            name = line_data[2]
            id_employee_list[id] = name
        return id_employee_list
    else:
        id_employee_list = []
        number_roles = 0
        roles_file = open(name_roles_file,'r',encoding='utf-8')
        for line in roles_file:
            number_roles += 1 
        for role in range(1,(number_roles+1)):
            role_dict = {}
            id_employee_list.append(role_dict)
        file_id_name = open(name_id_file, 'r',encoding='utf-8')
        for line in file_id_name:
            new_line = line.rstrip('\n')
            line_data=new_line.split(' ')
            role_id = line_data[1].rstrip(']')
            role_id = role_id.lstrip('[')
            line_data[1] = int(role_id)
            line_data[0] = int(line_data[0])
            for i in range(0,(number_roles+1)):
                if line_data[1] == i:
                    id = line_data[0]
                    name = line_data[2]
                    employee_dict_role = id_employee_list[i]
                    employee_dict_role[id] = name
        return id_employee_list