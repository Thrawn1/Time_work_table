from file_read_backwards import FileReadBackwards
from datetime import datetime, timedelta

def parse_period_backwards(filename, target_month, target_year):
    """
    Читает файл с конца до достижения нужного периода
    """
    target_date_start = datetime(target_year, target_month, 1)
    # Берем с запасом - предыдущий месяц для контекста
    cutoff_date = target_date_start - timedelta(days=30)
    
    records = []
    
    with FileReadBackwards(filename, encoding="utf-8") as frb:
        for line_num, line in enumerate(frb, 1):
            try:
                parts = line.strip().split('\t')
                employee_id = parts[0].strip()
                date_time_str = parts[1].strip()                
                # Парсим дату
                record_date = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M")  # или ваш формат

                # Если дошли до старых данных - останавливаемся
                if record_date < cutoff_date:
                    print(f"Reached cutoff date. Stopped at line {line_num}")
                    break
                
                records.append({
                    'employee_id': employee_id,
                    'time': time_str,
                    'date': record_date,
                    'raw_line': line
                })
                
            except Exception as e:
                raise ValueError(f"Invalid format at line {line_num}: {line.strip()}")
    
    # Возвращаем в хронологическом порядке
    return list(reversed(records))


file = "1_attlog.dat"

target_month = 10  # Октябрь
target_year = 2023  # 2023 год

records = parse_period_backwards(file, target_month, target_year)
for record in records:
    print(f"Employee ID: {record['employee_id']}, Time: {record['time']}, Date: {record['date'].strftime('%d.%m.%Y')}, Raw Line: {record['raw_line'].strip()}")