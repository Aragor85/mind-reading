# Dockerfile Streamlit pour Mind Reading Recommender
FROM python:3.10-slim

WORKDIR /app

# Installer les outils nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Streamlit
COPY requirements_streamlit.txt .
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements_streamlit.txt

# Copier le code de l'application
COPY . .

# Variables d'environnement pour Streamlit
ENV PORT=8501
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
ENV STREAMLIT_SERVER_ENABLE_CORS=false

# Exposer le port Streamlit
EXPOSE 8501

# Lancer l'application Streamlit
CMD ["sh", "-c", "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false"]
