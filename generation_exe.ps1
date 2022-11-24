.\.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller --onefile main.py 
Remove-Item .\build -Recurse -Force
Remove-Item main.spec -Force
New-Item -ItemType Directory -Path .\Time_table 
Copy-Item .\dist\main.exe .\Time_table\Time_table.exe
New-Item -ItemType Directory -Path .\Time_table\data
New-Item -ItemType Directory -Path .\Time_table\data\variable_data_for_app
Copy-Item .\data\variable_data_for_app\* .\Time_table\data\variable_data_for_app
Copy-Item .\data\1_attlog.dat .\Time_table\data
Remove-Item .\dist -Recurse -Force
Compress-Archive -Path .\Time_table -DestinationPath .\Time_table.zip
Write-Host "DONE! Executable file generated"