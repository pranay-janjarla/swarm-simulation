FROM python:3.11-slim

# Keeps Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install CPU-only PyTorch first to prevent camel-oasis from pulling in
# the full CUDA build (~2.5 GB of GPU libraries we don't need on Railway)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies and clean up to keep image small
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && find /usr/local/lib/python3.11 -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -name "*.pyc" -delete 2>/dev/null || true

# Copy source
COPY config.py event.py message_mutation.py agent.py model.py run.py dashboard.py test_scenarios.py social_platform.py real_estate_oasis.py oasis_ui.py social_ui.py start.sh ./
RUN chmod +x start.sh

# Agent profile data
RUN mkdir -p /app/data /app/transcripts
COPY data/ /app/data/

# Streamlit ports (dashboard on 8501, oasis-ui on 8503)
EXPOSE 8501 8503

# Default: launch the interactive dashboard
CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
