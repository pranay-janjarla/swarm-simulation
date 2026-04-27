#!/bin/sh
exec streamlit run oasis_ui.py \
    --server.port="${PORT:-8503}" \
    --server.address=0.0.0.0 \
    --server.headless=true
