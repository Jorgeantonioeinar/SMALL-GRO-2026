@echo off
cd /d %~dp0..
if not exist .venv (
  echo Creando entorno virtual...
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo.
echo Abriendo Streamlit en http://localhost:8501
streamlit run streamlit_app.py
