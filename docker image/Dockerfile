FROM python:latest
RUN mkdir /app
WORKDIR /app
COPY harporias.py /app/harporias.py
COPY haproxy_backend_server_tmpl.json /tmp/haproxy_backend_server_tmpl.json
COPY haproxy_backend_tmpl.json /tmp/haproxy_backend_tmpl.json
COPY haproxy_frontend_bind_tmpl.json /tmp/haproxy_frontend_bind_tmpl.json
COPY haproxy_frontend_tmpl.json /tmp/haproxy_frontend_tmpl.json
RUN pip install kubernetes pytz requests
CMD ["python","-u","harporias.py"]