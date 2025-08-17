from pathlib import Path
from typing import Callable

# Константа – 10 МБ в байтах
TEN_MB: int = 10 * 1024 * 1024


def get_file_size(file_path: Path) -> int:
    """
    Возвращает размер файла в байтах.

    Parameters
    ----------
    file_path : Path
        Путь к файлу.

    Raises
    ------
    FileNotFoundError
        Если файл не найден.
    PermissionError
        Если доступа к файлу нет.
    """
    return file_path.stat().st_size


def measure_and_call(file_path: Path,
                     less_than: Callable[[], None] | None = None,
                     greater_or_equal: Callable[[], None] | None = None,
                     *,
                     threshold: int = TEN_MB) -> None:
    """
    Определяет размер файла и вызывает одну из двух переданных функций.

    Если размер < threshold – вызывается `less_than`,
    иначе – `greater_or_equal`.

    Parameters
    ----------
    file_path : Path
        Путь к файлу.
    less_than : Callable[[], None] | None, optional
        Функция, вызываемая при размере < threshold.
        Если `None`, ничего не делается.
    greater_or_equal : Callable[[], None] | None, optional
        Функция, вызываемая при размере ≥ threshold.
        Если `None`, ничего не делается.
    threshold : int, optional
        Пороговое значение в байтах (по умолчанию 10 МБ).

    Raises
    ------
    FileNotFoundError
        Если файл не найден.
    PermissionError
        Если доступа к файлу нет.
    """
    size = get_file_size(file_path)

    if size < threshold:
        if less_than is not None:
            less_than()
    else:
        if greater_or_equal is not None:
            greater_or_equal()


# ----------------------------------------------------------------------
# Пример пользовательских функций
# ----------------------------------------------------------------------
def func_1() -> None:
    """Обрабатывает файлы меньше 10 МБ."""
    print("Файл меньше 10 МБ: выполняю func_1.")


def func_2() -> None:
    """Обрабатывает файлы 10 МБ и больше."""
    print("Файл 10 МБ и больше: выполняю func_2.")
