#!/usr/bin/env bash
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  python3.12 -m venv .venv || python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
echo "Abriendo Streamlit en http://localhost:8501"
streamlit run streamlit_app.py
