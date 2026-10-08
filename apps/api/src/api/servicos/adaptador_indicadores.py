"""Adaptador fino sobre os indicadores da spec (docs/metodologia/indicadores.md).

TODO(T-A02): trocar cada função por `indicadores.<função>` quando o pacote publicar (funções
puras polars→polars). Até lá este módulo é a **única** fonte das fórmulas na API — routers e
serviços nunca calculam taxa — e é coberto pelos vetores JSON da spec. Indefinido é `None`.
"""

import statistics
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


def penetracao(votos: int, aptos: int) -> float | None:
    """‰ dos aptos: 1000 × votos / aptos (§2.3); `aptos = 0` → `None`."""
    return 1000 * votos / aptos if aptos else None


def pct_validos(votos: int, validos: int) -> float | None:
    """% dos votos válidos (§2.2); denominador zero → `None`."""
    return 100 * votos / validos if validos else None


def diferenca(a: float | None, b: float | None) -> float | None:
    """`b − a`, indefinido se algum lado é `None`."""
    return None if a is None or b is None else b - a


# --------------------------------------------------------------------------- receitas (§4.1)
def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


_ORIGENS = {
    "RECURSOS DE PESSOAS FISICAS": "pessoa_fisica",
    "RECURSOS PROPRIOS": "recursos_proprios",
    "RECURSOS DE FINANCIAMENTO COLETIVO": "financiamento_coletivo",
    "RECURSOS DE PARTIDO POLITICO": "partido_outros_recursos",
    "RECURSOS DE OUTROS CANDIDATOS": "outros_candidatos",
    "RENDIMENTOS DE APLICACOES FINANCEIRAS": "outros",
    "COMERCIALIZACAO DE BENS OU REALIZACAO DE EVENTOS": "outros",
    "RECURSOS DE ORIGEM NAO IDENTIFICADA": "outros",
}


def classificar_receita(fonte: str, origem: str) -> str:
    """Categoria da receita: a fonte manda (FEFC/FP), depois a origem. Rótulo novo falha alto."""
    f = _norm(fonte)
    if f.startswith("FUNDO ESPECIAL"):
        return "fefc"
    if f.startswith("FUNDO PARTIDARIO"):
        return "fundo_partidario"
    if f != "OUTROS RECURSOS":
        raise ValueError("ds_fonte_receita desconhecida")
    categoria = _ORIGENS.get(_norm(origem))
    if categoria is None:
        raise ValueError("ds_origem_receita desconhecida")
    return categoria


@dataclass(frozen=True)
class LinhaReceita:
    """Receita com rótulos do TSE."""

    fonte: str
    origem: str
    natureza: str
    valor: float


@dataclass(frozen=True)
class ResumoReceitas:
    """Receita por categoria e taxas de dependência."""

    por_categoria: dict[str, float]
    receita_total: float
    receita_financeira: float
    pct_publico: float | None
    pct_autofinanciamento: float | None


def resumir_receitas(linhas: Iterable[LinhaReceita]) -> ResumoReceitas:
    """Agrega receitas (§4.1): total 0 → taxas `None`."""
    por: dict[str, float] = {}
    total = financeira = 0.0
    for r in linhas:
        categoria = classificar_receita(r.fonte, r.origem)
        por[categoria] = por.get(categoria, 0.0) + r.valor
        total += r.valor
        if _norm(r.natureza) == "FINANCEIRO":
            financeira += r.valor
    publico = por.get("fefc", 0.0) + por.get("fundo_partidario", 0.0)
    return ResumoReceitas(
        por_categoria=dict(sorted(por.items())),
        receita_total=total,
        receita_financeira=financeira,
        pct_publico=100 * publico / total if total else None,
        pct_autofinanciamento=100 * por.get("recursos_proprios", 0.0) / total if total else None,
    )


# ----------------------------------------------------------------------- custo por voto (§4.2)
_TRANSFERENCIA = "DOACOES FINANCEIRAS A OUTROS CANDIDATOS/PARTIDOS"


def eh_transferencia(origem_despesa: str) -> bool:
    """Transferência a outro candidato/partido não é custo da própria campanha."""
    return _norm(origem_despesa) == _TRANSFERENCIA


@dataclass(frozen=True)
class ContasCandidato:
    """Despesas de um candidato (sem transferências) e seus votos."""

    sq_candidato: int | str
    despesa_contratada: float
    despesa_paga: float
    votos: int


@dataclass(frozen=True)
class CustoCandidato:
    """Custo por voto de um candidato."""

    sq_candidato: int | str
    custo_voto_contratado: float | None
    custo_voto_pago: float | None
    divida: float


@dataclass(frozen=True)
class CustoGrupo:
    """Agregado do grupo: Σ despesa / Σ votos (não média de razões) e mediana por candidato."""

    despesa_contratada: float
    despesa_paga: float
    divida: float
    votos: int
    custo_voto_contratado: float | None
    custo_voto_pago: float | None
    mediana_custo_voto_contratado: float | None
    candidatos_sem_voto_excluidos: int


def custo_por_voto(contas: Sequence[ContasCandidato]) -> tuple[list[CustoCandidato], CustoGrupo]:
    """Custo por candidato e agregado do grupo (candidatos sem voto ficam fora da razão)."""
    candidatos = [
        CustoCandidato(
            c.sq_candidato,
            c.despesa_contratada / c.votos if c.votos else None,
            c.despesa_paga / c.votos if c.votos else None,
            c.despesa_contratada - c.despesa_paga,
        )
        for c in contas
    ]
    com_voto = [c for c in contas if c.votos > 0]
    votos = sum(c.votos for c in com_voto)
    contratada = sum(c.despesa_contratada for c in com_voto)
    paga = sum(c.despesa_paga for c in com_voto)
    medianas = [c.custo_voto_contratado for c in candidatos if c.custo_voto_contratado is not None]
    grupo = CustoGrupo(
        despesa_contratada=sum(c.despesa_contratada for c in contas),
        despesa_paga=sum(c.despesa_paga for c in contas),
        divida=sum(c.divida for c in candidatos),
        votos=sum(c.votos for c in contas),
        custo_voto_contratado=contratada / votos if votos else None,
        custo_voto_pago=paga / votos if votos else None,
        mediana_custo_voto_contratado=statistics.median(medianas) if medianas else None,
        candidatos_sem_voto_excluidos=len(contas) - len(com_voto),
    )
    return candidatos, grupo


# ------------------------------------------------------------------------- deflação (§4.3)
def _proximo_mes(mes: str) -> str:
    ano, m = int(mes[:4]), int(mes[5:7])
    return f"{ano + m // 12}-{m % 12 + 1:02d}"


def fator_ipca(variacao_mensal: Mapping[str, float], mes_origem: str, mes_base: str) -> float:
    """Π_{m=origem+1}^{base} (1 + v_m/100); mês ausente falha alto (sem fallback)."""
    fator, mes = 1.0, mes_origem
    while mes != mes_base:
        mes = _proximo_mes(mes)
        if mes not in variacao_mensal:
            raise ValueError(f"IPCA ausente para {mes}")
        fator *= 1 + variacao_mensal[mes] / 100
    return fator


# ------------------------------------------------------------------------- evolução (§5.1)
@dataclass(frozen=True)
class BaseMunicipio:
    """Votos do grupo e base eleitoral de um município num ano."""

    cd_mun_ibge: int
    aptos: int
    validos: int
    votos: int


@dataclass(frozen=True)
class EvolucaoAmc:
    """Evolução 2022→2026 numa AMC."""

    amc: int
    penetracao_2022: float | None
    penetracao_2026: float | None
    delta_penetracao: float | None
    swing_pp: float | None
    retencao: float | None
    ganho_absoluto: int
    votos_2022: int
    votos_2026: int


def _por_amc(amc: Mapping[int, int], linhas: Iterable[BaseMunicipio]) -> dict[int, list[int]]:
    soma: dict[int, list[int]] = {}
    for linha in linhas:
        if linha.cd_mun_ibge not in amc:
            raise ValueError(f"AMC ausente para o município {linha.cd_mun_ibge}")
        acc = soma.setdefault(amc[linha.cd_mun_ibge], [0, 0, 0])
        acc[0] += linha.aptos
        acc[1] += linha.validos
        acc[2] += linha.votos
    return soma


def evolucao(
    amc: Mapping[int, int],
    ano_2022: Iterable[BaseMunicipio],
    ano_2026: Iterable[BaseMunicipio],
) -> list[EvolucaoAmc]:
    """Soma por AMC **antes** de calcular taxas (§5.1); `retencao` é `None` se votos_2022 = 0."""
    a, b = _por_amc(amc, ano_2022), _por_amc(amc, ano_2026)
    saida = []
    for chave in sorted(a.keys() | b.keys()):
        apt22, val22, v22 = a.get(chave, [0, 0, 0])
        apt26, val26, v26 = b.get(chave, [0, 0, 0])
        p22, p26 = penetracao(v22, apt22), penetracao(v26, apt26)
        saida.append(
            EvolucaoAmc(
                amc=chave,
                penetracao_2022=p22,
                penetracao_2026=p26,
                delta_penetracao=diferenca(p22, p26),
                swing_pp=diferenca(pct_validos(v22, val22), pct_validos(v26, val26)),
                retencao=v26 / v22 if v22 else None,
                ganho_absoluto=v26 - v22,
                votos_2022=v22,
                votos_2026=v26,
            )
        )
    return saida
