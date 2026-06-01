FROM python:3.11-slim

# Dependências de sistema para mysqlclient, Pillow e reportlab
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    libpq-dev \
    pkg-config \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Variáveis de ambiente — todas obrigatórias, configurar no Railway
ENV FLASK_ENV=production
ENV PORT=5000
ENV SECRET_KEY=
ENV DB_HOST=
ENV DB_PORT=3306
ENV DB_NAME=
ENV DB_USER=
ENV DB_PASS=
ENV STORK_ERP_URL=
ENV STORK_API_KEY=

EXPOSE 5000

# 1 worker no Railway gratuito — evita duplo init_db e economiza memória
CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT} \
    --workers 1 \
    --timeout 120 \
    --preload \
    --access-logfile - \
    --error-logfile -