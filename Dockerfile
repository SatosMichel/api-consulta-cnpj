# Usa imagem com Chrome e ChromeDriver já instalados
FROM python:3.10-slim

# Instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    libgbm1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Instala o Google Chrome
RUN wget -O chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i chrome.deb || apt-get -fy install && \
    rm chrome.deb

# Instala o ChromeDriver compatível com o Chrome
RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+') && \
    DRIVER_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION) && \
    wget https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Define variáveis de ambiente para Chrome
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Cria diretório da aplicação
WORKDIR /app

# Copia os arquivos do projeto
COPY . .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Expondo a porta do FastAPI
EXPOSE 8000

# Comando para iniciar o FastAPI com uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
