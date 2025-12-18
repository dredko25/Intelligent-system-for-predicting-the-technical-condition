# FROM python:3.10-slim

# WORKDIR /app

# # Встановлюємо системні залежності для numpy, pandas, TensorFlow
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     libssl-dev \
#     libffi-dev \
#     libstdc++6 \
#     git \
#     && apt-get clean

# ENV TZ=Europe/Kyiv
# # Копіюємо requirements з правильного шляху
# COPY backend/requirements.txt .

# RUN pip install --upgrade pip
# RUN pip install --no-cache-dir -r requirements.txt

# COPY . .

# EXPOSE 8000

# ENV PYTHONPATH=/app:/app/backend
# # CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
# CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM python:3.10-slim

WORKDIR /app

# Встановлюємо системні залежності
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libstdc++6 \
    git \
    netcat-openbsd \
    && apt-get clean

ENV TZ=Europe/Kyiv

# Копіюємо requirements
COPY backend/requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код
COPY . .

# Робимо скрипт запуску виконуваним
RUN chmod +x backend/entrypoint.sh

EXPOSE 8000

ENV PYTHONPATH=/app:/app/backend

# Встановлюємо наш скрипт як команду запуску
ENTRYPOINT ["/app/backend/entrypoint.sh"]