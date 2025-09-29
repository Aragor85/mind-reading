# Utiliser l'image officielle Azure Functions Python 3.10
FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice

WORKDIR /home/site/wwwroot

# Installer dépendances système pour compiler scikit-surprise et numpy
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements.txt et installer les dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code
COPY . .
