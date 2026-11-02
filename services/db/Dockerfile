FROM mcr.microsoft.com/azurelinux/base/python:3.12
WORKDIR /app
RUN pip install --no-cache-dir python-tds certifi "pyOpenSSL==24.2.1"
COPY runner.py db0*.sql db1*.sql grants.sql.tpl /app/
RUN chmod -R a+rX /app
ENV PYTHONUNBUFFERED=1
USER 1001
CMD ["python3", "/app/runner.py"]
