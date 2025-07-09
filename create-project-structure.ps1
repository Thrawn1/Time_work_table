# Создание структуры проекта employee-time-tracker

# Создание корневой директории
New-Item -ItemType Directory -Path "employee-time-tracker" -Force
Set-Location "employee-time-tracker"

# Корневые файлы
New-Item -ItemType File -Path "README.md" -Force
New-Item -ItemType File -Path "pyproject.toml" -Force
New-Item -ItemType File -Path ".gitignore" -Force
New-Item -ItemType File -Path ".pre-commit-config.yaml" -Force

# Создание основной структуры src/
$srcDirs = @(
    "src/timetracker",
    "src/timetracker/domain/entities",
    "src/timetracker/domain/value_objects", 
    "src/timetracker/domain/services",
    "src/timetracker/domain/repositories",
    "src/timetracker/domain/exceptions",
    "src/timetracker/application/use_cases",
    "src/timetracker/application/dto",
    "src/timetracker/application/interfaces",
    "src/timetracker/infrastructure/persistence/file_based",
    "src/timetracker/infrastructure/persistence/database/migrations",
    "src/timetracker/infrastructure/file_parsers",
    "src/timetracker/infrastructure/report_generators/templates",
    "src/timetracker/infrastructure/notifications",
    "src/timetracker/infrastructure/analytics/engines",
    "src/timetracker/infrastructure/analytics/metrics",
    "src/timetracker/infrastructure/analytics/exporters",
    "src/timetracker/infrastructure/config",
    "src/timetracker/presentation/cli/commands",
    "src/timetracker/presentation/cli/utils",
    "src/timetracker/presentation/api/routes",
    "src/timetracker/presentation/api/schemas"
)

foreach ($dir in $srcDirs) {
    New-Item -ItemType Directory -Path $dir -Force
}

# Создание __init__.py файлов
$initFiles = @(
    "src/timetracker/__init__.py",
    "src/timetracker/domain/__init__.py",
    "src/timetracker/domain/entities/__init__.py",
    "src/timetracker/domain/value_objects/__init__.py",
    "src/timetracker/domain/services/__init__.py",
    "src/timetracker/domain/repositories/__init__.py",
    "src/timetracker/domain/exceptions/__init__.py",
    "src/timetracker/application/__init__.py",
    "src/timetracker/application/use_cases/__init__.py",
    "src/timetracker/application/dto/__init__.py",
    "src/timetracker/application/interfaces/__init__.py",
    "src/timetracker/infrastructure/__init__.py",
    "src/timetracker/infrastructure/persistence/__init__.py",
    "src/timetracker/infrastructure/persistence/file_based/__init__.py",
    "src/timetracker/infrastructure/persistence/database/__init__.py",
    "src/timetracker/infrastructure/file_parsers/__init__.py",
    "src/timetracker/infrastructure/report_generators/__init__.py",
    "src/timetracker/infrastructure/notifications/__init__.py",
    "src/timetracker/infrastructure/analytics/__init__.py",
    "src/timetracker/infrastructure/config/__init__.py",
    "src/timetracker/presentation/__init__.py",
    "src/timetracker/presentation/cli/__init__.py",
    "src/timetracker/presentation/cli/commands/__init__.py",
    "src/timetracker/presentation/cli/utils/__init__.py",
    "src/timetracker/presentation/api/__init__.py"
)

foreach ($file in $initFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Основные файлы domain/
$domainFiles = @(
    "src/timetracker/domain/entities/employee.py",
    "src/timetracker/domain/entities/work_day.py",
    "src/timetracker/domain/entities/payroll_period.py",
    "src/timetracker/domain/value_objects/employee_id.py",
    "src/timetracker/domain/value_objects/time_record.py",
    "src/timetracker/domain/value_objects/work_time.py",
    "src/timetracker/domain/value_objects/salary.py",
    "src/timetracker/domain/value_objects/special_day.py",
    "src/timetracker/domain/value_objects/enums.py",
    "src/timetracker/domain/services/record_processor.py",
    "src/timetracker/domain/services/salary_calculator.py",
    "src/timetracker/domain/services/work_day_validator.py",
    "src/timetracker/domain/services/special_day_manager.py",
    "src/timetracker/domain/repositories/employee_repository.py",
    "src/timetracker/domain/repositories/time_record_repository.py",
    "src/timetracker/domain/repositories/special_day_repository.py",
    "src/timetracker/domain/repositories/payroll_repository.py",
    "src/timetracker/domain/exceptions/employee_exceptions.py",
    "src/timetracker/domain/exceptions/time_record_exceptions.py",
    "src/timetracker/domain/exceptions/salary_exceptions.py"
)

foreach ($file in $domainFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Файлы application/
$applicationFiles = @(
    "src/timetracker/application/use_cases/process_time_records.py",
    "src/timetracker/application/use_cases/calculate_salaries.py",
    "src/timetracker/application/use_cases/generate_reports.py",
    "src/timetracker/application/use_cases/manage_employees.py",
    "src/timetracker/application/use_cases/manage_special_days.py",
    "src/timetracker/application/dto/employee_dto.py",
    "src/timetracker/application/dto/time_record_dto.py",
    "src/timetracker/application/dto/salary_dto.py",
    "src/timetracker/application/dto/report_dto.py",
    "src/timetracker/application/interfaces/file_parser.py",
    "src/timetracker/application/interfaces/report_generator.py",
    "src/timetracker/application/interfaces/notification_service.py"
)

foreach ($file in $applicationFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Файлы infrastructure/
$infrastructureFiles = @(
    "src/timetracker/infrastructure/persistence/file_based/employee_file_repository.py",
    "src/timetracker/infrastructure/persistence/file_based/time_record_file_repository.py",
    "src/timetracker/infrastructure/persistence/file_based/special_day_file_repository.py",
    "src/timetracker/infrastructure/persistence/database/models.py",
    "src/timetracker/infrastructure/persistence/database/employee_db_repository.py",
    "src/timetracker/infrastructure/persistence/database/time_record_db_repository.py",
    "src/timetracker/infrastructure/file_parsers/attlog_parser.py",
    "src/timetracker/infrastructure/file_parsers/employee_parser.py",
    "src/timetracker/infrastructure/file_parsers/config_parser.py",
    "src/timetracker/infrastructure/report_generators/excel_generator.py",
    "src/timetracker/infrastructure/report_generators/html_generator.py",
    "src/timetracker/infrastructure/report_generators/pdf_generator.py",
    "src/timetracker/infrastructure/report_generators/templates/employee_report.html",
    "src/timetracker/infrastructure/report_generators/templates/payroll_report.html",
    "src/timetracker/infrastructure/report_generators/templates/summary_report.html",
    "src/timetracker/infrastructure/notifications/telegram_service.py",
    "src/timetracker/infrastructure/notifications/email_service.py",
    "src/timetracker/infrastructure/config/settings.py",
    "src/timetracker/infrastructure/config/role_config.py",
    "src/timetracker/infrastructure/config/dependency_injection.py"
)

foreach ($file in $infrastructureFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Файлы presentation/
$presentationFiles = @(
    "src/timetracker/presentation/cli/main.py",
    "src/timetracker/presentation/cli/commands/process.py",
    "src/timetracker/presentation/cli/commands/calculate.py",
    "src/timetracker/presentation/cli/commands/report.py",
    "src/timetracker/presentation/cli/commands/employee.py",
    "src/timetracker/presentation/cli/commands/validate.py",
    "src/timetracker/presentation/cli/utils/progress.py",
    "src/timetracker/presentation/cli/utils/formatters.py",
    "src/timetracker/presentation/cli/utils/validators.py"
)

foreach ($file in $presentationFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Создание структуры tests/
$testDirs = @(
    "tests/unit/domain",
    "tests/unit/application", 
    "tests/unit/infrastructure",
    "tests/integration",
    "tests/e2e",
    "tests/fixtures/expected_reports"
)

foreach ($dir in $testDirs) {
    New-Item -ItemType Directory -Path $dir -Force
}

# Файлы тестов
$testFiles = @(
    "tests/__init__.py",
    "tests/unit/domain/test_entities.py",
    "tests/unit/domain/test_value_objects.py",
    "tests/unit/domain/test_services.py",
    "tests/unit/application/test_use_cases.py",
    "tests/unit/infrastructure/test_parsers.py",
    "tests/unit/infrastructure/test_generators.py",
    "tests/integration/test_file_processing.py",
    "tests/integration/test_salary_calculation.py",
    "tests/integration/test_report_generation.py",
    "tests/e2e/test_cli_commands.py",
    "tests/fixtures/sample_attlog.dat",
    "tests/fixtures/sample_employees.dat"
)

foreach ($file in $testFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Создание config/
New-Item -ItemType Directory -Path "config" -Force
$configFiles = @(
    "config/settings.yaml",
    "config/roles.yaml", 
    "config/holidays.yaml",
    "config/development.yaml"
)

foreach ($file in $configFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Создание data/
$dataDirs = @(
    "data/input/attlog",
    "data/input/employees",
    "data/input/special_days",
    "data/output/reports",
    "data/output/processed",
    "data/temp"
)

foreach ($dir in $dataDirs) {
    New-Item -ItemType Directory -Path $dir -Force
}

# Создание docs/
New-Item -ItemType Directory -Path "docs/examples" -Force
$docsFiles = @(
    "docs/architecture.md",
    "docs/domain_model.md",
    "docs/api.md",
    "docs/deployment.md"
)

foreach ($file in $docsFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Создание scripts/
New-Item -ItemType Directory -Path "scripts" -Force
$scriptFiles = @(
    "scripts/setup.py",
    "scripts/migrate_data.py",
    "scripts/generate_test_data.py"
)

foreach ($file in $scriptFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Создание docker/
New-Item -ItemType Directory -Path "docker" -Force
$dockerFiles = @(
    "docker/Dockerfile",
    "docker/docker-compose.yml",
    "docker/.dockerignore"
)

foreach ($file in $dockerFiles) {
    New-Item -ItemType File -Path $file -Force
}

Write-Host "Project structure created successfully!" -ForegroundColor Green
Write-Host "Total created:" -ForegroundColor Yellow
$totalDirs = ($srcDirs + $testDirs + $dataDirs + @('config', 'docs/examples', 'scripts', 'docker')).Count
$totalFiles = ($initFiles + $domainFiles + $applicationFiles + $infrastructureFiles + $presentationFiles + $testFiles + $configFiles + $docsFiles + $scriptFiles + $dockerFiles + @('README.md', 'pyproject.toml', '.gitignore', '.pre-commit-config.yaml')).Count
Write-Host "   - $totalDirs directories" -ForegroundColor Cyan
Write-Host "   - $totalFiles files" -ForegroundColor Cyan
Write-Host "Ready to start development!" -ForegroundColor Green