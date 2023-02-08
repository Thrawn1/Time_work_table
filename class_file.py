from os import path

class read_file_row_data():
    """Данный метод необходим, что бы открыть файл с датчика, прочитать данные и сформировать список с данными за месяц. 
    Данные об отметке хранятся как строка.Данный объект хранит имя файла с данными и путь к файлу."""
    def __init__(self):
        self.file_name = '1_attlog.dat'
        self.directory = 'data' 
        self.file_data = []
        self.requset_year = 0
        self.requset_month = 0
    def search_work_period(self):
        """Данный метод ищет в файле данные за определенный месяц и год. Данные хранятся в списке file_data"""
        with open(path.join(self.directory,self.file_name)) as file:
            for line in file:
                if self.detect_data(line[10:17]):
                    self.file_data.append(line)
    def detect_data(self,row_date:str):
        """Данный метод ищет в списке file_data данные за определенный месяц и год. Данные хранятся в списке file_data"""
        row_year = int(row_date[0:4])
        row_month = int(row_date[5:])
        if row_year == self.requset_year and row_month == self.requset_month:
            return True


class File_reader():
    pass

class Data_structure_builder():
    pass

class Validator():
    pass

class Editor_structure():
    pass

class Сalculator():
    pass

class Builder_result_file():
    pass



class Excel_table():
    """Данный класс хранит информацию для построения таблицы в excel,имя файла, путь до файла. Имеет метод построения excel файла"""
    pass

class Html_file():
    """Данный класс хранит информацию для построения html файла, имя файла, путь до файла. Имеет метод построения html файла"""
    pass