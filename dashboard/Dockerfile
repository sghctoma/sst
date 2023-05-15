# -- build image

FROM node:20.0-bullseye-slim as build

WORKDIR /usr/src/app
COPY frontend/ /usr/src/app/
RUN npm install && npm run build

# -- prod image

FROM python:3.9-slim-bullseye AS dashboard

WORKDIR /dashboard
EXPOSE 5000/tcp

COPY requirements.txt ./
RUN pip install \
	--extra-index-url https://www.piwheels.org/simple \
	--no-cache-dir -r requirements.txt
RUN apt-get update && apt-get -y install \
	libatlas-base-dev \
	libjpeg62-turbo \
	libopenjp2-7

COPY ./app ./app
COPY ./dashboard.py ./dashboard.py
COPY --from=build /usr/src/app/static/main.js ./app/static/

ENV FLASK_SQLALCHEMY_DATABASE_URI=sqlite:////data/sst.db
ENV FLASK_GOSST_HTTP_API=http://gosst-http:8080
ENV FLASK_JWT_PRIVATE_KEY_FILE=/data/private_key.pem
ENV FLASK_JWT_PUBLIC_KEY_FILE=/data/public_key.pem
ENV PYTHONUNBUFFERED=1

CMD flask init && gunicorn dashboard:app --bind 0.0.0.0:5000 --worker-class eventlet --workers 1
