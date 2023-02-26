FROM python:3.9-bullseye AS dashboard

WORKDIR /dashboard
EXPOSE 5100/tcp

COPY requirements.txt ./
RUN pip install \
	--extra-index-url https://www.piwheels.org/simple \
	--no-cache-dir -r requirements.txt
RUN apt-get update && apt-get -y install \
	libatlas-base-dev \
	libjpeg62-turbo \
	libopenjp2-7
COPY ./*.py ./
COPY ./templates ./templates/
COPY ./static ./static/

CMD ["bokeh", "serve", "--port", "5100", ".", "--args", \
     "--database", "/data/gosst.db", \
     "--gosst_api", "http://gosst-http:8080"]