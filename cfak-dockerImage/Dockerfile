FROM python:3.14.2-slim

RUN apt-get update && apt-get install -y curl unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN mkdir -p /app/bin

# --- DESCARGA DE HERRAMIENTAS (Esto es lo que faltaba) ---
RUN echo "Bajando AVML..." && \
    curl -L -o /app/bin/avml https://github.com/microsoft/avml/releases/download/v0.14.0/avml && \
    chmod +x /app/bin/avml

RUN echo "Bajando WinPMEM..." && \
    curl -L -o /app/bin/winpmem.exe https://github.com/Velocidex/WinPmem/releases/download/v4.0.rc1/winpmem_v4.0.rc1.exe

# --- PREPARACION DEL SCRIPT ---
RUN pip install boto3 requests
COPY main.py /app/main.py
CMD ["python", "/app/main.py"]