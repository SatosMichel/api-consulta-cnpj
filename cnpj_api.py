from datetime import date
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from google.auth.exceptions import DefaultCredentialsError
from pydantic import BaseModel, ConfigDict, Field

from comercial_auth import require_comercial_session
from cnpj_data_provider import (
    Cnae,
    CnpjDataProvider,
    CnpjProviderError,
    Empresa,
    FiltrosEmpresa,
    PaginaEmpresas,
    SituacaoCadastral,
    TipoCnae,
    TipoEstabelecimento,
)


router = APIRouter(
    prefix="/api",
    tags=["prospecção CNPJ"],
    dependencies=[Depends(require_comercial_session)],
)


class TelefoneResponse(BaseModel):
    ddd: str
    numero: str
    is_fax: bool


class EmpresaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cnpj: str
    razao_social: str
    nome_fantasia: str
    situacao_cadastral: str
    data_situacao_cadastral: date | None
    tipo_estabelecimento: str
    data_inicio_atividade: date | None
    cnae_principal: str
    cnaes_secundarios: tuple[str, ...]
    uf: str
    municipio: str
    codigo_municipio: str
    tipo_logradouro: str
    logradouro: str
    numero: str
    complemento: str
    bairro: str
    cep: str
    email: str
    telefones: tuple[TelefoneResponse, ...]
    porte: str
    simples_nacional: bool | None
    mei: bool | None


class PaginacaoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page: int
    limit: int
    total: int | None
    total_pages: int | None = Field(alias="totalPages")


class PaginaEmpresasResponse(BaseModel):
    data: tuple[EmpresaResponse, ...]
    pagination: PaginacaoResponse


class CnaeResponse(BaseModel):
    codigo: str
    descricao: str


def get_cnpj_data_provider(request: Request) -> CnpjDataProvider:
    provider = getattr(request.app.state, "cnpj_data_provider", None)
    if provider is not None:
        return provider

    factory = getattr(request.app.state, "cnpj_provider_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Fonte CNPJ não configurada.")

    if not (os.getenv("BIGQUERY_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")):
        raise HTTPException(
            status_code=503,
            detail=(
                "ID do projeto ausente no processo do servidor. Defina BIGQUERY_PROJECT_ID "
                "ou GOOGLE_CLOUD_PROJECT no mesmo terminal e reinicie o Uvicorn."
            ),
        )

    try:
        provider = factory()
    except DefaultCredentialsError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Credenciais ADC do Google Cloud não encontradas. No Render, adicione a chave "
                "JSON como Secret File e configure GOOGLE_APPLICATION_CREDENTIALS com o caminho "
                "do arquivo; localmente, use `gcloud auth application-default login`."
            ),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail=f"Configuração do BigQuery inválida: {error}",
        ) from error

    request.app.state.cnpj_data_provider = provider
    return provider


def _cnaes_from_query(values: list[str] | None) -> tuple[str, ...]:
    return tuple(
        value.strip()
        for item in values or ()
        for value in item.replace(";", ",").split(",")
        if value.strip()
    )


def _raise_provider_http_error(error: Exception) -> None:
    if isinstance(error, CnpjProviderError):
        raise HTTPException(
            status_code=502,
            detail="A fonte OpenCNPJ/BigQuery não respondeu. Tente novamente mais tarde.",
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


@router.get("/empresas", response_model=PaginaEmpresasResponse)
def buscar_empresas(
    provider: Annotated[CnpjDataProvider, Depends(get_cnpj_data_provider)],
    cnaes: Annotated[list[str] | None, Query()] = None,
    tipo_cnae: TipoCnae = TipoCnae.QUALQUER,
    uf: Annotated[str | None, Query(max_length=2)] = None,
    municipio: Annotated[str | None, Query(max_length=100)] = None,
    situacao: SituacaoCadastral | None = None,
    tipo_estabelecimento: TipoEstabelecimento | None = None,
    porte: Annotated[str | None, Query(max_length=40)] = None,
    simples_nacional: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginaEmpresas | dict:
    try:
        filtros = FiltrosEmpresa(
            cnaes=_cnaes_from_query(cnaes),
            tipo_cnae=tipo_cnae,
            uf=uf,
            municipio=municipio,
            situacao=situacao,
            tipo_estabelecimento=tipo_estabelecimento,
            porte=porte,
            simples_nacional=simples_nacional,
            page=page,
            limit=limit,
        )
        return provider.buscar_empresas(filtros)
    except (CnpjProviderError, ValueError) as error:
        _raise_provider_http_error(error)


@router.get("/empresas/{cnpj}", response_model=EmpresaResponse)
def consultar_empresa(
    cnpj: str,
    provider: Annotated[CnpjDataProvider, Depends(get_cnpj_data_provider)],
) -> Empresa:
    try:
        company = provider.consultar_empresa_por_cnpj(cnpj)
    except (CnpjProviderError, ValueError) as error:
        _raise_provider_http_error(error)
    if company is None:
        raise HTTPException(status_code=404, detail="CNPJ não encontrado na fonte publicada.")
    return company


@router.get("/cnaes", response_model=tuple[CnaeResponse, ...])
def buscar_cnaes(
    provider: Annotated[CnpjDataProvider, Depends(get_cnpj_data_provider)],
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> tuple[Cnae, ...]:
    try:
        return provider.buscar_cnaes(q, limit)
    except (CnpjProviderError, ValueError) as error:
        _raise_provider_http_error(error)