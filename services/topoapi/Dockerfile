FROM mcr.microsoft.com/azurelinux/base/python:3.12
WORKDIR /app
COPY topo_app.py /app/
COPY static /app/static
COPY aitel.py /app/
RUN chmod -R a+rX /app
ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
USER 1001
CMD ["python3", "/app/topo_app.py"]
