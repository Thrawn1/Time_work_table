# Имя входного файла
input_filename = '1_attlog.dat'

# Имена выходных файлов
output_special = 'ids_16_17.dat'
output_others = 'ids_others.dat'

# Целевые ID для отделения
target_ids = {'16', '17'}

try:
    with open(input_filename, 'r', encoding='utf-8') as infile, \
         open(output_special, 'w', encoding='utf-8') as f_special, \
         open(output_others, 'w', encoding='utf-8') as f_others:

        print(f"Обработка файла {input_filename}...")
        
        count_special = 0
        count_others = 0

        for line in infile:
            # Убираем лишние пробелы по краям
            clean_line = line.strip()
            
            # Пропускаем пустые строки
            if not clean_line:
                continue

            # Разбиваем строку по пробелам/табуляции, чтобы получить первый элемент (ID)
            parts = clean_line.split()
            
            if not parts:
                continue
                
            user_id = parts[0]

            # Проверяем ID и записываем в нужный файл
            if user_id in target_ids:
                f_special.write(line)
                count_special += 1
            else:
                f_others.write(line)
                count_others += 1

    print("Готово!")
    print(f"Записей с ID 16 и 17: {count_special} -> сохранено в {output_special}")
    print(f"Остальных записей: {count_others} -> сохранено в {output_others}")

except FileNotFoundError:
    print(f"Ошибка: Файл {input_filename} не найден. Убедитесь, что скрипт и файл находятся в одной папке.")
except Exception as e:
    print(f"Произошла ошибка: {e}")