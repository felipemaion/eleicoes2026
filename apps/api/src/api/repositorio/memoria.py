"""Implementação em memória do Repositorio, para testes de serviço (sem I/O)."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from api.pessoa import id_publico
from api.repositorio.modelos import (
    BaseEleitoral,
    Candidatura,
    CelulaH3,
    DespesaBruta,
    Municipio,
    ParDePessoa,
    PontoVotacao,
    ReceitaBruta,
    VariacaoIpca,
    VotosSemCoordenada,
    VotosTerritorio,
)
from api.texto import normalizar


@dataclass(frozen=True)
class VotoMemoria:
    """Linha de `votos_munzona`."""

    ano: int
    sq_candidato: int
    cd_mun_ibge: int
    nr_zona: int
    votos: int


@dataclass(frozen=True)
class EleitoradoMemoria:
    """Linha de `eleitorado_munzona`."""

    ano: int
    sg_uf: str
    ds_cargo: str
    cd_mun_ibge: int
    nr_zona: int
    aptos: int
    validos: int


@dataclass
class DadosMemoria:
    """Conteúdo das tabelas, no mesmo grão dos Parquet."""

    candidaturas: list[Candidatura] = field(default_factory=list)
    municipios: list[Municipio] = field(default_factory=list)
    votos: list[VotoMemoria] = field(default_factory=list)
    eleitorado: list[EleitoradoMemoria] = field(default_factory=list)
    receitas: dict[int, list[ReceitaBruta]] = field(default_factory=dict)
    despesas: dict[int, list[DespesaBruta]] = field(default_factory=dict)
    ipca: list[VariacaoIpca] = field(default_factory=list)


class RepositorioMemoria:
    """Repositorio sobre listas; mesmas semânticas do DuckDB nas leituras de domínio.

    Densidade espacial (H3, pontos) fica fora: só o DuckDB real a exercita.
    """

    def __init__(
        self,
        dt_geracao: str,
        anos: list[int],
        ufs: list[str],
        cargos: list[str],
        dados: DadosMemoria | None = None,
        prestacao: dict[int, str] | None = None,
    ) -> None:
        self._dt = dt_geracao
        self._anos = anos
        self._ufs = ufs
        self._cargos = cargos
        self._d = dados or DadosMemoria()
        self._prestacao = prestacao or {}

    def dt_geracao(self) -> str:
        """DT_GERACAO fixa."""
        return self._dt

    def tp_prestacao_contas(self, ano: int) -> str:
        """Situação fixa por ano (padrão FINAL)."""
        return self._prestacao.get(ano, "FINAL")

    def anos(self) -> list[int]:
        """Anos fixos."""
        return list(self._anos)

    def ufs(self) -> list[str]:
        """UFs fixas."""
        return list(self._ufs)

    def cargos(self) -> list[str]:
        """Cargos fixos."""
        return list(self._cargos)

    def candidaturas(
        self,
        ano: int,
        *,
        uf: str | None = None,
        cargo: str | None = None,
        partido: int | None = None,
        sqs: Sequence[int] | None = None,
    ) -> list[Candidatura]:
        """Filtra e ordena como o SQL."""
        achadas = [
            c
            for c in self._d.candidaturas
            if c.ano == ano
            and (uf is None or c.sg_uf == uf)
            and (cargo is None or c.ds_cargo == cargo)
            and (
                (partido is None and sqs is None)
                or (partido is not None and c.nr_partido == partido)
                or (sqs is not None and c.sq_candidato in sqs)
            )
        ]
        return sorted(achadas, key=lambda c: (c.sg_uf, c.ds_cargo, c.nm_urna, c.sq_candidato))

    def candidatura(self, ano: int, sq_candidato: int) -> Candidatura | None:
        """Busca por chave."""
        return next(
            (c for c in self._d.candidaturas if (c.ano, c.sq_candidato) == (ano, sq_candidato)),
            None,
        )

    def buscar_candidaturas(
        self,
        *,
        termo: str,
        ano: int | None = None,
        cargo: str | None = None,
        uf: str | None = None,
        partido: int | None = None,
        sqs: Sequence[int] | None = None,
        limite: int,
    ) -> tuple[int, list[Candidatura]]:
        """Mesma semântica do SQL: número ou nomes/sigla sem acento; início de palavra primeiro."""
        achadas = [
            c
            for c in self._d.candidaturas
            if (ano is None or c.ano == ano)
            and (cargo is None or c.ds_cargo == cargo)
            and (uf is None or c.sg_uf in ((uf, "BR") if cargo == "PRESIDENTE" else (uf,)))
            and (
                (partido is None and sqs is None)
                or (partido is not None and c.nr_partido == partido)
                or (sqs is not None and c.sq_candidato in sqs)
            )
            and _casa(c, termo)
        ]
        achadas.sort(key=lambda c: (_rank(c, termo), -c.ano, c.nm_urna, c.sq_candidato))
        return len(achadas), achadas[:limite]

    def candidaturas_de_pessoas(self, ano: int, publicos: Sequence[str]) -> list[Candidatura]:
        """Candidaturas do ano cujo `id_publico(pessoa_id)` está em `publicos`."""
        achadas = [
            c for c in self._d.candidaturas if c.ano == ano and id_publico(c.pessoa_id) in publicos
        ]
        return sorted(achadas, key=lambda c: (c.sg_uf, c.ds_cargo, c.nm_urna, c.sq_candidato))

    def pares_de_pessoas(
        self,
        ano_de: int,
        ano_para: int,
        *,
        termo: str | None = None,
        uf: str | None = None,
        cargo: str | None = None,
        limite: int,
    ) -> tuple[int, list[ParDePessoa]]:
        """Junta por `pessoa_id` as candidaturas dos dois anos."""
        pares = [
            ParDePessoa(a, b)
            for a in self._d.candidaturas
            if a.ano == ano_de
            for b in self._d.candidaturas
            if b.ano == ano_para and b.pessoa_id == a.pessoa_id
            if (cargo is None or (a.ds_cargo == cargo and b.ds_cargo == cargo))
            and (uf is None or uf in (a.sg_uf, b.sg_uf))
            and (not termo or _casa(a, termo) or _casa(b, termo))
        ]
        pares.sort(key=lambda p: (p.para.nm_urna, p.para.sq_candidato, p.de.sq_candidato))
        return len(pares), pares[:limite]

    def municipios(self, codigos: Sequence[int] | None = None) -> list[Municipio]:
        """Municípios pedidos."""
        todos = sorted(self._d.municipios, key=lambda m: m.cd_mun_ibge)
        return todos if codigos is None else [m for m in todos if m.cd_mun_ibge in codigos]

    def votos_territorio(
        self,
        ano: int,
        sqs: Sequence[int],
        *,
        por_zona: bool,
        uf: str | None = None,
        cd_mun_ibge: int | None = None,
    ) -> list[VotosTerritorio]:
        """Soma por município/zona."""
        uf_de = {m.cd_mun_ibge: m.uf for m in self._d.municipios}
        soma: dict[tuple[int, int | None], int] = {}
        for v in self._d.votos:
            if v.ano != ano or v.sq_candidato not in sqs or v.cd_mun_ibge not in uf_de:
                continue
            if uf is not None and uf_de[v.cd_mun_ibge] != uf:
                continue
            if cd_mun_ibge is not None and v.cd_mun_ibge != cd_mun_ibge:
                continue
            chave = (v.cd_mun_ibge, v.nr_zona if por_zona else None)
            soma[chave] = soma.get(chave, 0) + v.votos
        return [VotosTerritorio(m, z, n) for (m, z), n in sorted(soma.items(), key=_ordem)]

    def votos_totais(self, ano: int, sqs: Sequence[int]) -> dict[int, int]:
        """Votos totais por candidato."""
        total: dict[int, int] = {}
        for v in self._d.votos:
            if v.ano == ano and v.sq_candidato in sqs:
                total[v.sq_candidato] = total.get(v.sq_candidato, 0) + v.votos
        return total

    def base_eleitoral(
        self,
        ano: int,
        cargo: str,
        *,
        por_zona: bool,
        uf: str | None = None,
        cd_mun_ibge: int | None = None,
    ) -> list[BaseEleitoral]:
        """Soma aptos/válidos por município/zona."""
        soma: dict[tuple[int, int | None], tuple[int, int]] = {}
        for e in self._d.eleitorado:
            if e.ano != ano or e.ds_cargo != cargo or (uf is not None and e.sg_uf != uf):
                continue
            if cd_mun_ibge is not None and e.cd_mun_ibge != cd_mun_ibge:
                continue
            chave = (e.cd_mun_ibge, e.nr_zona if por_zona else None)
            a, v = soma.get(chave, (0, 0))
            soma[chave] = (a + e.aptos, v + e.validos)
        return [BaseEleitoral(m, z, a, v) for (m, z), (a, v) in sorted(soma.items(), key=_ordem)]

    def votos_h3(self, ano: int, sqs: Sequence[int], *, uf: str) -> list[CelulaH3]:
        """Não modelado em memória."""
        raise NotImplementedError("H3 só no DuckDB")

    def pontos(
        self,
        ano: int,
        sqs: Sequence[int],
        *,
        uf: str | None,
        limite: int,
        offset: int,
        grade_graus: float | None = None,
    ) -> tuple[int, list[PontoVotacao]]:
        """Não modelado em memória."""
        raise NotImplementedError("pontos só no DuckDB")

    def votos_sem_coordenada(
        self, ano: int, sqs: Sequence[int], *, uf: str | None, por_h3: bool
    ) -> VotosSemCoordenada:
        """Não modelado em memória."""
        raise NotImplementedError("coordenadas só no DuckDB")

    def receitas(self, ano: int, sqs: Sequence[int]) -> list[ReceitaBruta]:
        """Receitas dos candidatos pedidos."""
        return [r for sq in sqs for r in self._d.receitas.get(sq, [])]

    def despesas(self, ano: int, sqs: Sequence[int]) -> list[DespesaBruta]:
        """Despesas dos candidatos pedidos."""
        return [d for sq in sqs for d in self._d.despesas.get(sq, [])]

    def ipca(self) -> list[VariacaoIpca]:
        """Série fixa."""
        return list(self._d.ipca)

    def ping(self) -> None:
        """Sempre saudável."""

    def fechar(self) -> None:
        """Nada a liberar."""


def _ordem(item: tuple[tuple[int, int | None], object]) -> tuple[int, int]:
    (municipio, zona), _ = item
    return (municipio, zona if zona is not None else 0)


def _campos_busca(c: Candidatura) -> list[str]:
    return [normalizar(t) for t in (c.nm_urna, c.nm_civil or "", c.sg_partido)]


def _casa(c: Candidatura, termo: str) -> bool:
    if termo.isdigit():
        return str(c.nr_candidato or "").startswith(termo) or c.nr_partido == int(termo)
    return any(termo in campo for campo in _campos_busca(c))


def _rank(c: Candidatura, termo: str) -> int:
    """0 = início de palavra (ou prefixo do número), 1 = só substring."""
    if termo.isdigit():
        return 0 if str(c.nr_candidato or "").startswith(termo) else 1
    return 0 if any(f" {campo}".find(f" {termo}") >= 0 for campo in _campos_busca(c)) else 1
