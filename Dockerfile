# Dockerfile to install this version of code
# For release version, install using pip:
# FROM python:latest
# RUN python3 -m pip install --no-cache-dir webchanges

FROM python:latest

RUN python3 -m pip install --no-cache-dir -r requirements.txt

WORKDIR /opt/webchanges

COPY webchanges ./webchanges
COPY setup.py .

RUN python3 setup.py install

WORKDIR /root/.webchanges

ENTRYPOINT ["webchanges.py"]
