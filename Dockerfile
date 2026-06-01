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

# Variáveis de ambiente — Railway sobrescreve em runtime
ENV FLASK_ENV=production
ENV PORT=5000
ENV SECRET_KEY=change-me-in-railway
ENV DB_HOST=localhost
ENV DB_PORT=3306
ENV DB_NAME=estoque
ENV DB_USER=root
ENV DB_PASS=
ENV STORK_ERP_URL=https://erpstork-production.up.railway.app
ENV STORK_API_KEY=

EXPOSE 5000

# Gunicorn com 2 workers — adequado para Railway Hobby
CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT} \
    --workers 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
