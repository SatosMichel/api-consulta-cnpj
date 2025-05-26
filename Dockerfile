FROM python:3.11-slim

# Instalar dependências básicas do sistema e ferramentas necessárias
# Incluindo 'jq' para parsear JSON e 'libnss3', 'libgconf-2-4', 'libxi6' para o Chrome
RUN apt-get update && \
    apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    jq \
    libnss3 \
    libgconf-2-4 \
    libxi6 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Instalar o Google Chrome Stable
# Esta etapa adiciona o repositório oficial do Google Chrome e instala a versão estável mais recente.
# É a forma mais robusta de garantir que você tenha um Chrome funcional e atualizado.
RUN wget -O- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor | tee /etc/apt/keyrings/google-chrome.gpg > /dev/null && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list > /dev/null && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Baixar e instalar o ChromeDriver compatível com a versão do Chrome que acabou de ser instalada.
# Este é o ponto crucial para resolver o erro de incompatibilidade.
RUN CHROME_VERSION_FULL=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+') && \
    CHROME_MAJOR_VERSION=$(echo "$CHROME_VERSION_FULL" | grep -oP '^\d+') && \
    echo "Versão do Chrome detectada: ${CHROME_VERSION_FULL}" && \
    echo "Versão Major do Chrome detectada: ${CHROME_MAJOR_VERSION}" && \
    \
    # Busca a URL de download do ChromeDriver compatível usando o endpoint da Google
    # Este endpoint retorna um JSON com as últimas versões "boas" de Chrome/ChromeDriver
    DRIVER_INFO_URL="https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" && \
    DRIVER_DOWNLOAD_URL=$(curl -s "$DRIVER_INFO_URL" | jq -r ".versions[] | select(.version | startswith(\"${CHROME_MAJOR_VERSION}.\")) | .downloads.chromedriver[] | select(.platform == \"linux64\") | .url") && \
    \
    if [ -z "$DRIVER_DOWNLOAD_URL" ]; then \
        echo "Erro: Não foi possível encontrar a URL de download do ChromeDriver para a versão principal ${CHROME_MAJOR_VERSION}. Verifique ${DRIVER_INFO_URL}"; \
        exit 1; \
    fi && \
    \
    echo "Baixando ChromeDriver de: ${DRIVER_DOWNLOAD_URL}" && \
    wget -O /tmp/chromedriver.zip "${DRIVER_DOWNLOAD_URL}" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -r /usr/local/bin/chromedriver-linux64 && \
    rm /tmp/chromedriver.zip

# Definir variáveis de ambiente para o Chrome e ChromeDriver
# Garante que o chromedriver e o google-chrome estejam no PATH do sistema.
ENV PATH="${PATH}:/usr/local/bin:/usr/bin"

# Diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia todos os arquivos da aplicação para o diretório de trabalho
COPY . .

# Instala as dependências Python listadas em requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Porta que a aplicação FastAPI vai expor
EXPOSE 8000

# Comando para iniciar o servidor FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]