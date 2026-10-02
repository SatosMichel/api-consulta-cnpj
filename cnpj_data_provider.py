import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Protocol


class TipoCnae(str, Enum):
    QUALQUER = "QUALQUER"
    PRINCIPAL = "PRINCIPAL"
    SECUNDARIO = "SECUNDARIO"


class SituacaoCadastral(str, Enum):
    ATIVA = "ATIVA"
    SUSPENSA = "SUSPENSA"
    INAPTA = "INAPTA"
    BAIXADA = "BAIXADA"
    NULA = "NULA"


class TipoEstabelecimento(str, Enum):
    MATRIZ = "MATRIZ"
    FILIAL = "FILIAL"


@dataclass(frozen=True)
class FiltrosEmpresa:
    cnaes: tuple[str, ...] = ()
    tipo_cnae: TipoCnae = TipoCnae.QUALQUER
    uf: str | None = None
    municipio: str | None = None
    bairro: str | None = None
    nome: str | None = None
    situacao: SituacaoCadastral | None = None
    tipo_estabelecimento: TipoEstabelecimento | None = None
    porte: str | None = None
    simples_nacional: bool | None = None
    page: int = 1
    limit: int = 50

    def __post_init__(self) -> None:
        if self.uf is not None:
            if not isinstance(self.uf, str):
                raise ValueError("UF inválida.")
            object.__setattr__(self, "uf", self.uf.strip().upper())
        if self.municipio is not None:
            if not isinstance(self.municipio, str):
                raise ValueError("Município inválido.")
            object.__setattr__(self, "municipio", self._normalize_text_filter(self.municipio, "Município"))
        if self.bairro is not None:
            object.__setattr__(self, "bairro", self._normalize_text_filter(self.bairro, "Bairro"))
        if self.nome is not None:
            object.__setattr__(self, "nome", self._normalize_text_filter(self.nome, "Nome da empresa"))
        if isinstance(self.situacao, str):
            object.__setattr__(self, "situacao", SituacaoCadastral(self.situacao.strip().upper()))
        if isinstance(self.tipo_cnae, str):
            object.__setattr__(self, "tipo_cnae", TipoCnae(self.tipo_cnae.strip().upper()))
        if isinstance(self.tipo_estabelecimento, str):
            object.__setattr__(
                self,
                "tipo_estabelecimento",
                TipoEstabelecimento(self.tipo_estabelecimento.strip().upper()),
            )
        if self.porte is not None:
            if not isinstance(self.porte, str):
                raise ValueError("Porte inválido.")
            object.__setattr__(self, "porte", self.porte.strip())
        if not isinstance(self.page, int) or isinstance(self.page, bool):
            raise ValueError("page deve ser um inteiro.")
        if not isinstance(self.limit, int) or isinstance(self.limit, bool):
            raise ValueError("limit deve ser um inteiro.")

        normalized_cnaes = []
        for cnae in self.cnaes:
            if not isinstance(cnae, str) or not re.fullmatch(
                r"(?:[0-9]{7}|[0-9]{4}-[0-9]/[0-9]{2})", cnae.strip()
            ):
                raise ValueError("Cada CNAE deve ter 7 dígitos, com ou sem máscara.")
            normalized_cnaes.append(re.sub(r"[^0-9]", "", cnae))
        object.__setattr__(self, "cnaes", tuple(dict.fromkeys(normalized_cnaes)))

    @staticmethod
    def _normalize_text_filter(value: str, label: str) -> str | None:
        if not isinstance(value, str):
            raise ValueError(f"{label} inválido.")
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 100 or any(ord(char) < 32 for char in normalized):
            raise ValueError(f"{label} deve ter até 100 caracteres.")
        return normalized


@dataclass(frozen=True)
class TelefoneEmpresa:
    ddd: str
    numero: str
    is_fax: bool


@dataclass(frozen=True)
class Empresa:
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
    telefones: tuple[TelefoneEmpresa, ...]
    porte: str
    simples_nacional: bool | None
    mei: bool | None


@dataclass(frozen=True)
class Cnae:
    codigo: str
    descricao: str


@dataclass(frozen=True)
class Paginacao:
    page: int
    limit: int
    total: int | None = None
    total_pages: int | None = None


@dataclass(frozen=True)
class PaginaEmpresas:
    data: tuple[Empresa, ...]
    pagination: Paginacao


class CnpjProviderError(RuntimeError):
    """Falha ao consultar a fonte de dados CNPJ configurada."""


class CnpjDataProvider(Protocol):
    def buscar_empresas(self, filtros: FiltrosEmpresa) -> PaginaEmpresas:
        ...

    def consultar_empresa_por_cnpj(self, cnpj: str) -> Empresa | None:
        ...

    def buscar_cnaes(self, termo: str, limit: int = 20) -> tuple[Cnae, ...]:
        ...