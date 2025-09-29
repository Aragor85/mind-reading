# Utilise l'image officielle Azure Functions Python
FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice

# Définir le répertoire de travail
WORKDIR /home/site/wwwroot

# Copier requirements.txt et installer les dépendances
COPY requirements.txt /
RUN pip install -r /requirements.txt

# Copier le reste du code
COPY . .
