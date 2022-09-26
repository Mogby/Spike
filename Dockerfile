FROM alpine:3.16.2

RUN apk add --update --no-cache build-base python3 python3-dev && ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools

WORKDIR /spike/
COPY . .
RUN pip install -r requirements.txt

VOLUME ./workdir:/spike/workdir

ENTRYPOINT ./docker_entrypoint.sh
