from determination_period import*
from datetime import datetime


def read_file_data(file_name_data, requested_year, requested_month):
    """ Функция служит для прочтения файла данных, его информация переводится в вид словаря.
        Возвращается словарь, содержащий все записи из файла с данными, 
        относящимся к нужному периоду - определенный месяца определенного года
        Функция принимает имя файла данных, год и месяц. 
        Если словарь пуст - скорее всего данные запрашиваются за декабрь, вывести поздравление с НГ и рекомендацию
        ввести вручную дату и месяц
    """
    file_data = open(file_name_data, 'r')
    list_month = []
    for line in file_data:
        arbiter = determination_period(line, requested_year, requested_month)
        if arbiter == True:
            list_month.append(line)
    if len(list_month) != 0:
        return list_month
    else:
        print('Данных нет!\n\n\tСкорее всего не корректно определился месяц, за который строится выборка. \n\nУкажите явно год и месяц')
