from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import time
import re
import requests
import urllib3
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

def consultar_brasilapi(cnpj):
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get("descricao_situacao_cadastral", "")
            nome = data.get("razao_social", "")
            
            # Formatar o CNPJ
            cnpj_formatado = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}" if len(cnpj) == 14 else cnpj
            
            if status == "ATIVA":
                return (f"{cnpj_formatado} - {nome}", "CNPJ ATIVO NA RECEITA FEDERAL (ISENTO OU NÃO ENCONTRADO NA SEFAZ BA). APTO PARA EMISSÃO DE NFe PARA O CLIENTE.", "#ffffff", "normal")
            elif status == "BAIXADA":
                return (f"{cnpj_formatado} - {nome}", "CNPJ BAIXADO NA RECEITA FEDERAL.", "#ffcccc", "destaque")
            elif status == "INAPTA":
                return (f"{cnpj_formatado} - {nome}", "CNPJ INAPTO NA RECEITA FEDERAL. Não é possível emitir NFe para esse CNPJ.", "#ffcccc", "destaque")
            else:
                 return (f"{cnpj_formatado} - {nome}", f"Situação na Receita Federal: {status}", "#ffffff", "normal")
        else:
            return ("Situação cadastral: Não encontrada", "CNPJ não encontrado na SEFAZ e inválido na Receita Federal.", "#ffffff", "normal")
    except Exception as e:
        print(f"Erro na BrasilAPI: {e}")
        return ("Erro", "Situação cadastral não encontrada na SEFAZ. Erro ao consultar a Receita Federal.", "#ffffff", "normal")

def consultar_cnpj_sefaz(cnpj):
    # Remove pontuações
    cnpj_numeros = re.sub(r'\D', '', cnpj)
    
    url = "https://portal.sefaz.ba.gov.br/scripts/cadastro/cadastroBa/result.asp"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://portal.sefaz.ba.gov.br/scripts/cadastro/cadastroBa/consultaBa.asp"
    }

    data = {
        "sefp": "1",
        "estado": "BA",
        "CGC": cnpj_numeros,
        "B1": "CNPJ  ->        "
    }
    
    try:
        session = requests.Session()
        session.get("https://portal.sefaz.ba.gov.br/scripts/cadastro/cadastroBa/consultaBa.asp", verify=False, timeout=10)
        
        response = session.post(url, data=data, headers=headers, verify=False, timeout=10)
        response.encoding = 'ISO-8859-1' 
        
        page = response.text
        
        if "consulta_vazia.htm" in response.url or "consulta_vazia.htm" in page:
            return consultar_brasilapi(cnpj_numeros)
            
        # Converter para BeautifulSoup para extração limpa de texto
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page, "html.parser")
        texto_limpo = soup.get_text(separator=" ").replace('\xa0', ' ')

        if "Situação Cadastral" in texto_limpo:
            # Extrair Nome (Razão Social)
            nome = ""
            match_nome = re.search(r'Razão Social:\s*(.+?)(?=\s{2,}|\n|$)', texto_limpo, re.IGNORECASE)
            if match_nome:
                nome = match_nome.group(1).strip()
            
            cnpj_formatado = f"{cnpj_numeros[:2]}.{cnpj_numeros[2:5]}.{cnpj_numeros[5:8]}/{cnpj_numeros[8:12]}-{cnpj_numeros[12:]}" if len(cnpj_numeros) == 14 else cnpj_numeros
            
            if "ATIVO" in texto_limpo:
                if "Inscrição Estadual" in texto_limpo:
                    match_ie = re.search(r'Inscrição Estadual:\s*([\d\.\-]+)', texto_limpo, re.IGNORECASE)
                    if match_ie:
                        ie = match_ie.group(1).strip()
                        return (f"{cnpj_formatado} - {nome}", f"CNPJ ATIVO NA SEFAZ. Inscrição Estadual: {ie}. APTO PARA EMISSÃO DE NFe.", "#ffffff", "normal")
                    else:
                        return (f"{cnpj_formatado} - {nome}", "CNPJ ATIVO NA SEFAZ. IE não localizada.", "#ffffff", "normal")
            elif "BAIXADO" in texto_limpo:
                return consultar_brasilapi(cnpj_numeros)
            elif "INAPTO" in texto_limpo:
                return (f"{cnpj_formatado} - {nome}", "CNPJ INAPTO na Sefaz. Não é possível emitir NFe para esse CNPJ.", "#ffcccc", "destaque")
                
        return consultar_brasilapi(cnpj_numeros)

    except Exception as e:
        print(f"Erro na consulta: {e}") 
        return ("Erro", f"Erro ao consultar: {e}", "#ffffff", "normal")

# ----------------------------------------------------
# COMPONENTES HTML REUSÁVEIS
# ----------------------------------------------------
def template_base(titulo, conteudo, cor_fundo="#eafaf1", cor_texto="#000000"):
    footer_html = """
    <footer>
        <div class="footer-content">
            <p>&copy; 2026 Michel S Rebouças. Todos os direitos reservados.</p>
            <div class="social-links">
                <a href="https://www.linkedin.com/in/michel-santos-rebouças-5a81b561/" target="_blank" title="LinkedIn">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
                </a>
                <a href="https://www.instagram.com/satosmichel_oficial" target="_blank" title="Instagram">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                </a>
                <a href="https://api.whatsapp.com/send/?phone=5571987364775&text&type=phone_number&app_absent=0" target="_blank" title="WhatsApp">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12.031 0c-6.627 0-12.031 5.405-12.031 12.031 0 2.628.847 5.05 2.274 7l-1.66 6.075 6.22-1.631c1.9.1.868 2.053 5.197 2.053 6.628 0 12.032-5.406 12.032-12.032s-5.404-12.031-12.032-12.031zm5.882 17.203c-.266.746-1.531 1.441-2.11 1.523-.538.077-1.226.155-3.92-1.028-3.235-1.423-5.321-4.721-5.485-4.945-.164-.225-1.31-1.745-1.31-3.328 0-1.583.823-2.368 1.119-2.68.297-.312.646-.39.86-.39s.427.001.625.009c.198.009.465-.075.728.563.264.639.902 2.214.985 2.384.082.17.135.372.036.567-.099.195-.152.312-.298.483-.146.17-.308.384-.442.502-.143.125-.292.264-.131.542.161.277.718 1.185 1.54 1.918 1.059.946 1.956 1.24 2.235 1.383.279.143.442.12.607-.066.164-.187.715-.826.906-1.11.19-.283.382-.236.634-.143.252.093 1.594.75 1.867.886.273.136.455.204.521.318.066.115.066.666-.2 1.412z"/></svg>
                </a>
            </div>
        </div>
    </footer>
    """
    
    css_global = """
    * {
        box-sizing: border-box;
    }
    body {
        background-color: """ + cor_fundo + """;
        font-family: 'Segoe UI', Arial, sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        margin: 0;
        color: """ + cor_texto + """;
        transition: background-color 0.3s ease;
    }
    .container {
        width: 100%;
        max-width: 600px;
        background-color: white;
        padding: 40px;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 80px; /* Space for footer */
        color: #333;
    }
    h2 {
        color: #2c3e50;
        margin-bottom: 25px;
    }
    .input-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 15px;
        margin-bottom: 20px;
    }
    input[type="text"] {
        padding: 12px;
        width: 100%;
        max-width: 300px;
        font-size: 16px;
        border-radius: 6px;
        border: 1px solid #ccc;
        outline: none;
        transition: border-color 0.2s;
    }
    input[type="text"]:focus {
        border-color: #4CAF50;
    }
    input[type="submit"], .btn {
        padding: 12px 24px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 16px;
        cursor: pointer;
        text-decoration: none;
        font-weight: bold;
        transition: background-color 0.3s, transform 0.1s;
        display: inline-block;
    }
    input[type="submit"]:hover, .btn:hover {
        background-color: #45a049;
    }
    input[type="submit"]:active, .btn:active {
        transform: scale(0.98);
    }
    
    /* Footer styles */
    footer {
        position: fixed;
        bottom: 0;
        width: 100%;
        background-color: #0f172a;
        color: #94a3b8;
        padding: 15px 0;
        font-size: 14px;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    }
    .footer-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
    }
    .footer-content p {
        margin: 0;
    }
    .social-links {
        display: flex;
        gap: 15px;
    }
    .social-links a {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #cbd5e1;
        background-color: rgba(255,255,255,0.05);
        padding: 8px;
        border-radius: 50%;
        transition: color 0.3s, background-color 0.3s;
    }
    .social-links a:hover {
        color: #fff;
        background-color: rgba(255,255,255,0.15);
    }
    
    /* Selection Cards */
    .cards-container {
        display: flex;
        gap: 20px;
        justify-content: center;
        margin-top: 30px;
    }
    .card {
        flex: 1;
        padding: 30px 20px;
        border-radius: 10px;
        border: 2px solid #e2e8f0;
        cursor: pointer;
        text-decoration: none;
        color: #334155;
        transition: all 0.3s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 15px;
    }
    .card:hover {
        border-color: #4CAF50;
        box-shadow: 0 4px 12px rgba(76, 175, 80, 0.15);
        transform: translateY(-5px);
    }
    .card h3 {
        margin: 0;
        font-size: 20px;
    }
    .card p {
        margin: 0;
        font-size: 14px;
        color: #64748b;
    }
    
    /* Financeiro Detail Layout */
    .ficha {
        text-align: left;
        width: 100%;
        font-size: 15px;
    }
    .ficha-row {
        margin-bottom: 12px;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 8px;
    }
    .ficha-label {
        font-weight: bold;
        color: #475569;
        display: block;
        margin-bottom: 4px;
    }
    .ficha-value {
        color: #0f172a;
    }
    .qsa-list {
        margin: 0;
        padding-left: 20px;
    }
    """

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{titulo}</title>
        <style>{css_global}</style>
    </head>
    <body>
        <div class="container">
            {conteudo}
        </div>
        {footer_html}
    </body>
    </html>
    """

def format_cnpj(cnpj):
    cnpj = re.sub(r'\D', '', cnpj)
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj

# ----------------------------------------------------
# LÓGICA DE DADOS (FINANCEIRO E VENDEDOR)
# ----------------------------------------------------
def consultar_ficha_financeira(cnpj):
    cnpj_numeros = re.sub(r'\D', '', cnpj)
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_numeros}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # Extraindo campos
            cnpj_f = format_cnpj(data.get("cnpj", cnpj_numeros))
            razao = data.get("razao_social", "N/A")
            data_abertura = data.get("data_inicio_atividade", "N/A")
            telefone = data.get("ddd_telefone_1", "N/A")
            status = data.get("descricao_situacao_cadastral", "")
            
            # Endereço
            end_parts = [
                data.get("logradouro", ""),
                data.get("numero", ""),
                data.get("complemento", ""),
                data.get("bairro", ""),
                data.get("municipio", ""),
                data.get("uf", ""),
                data.get("cep", "")
            ]
            endereco = ", ".join([p for p in end_parts if p])
            
            # QSA (Quadro Societário)
            qsa_data = data.get("qsa", [])
            socios = [socio.get("nome_socio", "") for socio in qsa_data if socio.get("nome_socio")]
            
            if not socios:
                socios_html = "Sem informações de quadro societário."
            else:
                socios_html = "<ul class='qsa-list'>" + "".join([f"<li>{s}</li>" for s in socios]) + "</ul>"
                
            # Cores
            cor_fundo = "#d4edda" if status == "ATIVA" else "#f8d7da" # Verde claro vs Vermelho claro
            
            conteudo_ficha = f"""
            <div class="ficha">
                <div class="ficha-row"><span class="ficha-label">📌 CNPJ:</span> <span class="ficha-value">{cnpj_f}</span></div>
                <div class="ficha-row"><span class="ficha-label">🏢 Razão Social:</span> <span class="ficha-value">{razao}</span></div>
                <div class="ficha-row"><span class="ficha-label">🚦 Situação:</span> <span class="ficha-value"><strong>{status}</strong></span></div>
                <div class="ficha-row"><span class="ficha-label">📅 Data de Abertura:</span> <span class="ficha-value">{data_abertura}</span></div>
                <div class="ficha-row"><span class="ficha-label">📞 Telefone:</span> <span class="ficha-value">{telefone}</span></div>
                <div class="ficha-row"><span class="ficha-label">📍 Endereço:</span> <span class="ficha-value">{endereco}</span></div>
                <div class="ficha-row"><span class="ficha-label">👥 Quadro Societário:</span> <span class="ficha-value">{socios_html}</span></div>
            </div>
            """
            return template_base("Ficha Cadastral", f"<h2>Ficha Completa (RFB)</h2>{conteudo_ficha}<br><br><a href='/' class='btn'>Voltar ao Início</a>", cor_fundo)
            
        else:
            return template_base("Erro", "<h2>Erro na Consulta</h2><p>CNPJ não encontrado na Receita Federal ou formato inválido.</p><br><a href='/' class='btn'>Voltar ao Início</a>", "#f8d7da")
    except Exception as e:
        return template_base("Erro", f"<h2>Erro</h2><p>Falha ao conectar na API: {e}</p><br><a href='/' class='btn'>Voltar ao Início</a>", "#f8d7da")


# ----------------------------------------------------
# ROTAS DA APLICAÇÃO
# ----------------------------------------------------
@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
def home():
    conteudo = """
    <h2>Consulta de CNPJ</h2>
    <p style="color: #64748b; margin-bottom: 30px;">Selecione o seu perfil de uso para continuar:</p>
    
    <div class="cards-container">
        <a href="/vendedor" class="card">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
            <h3>Vendedor</h3>
            <p>Consulta na SEFAZ focada em permissão para emissão de NFe.</p>
        </a>
        
        <a href="/financeiro" class="card">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <h3>Financeiro</h3>
            <p>Ficha cadastral completa com dados da Receita Federal (QSA, Sócios).</p>
        </a>
    </div>
    """
    return template_base("Consulta CNPJ - Home", conteudo)


@app.get("/vendedor", response_class=HTMLResponse)
def form_vendedor():
    conteudo = """
    <h2>Perfil: VENDEDOR (SEFAZ BA)</h2>
    <form method="post" action="/vendedor">
        <div class="input-group">
            <input type="text" name="cnpj" placeholder="Digite o CNPJ" required>
            <input type="submit" value="Consultar Sefaz">
        </div>
    </form>
    <a href="/" style="color:#64748b; font-size:14px; margin-top:10px; display:inline-block;">← Voltar</a>
    """
    return template_base("Consulta Vendedor", conteudo)


@app.post("/vendedor", response_class=HTMLResponse)
def resultado_vendedor(cnpj: str = Form(...)):
    titulo, info, cor_fundo, estilo = consultar_cnpj_sefaz(cnpj)

    if cor_fundo == "#ffffff":
        cor_fundo_tela = "#d4edda" if "ATIVO" in titulo or "ATIVO" in info else "#eafaf1"
    elif cor_fundo == "#ffcccc" or estilo == "destaque":
        cor_fundo_tela = "#f8d7da" # Vermelho claro
    else:
        cor_fundo_tela = "#eafaf1"

    conteudo = f"""
    <h2 style="color: {'#b30000' if cor_fundo_tela == '#f8d7da' else '#2c3e50'};">{titulo}</h2>
    <p style="font-size: 18px; line-height: 1.5;">{info}</p>
    <br><br>
    <a href="/vendedor" class="btn" style="margin-right: 10px;">Nova Consulta</a>
    <a href="/" class="btn" style="background-color: #64748b;">Início</a>
    """
    return template_base("Resultado Sefaz", conteudo, cor_fundo_tela)


@app.get("/financeiro", response_class=HTMLResponse)
def form_financeiro():
    conteudo = """
    <h2>Perfil: FINANCEIRO (RFB)</h2>
    <form method="post" action="/financeiro">
        <div class="input-group">
            <input type="text" name="cnpj" placeholder="Digite o CNPJ" required>
            <input type="submit" value="Gerar Ficha Completa">
        </div>
    </form>
    <a href="/" style="color:#64748b; font-size:14px; margin-top:10px; display:inline-block;">← Voltar</a>
    """
    return template_base("Consulta Financeira", conteudo)


@app.post("/financeiro", response_class=HTMLResponse)
def resultado_financeiro(cnpj: str = Form(...)):
    return consultar_ficha_financeira(cnpj)