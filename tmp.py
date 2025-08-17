#!/usr/bin/env python3
"""
Подсистема работы с сырым файлом (.dat) - инкрементальная загрузка в SQLite
"""

import sqlite3
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, Iterator, Tuple, Dict, List, Any
from enum import Enum
from pathlib import Path
import threading
from contextlib import contextmanager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IngestMode(Enum):
    """Режимы работы подсистемы"""
    TAIL = "tail"      # Инкрементальное чтение хвоста
    COLD = "cold"      # Полное чтение с начала
    REPLAY = "replay"  # Пересчет из БД без чтения файла


class RejectReason(Enum):
    """Причины отбраковки записей"""
    BAD_FORMAT = "bad_format"
    BAD_DATE = "bad_date"
    OUT_OF_MONTH = "out_of_month"


@dataclass
class Config:
    """Конфигурация подсистемы"""
    # Целевой период
    month_start: datetime
    month_end: datetime
    
    # Путь к файлу
    dat_file_path: str
    db_path: str
    
    # Режим работы
    mode: IngestMode = IngestMode.TAIL
    
    # Батчирование
    batch_size: int = 100
    batch_max_interval_ms: int = 5000
    batch_max_bytes: int = 1024 * 1024  # 1MB
    
    # SQLite настройки
    sqlite_journal_mode: str = "WAL"
    sqlite_synchronous: str = "NORMAL"
    sqlite_busy_timeout_ms: int = 5000
    
    # Tail режим
    tail_fingerprint_bytes: int = 65536  # 64KB
    
    # Проверки качества
    gap_tolerance_hours: int = 48
    
    # Блокировки
    lock_mode: str = "sqlite"  # sqlite или file
    
    def validate(self):
        """Валидация конфигурации"""
        if self.month_start >= self.month_end:
            raise ValueError("month_start должен быть раньше month_end")
        if self.batch_size <= 0:
            raise ValueError("batch_size должен быть положительным")
        if not os.path.exists(self.dat_file_path):
            raise ValueError(f"Файл {self.dat_file_path} не существует")
        if self.lock_mode not in ["sqlite", "file"]:
            raise ValueError("lock_mode должен быть 'sqlite' или 'file'")


@dataclass
class TimeMarkRecord:
    """Нормализованная запись временной метки"""
    employee_id: str
    ts: datetime
    f3: str
    f4: str
    f5: str
    f6: str
    raw_json: Optional[str] = None
    source_file: Optional[str] = None
    ingest_run_id: Optional[int] = None


@dataclass
class Checkpoint:
    """Структура чекпоинта"""
    last_safe_offset: int = 0
    last_size: int = 0
    last_ts_seen: Optional[datetime] = None
    tail_fingerprint: Optional[str] = None
    updated_at: Optional[datetime] = None


@dataclass
class IngestCounters:
    """Счетчики прогона"""
    read_delta: int = 0
    kept_in_month: int = 0
    dropped_bad_format: int = 0
    dropped_bad_date: int = 0
    dropped_out_of_month: int = 0
    duplicate_ignored: int = 0
    updated_on_upsert: int = 0
    batches_committed: int = 0
    insert_latency_p50_ms: float = 0
    insert_latency_p95_ms: float = 0
    duration_ms: float = 0
    first_ts_in_month: Optional[datetime] = None
    last_ts_in_month: Optional[datetime] = None
    non_monotonic_count: int = 0
    gaps_count: int = 0


class DatabaseManager:
    """Управление БД и схемой"""
    
    def __init__(self, db_path: str, config: Config):
        self.db_path = db_path
        self.config = config
        self.conn: Optional[sqlite3.Connection] = None
        
    def connect(self):
        """Подключение к БД с настройками"""
        self.conn = sqlite3.connect(
            self.db_path,
            timeout=self.config.sqlite_busy_timeout_ms / 1000,
            isolation_level=None  # Автокоммит для PRAGMA
        )
        
        # Применяем настройки SQLite
        self.conn.execute(f"PRAGMA journal_mode = {self.config.sqlite_journal_mode}")
        self.conn.execute(f"PRAGMA synchronous = {self.config.sqlite_synchronous}")
        self.conn.execute(f"PRAGMA busy_timeout = {self.config.sqlite_busy_timeout_ms}")
        
        # Создаем схему если необходимо
        self._create_schema()
        
    def _create_schema(self):
        """Создание таблиц БД"""
        with self.conn:
            # Staging таблица
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS time_marks_raw (
                    employee_id TEXT NOT NULL,
                    ts TIMESTAMP NOT NULL,
                    f3 TEXT,
                    f4 TEXT,
                    f5 TEXT,
                    f6 TEXT,
                    source_file TEXT,
                    ingest_run_id INTEGER,
                    raw_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(employee_id, ts)
                )
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_time_marks_raw_ts 
                ON time_marks_raw(ts)
            """)
            
            # Таблица прогонов
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS ingest_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TIMESTAMP NOT NULL,
                    finished_at TIMESTAMP,
                    mode TEXT NOT NULL,
                    file_size_start INTEGER,
                    file_size_end INTEGER,
                    tail_bytes INTEGER,
                    non_monotonic BOOLEAN,
                    gaps_count INTEGER,
                    config_checksum TEXT,
                    status TEXT
                )
            """)
            
            # Счетчики прогона
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS ingest_counters (
                    run_id INTEGER PRIMARY KEY,
                    read_delta INTEGER,
                    kept_in_month INTEGER,
                    dropped_bad_format INTEGER,
                    dropped_bad_date INTEGER,
                    dropped_out_of_month INTEGER,
                    duplicate_ignored INTEGER,
                    updated_on_upsert INTEGER,
                    batches_committed INTEGER,
                    insert_latency_p50_ms REAL,
                    insert_latency_p95_ms REAL,
                    duration_ms REAL,
                    first_ts_in_month TIMESTAMP,
                    last_ts_in_month TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES ingest_runs(run_id)
                )
            """)
            
            # Гэпы
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS ingest_gaps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    gap_start TIMESTAMP,
                    gap_end TIMESTAMP,
                    duration_min REAL,
                    FOREIGN KEY (run_id) REFERENCES ingest_runs(run_id)
                )
            """)
            
            # Отбракованные записи
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS rejects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    reason TEXT,
                    raw_json TEXT,
                    line_idx_in_delta INTEGER,
                    detected_ts TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES ingest_runs(run_id)
                )
            """)
            
            # Чекпоинты
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    last_safe_offset INTEGER DEFAULT 0,
                    last_size INTEGER DEFAULT 0,
                    last_ts_seen TIMESTAMP,
                    tail_fingerprint TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Блокировки (для SQLite режима)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS locks (
                    name TEXT PRIMARY KEY,
                    holder TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
    def close(self):
        """Закрытие соединения"""
        if self.conn:
            self.conn.close()


class LockManager:
    """Управление конкурентным доступом"""
    
    def __init__(self, db_manager: DatabaseManager, config: Config):
        self.db = db_manager
        self.config = config
        self.lock_name = "ingest_lock"
        self.holder_id = f"{os.getpid()}_{threading.get_ident()}"
        
    @contextmanager
    def acquire_lock(self):
        """Контекстный менеджер для получения блокировки"""
        if self.config.lock_mode == "sqlite":
            self._acquire_sqlite_lock()
        else:
            self._acquire_file_lock()
            
        try:
            yield
        finally:
            if self.config.lock_mode == "sqlite":
                self._release_sqlite_lock()
            else:
                self._release_file_lock()
                
    def _acquire_sqlite_lock(self):
        """Получение блокировки через SQLite"""
        with self.db.conn:
            # Начинаем транзакцию с эксклюзивным доступом
            self.db.conn.execute("BEGIN IMMEDIATE")
            
            # Проверяем существующую блокировку
            cursor = self.db.conn.execute(
                "SELECT holder, updated_at FROM locks WHERE name = ?",
                (self.lock_name,)
            )
            row = cursor.fetchone()
            
            if row:
                holder, updated_at = row
                # Проверяем TTL (например, 5 минут)
                if (datetime.now() - datetime.fromisoformat(updated_at)).seconds > 300:
                    # Блокировка протухла, обновляем
                    self.db.conn.execute(
                        "UPDATE locks SET holder = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                        (self.holder_id, self.lock_name)
                    )
                else:
                    raise RuntimeError(f"Блокировка занята процессом {holder}")
            else:
                # Создаем новую блокировку
                self.db.conn.execute(
                    "INSERT INTO locks (name, holder) VALUES (?, ?)",
                    (self.lock_name, self.holder_id)
                )
                
    def _release_sqlite_lock(self):
        """Освобождение SQLite блокировки"""
        self.db.conn.execute(
            "DELETE FROM locks WHERE name = ? AND holder = ?",
            (self.lock_name, self.holder_id)
        )
        self.db.conn.execute("COMMIT")
        
    def _acquire_file_lock(self):
        """Получение файловой блокировки"""
        # Упрощенная реализация для демонстрации
        lock_file = Path(self.config.db_path).with_suffix('.lock')
        try:
            lock_file.touch(exist_ok=False)
        except FileExistsError:
            raise RuntimeError("Файловая блокировка уже существует")
            
    def _release_file_lock(self):
        """Освобождение файловой блокировки"""
        lock_file = Path(self.config.db_path).with_suffix('.lock')
        lock_file.unlink(missing_ok=True)


class TailFileReader:
    """Инкрементальное чтение хвоста файла"""
    
    def __init__(self, file_path: str, checkpoint: Checkpoint, config: Config):
        self.file_path = file_path
        self.checkpoint = checkpoint
        self.config = config
        
    def read_delta(self) -> Tuple[Iterator[Tuple[str, int]], int, str, int]:
        """
        Читает дельту файла от последнего чекпоинта
        Returns: (строки с индексами, безопасный офсет, fingerprint, размер файла)
        """
        file_size = os.path.getsize(self.file_path)
        
        # Вычисляем fingerprint хвоста
        tail_fingerprint = self._calculate_tail_fingerprint(file_size)
        
        # Определяем режим чтения
        if file_size == self.checkpoint.last_size:
            # Нет изменений
            return iter([]), self.checkpoint.last_safe_offset, tail_fingerprint, file_size
            
        elif file_size < self.checkpoint.last_size or \
             (self.checkpoint.tail_fingerprint and 
              tail_fingerprint != self.checkpoint.tail_fingerprint):
            # Файл усечен или изменен - нужен cold режим
            logger.warning("Обнаружено изменение файла, переход в cold режим")
            return self._read_from_beginning(file_size, tail_fingerprint)
        else:
            # Нормальное дополнение - читаем хвост
            return self._read_tail(file_size, tail_fingerprint)
            
    def _read_tail(self, file_size: int, tail_fingerprint: str) -> Tuple[Iterator[Tuple[str, int]], int, str, int]:
        """Чтение только хвоста файла"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            f.seek(self.checkpoint.last_safe_offset)
            
            def line_generator():
                line_idx = 0
                safe_offset = self.checkpoint.last_safe_offset
                
                for line in f:
                    if line.endswith('\n'):
                        safe_offset = f.tell()
                        yield line.strip(), line_idx
                        line_idx += 1
                    # Незавершенные строки игнорируются
                    
                # Обновляем безопасный офсет
                nonlocal final_safe_offset
                final_safe_offset = safe_offset
                
            final_safe_offset = self.checkpoint.last_safe_offset
            gen = line_generator()
            
            return gen, final_safe_offset, tail_fingerprint, file_size
            
    def _read_from_beginning(self, file_size: int, tail_fingerprint: str) -> Tuple[Iterator[Tuple[str, int]], int, str, int]:
        """Полное чтение файла с начала"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            
            def line_generator():
                line_idx = 0
                safe_offset = 0
                
                for line in f:
                    if line.endswith('\n'):
                        safe_offset = f.tell()
                        yield line.strip(), line_idx
                        line_idx += 1
                        
                nonlocal final_safe_offset
                final_safe_offset = safe_offset
                
            final_safe_offset = 0
            gen = line_generator()
            
            return gen, final_safe_offset, tail_fingerprint, file_size
            
    def _calculate_tail_fingerprint(self, file_size: int) -> str:
        """Вычисление хэша последних N байт файла"""
        bytes_to_read = min(self.config.tail_fingerprint_bytes, file_size)
        
        with open(self.file_path, 'rb') as f:
            if bytes_to_read > 0:
                f.seek(-bytes_to_read, os.SEEK_END)
                tail_data = f.read()
                return hashlib.md5(tail_data).hexdigest()
        return ""


class DatParser:
    """Парсер строк .dat файла"""
    
    def parse(self, line: str, line_idx: int) -> Tuple[Optional[TimeMarkRecord], Optional[Dict]]:
        """
        Парсит строку в запись
        Returns: (запись, reject_info)
        """
        try:
            parts = line.split('\t')
            
            if len(parts) != 6:
                return None, {
                    'reason': RejectReason.BAD_FORMAT.value,
                    'raw_json': json.dumps({'line': line}),
                    'line_idx_in_delta': line_idx
                }
                
            employee_id, date_str, f3, f4, f5, f6 = parts
            
            # Парсим дату
            try:
                ts = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                
                # Проверка на 2000 год
                if ts.year == 2000:
                    return None, {
                        'reason': RejectReason.BAD_DATE.value,
                        'raw_json': json.dumps({'line': line, 'date': date_str}),
                        'line_idx_in_delta': line_idx,
                        'detected_ts': ts
                    }
                    
            except ValueError:
                return None, {
                    'reason': RejectReason.BAD_DATE.value,
                    'raw_json': json.dumps({'line': line, 'date': date_str}),
                    'line_idx_in_delta': line_idx
                }
                
            record = TimeMarkRecord(
                employee_id=employee_id,
                ts=ts,
                f3=f3,
                f4=f4,
                f5=f5,
                f6=f6,
                raw_json=json.dumps({'line': line})
            )
            
            return record, None
            
        except Exception as e:
            return None, {
                'reason': RejectReason.BAD_FORMAT.value,
                'raw_json': json.dumps({'line': line, 'error': str(e)}),
                'line_idx_in_delta': line_idx
            }


class PeriodFilter:
    """Фильтр записей по периоду"""
    
    def __init__(self, config: Config):
        self.config = config
        
    def filter(self, record: TimeMarkRecord, line_idx: int) -> Tuple[bool, Optional[Dict]]:
        """
        Проверяет попадание записи в целевой период
        Returns: (в_периоде, reject_info)
        """
        if self.config.month_start <= record.ts < self.config.month_end:
            return True, None
        else:
            return False, {
                'reason': RejectReason.OUT_OF_MONTH.value,
                'raw_json': json.dumps({
                    'employee_id': record.employee_id,
                    'ts': record.ts.isoformat()
                }),
                'line_idx_in_delta': line_idx,
                'detected_ts': record.ts
            }


class SQLiteSink:
    """Батчированная вставка в SQLite"""
    
    def __init__(self, db_manager: DatabaseManager, config: Config, run_id: int):
        self.db = db_manager
        self.config = config
        self.run_id = run_id
        self.batch: List[TimeMarkRecord] = []
        self.batch_size_bytes = 0
        self.last_batch_time = time.time()
        self.insert_latencies: List[float] = []
        self.counters = IngestCounters()
        
    def add(self, record: TimeMarkRecord):
        """Добавление записи в батч"""
        record.ingest_run_id = self.run_id
        record.source_file = self.config.dat_file_path
        
        self.batch.append(record)
        self.batch_size_bytes += len(json.dumps(asdict(record)))
        
        # Проверяем условия флаша
        if self._should_flush():
            self.flush()
            
    def _should_flush(self) -> bool:
        """Проверка необходимости флаша батча"""
        if len(self.batch) >= self.config.batch_size:
            return True
            
        if self.batch_size_bytes >= self.config.batch_max_bytes:
            return True
            
        if (time.time() - self.last_batch_time) * 1000 >= self.config.batch_max_interval_ms:
            return True
            
        return False
        
    def flush(self):
        """Сброс батча в БД"""
        if not self.batch:
            return
            
        start_time = time.time()
        
        with self.db.conn:
            # UPSERT через INSERT OR REPLACE
            for record in self.batch:
                self.db.conn.execute("""
                    INSERT OR REPLACE INTO time_marks_raw 
                    (employee_id, ts, f3, f4, f5, f6, source_file, ingest_run_id, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.employee_id,
                    record.ts,
                    record.f3,
                    record.f4,
                    record.f5,
                    record.f6,
                    record.source_file,
                    record.ingest_run_id,
                    record.raw_json
                ))
                
        # Собираем метрики
        latency = (time.time() - start_time) * 1000
        self.insert_latencies.append(latency)
        self.counters.batches_committed += 1
        self.counters.kept_in_month += len(self.batch)
        
        # Обновляем временные границы
        for record in self.batch:
            if self.counters.first_ts_in_month is None or record.ts < self.counters.first_ts_in_month:
                self.counters.first_ts_in_month = record.ts
            if self.counters.last_ts_in_month is None or record.ts > self.counters.last_ts_in_month:
                self.counters.last_ts_in_month = record.ts
                
        # Очищаем батч
        self.batch.clear()
        self.batch_size_bytes = 0
        self.last_batch_time = time.time()
        
    def get_latency_percentiles(self) -> Tuple[float, float]:
        """Получение перцентилей задержек"""
        if not self.insert_latencies:
            return 0, 0
            
        sorted_latencies = sorted(self.insert_latencies)
        p50_idx = int(len(sorted_latencies) * 0.5)
        p95_idx = int(len(sorted_latencies) * 0.95)
        
        return sorted_latencies[p50_idx], sorted_latencies[p95_idx]


class QualityChecker:
    """Проверки качества данных"""
    
    def __init__(self, config: Config):
        self.config = config
        self.last_ts_seen: Optional[datetime] = None
        self.gaps: List[Dict] = []
        self.non_monotonic_count = 0
        
    def check_monotonicity(self, ts: datetime) -> bool:
        """Проверка монотонности временных меток"""
        if self.last_ts_seen and ts < self.last_ts_seen:
            logger.warning(f"NON_MONOTONIC: {ts} < {self.last_ts_seen}")
            self.non_monotonic_count += 1
            return False
            
        # Проверка на гэп
        if self.last_ts_seen:
            gap_hours = (ts - self.last_ts_seen).total_seconds() / 3600
            if gap_hours > self.config.gap_tolerance_hours:
                self.gaps.append({
                    'gap_start': self.last_ts_seen,
                    'gap_end': ts,
                    'duration_min': gap_hours * 60
                })
                
        self.last_ts_seen = ts
        return True


class IngestOrchestrator:
    """Главный оркестратор процесса загрузки"""
    
    def __init__(self, config: Config):
        self.config = config
        config.validate()
        
        self.db = DatabaseManager(config.db_path, config)
        self.db.connect()
        
        self.lock_manager = LockManager(self.db, config)
        
    def run(self):
        """Основной процесс загрузки"""
        start_time = time.time()
        
        with self.lock_manager.acquire_lock():
            # Создаем запись о прогоне
            run_id = self._create_run_record()
            
            try:
                if self.config.mode == IngestMode.REPLAY:
                    self._run_replay(run_id)
                else:
                    self._run_ingest(run_id)
                    
                # Обновляем статус прогона
                self._update_run_status(run_id, 'success', start_time)
                
            except Exception as e:
                logger.error(f"Ошибка при загрузке: {e}")
                self._update_run_status(run_id, 'failed', start_time)
                raise
                
    def _run_ingest(self, run_id: int):
        """Режим загрузки из файла (tail или cold)"""
        # Загружаем чекпоинт
        checkpoint = self._load_checkpoint()
        
        # Инициализируем компоненты
        reader = TailFileReader(self.config.dat_file_path, checkpoint, self.config)
        parser = DatParser()
        period_filter = PeriodFilter(self.config)
        sink = SQLiteSink(self.db, self.config, run_id)
        quality_checker = QualityChecker(self.config)
        
        # Счетчики и отбраковки
        rejects = []
        
        # Читаем дельту
        lines_iter, safe_offset, tail_fingerprint, file_size = reader.read_delta()
        
        for line, line_idx in lines_iter:
            sink.counters.read_delta += 1
            
            # Парсим строку
            record, reject = parser.parse(line, line_idx)
            
            if reject:
                reject['run_id'] = run_id
                rejects.append(reject)
                
                if reject['reason'] == RejectReason.BAD_FORMAT.value:
                    sink.counters.dropped_bad_format += 1
                elif reject['reason'] == RejectReason.BAD_DATE.value:
                    sink.counters.dropped_bad_date += 1
                    
                continue
                
            # Фильтруем по периоду
            in_period, reject = period_filter.filter(record, line_idx)
            
            if not in_period:
                reject['run_id'] = run_id
                rejects.append(reject)
                sink.counters.dropped_out_of_month += 1
                continue
                
            # Проверки качества
            quality_checker.check_monotonicity(record.ts)
            
            # Добавляем в батч
            sink.add(record)
            
        # Финальный флаш
        sink.flush()
        
        # Сохраняем результаты
        self._save_rejects(rejects)
        self._save_gaps(run_id, quality_checker.gaps)
        
        # Обновляем счетчики
        sink.counters.non_monotonic_count = quality_checker.non_monotonic_count
        sink.counters.gaps_count = len(quality_checker.gaps)
        p50, p95 = sink.get_latency_percentiles()
        sink.counters.insert_latency_p50_ms = p50
        sink.counters.insert_latency_p95_ms = p95
        sink.counters.duration_ms = (time.time() - start_time) * 1000
        
        self._save_counters(run_id, sink.counters)
        
        # Обновляем чекпоинт
        new_checkpoint = Checkpoint(
            last_safe_offset=safe_offset,
            last_size=file_size,
            last_ts_seen=quality_checker.last_ts_seen or checkpoint.last_ts_seen,
            tail_fingerprint=tail_fingerprint,
            updated_at=datetime.now()
        )
        self._save_checkpoint(new_checkpoint)
        
        # Выводим сводку
        self._print_summary(sink.counters)
        
    def _run_replay(self, run_id: int):
        """Режим пересчета из БД"""
        logger.info("Режим REPLAY - пересчет бизнес-правил из staging")
        # Здесь вызывается BusinessValidator (вне scope текущего ТЗ)
        pass
        
    def _create_run_record(self) -> int:
        """Создание записи о прогоне"""
        cursor = self.db.conn.execute("""
            INSERT INTO ingest_runs (started_at, mode, file_size_start, status)
            VALUES (?, ?, ?, 'running')
        """, (
            datetime.now(),
            self.config.mode.value,
            os.path.getsize(self.config.dat_file_path)
        ))
        return cursor.lastrowid
        
    def _update_run_status(self, run_id: int, status: str, start_time: float):
        """Обновление статуса прогона"""
        self.db.conn.execute("""
            UPDATE ingest_runs 
            SET finished_at = ?, 
                file_size_end = ?,
                status = ?
            WHERE run_id = ?
        """, (
            datetime.now(),
            os.path.getsize(self.config.dat_file_path),
            status,
            run_id
        ))
        
    def _load_checkpoint(self) -> Checkpoint:
        """Загрузка чекпоинта из БД"""
        cursor = self.db.conn.execute("""
            SELECT last_safe_offset, last_size, last_ts_seen, 
                   tail_fingerprint, updated_at
            FROM checkpoints WHERE id = 1
        """)
        row = cursor.fetchone()
        
        if row:
            return Checkpoint(
                last_safe_offset=row[0],
                last_size=row[1],
                last_ts_seen=datetime.fromisoformat(row[2]) if row[2] else None,
                tail_fingerprint=row[3],
                updated_at=datetime.fromisoformat(row[4]) if row[4] else None
            )
        else:
            # Первый запуск
            return Checkpoint()
            
    def _save_checkpoint(self, checkpoint: Checkpoint):
        """Сохранение чекпоинта в БД"""
        self.db.conn.execute("""
            INSERT OR REPLACE INTO checkpoints 
            (id, last_safe_offset, last_size, last_ts_seen, tail_fingerprint, updated_at)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (
            checkpoint.last_safe_offset,
            checkpoint.last_size,
            checkpoint.last_ts_seen,
            checkpoint.tail_fingerprint,
            checkpoint.updated_at
        ))
        
    def _save_counters(self, run_id: int, counters: IngestCounters):
        """Сохранение счетчиков прогона"""
        self.db.conn.execute("""
            INSERT INTO ingest_counters 
            (run_id, read_delta, kept_in_month, dropped_bad_format, 
             dropped_bad_date, dropped_out_of_month, duplicate_ignored,
             updated_on_upsert, batches_committed, insert_latency_p50_ms,
             insert_latency_p95_ms, duration_ms, first_ts_in_month, last_ts_in_month)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            counters.read_delta,
            counters.kept_in_month,
            counters.dropped_bad_format,
            counters.dropped_bad_date,
            counters.dropped_out_of_month,
            counters.duplicate_ignored,
            counters.updated_on_upsert,
            counters.batches_committed,
            counters.insert_latency_p50_ms,
            counters.insert_latency_p95_ms,
            counters.duration_ms,
            counters.first_ts_in_month,
            counters.last_ts_in_month
        ))
        
    def _save_rejects(self, rejects: List[Dict]):
        """Сохранение отбракованных записей"""
        for reject in rejects:
            self.db.conn.execute("""
                INSERT INTO rejects (run_id, reason, raw_json, line_idx_in_delta, detected_ts)
                VALUES (?, ?, ?, ?, ?)
            """, (
                reject.get('run_id'),
                reject.get('reason'),
                reject.get('raw_json'),
                reject.get('line_idx_in_delta'),
                reject.get('detected_ts')
            ))
            
    def _save_gaps(self, run_id: int, gaps: List[Dict]):
        """Сохранение информации о гэпах"""
        for gap in gaps:
            self.db.conn.execute("""
                INSERT INTO ingest_gaps (run_id, gap_start, gap_end, duration_min)
                VALUES (?, ?, ?, ?)
            """, (
                run_id,
                gap['gap_start'],
                gap['gap_end'],
                gap['duration_min']
            ))
            
    def _print_summary(self, counters: IngestCounters):
        """Вывод сводки прогона"""
        print("\n" + "="*60)
        print("СВОДКА ПРОГОНА ИНGEST")
        print("="*60)
        print(f"Прочитано строк: {counters.read_delta}")
        print(f"Загружено в месяц: {counters.kept_in_month}")
        print(f"Отброшено bad_format: {counters.dropped_bad_format}")
        print(f"Отброшено bad_date: {counters.dropped_bad_date}")
        print(f"Отброшено out_of_month: {counters.dropped_out_of_month}")
        print(f"Дубликатов игнорировано: {counters.duplicate_ignored}")
        print(f"Обновлено при UPSERT: {counters.updated_on_upsert}")
        print(f"Батчей закоммичено: {counters.batches_committed}")
        print(f"Задержка вставки p95: {counters.insert_latency_p95_ms:.2f} ms")
        print(f"Общее время: {counters.duration_ms:.2f} ms")
        
        if counters.first_ts_in_month:
            print(f"Первая метка в месяце: {counters.first_ts_in_month}")
        if counters.last_ts_in_month:
            print(f"Последняя метка в месяце: {counters.last_ts_in_month}")
            
        print(f"Немонотонных записей: {counters.non_monotonic_count}")
        print(f"Обнаружено гэпов: {counters.gaps_count}")
        
        # SLO проверки
        print("\n" + "-"*60)
        print("SLO ПРОВЕРКИ:")
        
        if counters.read_delta > 0:
            error_rate = (counters.dropped_bad_format + counters.dropped_bad_date) / counters.read_delta
            if error_rate > 0.01:
                print(f"⚠️  WARN: parse_error_rate = {error_rate:.2%} > 1%")
            else:
                print(f"✓ parse_error_rate = {error_rate:.2%} < 1%")
                
        if counters.insert_latency_p95_ms > 1000:
            print(f"⚠️  WARN: insert_latency_p95 = {counters.insert_latency_p95_ms:.2f} ms > 1000 ms")
        else:
            print(f"✓ insert_latency_p95 = {counters.insert_latency_p95_ms:.2f} ms < 1000 ms")
            
        print("="*60 + "\n")
        
    def close(self):
        """Закрытие ресурсов"""
        self.db.close()


# ============================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================================

def main():
    """Пример запуска подсистемы"""
    
    # Конфигурация
    config = Config(
        month_start=datetime(2024, 12, 1),
        month_end=datetime(2025, 1, 1),
        dat_file_path="/path/to/data.dat",
        db_path="/path/to/database.db",
        mode=IngestMode.TAIL,
        batch_size=100,
        batch_max_interval_ms=5000,
        batch_max_bytes=1024*1024,
        sqlite_journal_mode="WAL",
        sqlite_synchronous="NORMAL",
        sqlite_busy_timeout_ms=5000,
        tail_fingerprint_bytes=65536,
        gap_tolerance_hours=48,
        lock_mode="sqlite"
    )
    
    # Запуск оркестратора
    orchestrator = IngestOrchestrator(config)
    
    try:
        orchestrator.run()
    finally:
        orchestrator.close()


# ============================================================================
# МОДУЛЬНЫЕ ТЕСТЫ
# ============================================================================

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil


class TestDatParser(unittest.TestCase):
    """Тесты парсера"""
    
    def setUp(self):
        self.parser = DatParser()
        
    def test_valid_line(self):
        """Тест валидной строки"""
        line = "EMP001\t2024-12-15 10:30:00\tF3VAL\tF4VAL\tF5VAL\tF6VAL"
        record, reject = self.parser.parse(line, 0)
        
        self.assertIsNotNone(record)
        self.assertIsNone(reject)
        self.assertEqual(record.employee_id, "EMP001")
        self.assertEqual(record.ts, datetime(2024, 12, 15, 10, 30, 0))
        
    def test_bad_format(self):
        """Тест некорректного формата"""
        line = "EMP001,2024-12-15 10:30:00"  # Неверный разделитель
        record, reject = self.parser.parse(line, 0)
        
        self.assertIsNone(record)
        self.assertIsNotNone(reject)
        self.assertEqual(reject['reason'], 'bad_format')
        
    def test_year_2000(self):
        """Тест отбраковки 2000 года"""
        line = "EMP001\t2000-01-01 10:30:00\tF3\tF4\tF5\tF6"
        record, reject = self.parser.parse(line, 0)
        
        self.assertIsNone(record)
        self.assertIsNotNone(reject)
        self.assertEqual(reject['reason'], 'bad_date')
        
    def test_invalid_date(self):
        """Тест некорректной даты"""
        line = "EMP001\t2024-13-01 10:30:00\tF3\tF4\tF5\tF6"  # 13-й месяц
        record, reject = self.parser.parse(line, 0)
        
        self.assertIsNone(record)
        self.assertIsNotNone(reject)
        self.assertEqual(reject['reason'], 'bad_date')


class TestPeriodFilter(unittest.TestCase):
    """Тесты фильтра периода"""
    
    def setUp(self):
        self.config = Mock()
        self.config.month_start = datetime(2024, 12, 1)
        self.config.month_end = datetime(2025, 1, 1)
        self.filter = PeriodFilter(self.config)
        
    def test_in_period(self):
        """Тест записи в периоде"""
        record = TimeMarkRecord(
            employee_id="EMP001",
            ts=datetime(2024, 12, 15, 10, 30, 0),
            f3="", f4="", f5="", f6=""
        )
        
        in_period, reject = self.filter.filter(record, 0)
        self.assertTrue(in_period)
        self.assertIsNone(reject)
        
    def test_before_period(self):
        """Тест записи до периода"""
        record = TimeMarkRecord(
            employee_id="EMP001",
            ts=datetime(2024, 11, 30, 23, 59, 59),
            f3="", f4="", f5="", f6=""
        )
        
        in_period, reject = self.filter.filter(record, 0)
        self.assertFalse(in_period)
        self.assertIsNotNone(reject)
        self.assertEqual(reject['reason'], 'out_of_month')
        
    def test_after_period(self):
        """Тест записи после периода"""
        record = TimeMarkRecord(
            employee_id="EMP001",
            ts=datetime(2025, 1, 1, 0, 0, 0),
            f3="", f4="", f5="", f6=""
        )
        
        in_period, reject = self.filter.filter(record, 0)
        self.assertFalse(in_period)
        self.assertIsNotNone(reject)


class TestQualityChecker(unittest.TestCase):
    """Тесты проверок качества"""
    
    def setUp(self):
        self.config = Mock()
        self.config.gap_tolerance_hours = 48
        self.checker = QualityChecker(self.config)
        
    def test_monotonic(self):
        """Тест монотонной последовательности"""
        ts1 = datetime(2024, 12, 1, 10, 0, 0)
        ts2 = datetime(2024, 12, 1, 11, 0, 0)
        
        self.assertTrue(self.checker.check_monotonicity(ts1))
        self.assertTrue(self.checker.check_monotonicity(ts2))
        self.assertEqual(self.checker.non_monotonic_count, 0)
        
    def test_non_monotonic(self):
        """Тест немонотонной последовательности"""
        ts1 = datetime(2024, 12, 1, 11, 0, 0)
        ts2 = datetime(2024, 12, 1, 10, 0, 0)  # Раньше предыдущей
        
        self.assertTrue(self.checker.check_monotonicity(ts1))
        self.assertFalse(self.checker.check_monotonicity(ts2))
        self.assertEqual(self.checker.non_monotonic_count, 1)
        
    def test_gap_detection(self):
        """Тест обнаружения гэпов"""
        ts1 = datetime(2024, 12, 1, 10, 0, 0)
        ts2 = datetime(2024, 12, 4, 10, 0, 0)  # 3 дня спустя
        
        self.checker.check_monotonicity(ts1)
        self.checker.check_monotonicity(ts2)
        
        self.assertEqual(len(self.checker.gaps), 1)
        gap = self.checker.gaps[0]
        self.assertEqual(gap['gap_start'], ts1)
        self.assertEqual(gap['gap_end'], ts2)


class TestIntegration(unittest.TestCase):
    """Интеграционные тесты"""
    
    def setUp(self):
        # Создаем временные файлы
        self.temp_dir = tempfile.mkdtemp()
        self.dat_file = os.path.join(self.temp_dir, "test.dat")
        self.db_file = os.path.join(self.temp_dir, "test.db")
        
        # Создаем тестовый .dat файл
        with open(self.dat_file, 'w') as f:
            f.write("EMP001\t2024-12-01 09:00:00\tIN\t\t\t\n")
            f.write("EMP001\t2024-12-01 18:00:00\tOUT\t\t\t\n")
            f.write("EMP002\t2024-12-01 08:30:00\tIN\t\t\t\n")
            f.write("INVALID_LINE\n")  # Битая строка
            f.write("EMP002\t2000-01-01 00:00:00\tIN\t\t\t\n")  # 2000 год
            f.write("EMP002\t2024-11-30 23:59:59\tOUT\t\t\t\n")  # Вне периода
            
    def tearDown(self):
        # Удаляем временные файлы
        shutil.rmtree(self.temp_dir)
        
    def test_full_ingest_flow(self):
        """Тест полного процесса загрузки"""
        config = Config(
            month_start=datetime(2024, 12, 1),
            month_end=datetime(2025, 1, 1),
            dat_file_path=self.dat_file,
            db_path=self.db_file,
            mode=IngestMode.COLD
        )
        
        orchestrator = IngestOrchestrator(config)
        
        try:
            orchestrator.run()
            
            # Проверяем результаты в БД
            conn = sqlite3.connect(self.db_file)
            
            # Проверяем загруженные записи
            cursor = conn.execute("""
                SELECT COUNT(*) FROM time_marks_raw
                WHERE ts >= ? AND ts < ?
            """, (config.month_start, config.month_end))
            count = cursor.fetchone()[0]
            self.assertEqual(count, 2)  # Только 2 записи в декабре
            
            # Проверяем отбраковки
            cursor = conn.execute("SELECT COUNT(*) FROM rejects")
            rejects_count = cursor.fetchone()[0]
            self.assertEqual(rejects_count, 3)  # 1 bad_format + 1 bad_date + 1 out_of_month
            
            conn.close()
            
        finally:
            orchestrator.close()


if __name__ == "__main__":
    # Запуск тестов
    # unittest.main()
    
    # Или запуск основной программы
    main()