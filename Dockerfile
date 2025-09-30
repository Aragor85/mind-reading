# ---- Stage build: compile scikit-surprise and install wheels ----
FROM python:3.10-slim AS build

WORKDIR /build

# Installer outils nécessaires à la compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ gfortran pkg-config \
    libopenblas-dev liblapack-dev rsync ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Mise à jour pip et installation pré-requis pour compilation
RUN python -m pip install --upgrade pip setuptools wheel cython

# Installer les paquets Python (numpy d'abord, ensuite scikit-surprise qui doit compiler)
RUN python -m pip install numpy==1.23.5
RUN python -m pip install scikit-surprise==1.1.3

# Installer les autres dépendances
RUN python -m pip install pandas==2.1.1 joblib==1.3.2 requests azure-functions==1.18.0

# Récupérer le chemin site-packages et le copier pour l'image runtime
RUN PY_SITE=$(python -c "import site; print(site.getsitepackages()[0])") && \
    echo "SITE_PACKAGES=$PY_SITE" && \
    mkdir -p /python_packages && \
    rsync -a --exclude='__pycache__' "$PY_SITE/" /python_packages/

# ---- Stage runtime: image Azure Functions Python 3.10 ----
FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice

WORKDIR /home/site/wwwroot

# Installer libs système runtime si besoin (souvent déjà présentes dans l'image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev liblapack-dev && \
    rm -rf /var/lib/apt/lists/*

# Copier les site-packages compilés du stage build
COPY --from=build /python_packages/ /home/site/wwwroot/.python_packages/lib/site-packages/

# S'assurer que azure-functions est bien présent (souvent déjà présent, mais safe)
RUN python -m pip install --no-deps --target=/home/site/wwwroot/.python_packages/lib/site-packages azure-functions==1.18.0

# Copier le code de la Function dans wwwroot
COPY . /home/site/wwwroot

# L'image Azure Functions gère l'entrypoint et l'exécution
