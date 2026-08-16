FROM python:3.12-slim

# uvicorn "puro" (asyncio/h11, tutto Python) invece di [standard]: evita uvloop/httptools
# (estensioni C senza wheel su armv7/i386) così l'add-on compila su tutte le arch dichiarate
RUN pip install --no-cache-dir fastapi uvicorn astronomy-engine python-multipart

# librerie 3D incluse nell'immagine per rendering offline (.glb):
# model-viewer per l'anteprima del singolo mobile, three.js (+loader/controls) per la casa 3D
RUN mkdir -p /vendor && python -c "import urllib.request as u; [u.urlretrieve(url,'/vendor/'+n) for n,url in {'model-viewer.min.js':'https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js','three.min.js':'https://unpkg.com/three@0.128.0/build/three.min.js','GLTFLoader.js':'https://unpkg.com/three@0.128.0/examples/js/loaders/GLTFLoader.js','OrbitControls.js':'https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js','GLTFExporter.js':'https://unpkg.com/three@0.128.0/examples/js/exporters/GLTFExporter.js'}.items()]"

COPY app.py /app.py

EXPOSE 8099
CMD ["python", "/app.py"]
