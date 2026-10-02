import unittest
from datetime import date

from google.api_core.exceptions import ServiceUnavailable

from cnpj_data_provider import (
    CnpjProviderError,
    FiltrosEmpresa,
    SituacaoCadastral,
    TipoCnae,
    TipoEstabelecimento,
)
from opencnpj_bigquery_provider import OpenCnpjBigQueryProvider


class FakeJob:
    def __init__(self, rows):
        self._rows = rows
        self.timeout = None

    def result(self, timeout=None):
        self.timeout = timeout
        return self._rows


class FakeBigQueryClient:
    def __init__(self, rows=(), error=None, count_rows=()):
        self.rows = rows
        self.error = error
        self.sql = None
        self.job_config = None
        self.job = FakeJob(rows)
        self.count_rows = count_rows
        self.queries = []

    def query(self, sql, job_config):
        self.sql = sql
        self.job_config = job_config
        self.queries.append((sql, job_config))
        if self.error:
            raise self.error
        rows = self.count_rows if "COUNT(*) AS total" in sql else self.rows
        self.job = FakeJob(rows)
        return self.job


class OpenCnpjBigQueryProviderTests(unittest.TestCase):
    def test_search_uses_array_parameters_and_returns_total_pages(self):
        client = FakeBigQueryClient(rows=[{"filtered_total": 51}])
        provider = OpenCnpjBigQueryProvider(client=client)

        result = provider.buscar_empresas(
            FiltrosEmpresa(
                cnaes=("8650-0/04", "8630-5/03"),
                uf="BA",
                municipio="  Salvador' OR TRUE --  ",
                bairro="  Rebouças  ",
                nome="  Michel Santos Rebouças  ",
                situacao=SituacaoCadastral.ATIVA,
                tipo_estabelecimento=TipoEstabelecimento.MATRIZ,
                tipo_cnae=TipoCnae.QUALQUER,
                page=2,
                limit=25,
            )
        )

        parameters = {parameter.name: parameter for parameter in client.job_config.query_parameters}
        self.assertEqual(parameters["cnaes"].values, ["8650004", "8630503"])
        self.assertEqual(parameters["municipio"].value, "Salvador' OR TRUE --")
        self.assertEqual(parameters["bairro"].value, "Rebouças")
        self.assertEqual(parameters["nome"].value, "Michel Santos Rebouças")
        self.assertNotIn("Salvador' OR TRUE --", client.sql)
        self.assertNotIn("Michel Santos Rebouças", client.sql)
        self.assertIn("r.razao_social", client.sql)
        self.assertIn("r.nome_fantasia", client.sql)
        self.assertIn("r.bairro", client.sql)
        self.assertIn("r.cnaes_secundarios.list", client.sql)
        self.assertEqual(parameters["offset"].value, 25)
        self.assertEqual(result.pagination.page, 2)
        self.assertEqual(result.pagination.total, 51)
        self.assertEqual(result.pagination.total_pages, 3)

    def test_single_cnpj_maps_schema_fields_and_nested_phones(self):
        client = FakeBigQueryClient(
            rows=[
                {
                    "cnpj": "12345678000195",
                    "razao_social": "Empresa Exemplo",
                    "situacao_cadastral": "Ativa",
                    "data_inicio_atividade": date(2020, 1, 2),
                    "cnaes_secundarios": ["8630503"],
                    "email": "contato@exemplo.com.br",
                    "telefones": [{"ddd": "71", "numero": "33334444", "is_fax": False}],
                    "uf": "BA",
                    "municipio": "SALVADOR",
                }
            ]
        )
        provider = OpenCnpjBigQueryProvider(client=client)

        company = provider.consultar_empresa_por_cnpj("12.345.678/0001-95")

        self.assertEqual(company.cnpj, "12345678000195")
        self.assertEqual(company.data_inicio_atividade, date(2020, 1, 2))
        self.assertEqual(company.cnaes_secundarios, ("8630503",))
        self.assertEqual(company.email, "contato@exemplo.com.br")
        self.assertEqual(company.telefones[0].ddd, "71")
        parameters = {parameter.name: parameter for parameter in client.job_config.query_parameters}
        self.assertEqual(parameters["cnpj"].value, "12345678000195")

    def test_empty_filters_are_counted_in_the_page_query(self):
        client = FakeBigQueryClient(rows=[{"filtered_total": 1}])
        provider = OpenCnpjBigQueryProvider(client=client)

        result = provider.buscar_empresas(FiltrosEmpresa())

        self.assertNotIn("r.uf = @uf", client.sql)
        self.assertNotIn("r.situacao_cadastral = @situacao", client.sql)
        self.assertNotIn("r.cnae_principal IN UNNEST(@cnaes)", client.sql)
        self.assertEqual(len(client.queries), 1)
        self.assertEqual(result.pagination.total, 1)
        self.assertEqual(result.pagination.total_pages, 1)
        self.assertEqual(client.job.timeout, 30)

    def test_empty_page_runs_count_query_for_direct_page_navigation(self):
        client = FakeBigQueryClient(rows=[], count_rows=[{"total": 175}])
        provider = OpenCnpjBigQueryProvider(client=client)

        result = provider.buscar_empresas(FiltrosEmpresa(page=4, limit=50, nome="Rebouças"))

        self.assertEqual(len(result.data), 0)
        self.assertEqual(result.pagination.total, 175)
        self.assertEqual(result.pagination.total_pages, 4)
        self.assertEqual(len(client.queries), 2)
        page_parameters = {
            parameter.name: parameter for parameter in client.queries[0][1].query_parameters
        }
        count_parameters = {
            parameter.name: parameter for parameter in client.queries[1][1].query_parameters
        }
        self.assertEqual(page_parameters["offset"].value, 150)
        self.assertEqual(count_parameters["nome"].value, "Rebouças")
        self.assertIn("COUNT(*) AS total", client.queries[1][0])

    def test_cnae_lookup_uses_normalized_code_parameter(self):
        client = FakeBigQueryClient(rows=[{"codigo": "8650004", "descricao": "Atividades de fisioterapia"}])
        provider = OpenCnpjBigQueryProvider(client=client)

        result = provider.buscar_cnaes("8650-0/04")

        parameters = {parameter.name: parameter for parameter in client.job_config.query_parameters}
        self.assertEqual(parameters["code_prefix"].value, "8650004")
        self.assertEqual(parameters["description_term"].value, "")
        self.assertEqual(result[0].codigo, "8650004")

    def test_invalid_filters_are_rejected_before_query(self):
        client = FakeBigQueryClient()
        provider = OpenCnpjBigQueryProvider(client=client)

        with self.assertRaises(ValueError):
            provider.buscar_empresas(FiltrosEmpresa(uf="XX"))
        with self.assertRaises(ValueError):
            provider.consultar_empresa_por_cnpj("12.345")
        with self.assertRaises(ValueError):
            provider.buscar_empresas(FiltrosEmpresa(limit=101))

        self.assertIsNone(client.sql)

    def test_google_api_errors_are_translated_to_provider_error(self):
        client = FakeBigQueryClient(error=ServiceUnavailable("service unavailable"))
        provider = OpenCnpjBigQueryProvider(client=client)

        with self.assertRaises(CnpjProviderError):
            provider.buscar_empresas(FiltrosEmpresa())


if __name__ == "__main__":
    unittest.main()