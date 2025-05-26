FROM python:3.11-slim

# Instalar dependências necessárias para o Chrome Headless
# Nota: libnss3, libgconf-2-4, libxi6, libgconf-2-4 são algumas das dependências comuns.
# Para evitar erros de "missing shared libraries", inclua-as.
RUN apt-get update && \
    apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    libnss3 \
    libgconf-2-4 \
    libxi6 \
    libgconf-2-4 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Baixar e instalar Google Chrome stable (headless)
# A versão do Chrome precisa ser compatível com o ChromeDriver
# É mais robusto baixar o .deb diretamente
RUN CHROME_VERSION="125.0.6422.60" && \
    wget https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION}-1_amd64.deb -O /tmp/chrome.deb && \
    dpkg -i /tmp/chrome.deb || apt-get install -fy && \
    rm /tmp/chrome.deb

# Baixar e instalar ChromeDriver compatível
# É crucial que a versão do ChromeDriver seja compatível com a versão do Chrome
# Você pode consultar a compatibilidade em https://chromedriver.chromium.org/downloads
RUN CHROME_VERSION_MAJOR=$(google-chrome --version | grep -oP '\d+') && \
    DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_$CHROME_VERSION_MAJOR") && \
    wget -O /tmp/chromedriver.zip "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$DRIVER_VERSION/linux64/chromedriver-linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -r /usr/local/bin/chromedriver-linux64 && \
    rm /tmp/chromedriver.zip

# Definir variáveis de ambiente para o Chrome e ChromeDriver
ENV PATH="${PATH}:/usr/local/bin"

# Diretório de trabalho
WORKDIR /app

# Copia os arquivos da aplicação
COPY . .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Porta exposta
EXPOSE 8000

# Comando para iniciar o servidor FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]