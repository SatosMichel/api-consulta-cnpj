import os
import re
from collections.abc import Iterable, Mapping
from typing import Any

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery

from cnpj_data_provider import (
    Cnae,
    CnpjProviderError,
    Empresa,
    FiltrosEmpresa,
    PaginaEmpresas,
    Paginacao,
    SituacaoCadastral,
    TelefoneEmpresa,
    TipoCnae,
    TipoEstabelecimento,
)


class OpenCnpjBigQueryProvider:
    TABLE_ID = "opencnpj-bigquery.public.receita"
    MAX_LIMIT = 100
    MAX_CNAES = 20
    MAX_CNAE_SEARCH_LIMIT = 100
    COMPANY_PROJECTION = """
        r.cnpj,
        r.razao_social,
        r.nome_fantasia,
        r.situacao_cadastral,
        r.data_situacao_cadastral,
        r.matriz_filial AS tipo_estabelecimento,
        r.data_inicio_atividade,
        r.cnae_principal,
        ARRAY(
            SELECT item.element
            FROM UNNEST(r.cnaes_secundarios.list) AS item
            WHERE item.element IS NOT NULL
        ) AS cnaes_secundarios,
        r.uf,
        r.municipio,
        r.codigo_municipio,
        r.tipo_logradouro,
        r.logradouro,
        r.numero,
        r.complemento,
        r.bairro,
        r.cep,
        r.email,
        ARRAY(
            SELECT AS STRUCT
                item.element.ddd AS ddd,
                item.element.numero AS numero,
                item.element.is_fax AS is_fax
            FROM UNNEST(r.telefones.list) AS item
            WHERE item.element IS NOT NULL
        ) AS telefones,
        r.porte_empresa AS porte,
        r.opcao_simples AS simples_nacional,
        r.opcao_mei AS mei
    """

    _UF_VALUES = frozenset(
        {
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
            "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
            "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        }
    )
    _SITUATION_VALUES = {
        SituacaoCadastral.ATIVA: "Ativa",
        SituacaoCadastral.SUSPENSA: "Suspensa",
        SituacaoCadastral.INAPTA: "Inapta",
        SituacaoCadastral.BAIXADA: "Baixada",
        SituacaoCadastral.NULA: "Nula",
    }
    _PORTE_VALUES = frozenset(
        {"Não informado", "Microempresa (ME)", "Empresa de Pequeno Porte (EPP)", "Demais"}
    )

    def __init__(
        self,
        project_id: str | None = None,
        client: Any | None = None,
        timeout_seconds: float = 30,
        maximum_bytes_billed: int | None = None,
    ) -> None:
        resolved_project_id = (
            project_id
            or os.getenv("BIGQUERY_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
        if client is None and not resolved_project_id:
            raise ValueError(
                "Configure BIGQUERY_PROJECT_ID ou GOOGLE_CLOUD_PROJECT para executar consultas."
            )
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser maior que zero.")
        if maximum_bytes_billed is None:
            configured_maximum = os.getenv("BIGQUERY_MAX_BYTES_BILLED")
            if configured_maximum:
                try:
                    maximum_bytes_billed = int(configured_maximum)
                except ValueError as error:
                    raise ValueError(
                        "BIGQUERY_MAX_BYTES_BILLED deve ser um inteiro positivo."
                    ) from error
        if maximum_bytes_billed is not None and maximum_bytes_billed <= 0:
            raise ValueError("maximum_bytes_billed deve ser maior que zero.")

        self._client = client or bigquery.Client(project=resolved_project_id)
        self._timeout_seconds = timeout_seconds
        self._maximum_bytes_billed = maximum_bytes_billed

    def buscar_empresas(self, filtros: FiltrosEmpresa) -> PaginaEmpresas:
        self._validate_filters(filtros)
        where_clauses: list[str] = []
        parameters: list[Any] = [
            bigquery.ScalarQueryParameter("limit", "INT64", filtros.limit),
            bigquery.ScalarQueryParameter(
                "offset", "INT64", (filtros.page - 1) * filtros.limit
            ),
        ]

        if filtros.cnaes:
            parameters.append(
                bigquery.ArrayQueryParameter("cnaes", "STRING", list(filtros.cnaes))
            )
            if filtros.tipo_cnae is TipoCnae.PRINCIPAL:
                where_clauses.append("r.cnae_principal IN UNNEST(@cnaes)")
            elif filtros.tipo_cnae is TipoCnae.SECUNDARIO:
                where_clauses.append(
                    "EXISTS (SELECT 1 FROM UNNEST(r.cnaes_secundarios.list) AS item "
                    "WHERE item.element IN UNNEST(@cnaes))"
                )
            else:
                where_clauses.append(
                    "(r.cnae_principal IN UNNEST(@cnaes) OR "
                    "EXISTS (SELECT 1 FROM UNNEST(r.cnaes_secundarios.list) AS item "
                    "WHERE item.element IN UNNEST(@cnaes)))"
                )

        if filtros.uf:
            where_clauses.append("r.uf = @uf")
            parameters.append(bigquery.ScalarQueryParameter("uf", "STRING", filtros.uf))
        if filtros.municipio:
            where_clauses.append("UPPER(r.municipio) = UPPER(@municipio)")
            parameters.append(
                bigquery.ScalarQueryParameter("municipio", "STRING", filtros.municipio)
            )
        if filtros.situacao:
            where_clauses.append("r.situacao_cadastral = @situacao")
            parameters.append(
                bigquery.ScalarQueryParameter(
                    "situacao", "STRING", self._SITUATION_VALUES[filtros.situacao]
                )
            )
        if filtros.tipo_estabelecimento:
            where_clauses.append("r.matriz_filial = @tipo_estabelecimento")
            parameters.append(
                bigquery.ScalarQueryParameter(
                    "tipo_estabelecimento",
                    "STRING",
                    "Matriz"
                    if filtros.tipo_estabelecimento is TipoEstabelecimento.MATRIZ
                    else "Filial",
                )
            )
        if filtros.porte:
            where_clauses.append("r.porte_empresa = @porte")
            parameters.append(
                bigquery.ScalarQueryParameter("porte", "STRING", filtros.porte)
            )
        if filtros.simples_nacional is not None:
            where_clauses.append("r.opcao_simples = @simples_nacional")
            parameters.append(
                bigquery.ScalarQueryParameter(
                    "simples_nacional", "BOOL", filtros.simples_nacional
                )
            )

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        sql = f"""
            SELECT {self.COMPANY_PROJECTION}
            FROM `{self.TABLE_ID}` AS r
            {where_sql}
            ORDER BY r.cnpj
            LIMIT @limit OFFSET @offset
        """
        rows = self._run_query(sql, parameters)
        companies = tuple(self._company_from_row(row) for row in rows)
        return PaginaEmpresas(
            data=companies,
            pagination=Paginacao(page=filtros.page, limit=filtros.limit),
        )

    def consultar_empresa_por_cnpj(self, cnpj: str) -> Empresa | None:
        normalized_cnpj = self._normalize_cnpj(cnpj)
        sql = f"""
            SELECT {self.COMPANY_PROJECTION}
            FROM `{self.TABLE_ID}` AS r
            WHERE r.cnpj = @cnpj
            LIMIT 1
        """
        rows = self._run_query(
            sql, [bigquery.ScalarQueryParameter("cnpj", "STRING", normalized_cnpj)]
        )
        return self._company_from_row(rows[0]) if rows else None

    def buscar_cnaes(self, termo: str, limit: int = 20) -> tuple[Cnae, ...]:
        if not isinstance(termo, str) or not termo.strip() or len(termo.strip()) > 100:
            raise ValueError("Informe um termo de CNAE com até 100 caracteres.")
        if not 1 <= limit <= self.MAX_CNAE_SEARCH_LIMIT:
            raise ValueError(f"limit deve estar entre 1 e {self.MAX_CNAE_SEARCH_LIMIT}.")

        normalized_term = termo.strip()
        code_prefix = ""
        description_term = normalized_term
        if re.fullmatch(r"[0-9./ -]+", normalized_term):
            code_prefix = re.sub(r"[^0-9]", "", normalized_term)
            if not 1 <= len(code_prefix) <= 7:
                raise ValueError("O código CNAE deve ter de 1 a 7 dígitos.")
            description_term = ""
        elif len(normalized_term) < 2:
            raise ValueError("A busca por descrição exige pelo menos 2 caracteres.")

        sql = f"""
            SELECT DISTINCT
                item.element.codigo AS codigo,
                item.element.descricao AS descricao
            FROM `{self.TABLE_ID}` AS r
            CROSS JOIN UNNEST(r.cnaes.list) AS item
            WHERE (@code_prefix = '' OR item.element.codigo LIKE CONCAT(@code_prefix, '%'))
              AND (@description_term = '' OR STRPOS(
                    LOWER(item.element.descricao), LOWER(@description_term)
                  ) > 0)
            ORDER BY codigo
            LIMIT @limit
        """
        rows = self._run_query(
            sql,
            [
                bigquery.ScalarQueryParameter("code_prefix", "STRING", code_prefix),
                bigquery.ScalarQueryParameter(
                    "description_term", "STRING", description_term
                ),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ],
        )
        return tuple(
            Cnae(
                codigo=self._value(row, "codigo", ""),
                descricao=self._value(row, "descricao", ""),
            )
            for row in rows
        )

    def _run_query(self, sql: str, parameters: list[Any]) -> list[Any]:
        job_config = bigquery.QueryJobConfig(
            query_parameters=parameters,
            maximum_bytes_billed=self._maximum_bytes_billed,
        )
        try:
            job = self._client.query(sql, job_config=job_config)
            return list(job.result(timeout=self._timeout_seconds))
        except (GoogleAPICallError, TimeoutError) as error:
            raise CnpjProviderError("Falha ao consultar o BigQuery do OpenCNPJ.") from error

    @classmethod
    def _validate_filters(cls, filtros: FiltrosEmpresa) -> None:
        if not isinstance(filtros, FiltrosEmpresa):
            raise TypeError("filtros deve ser uma instância de FiltrosEmpresa.")
        if len(filtros.cnaes) > cls.MAX_CNAES:
            raise ValueError(f"Informe no máximo {cls.MAX_CNAES} CNAEs por pesquisa.")
        if filtros.uf and filtros.uf not in cls._UF_VALUES:
            raise ValueError("UF inválida.")
        if filtros.municipio is not None and (
            not filtros.municipio.strip()
            or len(filtros.municipio) > 100
            or any(ord(char) < 32 for char in filtros.municipio)
        ):
            raise ValueError("Município inválido.")
        if filtros.situacao and filtros.situacao not in cls._SITUATION_VALUES:
            raise ValueError("Situação cadastral inválida.")
        if filtros.porte and filtros.porte not in cls._PORTE_VALUES:
            raise ValueError("Porte inválido.")
        if filtros.page < 1:
            raise ValueError("page deve ser maior ou igual a 1.")
        if not 1 <= filtros.limit <= cls.MAX_LIMIT:
            raise ValueError(f"limit deve estar entre 1 e {cls.MAX_LIMIT}.")

    @staticmethod
    def _normalize_cnpj(cnpj: str) -> str:
        if not isinstance(cnpj, str):
            raise ValueError("CNPJ inválido.")
        normalized = re.sub(r"[^A-Za-z0-9]", "", cnpj).upper()
        if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", normalized):
            raise ValueError("CNPJ inválido.")
        return normalized

    @staticmethod
    def _value(row: Any, key: str, default: Any = None) -> Any:
        if isinstance(row, Mapping):
            return row.get(key, default)
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

    @classmethod
    def _company_from_row(cls, row: Any) -> Empresa:
        phones: Iterable[Any] = cls._value(row, "telefones", ()) or ()
        secondary_cnaes: Iterable[Any] = cls._value(row, "cnaes_secundarios", ()) or ()
        return Empresa(
            cnpj=cls._value(row, "cnpj", ""),
            razao_social=cls._value(row, "razao_social", ""),
            nome_fantasia=cls._value(row, "nome_fantasia", ""),
            situacao_cadastral=cls._value(row, "situacao_cadastral", ""),
            data_situacao_cadastral=cls._value(row, "data_situacao_cadastral"),
            tipo_estabelecimento=cls._value(row, "tipo_estabelecimento", ""),
            data_inicio_atividade=cls._value(row, "data_inicio_atividade"),
            cnae_principal=cls._value(row, "cnae_principal", ""),
            cnaes_secundarios=tuple(secondary_cnaes),
            uf=cls._value(row, "uf", ""),
            municipio=cls._value(row, "municipio", ""),
            codigo_municipio=cls._value(row, "codigo_municipio", ""),
            tipo_logradouro=cls._value(row, "tipo_logradouro", ""),
            logradouro=cls._value(row, "logradouro", ""),
            numero=cls._value(row, "numero", ""),
            complemento=cls._value(row, "complemento", ""),
            bairro=cls._value(row, "bairro", ""),
            cep=cls._value(row, "cep", ""),
            email=cls._value(row, "email", ""),
            telefones=tuple(
                TelefoneEmpresa(
                    ddd=cls._value(phone, "ddd", ""),
                    numero=cls._value(phone, "numero", ""),
                    is_fax=bool(cls._value(phone, "is_fax", False)),
                )
                for phone in phones
            ),
            porte=cls._value(row, "porte", ""),
            simples_nacional=cls._value(row, "simples_nacional"),
            mei=cls._value(row, "mei"),
        )