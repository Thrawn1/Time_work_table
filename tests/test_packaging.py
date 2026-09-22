"""Регрессия блока сборка/README/чистка: зависимости, скрипт, игнор, доки."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8-sig')


class TestRequirements:
    def test_runtime_deps(self):
        text = _read('requirements.txt')
        assert 'openpyxl' in text
        assert 'rich' in text
        # отдельный tomli не нужен: TOML читается штатным tomllib
        req_lines = [ln.strip().lower() for ln in text.splitlines()
                     if ln.strip() and not ln.strip().startswith('#')]
        assert not any(ln.startswith('tomli') for ln in req_lines)

    def test_dev_deps(self):
        text = _read('requirements-dev.txt')
        assert 'pytest' in text
        assert 'pyinstaller' in text

    def test_python_version_pinned(self):
        assert (ROOT / '.python-version').read_text(encoding='utf-8').strip().startswith('3.')


class TestBuildScript:
    def test_fails_fast(self):
        text = _read('generation_exe.ps1')
        assert "$ErrorActionPreference = 'Stop'" in text
        assert 'LASTEXITCODE' in text

    def test_no_wildcard_personal_data(self):
        text = _read('generation_exe.ps1')
        assert 'variable_data_for_app\\*' not in text
        assert 'variable_data_for_app/*' not in text

    def test_allowlist_only_safe_files(self):
        text = _read('generation_exe.ps1')
        assert 'holidays.dat' in text
        assert 'postponed_working_days.dat' in text
        assert 'roles_employee.dat' in text

    def test_personal_data_opt_in(self):
        text = _read('generation_exe.ps1')
        assert 'IncludePersonalData' in text
        # персональные файлы упоминаются только в opt-in ветке, не в безусловном копировании
        assert 'wage_rates.dat' in text
        assert 'id_employee.dat' in text

    def test_idempotent_archive(self):
        text = _read('generation_exe.ps1')
        assert '-Force' in text
        assert '--clean' in text

    def test_python_param_drives_build(self):
        """R21: выбранный интерпретатор выполняет установку и сборку."""
        text = _read('generation_exe.ps1')
        assert '-m pip install' in text
        assert '-m PyInstaller' in text

    def test_pay_admin_entry_point(self):
        """R21: EXE-поставка управляет справочником (PayAdmin)."""
        text = _read('generation_exe.ps1')
        assert 'PayAdmin' in text
        assert 'core/pay_cli.py' in text


class TestGitignore:
    def test_artifacts_ignored(self):
        text = _read('.gitignore')
        for needle in ('Time_table/', 'Time_table.zip', '*.spec',
                       'temporary_*.json', 'data/pay_directory.db',
                       'payroll_versions_*.json', '_secret_key.tmp',
                       'result/'):
            assert needle in text, needle


class TestReadme:
    def test_exists_with_key_sections(self):
        text = _read('README.md')
        for needle in ('## Установка', '## Быстрый старт', '-k', '--resume',
                       'pay_directory.db', '60 000', '--pay-dir',
                       '--output-dir', '--data-dir', 'скрыт',
                       'getpass',
                       '## Сборка EXE', '## Данные и приватность',
                       '## Ограничения', 'temporary.json'):
            assert needle in text, needle
