"""Cache LRU dos resultados dos serviços, invalidado pelo `dt_geracao` dos dados.

A chave inclui o `dt_geracao`: carga nova de dados = chaves novas, as antigas saem por LRU.
Os valores são modelos pydantic devolvidos como estão (os serviços não os mutam).
"""

from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import BoundedSemaphore, Event, Lock

from api.erros import ErroDominio

_BAIXA = ContextVar("cache_baixa_prioridade", default=False)


class CacheLRU:
    """LRU thread-safe com single-flight por chave e teto de cálculos simultâneos.

    * Single-flight: chamadas simultâneas à mesma chave esperam o líder (sem avalanche).
    * Semáforo: no máximo `simultaneos` cálculos ao mesmo tempo (a CPU do servidor é escassa —
      ADR 0002). Quem não acha vaga espera na fila até `espera_s`; só então recebe 503. Hit de
      cache e quem espera o líder não gastam vaga.
    * Prioridade: o aquecimento (`baixa_prioridade()`) usa no máximo 1 vaga e cede na hora (503,
      que ele já trata com nova tentativa) se houver usuário na fila.
    """

    def __init__(self, capacidade: int = 256, simultaneos: int = 4, espera_s: float = 10.0) -> None:
        self._espera_s = espera_s
        self._na_fila = 0
        self._baixas = 0
        self._capacidade = capacidade
        self._itens: OrderedDict[tuple[str, Hashable], object] = OrderedDict()
        self._trava = Lock()
        self._vagas = BoundedSemaphore(simultaneos)
        self._voando: dict[tuple[str, Hashable], Event] = {}

    def obter[T](self, dt_geracao: str, chave: Hashable, calcular: Callable[[], T]) -> T:
        """Valor em cache ou `calcular()` (uma vez por chave, dentro do teto de simultâneos)."""
        completa = (dt_geracao, chave)
        while True:
            with self._trava:
                if completa in self._itens:
                    self._itens.move_to_end(completa)
                    return self._itens[completa]  # type: ignore[return-value]
                esperar = self._voando.get(completa)
                if esperar is None:
                    self._voando[completa] = Event()
            if esperar is None:
                break  # sou o líder
            esperar.wait()  # o líder terminou (ou falhou): relê o cache ou assume a liderança
        try:
            baixa = _BAIXA.get()
            self._adquirir(baixa)
            try:
                valor = calcular()
            finally:
                self._liberar(baixa)
            with self._trava:
                self._itens[completa] = valor
                self._itens.move_to_end(completa)
                while len(self._itens) > self._capacidade:
                    self._itens.popitem(last=False)
            return valor
        finally:
            with self._trava:
                self._voando.pop(completa).set()

    @property
    def na_fila(self) -> int:
        """Usuários esperando vaga agora."""
        return self._na_fila

    @staticmethod
    @contextmanager
    def baixa_prioridade() -> Iterator[None]:
        """Cálculos nesta thread cedem aos usuários (usado pelo aquecimento)."""
        marca = _BAIXA.set(True)
        try:
            yield
        finally:
            _BAIXA.reset(marca)

    def _ocupado(self) -> ErroDominio:
        return ErroDominio(503, "servidor_ocupado", "muitos cálculos em andamento; tente já")

    def _adquirir(self, baixa: bool) -> None:
        """Vaga para um cálculo; levanta 503 se a fila estourar a espera (ou se `baixa` ceder)."""
        if baixa:
            with self._trava:
                if self._na_fila or self._baixas or not self._vagas.acquire(blocking=False):
                    raise self._ocupado()
                self._baixas += 1
            return
        if self._vagas.acquire(blocking=False):
            return
        with self._trava:
            self._na_fila += 1
        try:
            if not self._vagas.acquire(timeout=self._espera_s):
                raise self._ocupado()
        finally:
            with self._trava:
                self._na_fila -= 1

    def _liberar(self, baixa: bool) -> None:
        if baixa:
            with self._trava:
                self._baixas -= 1
        self._vagas.release()

    def __len__(self) -> int:
        return len(self._itens)
