# ---- stage build: installer conda + paquets depuis conda-forge ----
FROM continuumio/miniconda3 AS build

WORKDIR /build

# mettre à jour conda et installer mamba
RUN conda update -n base -c defaults conda -y && \
    conda install -y -c conda-forge mamba

# créer un env conda contenant scikit-surprise + numpy compatible + pandas + requests + joblib
RUN mamba create -y -n appenv python=3.10 \
    scikit-surprise=1.1.3 numpy=1.23.5 pandas=2.1.1 joblib requests azure-functions

# activer l'env et collecter site-packages
SHELL ["bash", "-lc"]
RUN source /opt/conda/etc/profile.d/conda.sh && \
    conda activate appenv && \
    SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])") && \
    echo "SITE_PACKAGES=$SITE_PACKAGES" && \
    mkdir -p /python_packages && \
    rsync -a --exclude='__pycache__' "$SITE_PACKAGES/" /python_packages/

# ---- stage runtime: image Azure Functions Python 3.10 ----
FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice

WORKDIR /home/site/wwwroot

# installer libs système utiles pour scikit-surprise / numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev liblapack-dev gfortran build-essential && \
    rm -rf /var/lib/apt/lists/*

# copier les site-packages depuis le build stage
COPY --from=build /python_packages/ /home/site/wwwroot/.python_packages/lib/site-packages/

# installer azure-functions si besoin
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-deps --target=/home/site/wwwroot/.python_packages/lib/site-packages azure-functions

# copier le code de la Function
COPY . /home/site/wwwroot

# l'expose/entrypoint est géré par l'image Azure Functions
