FROM python:3.11-slim

# Keeps Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (layer-cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY config.py event.py message_mutation.py agent.py model.py run.py dashboard.py test_scenarios.py social_platform.py real_estate_oasis.py oasis_ui.py social_ui.py ./

# Directory for CSV/JSON exports (mounted as a volume in compose)
RUN mkdir -p /app/data

# Streamlit ports (dashboard on 8501, oasis-ui on 8503)
EXPOSE 8501 8503

# Default: launch the interactive dashboard
CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
