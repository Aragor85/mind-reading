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

# Azure définit automatiquement la variable d'env PORT (par défaut 8000)
ENV PORT=8000
EXPOSE 8000

# Lancer Streamlit en utilisant la variable PORT
CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.enableCORS=false"]
