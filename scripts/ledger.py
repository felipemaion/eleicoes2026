#!/usr/bin/env python3
"""Registro de desenvolvimento: tempo, tokens e custo por tarefa.

Duas fontes alimentam o registro:

* **Transcripts de sessao** (`~/.claude/projects/<slug>/*.jsonl`) — cada mensagem
  do assistente carrega seu proprio bloco `usage`. E a fonte confiavel de tokens:
  nao depende de nenhum agente lembrar de anotar.
* **Eventos de tarefa** (`docs/registro/ledger/AAAA-MM.jsonl`) — inicio e fim de
  cada tarefa, com papel, modelo, branch e veredito da revisao.

O cruzamento dos dois produz `docs/registro/RELATORIO.md`.

Uso:
    ledger.py evento --task T-001 --papel backend --modelo claude-sonnet-5 --acao inicio
    ledger.py coletar
    ledger.py relatorio
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# Precos
# --------------------------------------------------------------------------- #


class UnknownModelError(ValueError):
    """Modelo sem preco de tabela.

    Falhamos alto de proposito: um custo estimado com preco errado e pior que
    custo nenhum, porque parece confiavel.
    """


@dataclass(frozen=True)
class ModelPrice:
    """Preco em dolares por milhao de tokens."""

    input_per_mtok: float
    output_per_mtok: float


#: Precos de tabela da API Anthropic. Conferidos em 2026-10-07.
PRICES: dict[str, ModelPrice] = {
    "claude-opus-5-5": ModelPrice(4.00, 20.00),
    "claude-sonnet-5-5": ModelPrice(2.00, 10.00),
    "claude-opus-5": ModelPrice(5.00, 25.00),
    "claude-opus-4-8": ModelPrice(5.00, 25.00),
    "claude-sonnet-5": ModelPrice(2.00, 10.00),
    "claude-sonnet-4-6": ModelPrice(3.00, 15.00),
    "claude-haiku-4-5": ModelPrice(1.00, 5.00),
}

#: Leitura de cache custa um decimo do preco de entrada.
CACHE_READ_MULTIPLIER = 0.10
#: Escrita de cache com TTL de uma hora custa o dobro da entrada.
CACHE_WRITE_1H_MULTIPLIER = 2.00
#: Escrita de cache com TTL de cinco minutos custa um quarto a mais.
CACHE_WRITE_5M_MULTIPLIER = 1.25

_TOKENS_PER_MTOK = 1_000_000
#: Marcador que o Claude Code usa quando a mensagem vem dele, nao de um
#: modelo: aviso de limite de sessao e afins. Zero tokens, nenhuma chamada.
SYNTHETIC_MODEL = "<synthetic>"

#: Sufixo de janela de contexto, como em `claude-opus-5[1m]`.
_SUFIXO_JANELA = re.compile(r"\[[^\]]*\]$")
#: Sufixo de data da versao, como em `claude-haiku-4-5-20251001`.
_SUFIXO_DATA = re.compile(r"-\d{8}$")


def normalize_model(model: str) -> str:
    """Reduz o id reportado pelo runtime ao nome que a tabela de precos conhece.

    `claude-opus-5[1m]` e `claude-haiku-4-5-20251001` viram `claude-opus-5` e
    `claude-haiku-4-5`. Sem isso, uma versao datada nao acha preco e o custo
    daquele modelo desaparece do relatorio.
    """
    return _SUFIXO_DATA.sub("", _SUFIXO_JANELA.sub("", model.strip()))


# --------------------------------------------------------------------------- #
# Uso de tokens
# --------------------------------------------------------------------------- #


def _as_int(value: object) -> int:
    """Converte um campo do transcript em inteiro, tratando ausencia como zero."""
    return value if isinstance(value, int) else 0


@dataclass(frozen=True)
class TokenUsage:
    """Tokens de uma ou mais mensagens, separados pelo preco que cada tipo paga."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_1h_tokens: int = 0
    cache_write_5m_tokens: int = 0

    @classmethod
    def from_transcript(cls, raw: object) -> TokenUsage:
        """Le o bloco `usage` de uma mensagem do transcript.

        `input_tokens` no transcript e apenas o resto nao cacheado; o prompt
        completo e a soma dos tres campos de entrada.
        """
        if not isinstance(raw, dict):
            return cls()
        creation = raw.get("cache_creation")
        creation = creation if isinstance(creation, dict) else {}
        return cls(
            input_tokens=_as_int(raw.get("input_tokens")),
            output_tokens=_as_int(raw.get("output_tokens")),
            cache_read_tokens=_as_int(raw.get("cache_read_input_tokens")),
            cache_write_1h_tokens=_as_int(creation.get("ephemeral_1h_input_tokens")),
            cache_write_5m_tokens=_as_int(creation.get("ephemeral_5m_input_tokens")),
        )

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_1h_tokens=self.cache_write_1h_tokens + other.cache_write_1h_tokens,
            cache_write_5m_tokens=self.cache_write_5m_tokens + other.cache_write_5m_tokens,
        )

    @property
    def prompt_tokens(self) -> int:
        """Tamanho real do prompt: o resto nao cacheado mais tudo que veio do cache."""
        return (
            self.input_tokens
            + self.cache_read_tokens
            + self.cache_write_1h_tokens
            + (self.cache_write_5m_tokens)
        )


def estimate_cost(usage: TokenUsage, model: str) -> float:
    """Custo em dolares de um uso de tokens, pelo preco de tabela do modelo."""
    price = PRICES.get(normalize_model(model))
    if price is None:
        raise UnknownModelError(f"modelo sem preco de tabela: {model}")
    entrada = price.input_per_mtok / _TOKENS_PER_MTOK
    saida = price.output_per_mtok / _TOKENS_PER_MTOK
    return (
        usage.input_tokens * entrada
        + usage.cache_read_tokens * entrada * CACHE_READ_MULTIPLIER
        + usage.cache_write_1h_tokens * entrada * CACHE_WRITE_1H_MULTIPLIER
        + usage.cache_write_5m_tokens * entrada * CACHE_WRITE_5M_MULTIPLIER
        + usage.output_tokens * saida
    )


# --------------------------------------------------------------------------- #
# Leitura dos transcripts
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TranscriptRecord:
    """Uma mensagem do assistente, com o que ela custou."""

    message_id: str
    model: str
    timestamp: str
    session_id: str
    is_subagent: bool
    usage: TokenUsage
    git_branch: str = ""


def parse_transcript(path: Path) -> Iterator[TranscriptRecord]:
    """Le um transcript de sessao, devolvendo uma entrada por mensagem do assistente.

    Linhas corrompidas sao ignoradas em silencio: um transcript sendo escrito
    enquanto lemos termina com uma linha parcial, e isso nao e motivo para
    derrubar o relatorio inteiro.
    """
    vistos: set[str] = set()
    with path.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            registro = _parse_line(linha)
            if registro is None or registro.message_id in vistos:
                continue
            vistos.add(registro.message_id)
            yield registro


def _parse_line(linha: str) -> TranscriptRecord | None:
    """Converte uma linha do transcript em registro, ou None se nao for util."""
    try:
        dados = json.loads(linha)
    except json.JSONDecodeError:
        return None
    if not isinstance(dados, dict) or dados.get("type") != "assistant":
        return None
    mensagem = dados.get("message")
    if not isinstance(mensagem, dict) or "usage" not in mensagem:
        return None
    message_id = mensagem.get("id")
    model = mensagem.get("model")
    if not isinstance(message_id, str) or not isinstance(model, str):
        return None
    if model == SYNTHETIC_MODEL:
        # Nao e uso de modelo: descartar aqui evita uma linha fantasma no
        # relatorio e preserva o aviso de "modelo sem preco" para o caso que
        # realmente importa.
        return None
    return TranscriptRecord(
        message_id=message_id,
        model=model,
        timestamp=str(dados.get("timestamp", "")),
        session_id=str(dados.get("sessionId", "")),
        is_subagent=bool(dados.get("isSidechain", False)),
        usage=TokenUsage.from_transcript(mensagem["usage"]),
        git_branch=str(dados.get("gitBranch", "")),
    )


def transcript_dir(project_root: Path) -> Path:
    """Diretorio de transcripts do Claude Code para um projeto."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(project_root.resolve()))
    return Path.home() / ".claude" / "projects" / slug


def transcript_dirs(project_root: Path) -> list[Path]:
    """Diretorios de transcript do projeto: o da raiz e o de cada worktree.

    Cada agente roda com o diretorio de trabalho na propria worktree, e o Claude
    Code deriva o nome do diretorio de transcript do caminho. Sem incluir as
    worktrees, o registro contabiliza so o orquestrador.

    O sufixo `--worktrees-` e exigido de proposito: aceitar qualquer nome que
    comece igual arrastaria para a conta um projeto vizinho de nome parecido.
    """
    base = transcript_dir(project_root)
    encontrados = [base] if base.is_dir() else []
    if base.parent.is_dir():
        encontrados += sorted(
            d for d in base.parent.glob(f"{base.name}--worktrees-*") if d.is_dir()
        )
    return encontrados


def collect_records(project_root: Path) -> list[TranscriptRecord]:
    """Le todos os transcripts do projeto, sem repetir mensagem entre arquivos."""
    vistos: set[str] = set()
    registros: list[TranscriptRecord] = []
    for diretorio in transcript_dirs(project_root):
        for arquivo in sorted(diretorio.glob("*.jsonl")):
            for registro in parse_transcript(arquivo):
                if registro.message_id in vistos:
                    continue
                vistos.add(registro.message_id)
                registros.append(registro)
    return registros


# --------------------------------------------------------------------------- #
# Agregacao
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ModelSummary:
    """Total consolidado de um modelo."""

    messages: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float = 0.0


def summarize(records: Iterable[TranscriptRecord]) -> dict[str, ModelSummary]:
    """Consolida os registros por modelo, ja normalizado."""
    resumo: dict[str, ModelSummary] = {}
    for registro in records:
        if registro.model == SYNTHETIC_MODEL:
            continue
        modelo = normalize_model(registro.model)
        atual = resumo.get(modelo, ModelSummary())
        resumo[modelo] = replace(
            atual, messages=atual.messages + 1, usage=atual.usage + registro.usage
        )
    return {
        modelo: replace(total, cost_usd=_safe_cost(total.usage, modelo))
        for modelo, total in resumo.items()
    }


def _safe_cost(usage: TokenUsage, model: str) -> float:
    """Custo do modelo, ou zero quando o preco e desconhecido (com aviso no stderr)."""
    try:
        return estimate_cost(usage, model)
    except UnknownModelError as erro:
        print(f"aviso: {erro}; custo contado como zero", file=sys.stderr)
        return 0.0


# --------------------------------------------------------------------------- #
# Eventos de tarefa
# --------------------------------------------------------------------------- #


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class TaskEvent:
    """Marco de uma tarefa: quem, com qual modelo, fazendo o que, e quando."""

    task: str
    papel: str
    modelo: str
    acao: str
    timestamp: str = field(default_factory=_agora)
    fase: str = ""
    descricao: str = ""
    branch: str = ""
    veredito: str = ""

    @classmethod
    def from_dict(cls, dados: dict[str, object]) -> TaskEvent:
        """Reconstroi um evento, ignorando campos que a versao atual nao conhece."""
        conhecidos = {campo for campo in cls.__dataclass_fields__}
        return cls(**{k: str(v) for k, v in dados.items() if k in conhecidos})


def append_event(path: Path, event: TaskEvent) -> None:
    """Acrescenta um evento ao ledger do mes, criando o arquivo se preciso."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


def read_events(path: Path) -> list[TaskEvent]:
    """Le os eventos de um ledger mensal; arquivo ausente significa nenhum evento."""
    if not path.is_file():
        return []
    eventos: list[TaskEvent] = []
    for linha in path.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            dados = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(dados, dict):
            eventos.append(TaskEvent.from_dict(dados))
    return eventos


def ledger_path(project_root: Path, quando: datetime | None = None) -> Path:
    """Caminho do ledger vivo do mes corrente.

    O arquivo termina em `.raw.jsonl` e fica fora do git de proposito: os agentes
    escrevem nele a cada inicio e fim de tarefa, e um arquivo versionado sendo
    alterado o tempo todo trava qualquer `git pull` na raiz. A consolidacao para
    o arquivo versionado acontece quando o orquestrador decide, via
    `ledger.py consolidar`.
    """
    momento = quando or datetime.now(timezone.utc)
    return project_root / "docs" / "registro" / "ledger" / f"{momento:%Y-%m}.raw.jsonl"


def consolidated_ledger_path(project_root: Path, quando: datetime | None = None) -> Path:
    """Caminho do ledger versionado do mes corrente."""
    momento = quando or datetime.now(timezone.utc)
    return project_root / "docs" / "registro" / "ledger" / f"{momento:%Y-%m}.jsonl"


def consolidate(project_root: Path, quando: datetime | None = None) -> int:
    """Copia os eventos do ledger vivo para o versionado, sem repetir.

    Devolve quantos eventos novos foram acrescentados.
    """
    vivo = read_events(ledger_path(project_root, quando))
    destino = consolidated_ledger_path(project_root, quando)
    ja_gravados = {(e.timestamp, e.task, e.papel, e.acao) for e in read_events(destino)}
    novos = [e for e in vivo if (e.timestamp, e.task, e.papel, e.acao) not in ja_gravados]
    for evento in novos:
        append_event(destino, evento)
    return len(novos)


# --------------------------------------------------------------------------- #
# Relatorio
# --------------------------------------------------------------------------- #


def render_report(resumo: dict[str, ModelSummary], events: Iterable[TaskEvent]) -> str:
    """Monta o RELATORIO.md a partir do resumo por modelo e dos eventos de tarefa."""
    linhas = [
        "# Registro de desenvolvimento",
        "",
        f"Gerado em {_agora()}.",
        "",
        "## Custo por modelo",
        "",
        "| Modelo | Mensagens | Entrada | Cache lido | Cache escrito | Saida | Custo (US$) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    total_custo = 0.0
    for modelo in sorted(resumo, key=lambda m: -resumo[m].cost_usd):
        item = resumo[modelo]
        uso = item.usage
        escrito = uso.cache_write_1h_tokens + uso.cache_write_5m_tokens
        linhas.append(
            f"| `{modelo}` | {item.messages:,} | {uso.input_tokens:,} | "
            f"{uso.cache_read_tokens:,} | {escrito:,} | {uso.output_tokens:,} | "
            f"{item.cost_usd:,.2f} |"
        )
        total_custo += item.cost_usd
    linhas += ["", f"**Custo total: US$ {total_custo:,.2f}**", ""]

    eventos = list(events)
    if eventos:
        linhas += [
            "## Tarefas",
            "",
            "| Quando | Tarefa | Fase | Papel | Modelo | Acao | Veredito |",
            "|---|---|---|---|---|---|---|",
        ]
        linhas += [
            f"| {e.timestamp} | {e.task} | {e.fase or '-'} | {e.papel} | `{e.modelo}` | "
            f"{e.acao} | {e.veredito or '-'} |"
            for e in eventos
        ]
        linhas.append("")
    return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# Linha de comando
# --------------------------------------------------------------------------- #


def project_root() -> Path:
    """Raiz do repositorio.

    `ELEICOES_ROOT` tem prioridade para que os testes — e um agente rodando de
    outro diretorio — apontem o ledger para onde quiserem.
    """
    from os import environ

    definido = environ.get("ELEICOES_ROOT")
    return Path(definido).resolve() if definido else Path(__file__).resolve().parent.parent


def _cmd_evento(args: argparse.Namespace) -> int:
    raiz = project_root()
    evento = TaskEvent(
        task=args.task,
        papel=args.papel,
        modelo=args.modelo,
        acao=args.acao,
        fase=args.fase,
        descricao=args.descricao,
        branch=args.branch,
        veredito=args.veredito,
    )
    append_event(ledger_path(raiz), evento)
    print(f"{evento.timestamp} {evento.task} {evento.papel} {evento.acao}")
    return 0


def _cmd_coletar(args: argparse.Namespace) -> int:
    raiz = project_root()
    resumo = summarize(collect_records(raiz))
    if not resumo:
        print(f"nenhum transcript encontrado em {transcript_dir(raiz)}", file=sys.stderr)
        return 1
    for modelo, item in sorted(resumo.items(), key=lambda par: -par[1].cost_usd):
        print(f"{modelo:24} {item.messages:5} msgs  US$ {item.cost_usd:8,.2f}")
    print(f"{'TOTAL':24} {'':5}       US$ {sum(i.cost_usd for i in resumo.values()):8,.2f}")
    return 0


def _cmd_relatorio(args: argparse.Namespace) -> int:
    raiz = project_root()
    eventos = read_events(consolidated_ledger_path(raiz)) + read_events(ledger_path(raiz))
    texto = render_report(summarize(collect_records(raiz)), eventos)
    destino = raiz / "docs" / "registro" / "RELATORIO.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    print(f"relatorio escrito em {destino.relative_to(raiz)}")
    return 0


def _cmd_consolidar(args: argparse.Namespace) -> int:
    raiz = project_root()
    novos = consolidate(raiz)
    print(f"{novos} evento(s) consolidado(s) em {consolidated_ledger_path(raiz).name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    evento = sub.add_parser("evento", help="registra o inicio ou o fim de uma tarefa")
    evento.add_argument("--task", required=True, help="identificador, ex.: T-014")
    evento.add_argument("--papel", required=True, help="dados, analise, backend, frontend")
    evento.add_argument("--modelo", required=True, help="id do modelo em uso")
    evento.add_argument("--acao", required=True, choices=["inicio", "fim", "revisao"])
    evento.add_argument("--fase", default="", help="fase do plano")
    evento.add_argument("--descricao", default="", help="resumo de uma linha")
    evento.add_argument("--branch", default="", help="branch de trabalho")
    evento.add_argument("--veredito", default="", help="aprovado, ajustes, rejeitado")
    evento.set_defaults(func=_cmd_evento)

    sub.add_parser("coletar", help="resume tokens e custo dos transcripts").set_defaults(
        func=_cmd_coletar
    )
    sub.add_parser("relatorio", help="regenera docs/registro/RELATORIO.md").set_defaults(
        func=_cmd_relatorio
    )
    sub.add_parser(
        "consolidar", help="passa os eventos do ledger vivo para o versionado"
    ).set_defaults(func=_cmd_consolidar)

    args = parser.parse_args(argv)
    resultado: int = args.func(args)
    return resultado


if __name__ == "__main__":
    raise SystemExit(main())
