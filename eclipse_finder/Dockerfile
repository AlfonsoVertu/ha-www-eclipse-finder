FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" astronomy-engine python-multipart

# libreria model-viewer inclusa nell'immagine per l'anteprima 3D offline (.glb)
RUN mkdir -p /vendor && python -c "import urllib.request; urllib.request.urlretrieve('https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js','/vendor/model-viewer.min.js')"

COPY app.py /app.py

EXPOSE 8099
CMD ["python", "/app.py"]
