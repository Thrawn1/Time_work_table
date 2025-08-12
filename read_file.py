from file_read_backwards import FileReadBackwards
from datetime import datetime, timedelta

def parse_period_backwards(
    filename: str,
    target_month: int,
    target_year: int,
    context_days: int = 0,
    encoding: str = "utf-8",
    date_format: str = "%Y-%m-%d",
    strict: bool = False,
):
    """
    Читает лог с конца и возвращает записи за целевой месяц [start; end),
    опционально добавляет контекст перед start на context_days.
    
    Возвращает (records, skipped), где:
      - records: список словарей с полями employee_id, datetime, date, time, raw_line
      - skipped: число пропущенных (некорректных) строк
    """
    # Границы периода
    start = datetime(target_year, target_month, 1)
    end = datetime(target_year + (1 if target_month == 12 else 0),
                   1 if target_month == 12 else target_month + 1, 1)
    context_start = start - timedelta(days=context_days)

    records = []
    skipped = 0
    seen_in_target = False  # встретили хотя бы одну запись целевого месяца

    def _parse_time_safe(t: str):
        # Поддержка HH:MM:SS и HH:MM
        for tf in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(t, tf).time()
            except Exception:
                pass
        return None

    with FileReadBackwards(filename, encoding=encoding) as frb:
        for read_idx, raw_line in enumerate(frb, 1):
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split('\t')
            if len(parts) < 2:
                skipped += 1
                if strict:
                    raise ValueError(f"Invalid format at read #{read_idx}: {line}")
                continue

            employee_id = parts[0].strip()
            dt_field = parts[1].strip()

            # Надёжно разделяем дату и время (если есть)
            try:
                if ' ' in dt_field:
                    date_part, time_part = dt_field.split(None, 1)
                else:
                    date_part, time_part = dt_field, None

                record_date = datetime.strptime(date_part, date_format)

            except Exception as e:
                skipped += 1
                if strict:
                    raise ValueError(f"Invalid datetime at read #{read_idx}: {line}") from e
                continue

            # Пропускаем всё, что позже конечной границы периода: мы ещё не "дошли" до нужного месяца
            if record_date >= end:
                continue

            # Если ушли раньше контекстного окна — дальше только старее, можно выходим
            if record_date < context_start:
                break

            # Внутри окна [context_start; end) — добавляем
            time_obj = _parse_time_safe(time_part) if time_part else None
            dt = datetime.combine(record_date.date(), time_obj) if time_obj else record_date

            in_target = start <= record_date < end
            if in_target:
                seen_in_target = True

            records.append({
                "employee_id": employee_id,
                "datetime": dt,
                "date": dt.date(),
                "time": dt.strftime("%H:%M:%S") if time_obj else None,
                "raw_line": raw_line.rstrip("\r\n"),
            })

            # Как только прошли раньше начала месяца и уже собрали целевой месяц — стоп
            if record_date < start and seen_in_target:
                break

    # Хронологический порядок (по точному datetime)
    records.sort(key=lambda r: r["datetime"])
    return records, skipped


if __name__ == "__main__":
    file = "1_attlog.dat"
    target_month = 7      # Октябрь
    target_year = 2025  # 2023 год

    records, skipped = parse_period_backwards(file, target_month, target_year, context_days=30)
    for r in records:
        print(
            f"Employee ID: {r['employee_id']}, "
            f"Time: {r['time'] or '—'}, "
            f"Date: {r['date'].strftime('%d.%m.%Y')}, "
            f"Raw Line: {r['raw_line']}"
        )
    if skipped:
        print(f"Пропущено некорректных строк: {skipped}")
