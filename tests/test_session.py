"""
Тесты модуля сессий: JSON-формат, атомарная запись, валидация.
"""
import json
import os
import pytest
from datetime import datetime


def make_dt(date_str, time_str):
    return datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path, monkeypatch):
        """Сохранение и загрузка: данные не теряются."""
        from core.session import save_session, load_session
        monkeypatch.chdir(tmp_path)
        time_table = {
            '2026-07-06': {
                101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work'],
                102: [make_dt('2026-07-06', '00:00:01'), make_dt('2026-07-06', '00:00:01'), 'vacation'],
            },
            '2026-07-07': {
                101: [make_dt('2026-07-07', '18:00:00'), make_dt('2026-07-07', '07:30:00'), 'work'],
            },
        }
        save_session(time_table)
        loaded = load_session()
        assert loaded is not None
        assert set(loaded.keys()) == {'2026-07-06', '2026-07-07'}
        assert loaded['2026-07-06'][101][0] == make_dt('2026-07-06', '16:00:00')
        assert loaded['2026-07-06'][101][1] == make_dt('2026-07-06', '08:00:00')
        assert loaded['2026-07-06'][101][2] == 'work'
        assert loaded['2026-07-06'][102][2] == 'vacation'
        assert loaded['2026-07-07'][101][0] == make_dt('2026-07-07', '18:00:00')

    def test_atomic_write_no_temp_left(self, tmp_path, monkeypatch):
        """После записи temp-файл не остаётся."""
        from core.session import save_session, SESSION_FILE
        monkeypatch.chdir(tmp_path)
        save_session({'2026-07-06': {101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work']}})
        assert os.path.exists(SESSION_FILE)
        for f in os.listdir(tmp_path):
            assert not f.endswith('.tmp')

    def test_json_is_valid(self, tmp_path, monkeypatch):
        """Файл — валидный JSON с правильной структурой."""
        from core.session import save_session, SESSION_FILE, SESSION_VERSION
        monkeypatch.chdir(tmp_path)
        save_session({'2026-01-01': {1: [make_dt('2026-01-01', '08:00:00'), make_dt('2026-01-01', '08:00:00'), 'holiday']}})
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        assert raw['version'] == SESSION_VERSION
        assert 'entries' in raw
        assert raw['entries']['2026-01-01']['1'][2] == 'holiday'


class TestLoadValidation:
    def test_missing_file(self, tmp_path, monkeypatch):
        """Несуществующий файл → None."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        assert load_session('nonexistent.json') is None

    def test_invalid_json(self, tmp_path, monkeypatch):
        """Повреждённый JSON → None + сообщение."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        with open('bad.json', 'w') as f:
            f.write('{broken')
        assert load_session('bad.json') is None

    def test_missing_version_field(self, tmp_path, monkeypatch):
        """Нет поля version → None."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        with open('no_ver.json', 'w') as f:
            json.dump({'entries': {}}, f)
        assert load_session('no_ver.json') is None

    def test_missing_entries_field(self, tmp_path, monkeypatch):
        """Нет поля entries → None."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        with open('no_ent.json', 'w') as f:
            json.dump({'version': 1}, f)
        assert load_session('no_ent.json') is None

    def test_wrong_version(self, tmp_path, monkeypatch):
        """Неизвестная версия → None."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        with open('old.json', 'w') as f:
            json.dump({'version': 999, 'entries': {}}, f)
        assert load_session('old.json') is None

    def test_pickle_file_rejected(self, tmp_path, monkeypatch):
        """Pickle-файл → None + предупреждение."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        with open('session.pickle', 'wb') as f:
            f.write(b'not a real pickle')
        assert load_session('session.pickle') is None

    def test_corrupted_marks_rejected(self, tmp_path, monkeypatch):
        """Повреждённые отметки — отказ в восстановлении целиком (не частичный расчёт)."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        data = {
            'version': 1,
            'entries': {
                '2026-07-06': {
                    '101': ['2026-07-06T16:00:00', '2026-07-06T08:00:00', 'work'],
                    '102': ['bad', 'marks', 'here'],
                    '103': [123, 456, 789],
                },
            },
        }
        with open('partial.json', 'w') as f:
            json.dump(data, f)
        assert load_session('partial.json') is None

    def test_inverted_times_rejected(self, tmp_path, monkeypatch):
        """Приход позже ухода — отказ (иначе отрицательное начисление)."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        data = {
            'version': 1,
            'entries': {
                '2026-07-06': {
                    '101': ['2026-07-06T08:00:00', '2026-07-06T09:00:00', 'work'],
                },
            },
        }
        with open('inverted.json', 'w') as f:
            json.dump(data, f)
        assert load_session('inverted.json') is None

    def test_bad_tag_rejected(self, tmp_path, monkeypatch):
        """Недопустимый статус — отказ."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        data = {
            'version': 1,
            'entries': {
                '2026-07-06': {
                    '101': ['2026-07-06T16:00:00', '2026-07-06T08:00:00', 'wrok'],
                },
            },
        }
        with open('badtag.json', 'w') as f:
            json.dump(data, f)
        assert load_session('badtag.json') is None

    def test_entries_list_rejected(self, tmp_path, monkeypatch, capsys):
        """"entries": [] — диагностируемый отказ, а не AttributeError."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        with open('empty_list.json', 'w') as f:
            json.dump({'version': 1, 'entries': []}, f)
        assert load_session('empty_list.json') is None
        out = capsys.readouterr().out
        assert 'entries' in out

    def test_mixed_period_rejected(self, tmp_path, monkeypatch):
        """Даты из разных месяцев — отказ (несогласованный период)."""
        from core.session import load_session
        monkeypatch.chdir(tmp_path)
        data = {
            'version': 1,
            'entries': {
                '2026-06-15': {'101': ['2026-06-15T16:00:00', '2026-06-15T08:00:00', 'work']},
                '2026-07-06': {'101': ['2026-07-06T16:00:00', '2026-07-06T08:00:00', 'work']},
            },
        }
        with open('mixed.json', 'w') as f:
            json.dump(data, f)
        assert load_session('mixed.json') is None


class TestSessionExistsAndRemove:
    def test_session_exists_json(self, tmp_path, monkeypatch):
        """session_exists находит JSON."""
        from core.session import save_session, session_exists, SESSION_FILE
        monkeypatch.chdir(tmp_path)
        assert not session_exists()
        save_session({})
        assert session_exists()

    def test_session_exists_pickle(self, tmp_path, monkeypatch):
        """session_exists находит legacy pickle."""
        from core.session import session_exists, SESSION_FILE_LEGACY
        monkeypatch.chdir(tmp_path)
        with open(SESSION_FILE_LEGACY, 'wb') as f:
            f.write(b'data')
        assert session_exists()

    def test_remove_cleans_both(self, tmp_path, monkeypatch):
        """remove_session удаляет и JSON, и pickle."""
        from core.session import save_session, remove_session, session_exists, SESSION_FILE_LEGACY
        monkeypatch.chdir(tmp_path)
        save_session({})
        with open(SESSION_FILE_LEGACY, 'wb') as f:
            f.write(b'data')
        assert session_exists()
        remove_session()
        assert not session_exists()

    def test_backup_preserves_ignored_session(self, tmp_path, monkeypatch):
        """Игнорируемая сессия сохраняется в бэкап, а не затирается."""
        from core.session import save_session, backup_existing_session, SESSION_FILE
        monkeypatch.chdir(tmp_path)
        save_session({'2026-06-15': {101: [make_dt('2026-06-15', '16:00:00'), make_dt('2026-06-15', '08:00:00'), 'work']}})
        assert os.path.exists(SESSION_FILE)
        backup = backup_existing_session()
        assert backup is not None
        assert os.path.exists(backup)
        assert not os.path.exists(SESSION_FILE)
