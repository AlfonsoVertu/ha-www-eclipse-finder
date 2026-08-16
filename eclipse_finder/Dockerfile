FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" astronomy-engine python-multipart

COPY app.py /app.py

EXPOSE 8099
CMD ["python", "/app.py"]
