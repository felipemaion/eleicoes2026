"""Aquecimento do cache: pré-calcula em segundo plano as consultas mais acessadas.

Medido em produção: cache frio de 2,4–3,3 s em /candidatos, /gastos e /comparativo (SP, dep.
federal). O aquecimento roda numa thread própria, **um cálculo por vez** (ocupa no máximo uma das
vagas do semáforo, deixando o resto para os usuários), com orçamento de entradas para não
expulsar do LRU o que já está quente. O `/api/health` não espera por ele.
"""

import logging
import threading
from collections.abc import Callable, Iterator

from api.cache_servico import CacheLRU
from api.dominio import UF, Cargo
from api.erros import ErroDominio
from api.repositorio.base import Repositorio
from api.servicos.consultas import candidatos_em_cache, comparativo_em_cache, gastos_em_cache
from api.servicos.grupos import Catalogo, DefinicaoGrupo, candidaturas_do_grupo

logger = logging.getLogger(__name__)

CARGOS_DEPUTADO = (Cargo.DEPUTADO_FEDERAL, Cargo.DEPUTADO_ESTADUAL, Cargo.DEPUTADO_DISTRITAL)
LIMITE_PADRAO, OFFSET_PADRAO = 200, 0  # os defaults que o frontend usa em /candidatos
TENTATIVAS_OCUPADO, ESPERA_OCUPADO_S = 120, 0.5  # cede por até 1 min aos usuários

Consulta = Callable[[], object]


class Aquecimento(threading.Thread):
    """Thread daemon que percorre o plano de consultas até esgotá-lo, o orçamento ou `parar`."""

    def __init__(
        self, repo: Repositorio, catalogo: Catalogo, cache: CacheLRU, max_entradas: int
    ) -> None:
        super().__init__(name="aquecimento-cache", daemon=True)
        self._repo, self._catalogo, self._cache = repo, catalogo, cache
        self._max_entradas = max_entradas
        self._parar = threading.Event()
        self.aquecidas = 0
        self.erros = 0

    def parar(self) -> None:
        """Pede o fim; vale entre duas consultas (a em curso termina)."""
        self._parar.set()

    def run(self) -> None:
        """Executa o plano; falha de uma consulta é logada e contada, nunca engolida."""
        try:
            for nome, consulta in self._plano():
                if self._parar.is_set() or self.aquecidas >= self._max_entradas:
                    break
                try:
                    self._executar(consulta)
                    self.aquecidas += 1
                except Exception:
                    self.erros += 1
                    logger.exception("aquecimento: falhou %s", nome)
        except Exception:  # o próprio plano (consulta de candidaturas) falhou
            self.erros += 1
            logger.exception("aquecimento: plano interrompido")
        logger.info("aquecimento: %d consultas, %d erros", self.aquecidas, self.erros)

    def _executar(self, consulta: Consulta) -> None:
        """Roda a consulta; se o servidor estiver ocupado (503), espera a vez dos usuários."""
        for tentativa in range(TENTATIVAS_OCUPADO):
            try:
                with self._cache.baixa_prioridade():
                    consulta()
                return
            except ErroDominio as erro:
                if erro.status != 503 or tentativa == TENTATIVAS_OCUPADO - 1:
                    raise
                if self._parar.wait(ESPERA_OCUPADO_S):
                    return

    def _plano(self) -> Iterator[tuple[str, Consulta]]:
        """Brasil primeiro (o mais pedido), depois cada UF; candidatos/gastos por grupo."""
        repo, catalogo, cache = self._repo, self._catalogo, self._cache
        for grupo in catalogo.grupos.values():
            for uf, cargo in self._recortes(grupo):
                uf_v, cargo_v = (uf.value if uf else None), cargo.value
                yield (
                    f"candidatos {grupo.id} {uf_v} {cargo_v}",
                    lambda g=grupo.id, u=uf_v, c=cargo_v: candidatos_em_cache(  # type: ignore[misc]
                        repo,
                        catalogo,
                        cache,
                        grupo=g,
                        uf=u,
                        cargo=c,
                        limite=LIMITE_PADRAO,
                        offset=OFFSET_PADRAO,
                    ),
                )
                yield (
                    f"gastos {grupo.id} {uf_v} {cargo_v}",
                    lambda g=grupo.id, u=uf_v, c=cargo_v: gastos_em_cache(  # type: ignore[misc]
                        repo, catalogo, cache, grupo=g, uf=u, cargo=c
                    ),
                )
        for comparacao in catalogo.comparacoes.values():
            para = catalogo.grupo(comparacao.para)
            for uf, cargo in self._recortes(para):
                uf_v = uf.value if uf else None
                yield (
                    f"comparativo {comparacao.id} {uf_v} {cargo.value}",
                    lambda i=comparacao.id, u=uf_v, c=cargo: comparativo_em_cache(  # type: ignore[misc]
                        repo,
                        catalogo,
                        cache,
                        comparacao=i,
                        cargo=c,
                        uf=u,
                        mesmos_candidatos=False,
                    ),
                )

    def _recortes(self, grupo: DefinicaoGrupo) -> Iterator[tuple[UF | None, Cargo]]:
        """(UF, cargo) com candidatos do grupo: Brasil (`None`) e cada UF, só deputados."""
        ufs_validas = {u.value: u for u in UF}
        for cargo in CARGOS_DEPUTADO:
            achadas = candidaturas_do_grupo(self._repo, grupo, cargo=cargo.value)
            if not achadas:
                continue
            yield None, cargo
            for sigla in sorted({c.sg_uf for c in achadas} & ufs_validas.keys()):
                yield ufs_validas[sigla], cargo
