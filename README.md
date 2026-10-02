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

### Restrição de acesso Comercial

A tela Comercial e todas as rotas `/api` exigem uma sessão autenticada. A sessão expira após 12 horas, usa cookie `HttpOnly`/`SameSite=Lax` e é marcada `Secure` quando servida por HTTPS. Usuário, senha e segredo de assinatura são lidos somente do ambiente.

Configure estes secrets no Render em **Environment Variables**:

* `COMERCIAL_USERNAME`: `administrador`
* `COMERCIAL_PASSWORD`: a senha definida para a conta; armazene somente como secret do Render, nunca no código, README ou Git.
* `COMERCIAL_SESSION_SECRET`: segredo aleatório com pelo menos 32 caracteres. Gere um valor com:
   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

Salve e faça redeploy para aplicar. Para testar localmente, defina as mesmas variáveis no PowerShell que iniciará o Uvicorn. Quando qualquer variável de autenticação estiver ausente, a área permanece fechada.

### Acesso da área Comercial ao BigQuery

A área Comercial consulta sob demanda a tabela pública `opencnpj-bigquery.public.receita`.
O projeto Google Cloud configurado abaixo executa os jobs e responde pelo faturamento das consultas; a aplicação não copia nem armazena a base CNPJ.

1. Crie ou selecione um projeto Google Cloud e habilite o BigQuery. Para desenvolvimento, o sandbox do BigQuery permite consultar tabelas públicas sem cadastrar faturamento, sujeito às cotas e limitações do sandbox.
2. Instale a Google Cloud CLI e autentique as credenciais ADC da sua conta:
   ```powershell
   gcloud auth application-default login
   ```
3. No PowerShell, configure o ID do projeto que executará as consultas:
   ```powershell
   $env:BIGQUERY_PROJECT_ID = "seu-id-de-projeto"
   ```
4. Opcionalmente, defina o limite de bytes faturados por consulta. O BigQuery rejeitará uma consulta que ultrapassar o limite:
   ```powershell
   $env:BIGQUERY_MAX_BYTES_BILLED = "53687091200"
   ```
5. Inicie ou reinicie a aplicação no mesmo terminal:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn main:app --reload
   ```

No desenvolvimento local, mantenha a credencial ADC fora do repositório. Em produção, use identidade de workload/serviço gerenciada pelo provedor; não coloque chaves de conta de serviço no frontend nem no Git. Sem projeto ou credenciais disponíveis, as páginas existentes continuam iniciando normalmente e as rotas Comerciais retornam `503` com a configuração necessária.

#### Autenticação de produção no Render

O OIDC gerenciado atualmente documentado pelo Render não lista o Google Cloud como provedor. Para manter o serviço autenticado sem login interativo:

1. No Google Cloud, crie uma conta de serviço dedicada à aplicação e uma chave JSON para ela. Conceda `BigQuery Job User` no projeto que executará as consultas. A tabela OpenCNPJ é pública; se a política de acesso efetiva exigir, conceda também `BigQuery Data Viewer` no dataset de leitura. Não use uma conta de usuário pessoal.
2. No Render, abra o serviço e acesse **Environment** > **Secret Files**. Adicione o conteúdo do JSON com o nome `opencnpj-bigquery.json`. O arquivo fica disponível em `/etc/secrets/opencnpj-bigquery.json` em runtime.
3. Em **Environment Variables**, configure:
   - `GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/opencnpj-bigquery.json`
   - `BIGQUERY_PROJECT_ID` com o ID do projeto executor
   - `BIGQUERY_MAX_BYTES_BILLED` com o teto de bytes por consulta, por exemplo `374575253160`
4. Salve e faça deploy do serviço. O cliente Google usa ADC a partir do Secret File, sem `gcloud auth application-default login` nem interação durante as 24 horas de execução.

Restrinja a chave à conta de serviço dedicada, mantenha-a somente em Secret Files, não a envie por chat, não a coloque em variável pública, `render.yaml`, `.env` versionado ou Git, e rotacione/revogue-a se houver exposição. Em ambientes que suportam identidade de serviço nativa, prefira essa opção sem chave persistente.

Endpoints da área Comercial:

* `GET /api/empresas`: filtros repetíveis `cnaes`, `tipo_cnae`, `uf`, `municipio`, `situacao`, `tipo_estabelecimento`, `porte`, `simples_nacional`, `page` e `limit`.
* `GET /api/empresas/{cnpj}`: detalhes cadastrais sob demanda.
* `GET /api/cnaes?q=termo`: busca códigos/descrições para o autocomplete.

O campo de total permanece `null`; não é feita consulta de contagem adicional. `LIMIT` controla as linhas retornadas, não necessariamente os bytes processados pelo BigQuery. Consulte o preview de custos do console e configure um limite adequado antes de liberar pesquisas em produção.

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

Depois do primeiro deploy, configure também os secrets de autenticação Comercial listados acima e os secrets de BigQuery. Ao salvar, escolha **Save, rebuild, and deploy** (ou **Save and deploy**) para aplicar as variáveis ao processo do serviço.

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