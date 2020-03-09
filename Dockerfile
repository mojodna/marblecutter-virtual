FROM quay.io/mojodna/gdal
LABEL maintainer="Seth Fitzsimmons <seth@mojodna.net>"

ARG http_proxy

ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL C.UTF-8
ENV GDAL_CACHEMAX 512
ENV GDAL_DISABLE_READDIR_ON_OPEN TRUE
ENV GDAL_HTTP_MERGE_CONSECUTIVE_RANGES YES
ENV VSI_CACHE TRUE
# tune this according to how much memory is available
ENV VSI_CACHE_SIZE 536870912
# override this accordingly; should be 2-4x $(nproc)
ENV WEB_CONCURRENCY 4

EXPOSE 8000

RUN apt-get update \
  && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cython \
    git \
    python-pip \
    python-wheel \
    python-setuptools \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/marblecutter

COPY requirements-server.txt /opt/marblecutter/
COPY requirements.txt /opt/marblecutter/

RUN pip install -U numpy~=1.16.0 && \
  pip install -r requirements-server.txt && \
  rm -rf /root/.cache

COPY templates /opt/marblecutter/templates
COPY virtual /opt/marblecutter/virtual
COPY server.py /opt/marblecutter/server.py

USER nobody

ENTRYPOINT ["gunicorn", "-k", "gevent", "-b", "0.0.0.0", "--access-logfile", "-", "virtual.web:app"]
