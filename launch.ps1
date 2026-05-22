# RENMAD Content Generator — launcher
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$python = "C:\Users\Belén\AppData\Local\Programs\Python\Python312\python.exe"
Set-Location $PSScriptRoot
& $python -m streamlit run app.py --server.port 8501 --server.headless false
