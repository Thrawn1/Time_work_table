from db_manager import DBManager

def post_data_employee(db_path:str):

    db_manager = DBManager(db_path)

    while True:
        print("\nМеню:")
        print("1. Добавить сотрудника")
        print("2. Показать всех сотрудников")
        print("0. Выход")
        
        choice = input("Введите номер действия: ").strip()

        if choice == "1":
            # Запрашиваем данные о сотруднике
            try:
                employee_id = int(input("Введите ID сотрудника: ").strip())
            except ValueError:
                print("Ошибка: ID должен быть числом.")
                continue

            first_name = input("Введите имя: ").strip()
            last_name = input("Введите фамилию: ").strip()
            role = input("Введите должность: ").strip()

            # Для числовых значений делаем проверку на корректность ввода
            try:
                hourly_rate = float(input("Введите почасовую ставку: ").strip())
            except ValueError:
                print("Ошибка: почасовая ставка должна быть числом.")
                continue
            
            try:
                # Коэффициент необязательный – если не хотите вводить, можете оставить по умолчанию 1.0
                role_coefficient_input = input("Введите коэффициент (по умолчанию 1.0): ").strip()
                if role_coefficient_input == "":
                    role_coefficient = 1.0
                else:
                    role_coefficient = float(role_coefficient_input)
            except ValueError:
                print("Ошибка: коэффициент должен быть числом.")
                continue
            
            # Добавляем сотрудника в БД
            db_manager.add_employee(
                employee_id,
                first_name,
                last_name,
                role,
                hourly_rate,
                role_coefficient
            )
            print("Сотрудник добавлен (или проигнорирован, если такой ID уже существует).")

        elif choice == "2":
            # Получаем список всех сотрудников
            employees = db_manager.get_all_employees()
            if not employees:
                print("В таблице нет сотрудников.")
            else:
                print("Список сотрудников:")
                for emp in employees:
                    print(f"ID: {emp['employee_id']} | "
                          f"{emp['first_name']} {emp['last_name']}, "
                          f"Должность: {emp['role']}, "
                          f"Ставка: {emp['hourly_rate']}, "
                          f"Коэффициент: {emp['role_coefficient']}")

        elif choice == "0":
            print("Программа завершена.")
            break

        else:
            print("Неверный выбор. Повторите ввод.")
