FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Directorio de trabajo
WORKDIR /app

# Copiar archivos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright
RUN playwright install chromium

COPY . .

# Puerto que usa Render
EXPOSE 10000

# Comando para arrancar la app
CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:10000"]