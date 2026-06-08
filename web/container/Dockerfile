# lidar-arch pipeline container — runs the CLI behind a tiny HTTP server on :8080.
# Cloudflare Containers require linux/amd64. Build from the REPO ROOT:
#   docker build -f web/container/Dockerfile -t lidar-arch:dev .
FROM --platform=linux/amd64 mambaorg/micromamba:latest
USER root
WORKDIR /app

# 1) geospatial toolchain (PDAL / GDAL / rasterio / pyproj / ...) via conda-forge
COPY web/container/env.yml /tmp/env.yml
RUN micromamba install -y -n base -f /tmp/env.yml && micromamba clean -ay
# rvt-py: pip, --no-deps (conda already provides gdal / numpy / scipy / matplotlib)
RUN micromamba run -n base python -m pip install --no-deps rvt-py

# 2) the lidar-arch CLI (editable install from source)
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN micromamba run -n base python -m pip install -e /app

# 3) the thin HTTP entrypoint
COPY web/container/server.py /app/server.py
ENV PORT=8080
EXPOSE 8080
# `micromamba run -n base` activates the env (sets GDAL_DATA/PROJ_LIB); the server
# shells out to `lidar-arch`, which inherits the activated environment.
CMD ["micromamba", "run", "-n", "base", "python", "/app/server.py"]
