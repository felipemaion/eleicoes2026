"""Casos de uso /busca e /evolucao/pessoas: achar candidaturas e ligar a mesma pessoa entre anos."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from api.dominio import Cargo
from api.erros import parametro_invalido
from api.pessoa import id_publico
from api.repositorio.base import Repositorio
from api.repositorio.modelos import Candidatura
from api.servicos.candidatos import Abrangencia, Partido, abrangencia_de
from api.servicos.comparativo import ANO_DE, ANO_PARA
from api.servicos.grupos import Catalogo
from api.texto import normalizar


class CandidaturaBusca(BaseModel):
    """Candidatura achada: o bastante para listar, escolher e enquadrar o mapa."""

    ano: int
    sq_candidato: int
    nm_urna: str
    nome: str | None = Field(description="Nome civil, como no registro de candidatura do TSE.")
    numero: int | None = Field(description="Número de urna.")
    cargo: str
    uf: str = Field(description="UF da candidatura; `BR` para presidente.")
    partido: Partido
    votos: int = Field(description="Votos nominais válidos (spec §2.1); 0 sem apuração.")
    resultado: str | None = Field(description="`ds_sit_tot_turno`; null se sem apuração.")
    indicado: bool = Field(description="Candidatura indicada pelo grupo (lista de referência).")
    pessoa_id_publico: str = Field(
        description="Hash curto e não reversível da pessoa, só para ligar anos. Não é o "
        "`pessoa_id` interno nem identifica ninguém fora desta API."
    )
    abrangencia: Abrangencia


class ResultadoBusca(BaseModel):
    """Corpo de GET /busca."""

    total: int = Field(description="Candidaturas que casam (além da página devolvida).")
    limite: int
    itens: list[CandidaturaBusca]
    dt_geracao: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total": 1,
                    "limite": 20,
                    "itens": [
                        {
                            "ano": 2026,
                            "sq_candidato": 3,
                            "nm_urna": "A",
                            "nome": "ANA ALVES DA SILVA",
                            "numero": 1415,
                            "cargo": "DEPUTADO FEDERAL",
                            "uf": "SP",
                            "partido": {"numero": 14, "sigla": "MISSÃO"},
                            "votos": 1000,
                            "resultado": "SUPLENTE",
                            "indicado": False,
                            "pessoa_id_publico": "3f2a9c1d7b40",
                            "abrangencia": {"tipo": "uf", "uf": "SP"},
                        }
                    ],
                    "dt_geracao": "2026-10-06",
                }
            ]
        }
    )


def _itens(
    repo: Repositorio, catalogo: Catalogo, candidaturas: Sequence[Candidatura]
) -> dict[int, CandidaturaBusca]:
    """Candidaturas → itens por `sq_candidato`, com os votos buscados uma vez por ano."""
    votos: dict[int, int] = {}
    for ano in {c.ano for c in candidaturas}:
        votos |= repo.votos_totais(ano, [c.sq_candidato for c in candidaturas if c.ano == ano])
    return {
        c.sq_candidato: CandidaturaBusca(
            ano=c.ano,
            sq_candidato=c.sq_candidato,
            nm_urna=c.nm_urna,
            nome=c.nm_civil,
            numero=c.nr_candidato,
            cargo=c.ds_cargo,
            uf=c.sg_uf,
            partido=Partido(numero=c.nr_partido, sigla=c.sg_partido),
            votos=votos.get(c.sq_candidato, 0),
            resultado=c.ds_sit_tot_turno,
            indicado=c.sq_candidato in catalogo.indicados,
            pessoa_id_publico=id_publico(c.pessoa_id),
            abrangencia=abrangencia_de(c),
        )
        for c in candidaturas
    }


def buscar(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    q: str,
    ano: int | None,
    cargo: str | None,
    uf: str | None,
    grupo_id: str | None,
    limite: int,
) -> ResultadoBusca:
    """Candidaturas por nome (urna/civil), número ou partido; início de palavra primeiro."""
    termo = normalizar(q)
    if not termo:
        raise parametro_invalido("busca_vazia", "'q' precisa de ao menos um caractere útil")
    partido: int | None = None
    sqs: list[int] | None = None
    if grupo_id is not None:
        grupo = catalogo.grupo(grupo_id)
        if ano is not None and ano != grupo.ano:
            raise parametro_invalido(
                "grupo_ano_incompativel", f"o grupo '{grupo_id}' é de {grupo.ano}, não de {ano}"
            )
        ano, partido, sqs = grupo.ano, grupo.partido, sorted(grupo.sqs)
    total, achadas = repo.buscar_candidaturas(
        termo=termo, ano=ano, cargo=cargo, uf=uf, partido=partido, sqs=sqs, limite=limite
    )
    itens = _itens(repo, catalogo, achadas)
    return ResultadoBusca(
        total=total,
        limite=limite,
        itens=[itens[c.sq_candidato] for c in achadas],
        dt_geracao=repo.dt_geracao(),
    )


class PessoaEvolucao(BaseModel):
    """Uma pessoa com candidatura em 2022 e em 2026, resumida nos dois anos."""

    pessoa_id_publico: str
    nome: str = Field(description="Nome de urna em 2026.")
    mesmo_cargo: bool = Field(description="Concorreu ao mesmo cargo nos dois anos.")
    comparavel: bool = Field(
        description="Entra em /comparativo: mesmo cargo e não Senado (1 voto × 2 votos, §1.8)."
    )
    de: CandidaturaBusca = Field(description="Candidatura de 2022.")
    para: CandidaturaBusca = Field(description="Candidatura de 2026.")


class ListaPessoas(BaseModel):
    """Corpo de GET /evolucao/pessoas."""

    total: int
    limite: int
    itens: list[PessoaEvolucao]
    dt_geracao: str


def listar_pessoas(
    repo: Repositorio,
    catalogo: Catalogo,
    *,
    q: str | None,
    uf: str | None,
    cargo: str | None,
    limite: int,
) -> ListaPessoas:
    """Quem concorreu em 2022 e em 2026 (ligados por `pessoa_id`), filtrável por nome/UF/cargo."""
    termo = normalizar(q) if q else None
    total, pares = repo.pares_de_pessoas(
        ANO_DE, ANO_PARA, termo=termo or None, uf=uf, cargo=cargo, limite=limite
    )
    itens = _itens(repo, catalogo, [c for p in pares for c in (p.de, p.para)])
    return ListaPessoas(
        total=total,
        limite=limite,
        itens=[
            PessoaEvolucao(
                pessoa_id_publico=id_publico(p.para.pessoa_id),
                nome=p.para.nm_urna,
                mesmo_cargo=p.de.ds_cargo == p.para.ds_cargo,
                comparavel=p.de.ds_cargo == p.para.ds_cargo != Cargo.SENADOR.value,
                de=itens[p.de.sq_candidato],
                para=itens[p.para.sq_candidato],
            )
            for p in pares
        ],
        dt_geracao=repo.dt_geracao(),
    )
