import random


def str_format(number:str):
    if len(number) == 1:
        number_str = '0' + number
        return number_str
    else:
        return number

def random_line(file_for_data):
    list_id = [1,2,3,4,5,6,7,8,9,10,27]
    list_year = [2015,2016,2017,2018,2019,2021]
    list_month = [1,2,4,5,6,7,8,9,10,11,12]
    tmp_1 = 1
    tmp_2 = 255
    tmp_3 = 0
    count = 12
    while count != 0:
        id = str(random.choice(list_id))
        year_str = str(random.choice(list_year))
        month_str = str_format(str(random.choice(list_month)))
        day_str = str_format(str(random.randint(1,31)))
        str_hour = str_format(str(random.randint(6,22)))
        str_minute = str_format(str(random.randint(0,59)))
        str_seconds =  str_format(str(random.randint(0,59)))
        data = year_str + '-' + month_str + '-' + day_str
        time = str_hour + ':' + str_minute + ':' + str_seconds
        end_line = '	' + str(tmp_1) + '	' + str(tmp_2) + '	' + str(tmp_1) + '	' + str(tmp_3)
        line = '        '+ id + '	' + data + ' ' + time  + end_line +'\n'
        file_for_data.write(line)
        count -= 1
    print('Внесены 11 строк!')
name_file_for_data = 'test_file_data_part_1.dat'
name_file_for_data_gen = 'test_file_data_part_3.dat'
file_for_data = open(name_file_for_data,'w',encoding='utf-8')
random_line(file_for_data)
strict_data ="""        8	2020-11-01 05:55:00	1	255	1	0
        4	2018-12-31 06:30:00	1	255	1	0
        5	2021-03-01 06:45:15	1	255	1	0
        6	2021-03-01 07:00:00	1	255	1	0
        9	2021-03-01 07:30:10	1	255	1	0
        3	2021-03-01 08:00:00	1	255	1	0
        5	2021-03-01 14:00:00	1	255	1	0
        6	2021-03-01 15:00:00	1	255	1	0
        9	2021-03-01 16:00:00	1	255	1	0
        4	2021-03-01 17:00:00	1	255	1	0
        3	2021-03-01 18:00:00	1	255	1	0
"""

def generation_line(file_for_data):
    #list_id = [1,2,3,4,5,6,7,8,9,10,27]
    list_id = [3,4,5,6,9,]
    year = 2021
    month = 3
    tmp_1 = 1
    tmp_2 = 255
    tmp_3 = 0
    id = str(3)
    year_str = str(year)
    month_str = str_format(str(month))
    for id_int in list_id:
        id = str(id_int)
        for num_day in range(1,32):
            day_str = str_format(str(num_day))
            for i in range(2):
                str_hour = str_format(str(random.randint(6,22)))
                str_minute = str_format(str(random.randint(0,59)))
                str_seconds =  str_format(str(random.randint(0,59)))
                data = year_str + '-' + month_str + '-' + day_str
                time = str_hour + ':' + str_minute + ':' + str_seconds
                end_line = '	' + str(tmp_1) + '	' + str(tmp_2) + '	' + str(tmp_1) + '	' + str(tmp_3)
                line = '        '+ id + '	' + data + ' ' + time  + end_line +'\n'
                file_for_data.write(line)
    print('Сгенерирован файл!')

def generation_file_all_id(file_for_data):
    #list_id = [1,2,3,4,5,6,7,8,9,10,27]
    #list_id = [3,4,5,6,9]
    list_id = [3]
    year = 2021
    month = 3
    tmp_1 = 1
    tmp_2 = 255
    tmp_3 = 0
    id = str(3)
    year_str = str(year)
    month_str = str_format(str(month))
    for num_day in range(1,32):
        for id_int in list_id:
            id = str(id_int)
            end_line = '	' + str(tmp_1) + '	' + str(tmp_2) + '	' + str(tmp_1) + '	' + str(tmp_3)
            day_str = str_format(str(num_day))
            data = year_str + '-' + month_str + '-' + day_str
            str_hour_start = str_format(str(random.randint(5,10)))
            str_minute = str_format(str(random.randint(0,59)))
            str_seconds =  str_format(str(random.randint(0,59)))
            time = str_hour_start + ':' + str_minute + ':' + str_seconds
            line = '        '+ id + '	' + data + ' ' + time  + end_line +'\n'
            file_for_data.write(line)
            str_hour_end = str_format(str(random.randint(13,23)))
            str_minute = str_format(str(random.randint(0,59)))
            str_seconds =  str_format(str(random.randint(0,59)))
            time = str_hour_end + ':' + str_minute + ':' + str_seconds
            line = '        '+ id + '	' + data + ' ' + time  + end_line +'\n'
            file_for_data.write(line)
    print('Сгенерирован файл!')




file_for_data.write(strict_data)
random_line(file_for_data)
file_for_data.close()
file_for_data_gen = open(name_file_for_data_gen,'w',encoding='utf-8')
generation_file_all_id(file_for_data_gen)
file_for_data_gen.close()
print('ALL!')