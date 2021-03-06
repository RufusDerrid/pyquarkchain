FROM ubuntu:bionic

MAINTAINER quarkchain

### set up basic system packages
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y libpq-dev libxml2-dev libxslt1-dev nginx openssh-client openssh-server openssl rsyslog rsyslog-gnutls liblcms2-dev libwebp-dev python-tk libfreetype6-dev vim-nox imagemagick libffi-dev libgmp-dev build-essential libssl-dev software-properties-common pkg-config libtool && \
    apt-get clean

# install git
RUN apt-get update && apt-get install -y git-core && apt-get clean

# install rocksdb
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y libsnappy-dev zlib1g-dev libbz2-dev libgflags-dev liblz4-dev libzstd-dev
WORKDIR /opt
RUN git clone https://github.com/facebook/rocksdb.git
RUN cd rocksdb && DEBUG_LEVEL=0 make shared_lib install-shared
RUN mkdir /data

# install python development tools, setuptools and pip for Python 3
WORKDIR /opt
RUN wget https://bitbucket.org/pypy/pypy/downloads/pypy3-v6.0.0-linux64.tar.bz2
RUN tar fxv pypy3-v6.0.0-linux64.tar.bz2
RUN ln -s /opt/pypy3-v6.0.0-linux64/bin/pypy3 /usr/bin/pypy3
RUN pypy3 -m ensurepip
RUN pypy3 -m pip install -U pip wheel

# configure locale
RUN apt-get update && apt-get install -y locales
RUN locale-gen en_US.UTF-8 && dpkg-reconfigure --frontend noninteractive locales
ENV LC_ALL="en_US.UTF-8" LANG="en_US.UTF-8"

RUN apt-get install -y curl

EXPOSE 22 80 443 38291 38391 38491 8000 29000

### set up code
RUN mkdir /code
WORKDIR /code
RUN git clone https://github.com/RufusDerrid/pyquarkchain.git

RUN pypy3 -m pip install -r pyquarkchain/requirements.txt
# crypto lib issue
# https://github.com/ethereum/pyethapp/issues/274#issuecomment-385268798
RUN pypy3 -m pip uninstall -y pyelliptic
RUN pypy3 -m pip install https://github.com/mfranciszkiewicz/pyelliptic/archive/1.5.10.tar.gz#egg=pyelliptic

ENV PYTHONPATH /code/pyquarkchain

CMD [ "pypy3", "pyquarkchain/quarkchain/cluster/cluster.py", "--mine" ]
