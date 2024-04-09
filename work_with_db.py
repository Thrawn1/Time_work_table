from os.path import isfile
from toml import load

def generate_toml(name_file:str) -> None:
    pass


def check_data_toml(name_file:str) -> bool:
    if isfile(name_file):
        with open(name_file, 'r') as file:
            data = load(file)
            if len(data) == 0:
                return False
            return True
    else:
        generate_toml(name_file)
        print(f"Файл '{name_file}' не найден. Создан новый дефолтный файл.")
        return False
    
