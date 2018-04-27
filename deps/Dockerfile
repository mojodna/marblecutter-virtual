FROM lambci/lambda:build-python2.7

ARG http_proxy

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
  && curl -sfL https://github.com/nghttp2/nghttp2/releases/download/v1.26.0/nghttp2-1.26.0.tar.gz | tar zxf - -C /tmp/nghttp2 --strip-components=1 \
  && cd /tmp/nghttp2 \
  && ./configure --enable-lib-only --prefix=/var/task \
  && make -j $(nproc) install

# Fetch and install libcurl

RUN mkdir /tmp/curl \
  && curl -sfL https://curl.haxx.se/download/curl-7.56.0.tar.gz | tar zxf - -C /tmp/curl --strip-components=1 \
  && cd /tmp/curl \
  && ./configure --prefix=/var/task --disable-manual --disable-cookies --with-nghttp2=/var/task \
  && make -j $(nproc) install

# Fetch PROJ.4

RUN \
  curl -sfL http://download.osgeo.org/proj/proj-4.9.3.tar.gz | tar zxf - -C /tmp

# Build and install PROJ.4

WORKDIR /tmp/proj-4.9.3

RUN \
  ./configure \
    --prefix=/var/task && \
  make -j $(nproc) && \
  make install

# Fetch GDAL

RUN \
  mkdir -p /tmp/gdal && \
  curl -sfL https://github.com/OSGeo/gdal/archive/5c1e079.tar.gz | tar zxf - -C /tmp/gdal --strip-components=2

# Build + install GDAL

WORKDIR /tmp/gdal

RUN \
  ./configure \
    --prefix=/var/task \
    --datarootdir=/var/task/share/gdal \
    --with-curl=/var/task/bin/curl-config \
    --with-jpeg=internal \
    --without-qhull \
    --without-mrf \
    --without-grib \
    --without-pcraster \
    --without-png \
    --without-gif \
    --without-pcidsk && \
  make -j $(nproc) && \
  make install

# Install Python deps

WORKDIR /var/task

COPY requirements-lambda.txt /var/task/
COPY requirements.txt /var/task/

ENV PYTHONPATH /var/task/.pypath

RUN \
  mkdir -p .pypath && \
  pip install -U numpy Cython -t .pypath/ && \
  pip install -r requirements-lambda.txt -t .pypath/

RUN find . -name \*.so\* -exec strip {} \;

COPY deps/required.txt /var/task/required.txt
COPY deps/prune.sh /var/task/prune.sh

RUN /var/task/prune.sh
