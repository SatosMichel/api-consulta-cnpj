from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import os
import time
import re # Adicionado para expressões regulares na extração da Inscrição Estadual

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Função para iniciar o driver do Selenium
# MUITO IMPORTANTE: Usamos o caminho exato do chromedriver que vamos instalar no Dockerfile
def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")              # Executa o Chrome sem interface gráfica
    chrome_options.add_argument("--no-sandbox")            # Essencial para rodar no Docker
    chrome_options.add_argument("--disable-dev-shm-usage") # Reduz problemas de memória
    chrome_options.add_argument("--disable-gpu")           # Desativa uso da GPU
    chrome_options.add_argument("--window-size=1920,1080") # Define o tamanho da janela virtual

    # Força o Selenium a usar o ChromeDriver que instalamos em /usr/local/bin
    service = Service(executable_path="/usr/local/bin/chromedriver") # ESTA É A LINHA CRÍTICA!

    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def consultar_cnpj_sefaz(cnpj):
    driver = None # Inicializa driver como None
    try:
        driver = get_chrome_driver() # Inicia um novo driver para cada consulta
        driver.get("https://portal.sefaz.ba.gov.br/scripts/cadastro/cadastroBa/consultaBa.asp")
        time.sleep(2)

        campo_cnpj = driver.find_element(By.NAME, "CGC")
        campo_cnpj.send_keys(cnpj)

        botao = driver.find_element(By.NAME, "B1")
        botao.click()

        time.sleep(3)

        if "consulta_vazia.htm" in driver.current_url:
            return ("CNPJ - Ativo", "ISENTO - de Inscrição Estadual", "#ffffff", "normal")

        if "result.asp" in driver.current_url:
            page = driver.page_source

            if "Situação Cadastral Vigente" in page:
                inicio = page.find("Situação Cadastral Vigente")
                trecho = page[inicio:inicio+500]

                if "ATIVO" in trecho:
                    if "Inscrição Estadual" in page:
                        inicio_ie = page.find("Inscrição Estadual")
                        trecho_ie = page[inicio_ie:inicio_ie+150]
                        
                        # Usando regex para uma extração mais robusta da Inscrição Estadual
                        match = re.search(r'Inscrição Estadual[\s\S]*?<td>\s*(\d+)\s*</td>', trecho_ie)
                        if match:
                            ie = match.group(1).strip()
                            return ("CNPJ - Ativo", f"Inscrição Estadual: {ie}", "#ffffff", "normal")
                        else:
                             return ("CNPJ - Ativo", "Inscrição Estadual não encontrada", "#ffffff", "normal")

                elif "BAIXADO" in trecho:
                    return ("CNPJ - Ativo", "ISENTO - de Inscrição Estadual", "#ffffff", "normal")

                elif "INAPTO" in trecho:
                    return ("CNPJ - INAPTO na Sefaz", "Não é possível emitir NFe para esse CNPJ.", "#ffcccc", "destaque")

        return ("Erro", "Não foi possível consultar o CNPJ.", "#ffffff", "normal")

    except Exception as e:
        print(f"Erro na consulta: {e}") # Para ver o erro no terminal do Docker
        return ("Erro", f"Erro ao consultar: {e}", "#ffffff", "normal")

    finally:
        if driver: # Garante que o driver só será fechado se tiver sido inicializado
            driver.quit()

@app.get("/", response_class=HTMLResponse)
def formulario():
    return """
    <html>
        <head>
            <title>Consulta CNPJ - SEFAZ BA</title>
            <style>
                body {
                    background-color: #eafaf1;
                    font-family: Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }
                form {
                    background-color: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }
                input[type="text"] {
                    padding: 10px;
                    width: 250px;
                    margin-bottom: 15px;
                    font-size: 16px;
                    border-radius: 6px;
                    border: 1px solid #ccc;
                }
                input[type="submit"] {
                    padding: 10px 20px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 16px;
                    cursor: pointer;
                }
                input[type="submit"]:hover {
                    background-color: #45a049;
                }
                footer {
                    position: fixed;
                    bottom: 10px;
                    text-align: center;
                    width: 100%;
                    color: #555;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <form method="post">
                <h2>Consulta de CNPJ - SEFAZ BA</h2>
                <input type="text" name="cnpj" placeholder="Digite o CNPJ" required><br>
                <input type="submit" value="Consultar">
            </form>
            <footer>
                Desenvolvido por @satosmichel_oficial.
            </footer>
        </body>
    </html>
    """

@app.post("/", response_class=HTMLResponse)
def resultado(cnpj: str = Form(...)):
    titulo, info, cor_fundo, estilo = consultar_cnpj_sefaz(cnpj)

    cor_texto = "#000000"
    if estilo == "destaque":
        cor_texto = "#b30000"

    return f"""
    <html>
        <head>
            <title>Resultado da Consulta</title>
            <style>
                body {{
                    background-color: {cor_fundo};
                    font-family: Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    color: {cor_texto};
                }}
                .resultado {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                a {{
                    display: inline-block;
                    margin-top: 20px;
                    padding: 10px 20px;
                    background-color: #4CAF50;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                }}
                a:hover {{
                    background-color: #45a049;
                }}
                footer {{
                    position: fixed;
                    bottom: 10px;
                    text-align: center;
                    width: 100%;
                    color: #555;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="resultado">
                <h2>{titulo}</h2>
                <p>{info}</p>
                <a href="/">Voltar</a>
            </div>
            <footer>
                Desenvolvido por @satosmichel_oficial.
            </footer>
        </body>
    </html>
    """