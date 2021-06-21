#FROM python:3-alpine
FROM python:3-slim-buster

LABEL org.opencontainers.image.source https://github.com/SENERGY-Platform/mgw-dyson-dc

#RUN apk --no-cache add git gcc openssl-dev musl-dev libffi-dev
RUN apt-get update && apt-get install -y git gcc libssl-dev musl-dev libffi-dev

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "-u", "./dc.py"]