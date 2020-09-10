# Dockerfile to install this version of code
# For release version, install using pip:
# FROM python:latest
# RUN python3 -m pip install --no-cache-dir urlwatch

FROM python:latest

RUN python3 -m pip install --no-cache-dir appdirs html2text lxml markdown2 minidb pyyaml requests

WORKDIR /opt/urlwatch

COPY urlwatch ./urlwatch
COPY setup.py .

RUN python3 setup.py install

WORKDIR /root/.urlwatch

ENTRYPOINT ["urlwatch.py"]
