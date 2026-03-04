# API & Interface de Consulta CNPJ (SEFAZ-BA e Receita Federal) 🏢🚀

Este projeto é uma aplicação web completa e otimizada (construída com **FastAPI** e **Python**) que permite aos usuários consultarem a situação de um CNPJ de forma rápida, segura e sem captchas chatos.

A aplicação nasceu da necessidade de consultar a aptidão de empresas para **Emissão de Notas Fiscais (NFe)** no estado da Bahia, mas foi expandida para incluir um módulo completo de **Ficha Financeira Nacional** através de dados públicos da Receita Federal.

---

## ✨ Funcionalidades

O sistema foi dividido em duas grandes opções de perfil:

1. **VENDEDOR (Consulta Estadual - SEFAZ BA)**
   * Focado em validar se a empresa alvo está apta para emitir notas fiscais.
   * Realiza um parse profundo e inteligente no site da Sefaz-BA usando `BeautifulSoup` para desviar de bloqueios.
   * Informa a Situação Cadastral (Ativo, Baixado, Inapto) de forma visual.
   * Busca automaticamente a **Inscrição Estadual** vigente (fundamental para faturamento remoto e e-commerce).

2. **FINANCEIRO (Consulta Federal - BrasilAPI / RFB)**
   * Focado na inteligência de crédito e cadastro completo de fornecedores/clientes.
   * Consome a excelente `BrasilAPI` para trazer todos os dados primários do CNPJ.
   * Traz as informações organizadas numa Ficha Limpa: Razão Social, Data de Abertura, Situação Ativa/Inativa, Endereço formatado e Telefones comerciais oficiais.
   * Módulo especial em HTML para exibir uma listagem com os nomes de todos os **SÓCIOS** (Quadro Societário - QSA).

## ⚡ Tecnologias Utilizadas

A aplicação substituiu bibliotecas extremamente pesadas (como Selenium/ChromeDriver) por requisições HTTP ultrarrápidas, derrubando o consumo de RAM no servidor para menos de 50MB.

* **Python 3.10+**
* **FastAPI** (Micro-framework web absurdamente rápido)
* **Requests & BeautifulSoup4** (Para extração e formatação cirúrgica de dados online)
* **Uvicorn** (Servidor ASGI)
* **HTML5 e CSS3** (Front-end responsivo renderizado via Jinja/F-Strings, dispensando frameworks pesados no cliente)

---

## 🚀 Como instalar e rodar (Localmente)

1. Clone o repositório em sua máquina:
   ```bash
   git clone https://github.com/SEU_USUARIO/api-consulta-cnpj.git
   cd api-consulta-cnpj
   ```

2. Crie e ative um ambiente virtual (opcional mas recomendado):
   ```bash
   python -m venv venv
   # No Windows:
   venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```

3. Instale as dependências contidas no `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

4. Suba o servidor Uvicorn:
   ```bash
   uvicorn main:app --reload
   ```

5. Acesse na sua máquina a página principal:
   `http://127.0.0.1:8000/`

---

## ☁️ Como Fazer o Deploy Fácil no Render.com (Gratuito)

Uma grande vantagem dessa reestruturação é que ela roda solta na camada gratuita do **Render**. Siga esses passos para colocar a API no ar para o mundo:

1. Crie uma conta no [Render](https://render.com/).
2. Faça "Fork" ou suba esse repositório no seu próprio perfil do GitHub.
3. No painel do Render, clique em **New** > **Web Service**.
4. Conecte sua conta do GitHub e selecione este repositório.
5. Em **Runtime**, escolha `Python`.
6. Em **Build Command**, coloque:
   `pip install -r requirements.txt`
7. Em **Start Command**, coloque:
   `uvicorn main:app --host 0.0.0.0 --port $PORT`
8. Aceite o plano Free e clique em *Create Web Service*.

Após poucos minutos, sua plataforma de consulta já terá um link público (Ex: `https://meu-cnpj-app.onrender.com`).

---

## 🎨 Design Atualizado

O UX/UI foi refinado para ser extremamente acessível a usuários corporativos:
- **Redimensionamento fixo:** As caixas de pesquisa e de resultado não sofrem glitches de tamanho, garantindo paz visual.
- **Card-Selector:** Menus autoexplicativos na página inicial divididos por intenção do usuário.
- **Sistema de Semáforo:** Se o CNPJ for Inapto, a tela ganha uma pigmentação de alerta avermelhada. Se for Ativo, tons calmos de verde e branco tomam conta da tela.

---

## 👨‍💻 Autor

Feito com dedicação por **Michel S Rebouças**:

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/michel-santos-rebouças-5a81b561/)
[![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://www.instagram.com/satosmichel_oficial)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)](https://api.whatsapp.com/send/?phone=5571987364775&text&type=phone_number&app_absent=0)

*Sinta-se à vontade para enviar um "Oi" se este projeto salvou a vida do seu faturamento!* 🤝
