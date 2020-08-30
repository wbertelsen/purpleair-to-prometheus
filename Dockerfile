FROM python:3.8-alpine

RUN mkdir /purple-to-prom
WORKDIR /purple-to-prom

COPY requirements.txt /purple-to-prom
RUN pip install -r requirements.txt && rm ./requirements.txt

COPY purple_to_prom.py /purple-to-prom
