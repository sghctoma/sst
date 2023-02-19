FROM python:3 AS dashboard

WORKDIR /dashboard
EXPOSE 5100/tcp

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ./*.py ./
COPY ./templates ./templates/
COPY ./static ./static/

CMD ["bokeh", "serve", "--port", "5100", ".", "--args", \
     "--datastore", "/data/", \
     "--gosst_api", "http://gosst-http/8080"]