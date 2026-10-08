"""Cache LRU dos resultados dos serviços, invalidado pelo `dt_geracao` dos dados.

A chave inclui o `dt_geracao`: carga nova de dados = chaves novas, as antigas saem por LRU.
Os valores são modelos pydantic devolvidos como estão (os serviços não os mutam).
"""

from collections import OrderedDict
from collections.abc import Callable, Hashable
from threading import BoundedSemaphore, Event, Lock

from api.erros import ErroDominio


class CacheLRU:
    """LRU thread-safe com single-flight por chave e teto de cálculos simultâneos.

    * Single-flight: chamadas simultâneas à mesma chave esperam o líder (sem avalanche).
    * Semáforo: no máximo `simultaneos` cálculos ao mesmo tempo; o excedente recebe 503
      (a CPU do servidor é escassa — ADR 0002). Hit de cache e quem espera o líder não gastam vaga.
    """

    def __init__(self, capacidade: int = 256, simultaneos: int = 4) -> None:
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
            if not self._vagas.acquire(blocking=False):
                raise ErroDominio(503, "servidor_ocupado", "muitos cálculos em andamento; tente já")
            try:
                valor = calcular()
            finally:
                self._vagas.release()
            with self._trava:
                self._itens[completa] = valor
                self._itens.move_to_end(completa)
                while len(self._itens) > self._capacidade:
                    self._itens.popitem(last=False)
            return valor
        finally:
            with self._trava:
                self._voando.pop(completa).set()

    def __len__(self) -> int:
        return len(self._itens)
