"""Enums de parâmetros validados na borda HTTP.

TODO(T-D02): mover para `packages/contratos` quando o pacote publicar os enums de UF, cargo e
ano; até lá esta é a única definição (nenhum router declara string livre).
"""

from enum import IntEnum, StrEnum


class Cargo(StrEnum):
    """`ds_cargo` em maiúsculas; o ETL grava em caixa de título e as views aplicam `upper`."""

    PRESIDENTE = "PRESIDENTE"
    GOVERNADOR = "GOVERNADOR"
    SENADOR = "SENADOR"
    DEPUTADO_FEDERAL = "DEPUTADO FEDERAL"
    DEPUTADO_ESTADUAL = "DEPUTADO ESTADUAL"
    DEPUTADO_DISTRITAL = "DEPUTADO DISTRITAL"

    @property
    def codigo(self) -> int:
        """`cd_cargo` do TSE (1 presidente, 3 governador, 5 senador, 6/7/8 deputados)."""
        return _CODIGO_CARGO[self]


_CODIGO_CARGO = {
    Cargo.PRESIDENTE: 1,
    Cargo.GOVERNADOR: 3,
    Cargo.SENADOR: 5,
    Cargo.DEPUTADO_FEDERAL: 6,
    Cargo.DEPUTADO_ESTADUAL: 7,
    Cargo.DEPUTADO_DISTRITAL: 8,
}


class UF(StrEnum):
    """Unidades da federação (sem exterior: `ZZ` não tem mapa)."""

    AC = "AC"
    AL = "AL"
    AM = "AM"
    AP = "AP"
    BA = "BA"
    CE = "CE"
    DF = "DF"
    ES = "ES"
    GO = "GO"
    MA = "MA"
    MG = "MG"
    MS = "MS"
    MT = "MT"
    PA = "PA"
    PB = "PB"
    PE = "PE"
    PI = "PI"
    PR = "PR"
    RJ = "RJ"
    RN = "RN"
    RO = "RO"
    RR = "RR"
    RS = "RS"
    SC = "SC"
    SE = "SE"
    SP = "SP"
    TO = "TO"


class Ano(IntEnum):
    """Anos de eleição geral suportados."""

    A2022 = 2022
    A2026 = 2026


class Nivel(StrEnum):
    """Recorte espacial do mapa."""

    MUNICIPIO = "municipio"
    ZONA = "zona"
    H3 = "h3"


class Indicador(StrEnum):
    """Indicadores mapeáveis (spec §2): taxas em coroplético, absoluto em símbolo."""

    PENETRACAO = "penetracao"
    PCT_VALIDOS = "pct_validos"
    VOTOS = "votos"
