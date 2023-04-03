FROM python:3.9-bullseye AS cache

WORKDIR /cache
EXPOSE 5555/tcp

COPY requirements.txt ./
RUN pip install \
	--extra-index-url https://www.piwheels.org/simple \
	--no-cache-dir -r requirements.txt
RUN apt-get update && apt-get -y install \
	libatlas-base-dev \
	libjpeg62-turbo \
	libopenjp2-7
COPY ./*.py ./

CMD ["python", "cache.py", "serve", "--database", "/data/gosst.db"]
