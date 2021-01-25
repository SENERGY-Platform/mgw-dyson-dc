FROM python:3-alpine

LABEL org.opencontainers.image.source https://github.com/SENERGY-Platform/mgw-dyson-dc

RUN apk update && apk upgrade && apk add git gcc openssl-dev musl-dev libffi-dev && rm -vrf /var/cache/apk/*

WORKDIR /usr/src/app

COPY . .
RUN pip install -r requirements.txt

CMD [ "python", "-u", "./dc.py"]