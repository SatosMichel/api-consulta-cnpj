import unittest
import os
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from fastapi import FastAPI
from google.auth.exceptions import DefaultCredentialsError
from fastapi.testclient import TestClient

from comercial_auth import SESSION_COOKIE, require_comercial_session
from cnpj_api import router
from cnpj_data_provider import (
    Cnae,
    CnpjProviderError,
    Empresa,
    FiltrosEmpresa,
    PaginaEmpresas,
    Paginacao,
    TelefoneEmpresa,
)
from main import app as web_app


TEST_AUTH_SETTINGS = {
    "COMERCIAL_USERNAME": "administrador-teste",
    "COMERCIAL_PASSWORD": "senha-apenas-de-teste",
    "COMERCIAL_SESSION_SECRET": "chave-de-sessao-apenas-de-teste-com-mais-de-32-caracteres",
}


def make_company() -> Empresa:
    return Empresa(
        cnpj="12345678000195",
        razao_social="Empresa Exemplo",
        nome_fantasia="Exemplo",
        situacao_cadastral="Ativa",
        data_situacao_cadastral=None,
        tipo_estabelecimento="Matriz",
        data_inicio_atividade=date(2020, 1, 2),
        cnae_principal="8650004",
        cnaes_secundarios=("8630503",),
        uf="BA",
        municipio="SALVADOR",
        codigo_municipio="3849",
        tipo_logradouro="RUA",
        logradouro="EXEMPLO",
        numero="100",
        complemento="",
        bairro="CENTRO",
        cep="40000000",
        email="contato@exemplo.com.br",
        telefones=(TelefoneEmpresa(ddd="71", numero="33334444", is_fax=False),),
        porte="Microempresa (ME)",
        simples_nacional=True,
        mei=False,
    )


class FakeProvider:
    def __init__(self, error=None):
        self.error = error
        self.filters = None

    def buscar_empresas(self, filtros: FiltrosEmpresa) -> PaginaEmpresas:
        self.filters = filtros
        if self.error:
            raise self.error
        return PaginaEmpresas(
            data=(make_company(),),
            pagination=Paginacao(
                page=filtros.page,
                limit=filtros.limit,
                total=101,
                total_pages=3,
            ),
        )

    def consultar_empresa_por_cnpj(self, cnpj: str) -> Empresa | None:
        if self.error:
            raise self.error
        return make_company() if cnpj == "12345678000195" else None

    def buscar_cnaes(self, termo: str, limit: int = 20) -> tuple[Cnae, ...]:
        if self.error:
            raise self.error
        return (Cnae(codigo="8650004", descricao="Atividades de fisioterapia"),)


class CnpjApiTests(unittest.TestCase):
    def make_client(self, provider):
        app = FastAPI()
        app.state.cnpj_data_provider = provider
        app.include_router(router)
        app.dependency_overrides[require_comercial_session] = lambda: "administrador-teste"
        return TestClient(app)

    @contextmanager
    def authenticated_web_client(self):
        original_provider = web_app.state.cnpj_data_provider
        web_app.state.cnpj_data_provider = FakeProvider()
        try:
            with patch.dict(os.environ, TEST_AUTH_SETTINGS):
                with TestClient(
                    web_app,
                    base_url="https://testserver",
                    follow_redirects=False,
                ) as client:
                    response = client.post(
                        "/comercial/login",
                        data={
                            "username": TEST_AUTH_SETTINGS["COMERCIAL_USERNAME"],
                            "password": TEST_AUTH_SETTINGS["COMERCIAL_PASSWORD"],
                        },
                    )
                    self.assertEqual(response.status_code, 303)
                    yield client
        finally:
            web_app.state.cnpj_data_provider = original_provider

    def test_search_maps_filters_and_standard_response(self):
        provider = FakeProvider()
        client = self.make_client(provider)

        response = client.get(
            "/api/empresas",
            params=[
                ("cnaes", "8650-0/04"),
                ("cnaes", "8630-5/03"),
                ("uf", "ba"),
                ("municipio", "Salvador"),
                ("bairro", "Rebouças"),
                ("nome", "Michel Santos Rebouças"),
                ("situacao", "ATIVA"),
                ("page", "2"),
                ("limit", "25"),
            ],
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"][0]["cnpj"], "12345678000195")
        self.assertEqual(payload["data"][0]["email"], "contato@exemplo.com.br")
        self.assertEqual(payload["pagination"], {
            "page": 2,
            "limit": 25,
            "total": 101,
            "totalPages": 3,
        })
        self.assertEqual(provider.filters.cnaes, ("8650004", "8630503"))
        self.assertEqual(provider.filters.uf, "BA")
        self.assertEqual(provider.filters.municipio, "Salvador")
        self.assertEqual(provider.filters.bairro, "Rebouças")
        self.assertEqual(provider.filters.nome, "Michel Santos Rebouças")

    def test_empty_filters_are_allowed_and_return_a_page(self):
        client = self.make_client(FakeProvider())

        response = client.get("/api/empresas")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["page"], 1)

    def test_invalid_pagination_is_rejected_by_api(self):
        client = self.make_client(FakeProvider())

        response = client.get("/api/empresas?page=0&limit=101")

        self.assertEqual(response.status_code, 422)

    def test_cnae_lookup_and_company_not_found(self):
        client = self.make_client(FakeProvider())

        cnae_response = client.get("/api/cnaes?q=8650-0/04")
        missing_response = client.get("/api/empresas/00000000000000")

        self.assertEqual(cnae_response.status_code, 200)
        self.assertEqual(cnae_response.json()[0]["codigo"], "8650004")
        self.assertEqual(missing_response.status_code, 404)

    def test_company_detail_includes_registration_email(self):
        client = self.make_client(FakeProvider())

        response = client.get("/api/empresas/12345678000195")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "contato@exemplo.com.br")

    def test_provider_error_becomes_gateway_error(self):
        client = self.make_client(FakeProvider(error=CnpjProviderError("internal detail")))

        response = client.get("/api/empresas")

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("internal detail", response.text)

    def test_missing_google_configuration_becomes_service_unavailable(self):
        app = FastAPI()
        app.state.cnpj_data_provider = None
        app.state.cnpj_provider_factory = lambda: (_ for _ in ()).throw(
            ValueError("missing project configuration")
        )
        app.include_router(router)
        app.dependency_overrides[require_comercial_session] = lambda: "administrador-teste"

        with patch.dict(os.environ, {"BIGQUERY_PROJECT_ID": "", "GOOGLE_CLOUD_PROJECT": ""}):
            response = TestClient(app).get("/api/empresas")

        self.assertEqual(response.status_code, 503)
        self.assertIn("BIGQUERY_PROJECT_ID", response.json()["detail"])

    def test_missing_adc_explains_render_secret_file_configuration(self):
        app = FastAPI()
        app.state.cnpj_data_provider = None
        app.state.cnpj_provider_factory = lambda: (_ for _ in ()).throw(
            DefaultCredentialsError("ADC not available")
        )
        app.include_router(router)
        app.dependency_overrides[require_comercial_session] = lambda: "administrador-teste"

        with patch.dict(os.environ, {"BIGQUERY_PROJECT_ID": "test-project"}):
            response = TestClient(app).get("/api/empresas")

        self.assertEqual(response.status_code, 503)
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", response.json()["detail"])

    def test_commercial_screen_and_assets_are_served(self):
        with self.authenticated_web_client() as client:
            page = client.get("/comercial")
            stylesheet = client.get("/static/comercial.css")
            script = client.get("/static/comercial.js")

        self.assertEqual(page.status_code, 200)
        self.assertIn("Empresas por atividade", page.text)
        self.assertIn('id="cnae-lookup-button"', page.text)
        self.assertIn('name="bairro"', page.text)
        self.assertIn('name="nome"', page.text)
        self.assertIn('id="page-jump-form"', page.text)
        self.assertIn("/api/empresas", script.text)
        self.assertIn("payload.pagination.totalPages", script.text)
        self.assertIn("pageJumpForm.addEventListener", script.text)
        self.assertIn("cnaeLookupButton.addEventListener", script.text)
        self.assertIn("addDetailRow('E-mail', company.email", script.text)
        self.assertIn("[hidden] { display: none !important; }", stylesheet.text)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(script.status_code, 200)

    def test_comercial_login_protects_page_and_api_and_logout_expires_session(self):
        original_provider = web_app.state.cnpj_data_provider
        web_app.state.cnpj_data_provider = FakeProvider()
        try:
            with patch.dict(os.environ, TEST_AUTH_SETTINGS):
                with TestClient(
                    web_app,
                    base_url="https://testserver",
                    follow_redirects=False,
                ) as client:
                    page_response = client.get("/comercial")
                    api_response = client.get("/api/empresas")
                    login_page = client.get("/comercial/login")
                    bad_login = client.post(
                        "/comercial/login",
                        data={"username": "administrador-teste", "password": "errada"},
                    )

                    self.assertEqual(page_response.status_code, 303)
                    self.assertEqual(page_response.headers["location"], "/comercial/login")
                    self.assertEqual(api_response.status_code, 401)
                    self.assertEqual(login_page.status_code, 200)
                    self.assertEqual(bad_login.status_code, 401)
                    self.assertNotIn(SESSION_COOKIE, client.cookies)

                    login = client.post(
                        "/comercial/login",
                        data={
                            "username": TEST_AUTH_SETTINGS["COMERCIAL_USERNAME"],
                            "password": TEST_AUTH_SETTINGS["COMERCIAL_PASSWORD"],
                        },
                    )
                    self.assertEqual(login.status_code, 303)
                    self.assertIn("httponly", login.headers["set-cookie"].lower())
                    self.assertIn("secure", login.headers["set-cookie"].lower())
                    self.assertIn("samesite=lax", login.headers["set-cookie"].lower())
                    self.assertEqual(client.get("/comercial").status_code, 200)
                    self.assertEqual(client.get("/api/empresas").status_code, 200)

                    logout = client.post("/comercial/logout")
                    self.assertEqual(logout.status_code, 303)
                    self.assertEqual(client.get("/api/empresas").status_code, 401)
        finally:
            web_app.state.cnpj_data_provider = original_provider

    def test_unconfigured_login_page_shows_one_configuration_notice(self):
        auth_environment = {
            "COMERCIAL_USERNAME": "",
            "COMERCIAL_PASSWORD": "",
            "COMERCIAL_SESSION_SECRET": "",
        }
        with patch.dict(os.environ, auth_environment):
            response = TestClient(web_app).get("/comercial/login")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text.count("O acesso ainda não foi configurado no servidor."), 1)


if __name__ == "__main__":
    unittest.main()