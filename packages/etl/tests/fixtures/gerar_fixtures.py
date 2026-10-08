"""Gera as fixtures reais mínimas (2 municípios do AC, 2022) a partir de ``data/raw``.

Uso (na raiz do repo, depois de ``etl baixar --ano 2022``)::

    uv run python packages/etl/tests/fixtures/gerar_fixtures.py

Cada ZIP de saída imita o original: um CSV por UF, o ``_BR`` (presidente) e um ``_BRASIL``
(união) — este último existe de propósito, para o teste provar que ele é ignorado.
CPF e título são SUBSTITUÍDOS por valores sintéticos: dado pessoal nunca entra em fixture.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
BRUTO = RAIZ / "data" / "raw" / "tse"
SAIDA = Path(__file__).resolve().parent
ANO = 2022
UF = "AC"
MUNICIPIOS_TSE = {"01007", "01015"}  # Bujari, Capixaba
SINTETICO = {"NR_CPF_CANDIDATO", "NR_TITULO_ELEITORAL_CANDIDATO"}
ZIPS = {  # id do catálogo → <id>/<arquivo> em data/raw/tse
    "municipio_tse_ibge": "municipio_tse_ibge/municipio_tse_ibge.zip",
    **{
        k: f"{k}/{k}_{ANO}.zip"
        for k in (
            "consulta_cand", "consulta_vagas", "detalhe_votacao_munzona",
            "votacao_partido_munzona", "votacao_candidato_munzona", "eleitorado_local_votacao",
        )
    },
}  # fmt: skip


def _linhas(zf: zipfile.ZipFile, membro: str):  # type: ignore[no-untyped-def]
    with zf.open(membro) as f:
        yield from csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def _escrever(zf: zipfile.ZipFile, membro: str, cab: list[str], linhas: list[list[str]]) -> None:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(cab)
    w.writerows(linhas)
    zf.writestr(membro, buf.getvalue().encode("latin-1"))


def _manter(cab: list[str], linha: list[str], sq_ok: set[str] | None) -> bool:
    d = dict(zip(cab, linha, strict=True))
    if "CD_MUNICIPIO" in d and d["CD_MUNICIPIO"].zfill(5) not in MUNICIPIOS_TSE:
        return False
    return sq_ok is None or "SQ_CANDIDATO" not in d or d["SQ_CANDIDATO"] in sq_ok


def _recorte(
    origem: Path, destino: Path, membros_uf: list[str], sq_ok: set[str] | None
) -> set[str]:
    """Filtra os membros indicados; devolve os SQ_CANDIDATO mantidos (se houver a coluna)."""
    sqs: set[str] = set()
    with (
        zipfile.ZipFile(origem) as zin,
        zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout,
    ):
        todas: list[list[str]] = []
        cab_final: list[str] = []
        for membro in membros_uf:
            it = _linhas(zin, membro)
            cab = next(it)
            cab_final = cab
            linhas = [x for x in it if _manter(cab, x, sq_ok)]
            if "SQ_CANDIDATO" in cab:
                sqs |= {dict(zip(cab, x, strict=True))["SQ_CANDIDATO"] for x in linhas}
            linhas = [_anonimizar(cab, x, len(todas) + i) for i, x in enumerate(linhas)]
            _escrever(zout, membro, cab, linhas)
            todas += linhas
        # `_BRASIL` = união: serve para provar que o parser o ignora (senão duplica tudo).
        brasil = membros_uf[0].rsplit("_", 1)[0] + "_BRASIL.csv"
        _escrever(zout, brasil, cab_final, todas)
    return sqs


def _cpf_sintetico(i: int) -> str:
    """CPF com dígitos verificadores válidos (o ETL rejeita CPF malformado), base 900…"""
    nums = [int(d) for d in f"{900000000 + i:09d}"]
    for n in (9, 10):
        nums.append(sum(d * (n + 1 - k) for k, d in enumerate(nums)) * 10 % 11 % 10)
    return "".join(map(str, nums))


def _anonimizar(cab: list[str], linha: list[str], i: int) -> list[str]:
    d = dict(zip(cab, linha, strict=True))
    for c in SINTETICO & d.keys():
        d[c] = _cpf_sintetico(i) if c == "NR_CPF_CANDIDATO" else f"{i + 1:012d}"
    if "DS_EMAIL" in d:
        d["DS_EMAIL"] = "NÃO DIVULGÁVEL"
    return [d[c] for c in cab]


# Pessoas físicas (doadores, fornecedores, vice) e texto livre: nunca entram em fixture.
PII_CONTAS = {
    "NR_CPF_CANDIDATO": "-4", "NR_CPF_VICE_CANDIDATO": "-4", "NR_CPF_CNPJ_DOADOR": "-1",
    "NM_DOADOR": "#NULO", "NM_DOADOR_RFB": "#NULO", "NR_CPF_CNPJ_FORNECEDOR": "-1",
    "NM_FORNECEDOR": "#NULO", "NM_FORNECEDOR_RFB": "#NULO", "DS_RECEITA": "#NULO",
    "DS_DESPESA": "#NULO", "NR_RECIBO_DOACAO": "#NULO",
}  # fmt: skip
CONTAS = ("receitas_candidatos", "despesas_contratadas_candidatos", "despesas_pagas_candidatos")


def _contas(sqs: set[str]) -> None:
    """Prestação de contas de poucas candidaturas (as menores) do recorte, mais 40 linhas do
    ``_BR``; pagas filtradas por SQ_PRESTADOR_CONTAS. Doadores/fornecedores anonimizados."""
    origem = BRUTO / f"prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ANO}.zip"
    destino = SAIDA / f"prestacao_de_contas_eleitorais_candidatos_{ANO}.zip"
    with zipfile.ZipFile(origem) as zin:

        def ler(nome: str, suf: str) -> tuple[list[str], list[list[str]]]:
            it = _linhas(zin, f"{nome}_{ANO}_{suf}.csv")
            return next(it), list(it)

        dados = {(n, suf): ler(n, suf) for n in CONTAS for suf in (UF, "BR")}

    def por_cand(nome: str) -> dict[str, int]:
        cab, linhas = dados[(nome, UF)]
        k = cab.index("SQ_CANDIDATO")
        cont: dict[str, int] = {}
        for x in linhas:
            if x[k] in sqs:
                cont[x[k]] = cont.get(x[k], 0) + 1
        return cont

    rec, con = por_cand("receitas_candidatos"), por_cand("despesas_contratadas_candidatos")
    ambos = sorted(set(rec) & set(con), key=lambda q: (rec[q] + con[q], q))
    mantidos = set(ambos[:8])
    cab_br, linhas_br = dados[("receitas_candidatos", "BR")]
    k_br = cab_br.index("SQ_CANDIDATO")
    presidente = linhas_br[0][k_br]
    mantidos.add(presidente)

    prestadores: set[str] = set()
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
        for nome in CONTAS:  # pagas por último: precisa dos prestadores das outras duas
            todas: list[list[str]] = []
            for suf in (UF, "BR"):
                cab, linhas = dados[(nome, suf)]
                i = {c: k for k, c in enumerate(cab)}
                if nome == "despesas_pagas_candidatos":
                    sel = [x for x in linhas if x[i["SQ_PRESTADOR_CONTAS"]] in prestadores]
                    sel = sel[:40] if suf == "BR" else sel
                else:
                    sel = [x for x in linhas if x[i["SQ_CANDIDATO"]] in mantidos]
                    sel = sel[:40] if suf == "BR" else sel
                    prestadores |= {x[i["SQ_PRESTADOR_CONTAS"]] for x in sel}
                for x in sel:
                    for c, v in PII_CONTAS.items():
                        if c in i:
                            x[i[c]] = v
                _escrever(zout, f"{nome}_{ANO}_{suf}.csv", cab, sel)
                todas += sel
            _escrever(zout, f"{nome}_{ANO}_BRASIL.csv", cab, todas)  # união: deve ser ignorada


def main() -> None:
    nome = lambda k, suf: f"{k}_{ANO}_{suf}.csv"  # noqa: E731
    # votação candidato (define o conjunto de candidatos mantidos)
    k = "votacao_candidato_munzona"
    sqs = _recorte(BRUTO / ZIPS[k], SAIDA / f"{k}_{ANO}.zip", [nome(k, UF), nome(k, "BR")], None)
    for k in ("detalhe_votacao_munzona", "votacao_partido_munzona"):
        _recorte(BRUTO / ZIPS[k], SAIDA / f"{k}_{ANO}.zip", [nome(k, UF), nome(k, "BR")], None)
    k = "consulta_cand"
    _recorte(BRUTO / ZIPS[k], SAIDA / f"{k}_{ANO}.zip", [nome(k, UF), nome(k, "BR")], sqs)
    _contas(sqs)
    k = "consulta_vagas"
    _recorte(BRUTO / ZIPS[k], SAIDA / f"{k}_{ANO}.zip", [nome(k, UF), nome(k, "BR")], None)
    # locais: um único CSV, filtrado por município
    k = "eleitorado_local_votacao"
    with (
        zipfile.ZipFile(BRUTO / ZIPS[k]) as zin,
        zipfile.ZipFile(SAIDA / f"{k}_{ANO}.zip", "w", zipfile.ZIP_DEFLATED) as zout,
    ):
        it = _linhas(zin, f"{k}_{ANO}.csv")
        cab = next(it)
        _escrever(zout, f"{k}_{ANO}.csv", cab, [x for x in it if _manter(cab, x, None)])
    # votação por seção: um CSV por UF, recortado nos mesmos municípios
    k = "votacao_secao"
    with (
        zipfile.ZipFile(BRUTO / f"{k}/{k}_{ANO}_{UF}.zip") as zin,
        zipfile.ZipFile(SAIDA / f"{k}_{ANO}_{UF}.zip", "w", zipfile.ZIP_DEFLATED) as zout,
    ):
        it = _linhas(zin, nome(k, UF))
        cab = next(it)
        _escrever(zout, nome(k, UF), cab, [x for x in it if _manter(cab, x, None)])
    # crosswalk: só AC
    k = "municipio_tse_ibge"
    with (
        zipfile.ZipFile(BRUTO / ZIPS[k]) as zin,
        zipfile.ZipFile(SAIDA / f"{k}.zip", "w", zipfile.ZIP_DEFLATED) as zout,
    ):
        it = _linhas(zin, f"{k}.csv")
        cab = next(it)
        i = cab.index("SG_UF")
        _escrever(zout, f"{k}.csv", cab, [x for x in it if x[i] == UF])


if __name__ == "__main__":
    main()
