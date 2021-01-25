FROM python:3-alpine

LABEL org.opencontainers.image.source https://github.com/SENERGY-Platform/mgw-dyson-dc

RUN apk --no-cache add git gcc openssl-dev musl-dev libffi-dev

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "-u", "./dc.py"]