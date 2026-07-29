FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Copia i requisiti e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente del bot
COPY . .

# Esegue l'applicazione unificata (Instant Webhook + 24/7 Scanner)
CMD ["python", "app.py"]
