FROM mcr.microsoft.com/azure-functions/python:4-python3.10

# Installer dépendances système (fix numpy, pandas, scipy…)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    libatlas-base-dev \
    liblapack-dev \
    libblas-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/site/wwwroot

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
