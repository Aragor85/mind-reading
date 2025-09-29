# ---- stage build: installer conda + paquets depuis conda-forge ----
FROM continuumio/miniconda3 AS build

WORKDIR /build

# créer env et installer paquets binaires depuis conda-forge
# on verrouille python=3.10 pour correspondre à Azure Functions
RUN conda update -n base -c defaults conda -y && \
    conda install -y -c conda-forge mamba

# créer un env conda contenant scikit-surprise + numpy compatible + pandas + requests + joblib
RUN mamba create -y -n appenv python=3.10 \
    scikit-surprise=1.1.3 numpy=1.23.5 pandas=2.1.1 joblib requests azure-functions

# activer l'env, collecter site-packages
SHELL ["bash", "-lc"]
RUN source /opt/conda/etc/profile.d/conda.sh && \
    conda activate appenv && \
    python -c "import site,sys,os; print(site.getsitepackages())" > /tmp/sitepacks && \
    SITE_PACKAGES=$(python - <<'PY'
import site
print(site.getsitepackages()[0])
PY
) && \
    echo "SITE_PACKAGES=$SITE_PACKAGES" && \
    mkdir -p /python_packages && \
    rsync -a --exclude='__pycache__' \"$SITE_PACKAGES/\" /python_packages/

# ---- stage runtime: image Azure Functions Python 3.10 ----
FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice

WORKDIR /home/site/wwwroot

# (optionnel) installer libs système utiles
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev liblapack-dev gfortran build-essential && \
    rm -rf /var/lib/apt/lists/*

# copier les site-packages depuis le build stage vers l'emplacement attendu par Functions
COPY --from=build /python_packages/ /home/site/wwwroot/.python_packages/lib/site-packages/

# s'assurer que le host runtime ait azure-functions (souvent déjà présent, sinon)
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-deps --target=/home/site/wwwroot/.python_packages/lib/site-packages azure-functions

# copier le code de la Function
COPY . /home/site/wwwroot

# expose/entrypoint géré par l'image Azure Functions
