# ---- Base ----
FROM python:3.10-slim

WORKDIR /app

# Installer les dépendances système légères
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copier requirements et installer Python packages
COPY requirements.txt .
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code de l'app
COPY . .

# Streamlit server config
ENV PORT=8501
EXPOSE 8501

# Commande pour lancer Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.baseUrlPath=/"]
