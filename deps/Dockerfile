FROM lambci/lambda:build-python2.7

ARG http_proxy
ARG CURL_VERSION=7.59.0
ARG GDAL_VERSION=2.3.0
ARG LIBJPEG_TURBO_VERSION=1.5.90
ARG NGHTTP2_VERSION=1.31.1
ARG PROJ_VERSION=4.9.3

# add gdal-config and curl to PATH for rasterio + libcurl usage
ENV PATH /var/task/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Install deps

RUN \
  rpm --rebuilddb && \
  yum install -y \
    automake16 \
    libpng-devel

# Fetch and build nghttp2

RUN mkdir /tmp/nghttp2 \
  && curl -sfL https://github.com/nghttp2/nghttp2/releases/download/v${NGHTTP2_VERSION}/nghttp2-${NGHTTP2_VERSION}.tar.gz | tar zxf - -C /tmp/nghttp2 --strip-components=1 \
  && cd /tmp/nghttp2 \
  && ./configure --enable-lib-only --prefix=/var/task \
  && make -j $(nproc) install

# Fetch and install libcurl

RUN mkdir /tmp/curl \
  && curl -sfL https://curl.haxx.se/download/curl-${CURL_VERSION}.tar.gz | tar zxf - -C /tmp/curl --strip-components=1 \
  && cd /tmp/curl \
  && ./configure --prefix=/var/task --disable-manual --disable-cookies --with-nghttp2=/var/task \
  && make -j $(nproc) install

# Fetch PROJ.4

RUN \
  curl -sfL http://download.osgeo.org/proj/proj-${PROJ_VERSION}.tar.gz | tar zxf - -C /tmp

# Build and install PROJ.4

WORKDIR /tmp/proj-${PROJ_VERSION}

RUN \
  ./configure \
    --prefix=/var/task && \
  make -j $(nproc) && \
  make install

# Build and install libjpeg-turbo

RUN \
  rpm --rebuilddb && \
  yum install -y \
    nasm

RUN mkdir -p /tmp/libjpeg-turbo \
  && curl -sfL https://github.com/libjpeg-turbo/libjpeg-turbo/archive/${LIBJPEG_TURBO_VERSION}.tar.gz | tar zxf - -C /tmp/libjpeg-turbo --strip-components=1 \
  && cd /tmp/libjpeg-turbo \
  && cmake -G"Unix Makefiles" -DCMAKE_INSTALL_PREFIX=/var/task . \
  && make -j $(nproc) install

# Fetch GDAL

RUN \
  mkdir -p /tmp/gdal \
  && curl -sfL https://github.com/OSGeo/gdal/archive/v${GDAL_VERSION}.tar.gz | tar zxf - -C /tmp/gdal --strip-components=2

# Build + install GDAL

WORKDIR /tmp/gdal

ENV LD_LIBRARY_PATH /var/task/lib64
ENV LIBRARY_PATH /var/task/lib64

RUN \
  ./configure \
    --prefix=/var/task \
    --datarootdir=/var/task/share/gdal \
    --with-curl=/var/task/bin/curl-config \
    --without-qhull \
    --without-mrf \
    --without-grib \
    --without-pcraster \
    --without-png \
    --without-gif \
    --with-jpeg=/var/task \
    --without-pcidsk && \
  make -j $(nproc) && \
  make -j $(nproc) install

# Install Python deps

WORKDIR /var/task

COPY requirements-lambda.txt /var/task/
COPY requirements.txt /var/task/

ENV PYTHONPATH /var/task/.pypath

RUN \
  mkdir -p .pypath && \
  pip install -U "numpy == 1.13.1" Cython -t .pypath/ && \
  pip install -r requirements-lambda.txt -t .pypath/

RUN find . -name \*.so\* -exec strip {} \;

COPY deps/required.txt /var/task/required.txt
COPY deps/prune.sh /var/task/prune.sh

RUN /var/task/prune.sh
