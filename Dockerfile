# ---- stage build: installer conda + paquets + compiler scikit-surprise ----
FROM continuumio/miniconda3 AS build

WORKDIR /build

# installer outils système nécessaires pour compiler des extensions C
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential gcc g++ gfortran pkg-config \
      libopenblas-dev liblapack-dev libatlas-base-dev \
      rsync ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# mettre à jour conda et installer mamba (rapide)
RUN conda update -n base -c defaults conda -y && \
    conda install -y -c conda-forge mamba

# créer un env conda vide (on utilisera pip pour scikit-surprise pour plus de fiabilité)
RUN mamba create -y -n appenv python=3.10

SHELL ["bash", "-lc"]

# activer l'env, installer d'abord pip, wheel et cython + numpy (pré-requis) puis scikit-surprise
RUN source /opt/conda/etc/profile.d/conda.sh && \
    conda activate appenv && \
    python -m pip install --upgrade pip setuptools wheel cython && \
    python -m pip install numpy==1.23.5 && \
    # maintenant installer scikit-surprise (compile)
    python -m pip install scikit-surprise==1.1.3 && \
    # installer le reste des dépendances
    python -m pip install pandas==2.1.1 joblib==1.3.2 requests azure-functions==1.18.0 && \
    # récupérer le site-packages de l'env conda pour le copier dans l'image finale
    PY_SITE=$(python - <<'PY'
import site
print(site.getsitepackages()[0])
PY
) && \
    echo "SITE_PACKAGES=$PY_SITE" && \
    mkdir -p /python_packages && \
    rsync -a --exclude='__pycache__' "$PY_SITE/" /python_packages/

# ---- stage runtime: image Azure Functions Python 3.10 ----
FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice

WORKDIR /home/site/wwwroot

# (optionnel) libs système utiles pour runtime (si besoin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev liblapack-dev && \
    rm -rf /var/lib/apt/lists/*

# Copier les site-packages compilés depuis le build stage
COPY --from=build /python_packages/ /home/site/wwwroot/.python_packages/lib/site-packages/

# S'assurer que azure-functions est présent (souvent déjà, mais safe)
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-deps --target=/home/site/wwwroot/.python_packages/lib/site-packages azure-functions==1.18.0

# Copier le code de la Function
COPY . /home/site/wwwroot

# L'image officielle gère l'entrypoint; rien d'autre à faire
