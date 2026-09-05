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
    def test_round_trip(self, tmp_path):
        """Сохранение и загрузка: данные не теряются."""
        from core.session import save_session, load_session
        os.chdir(tmp_path)
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

    def test_atomic_write_no_temp_left(self, tmp_path):
        """После записи temp-файл не остаётся."""
        from core.session import save_session, SESSION_FILE
        os.chdir(tmp_path)
        save_session({'2026-07-06': {101: [make_dt('2026-07-06', '16:00:00'), make_dt('2026-07-06', '08:00:00'), 'work']}})
        assert os.path.exists(SESSION_FILE)
        for f in os.listdir(tmp_path):
            assert not f.endswith('.tmp')

    def test_json_is_valid(self, tmp_path):
        """Файл — валидный JSON с правильной структурой."""
        from core.session import save_session, SESSION_FILE, SESSION_VERSION
        os.chdir(tmp_path)
        save_session({'2026-01-01': {1: [make_dt('2026-01-01', '08:00:00'), make_dt('2026-01-01', '08:00:00'), 'holiday']}})
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        assert raw['version'] == SESSION_VERSION
        assert 'entries' in raw
        assert raw['entries']['2026-01-01']['1'][2] == 'holiday'


class TestLoadValidation:
    def test_missing_file(self, tmp_path):
        """Несуществующий файл → None."""
        from core.session import load_session
        os.chdir(tmp_path)
        assert load_session('nonexistent.json') is None

    def test_invalid_json(self, tmp_path):
        """Повреждённый JSON → None + сообщение."""
        from core.session import load_session
        os.chdir(tmp_path)
        with open('bad.json', 'w') as f:
            f.write('{broken')
        assert load_session('bad.json') is None

    def test_missing_version_field(self, tmp_path):
        """Нет поля version → None."""
        from core.session import load_session
        os.chdir(tmp_path)
        with open('no_ver.json', 'w') as f:
            json.dump({'entries': {}}, f)
        assert load_session('no_ver.json') is None

    def test_missing_entries_field(self, tmp_path):
        """Нет поля entries → None."""
        from core.session import load_session
        os.chdir(tmp_path)
        with open('no_ent.json', 'w') as f:
            json.dump({'version': 1}, f)
        assert load_session('no_ent.json') is None

    def test_wrong_version(self, tmp_path):
        """Неизвестная версия → None."""
        from core.session import load_session
        os.chdir(tmp_path)
        with open('old.json', 'w') as f:
            json.dump({'version': 999, 'entries': {}}, f)
        assert load_session('old.json') is None

    def test_pickle_file_rejected(self, tmp_path):
        """Pickle-файл → None + предупреждение."""
        from core.session import load_session
        os.chdir(tmp_path)
        with open('session.pickle', 'wb') as f:
            f.write(b'not a real pickle')
        assert load_session('session.pickle') is None

    def test_corrupted_marks_skipped(self, tmp_path):
        """Повреждённые отметки пропускаются, корректные загружаются."""
        from core.session import load_session
        os.chdir(tmp_path)
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
        loaded = load_session('partial.json')
        assert loaded is not None
        assert 101 in loaded['2026-07-06']
        assert 102 not in loaded['2026-07-06']
        assert 103 not in loaded['2026-07-06']


class TestSessionExistsAndRemove:
    def test_session_exists_json(self, tmp_path):
        """session_exists находит JSON."""
        from core.session import save_session, session_exists, SESSION_FILE
        os.chdir(tmp_path)
        assert not session_exists()
        save_session({})
        assert session_exists()

    def test_session_exists_pickle(self, tmp_path):
        """session_exists находит legacy pickle."""
        from core.session import session_exists, SESSION_FILE_LEGACY
        os.chdir(tmp_path)
        with open(SESSION_FILE_LEGACY, 'wb') as f:
            f.write(b'data')
        assert session_exists()

    def test_remove_cleans_both(self, tmp_path):
        """remove_session удаляет и JSON, и pickle."""
        from core.session import save_session, remove_session, session_exists, SESSION_FILE_LEGACY
        os.chdir(tmp_path)
        save_session({})
        with open(SESSION_FILE_LEGACY, 'wb') as f:
            f.write(b'data')
        assert session_exists()
        remove_session()
        assert not session_exists()
