"""Cache LRU dos resultados dos serviços, invalidado pelo `dt_geracao` dos dados.

A chave inclui o `dt_geracao`: carga nova de dados = chaves novas, as antigas saem por LRU.
Os valores são modelos pydantic devolvidos como estão (os serviços não os mutam).
"""

from collections import OrderedDict
from collections.abc import Callable, Hashable
from threading import Lock


class CacheLRU:
    """LRU simples e thread-safe (as rotas `def` rodam no threadpool)."""

    def __init__(self, capacidade: int = 256) -> None:
        self._capacidade = capacidade
        self._itens: OrderedDict[tuple[str, Hashable], object] = OrderedDict()
        self._trava = Lock()

    def obter[T](self, dt_geracao: str, chave: Hashable, calcular: Callable[[], T]) -> T:
        """Valor em cache ou `calcular()`; o cálculo roda fora da trava (pode duplicar)."""
        completa = (dt_geracao, chave)
        with self._trava:
            if completa in self._itens:
                self._itens.move_to_end(completa)
                return self._itens[completa]  # type: ignore[return-value]
        valor = calcular()
        with self._trava:
            self._itens[completa] = valor
            self._itens.move_to_end(completa)
            while len(self._itens) > self._capacidade:
                self._itens.popitem(last=False)
        return valor

    def __len__(self) -> int:
        return len(self._itens)
