FROM ubuntu
MAINTAINER loblab

ARG PYTHON=python3
RUN apt-get update --fix-missing && apt-get -y upgrade
RUN apt-get -y install ${PYTHON}-pip
RUN $PYTHON -m pip install flask
RUN $PYTHON -m pip install influxdb
RUN apt-get -y install influxdb-client

