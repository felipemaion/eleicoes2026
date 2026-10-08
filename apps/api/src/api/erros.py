"""Erros de domínio com corpo padronizado `{"detail": {"codigo", "mensagem"}}`."""


class ErroDominio(Exception):  # noqa: N818 - nome de domínio
    """Falha esperada de uso da API (parâmetro incoerente, recurso inexistente)."""

    def __init__(self, status: int, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem


def parametro_invalido(codigo: str, mensagem: str) -> ErroDominio:
    """422: combinação de parâmetros que o schema sozinho não barra."""
    return ErroDominio(422, codigo, mensagem)


def nao_encontrado(codigo: str, mensagem: str) -> ErroDominio:
    """404: recurso inexistente."""
    return ErroDominio(404, codigo, mensagem)
