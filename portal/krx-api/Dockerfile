FROM mcr.microsoft.com/azurelinux/base/python:3.12
WORKDIR /app
RUN pip install --no-cache-dir python-pptx==1.0.2
COPY server.py /app/server.py
COPY report_service.py /app/report_service.py
COPY ai_insights.py /app/ai_insights.py
COPY seed.json /app/seed.json
COPY report /app/report
RUN chmod -R a+rX /app
ENV PYTHONUNBUFFERED=1 PORT=8080 REPORT_RULES=/app/report/WRITING-RULES.md REPORT_TEMPLATE=/app/report/Carbon-Energy-Management-Template.pptx
EXPOSE 8080
USER 1001
CMD ["python3", "/app/server.py"]
