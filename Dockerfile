FROM python:3.11-slim

# Instalar TODAS as dependências que o Google Chrome Stable precisa
# Esta é a lista mais abrangente de dependências para o Chrome em Debian/Ubuntu.
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
    libxcomposite1 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    fonts-liberation \
    xxd \
    # Dependências adicionais essenciais para o Chrome que faltavam
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libu2f-udev \
    libvulkan1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Definir a versão específica do Chrome para instalação
# Mantemos a versão 125 para compatibilidade garantida com o ChromeDriver
ARG CHROME_VERSION="125.0.6422.60"

# Instalar o Google Chrome Stable (versão específica)
# Agora, o dpkg deve ter todas as dependências pré-instaladas
RUN wget https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION}-1_amd64.deb -O /tmp/chrome.deb && \
    dpkg -i /tmp/chrome.deb && \
    rm /tmp/chrome.deb

# Verificar se o Chrome está presente e onde. Isso DEVE funcionar agora.
RUN which google-chrome && google-chrome --version

# Baixar e instalar ChromeDriver compatível
# Mantenha a versão fixa e a URL direta que sabemos que funciona para Chrome 125
RUN CHROMEDRIVER_VERSION="125.0.6422.141" && \
    CHROMEDRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
    echo "Baixando ChromeDriver ${CHROMEDRIVER_VERSION} de: ${CHROMEDRIVER_URL}" && \
    wget -O /tmp/chromedriver.zip "${CHROMEDRIVER_URL}" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -r /usr/local/bin/chromedriver-linux64 && \
    rm /tmp/chromedriver.zip

# Definir variáveis de ambiente para o Chrome e ChromeDriver
ENV PATH="/usr/local/bin:/usr/bin:${PATH}" 
# Garante que /usr/local/bin e /usr/bin estejam no início do PATH
ENV CHROME_BINARY_LOCATION="/usr/bin/google-chrome" 
# Explicitamente informa ao Selenium onde está o binário
ENV DISPLAY=":99" 
# Necessário para alguns sistemas, mesmo em headless

# Define o diretório de trabalho dentro do contêiner para /app
WORKDIR /app

# Copia todos os arquivos da sua aplicação para o diretório de trabalho.
COPY . .

# Instala as dependências Python listadas em requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Porta que a aplicação FastAPI vai expor.
EXPOSE 8000

# Comando para iniciar o servidor FastAPI quando o contêiner for executado.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]