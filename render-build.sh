#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Installing Chrome and ChromeDriver ---"

# Install dependencies
apt-get update && apt-get install -y \
    wget \
    unzip \
    fonts-liberation \
    libappindicator1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxft2 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Download and install Google Chrome Stable
CHROME_VERSION="125.0.6422.60" # Versão do Chrome que você está usando
wget -q https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION}-1_amd64.deb -O /tmp/chrome.deb
dpkg -i /tmp/chrome.deb || apt-get install -fy # Instala o Chrome e resolve dependências se necessário
rm /tmp/chrome.deb

# Download and install ChromeDriver
CHROMEDRIVER_VERSION="125.0.6422.141" # Versão do ChromeDriver compatível
wget -q https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip -O /tmp/chromedriver.zip
unzip -q /tmp/chromedriver.zip -d /usr/local/bin/
mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
chmod +x /usr/local/bin/chromedriver
rm -r /usr/local/bin/chromedriver-linux64
rm /tmp/chromedriver.zip

echo "--- Chrome and ChromeDriver installed ---"

# Set environment variables for Selenium (Render will pick these up)
echo "export CHROME_BINARY_LOCATION=/usr/bin/google-chrome" >> ~/.bashrc
echo "export PATH=$PATH:/usr/local/bin" >> ~/.bashrc
echo "export DISPLAY=:99" >> ~/.bashrc # For headless, often still needed