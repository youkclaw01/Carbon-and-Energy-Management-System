FROM mcr.microsoft.com/azurelinux/base/python:3.12
WORKDIR /app
RUN pip install --no-cache-dir python-tds certifi "pyOpenSSL==24.2.1"
COPY evid_app.py evid_core.py /app/
COPY aitel.py /app/
RUN chmod -R a+rX /app
ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
USER 1001
CMD ["python3", "/app/evid_app.py"]
