FROM mcr.microsoft.com/azurelinux/base/python:3.12
WORKDIR /app
RUN pip install --no-cache-dir pyarrow

COPY refine.py /app/refine.py
RUN chmod -R a+rX /app
ENV PYTHONUNBUFFERED=1
USER 1001
CMD ["python3", "/app/refine.py"]
