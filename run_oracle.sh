#!/usr/bin/env bash
# Run ORACLE Streamlit app from the project root (keeps agents/ namespace correct)
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
cd "$(dirname "$0")"
python -m streamlit run oracle/app.py "$@"
