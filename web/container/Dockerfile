# lidar-arch pipeline container — runs the CLI behind a tiny HTTP server on :8080.
# Cloudflare Containers require linux/amd64.
#
# Build context is THIS directory (web/container/) so `wrangler deploy` can build
# it directly. The lidar-arch CLI ships as a pre-built wheel under wheels/ — run
# ./build-wheel.ps1 (or see build-wheel.md) to (re)generate it before building.
#   docker build -t lidar-arch:dev web/container        # from repo root
#   docker build -t lidar-arch:dev .                    # from web/container/
FROM --platform=linux/amd64 mambaorg/micromamba:latest
USER root
WORKDIR /app

# 1) geospatial toolchain (PDAL / GDAL / rasterio / pyproj / ...) via conda-forge
COPY env.yml /tmp/env.yml
RUN micromamba install -y -n base -f /tmp/env.yml && micromamba clean -ay
# rvt-py: pip, --no-deps (conda already provides gdal / numpy / scipy / matplotlib)
RUN micromamba run -n base python -m pip install --no-deps rvt-py

# 2) the lidar-arch CLI — install the pre-built wheel (no repo-root context needed)
COPY wheels/*.whl /tmp/wheels/
RUN micromamba run -n base python -m pip install --no-deps /tmp/wheels/*.whl

# 3) the thin HTTP entrypoint
COPY server.py /app/server.py
ENV PORT=8080
EXPOSE 8080
# `micromamba run -n base` activates the env (sets GDAL_DATA/PROJ_LIB); the server
# shells out to `lidar-arch`, which inherits the activated environment.
CMD ["micromamba", "run", "-n", "base", "python", "/app/server.py"]
