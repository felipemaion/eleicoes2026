"""Repositorio sobre DuckDB lendo Parquet; conexão em memória, arquivos só lidos."""

import json
from collections.abc import Sequence
from pathlib import Path

import duckdb

from api.repositorio.base import DadosIndisponiveis
from api.repositorio.modelos import (
    BaseEleitoral,
    Candidatura,
    CelulaH3,
    DespesaBruta,
    Municipio,
    PontoVotacao,
    ReceitaBruta,
    VariacaoIpca,
    VotosSemCoordenada,
    VotosTerritorio,
)

# Datasets com contrato (packages/contratos/tse.py), em `<dir>/<dataset>/ano=AAAA/*.parquet`.
# A API lê só `consulta_cand` como obrigatório; os demais viram view se existirem e, se faltarem,
# a consulta que os usa falha alto (503) em vez de devolver vazio.
CONTRATADOS = (
    "consulta_cand",
    "votacao_candidato_munzona",
    "detalhe_votacao_munzona",
    "eleitorado_local_votacao",
    "municipio_tse_ibge",
    "receitas_candidatos",
    "despesas_contratadas_candidatos",
    "despesas_pagas_candidatos",
)
# TODO(dados): ainda sem contrato — IPCA, área/AMC do município, H3 e votos por local de
# votação. Formato provisório: `<dir>/<nome>.parquet` ou `<dir>/<nome>/*.parquet`.
PROVISORIOS = (
    "municipios_extra",
    "locais_h3",
    "votos_local",
    "ipca",
)
# Colunas que a API lê de cada fonte: validadas na abertura (falha clara, sem `SELECT *`).
COLUNAS_MINIMAS: dict[str, tuple[str, ...]] = {
    "consulta_cand": (
        "nr_turno", "sg_uf", "ds_cargo", "sq_candidato", "nm_urna_candidato", "nr_partido",
        "sg_partido", "ds_situacao_candidatura", "ds_sit_tot_turno", "pessoa_id", "dt_geracao",
    ),
    "votacao_candidato_munzona": (
        "nr_turno", "sg_uf", "cd_mun_ibge", "nr_zona", "sq_candidato",
        "qt_votos_nominais_validos", "dt_geracao",
    ),
    "detalhe_votacao_munzona": (
        "nr_turno", "sg_uf", "ds_cargo", "cd_mun_ibge", "nr_zona", "qt_aptos",
        "qt_total_votos_validos", "dt_geracao",
    ),
    "eleitorado_local_votacao": (
        "nr_turno", "sg_uf", "cd_mun_ibge", "nr_zona", "nr_local_votacao", "nr_latitude",
        "nr_longitude", "qt_eleitor_secao", "dt_geracao",
    ),
    "municipio_tse_ibge": ("cd_mun_ibge", "nm_municipio_ibge", "sg_uf", "dt_geracao"),
    "municipios_extra": ("cd_mun_ibge", "cd_amc", "area_km2"),
    "locais_h3": ("ano", "cd_mun_ibge", "nr_zona", "nr_local", "h3"),
    "votos_local": ("ano", "sq_candidato", "cd_mun_ibge", "nr_zona", "nr_local", "votos"),
    "receitas_candidatos": (
        "nr_turno", "tp_prestacao_contas", "sq_candidato", "ds_fonte_receita",
        "ds_origem_receita", "ds_natureza_receita", "vr_receita", "dt_geracao",
    ),
    "despesas_contratadas_candidatos": (
        "nr_turno", "tp_prestacao_contas", "sq_candidato", "ds_origem_despesa",
        "vr_despesa_contratada", "dt_geracao",
    ),
    "despesas_pagas_candidatos": (
        "nr_turno", "tp_prestacao_contas", "sq_candidato", "ds_origem_despesa",
        "vr_pagto_despesa", "dt_geracao",
    ),
    "ipca": ("mes", "variacao"),
}  # fmt: skip
# `ano` vem da partição hive (`ano=AAAA/`): é ele que o DuckDB poda, sem abrir os outros anos.
# `ds_cargo` vem em caixa de título do TSE ("Deputado Federal"); `upper` casa com o enum `Cargo`.
# Turno 1 em todas as views: 2º turno tem decisão própria (spec §1.3).
_VIEWS = {
    "candidatos": (
        "consulta_cand",
        "SELECT ano, sq_candidato, pessoa_id, nm_urna_candidato AS nm_urna, sg_uf,"
        " upper(ds_cargo) AS ds_cargo, nr_partido, sg_partido, ds_situacao_candidatura,"
        " ds_sit_tot_turno"
        " FROM {fonte} WHERE nr_turno = 1",
    ),
    # Votos nominais válidos somados nas zonas e no voto em trânsito (spec §2.1).
    "votos_munzona": (
        "votacao_candidato_munzona",
        "SELECT ano, sq_candidato, sg_uf, cd_mun_ibge, nr_zona,"
        " SUM(qt_votos_nominais_validos)::BIGINT AS votos FROM {fonte} WHERE nr_turno = 1"
        " GROUP BY ALL",
    ),
    "eleitorado_munzona": (
        "detalhe_votacao_munzona",
        "SELECT ano, sg_uf, upper(ds_cargo) AS ds_cargo, cd_mun_ibge, nr_zona,"
        " SUM(qt_aptos)::BIGINT AS aptos, SUM(qt_total_votos_validos)::BIGINT AS votos_validos"
        " FROM {fonte} WHERE nr_turno = 1 GROUP BY ALL",
    ),
    "municipios_base": (
        "municipio_tse_ibge",
        "SELECT DISTINCT cd_mun_ibge, nm_municipio_ibge AS nome, sg_uf AS uf FROM {fonte}",
    ),
}
_COLUNAS_CANDIDATURA = (
    "ano, sq_candidato, pessoa_id, nm_urna, sg_uf, ds_cargo, nr_partido, sg_partido,"
    " ds_situacao_candidatura, ds_sit_tot_turno"
)
# `sq IN (SELECT unnest(?))`: a lista vai como parâmetro (nunca interpolada no SQL).
_SQS = "sq_candidato IN (SELECT unnest(?::BIGINT[]))"


class RepositorioDuckDB:
    """Consultas parametrizadas sobre `<dir>/*.parquet`; `<dir>/manifesto.json` dá o DT_GERACAO."""

    def __init__(
        self,
        dir_dados: Path,
        threads: int = 2,
        *,
        memory_limit: str = "1200MB",
        max_temp_directory_size: str = "400MB",
        temp_directory: Path = Path("/tmp/duck"),  # noqa: S108 - tmpfs do contêiner
    ) -> None:
        if not any((dir_dados / "consulta_cand").glob("ano=*/*.parquet")):
            raise DadosIndisponiveis(f"consulta_cand ausente em {dir_dados}")
        try:
            self._prestacao = self._ler_prestacao(dir_dados / "manifesto.json")
            self._prestacao_dados: dict[int, str] = {}
            # Somente leitura na prática: banco em memória + views sobre Parquet (nunca escrito);
            # lock_configuration impede que consultas mudem threads/limites depois.
            self._con = duckdb.connect(":memory:")
            self._con.execute("SET threads = ?", [threads])
            # Teto de memória e de derramamento em disco: consulta gulosa vira erro, não OOM.
            # DDL/SET não aceitam parâmetros em todos os casos; valores vêm da configuração.
            self._con.execute("SET memory_limit = ?", [memory_limit])
            self._con.execute("SET max_temp_directory_size = ?", [max_temp_directory_size])
            self._con.execute("SET temp_directory = ?", [str(temp_directory)])
            fontes = {n: self._fonte(dir_dados, n) for n in (*CONTRATADOS, *PROVISORIOS)}
            self._validar_colunas(fontes)
            for nome, (dataset, sql) in _VIEWS.items():
                if fontes.get(dataset):
                    self._view(nome, sql.format(fonte=fontes[dataset]))
            for nome in PROVISORIOS:
                if fontes[nome]:
                    colunas = ", ".join(COLUNAS_MINIMAS[nome])
                    self._view(nome, f"SELECT {colunas} FROM {fontes[nome]}")  # noqa: S608
            self._ipca: list[VariacaoIpca] | None = None
            self._municipios: list[Municipio] | None = None
            self._tem_h3 = bool(fontes["locais_h3"])
            self._criar_views_compostas(fontes)
            self._criar_views_prestacao(fontes)
            self._dt = self._dt_geracao_dos_dados(fontes)
            self._con.execute("SET lock_configuration = true")
        except (duckdb.Error, KeyError, ValueError) as erro:
            raise DadosIndisponiveis(str(erro)) from erro

    def _validar_colunas(self, fontes: dict[str, str | None]) -> None:
        """Falha clara na abertura se faltar coluna que a API lê (em vez de erro na 1ª consulta)."""
        for nome, fonte in fontes.items():
            if not fonte:
                continue
            existentes = {
                str(linha[0])
                for linha in self._con.execute(f"DESCRIBE SELECT * FROM {fonte}").fetchall()  # noqa: S608
            }
            ausentes = [c for c in COLUNAS_MINIMAS[nome] if c not in existentes]
            if ausentes:
                raise DadosIndisponiveis(f"{nome}: colunas ausentes {ausentes}")

    @staticmethod
    def _ler_prestacao(manifesto: Path) -> dict[int, str]:
        """Situação da prestação de contas por ano (opcional, ver `manifesto.json`)."""
        if not manifesto.is_file():
            return {}
        bruto = json.loads(manifesto.read_text())
        return {int(a): str(t) for a, t in bruto.get("tp_prestacao_contas", {}).items()}

    @staticmethod
    def _fonte(dir_dados: Path, nome: str) -> str | None:
        """Expressão `read_parquet` do dataset (hive ou flat) ou `None` se ausente."""
        # O caminho vem da configuração, nunca do usuário; aspas simples escapadas por garantia.
        if any((dir_dados / nome).glob("ano=*/*.parquet")):
            caminho = str(dir_dados / nome / "ano=*" / "*.parquet").replace("'", "''")
            return f"read_parquet('{caminho}', hive_partitioning = true, union_by_name = true)"
        if any((dir_dados / nome).glob("*.parquet")):  # ex.: ipca/ipca.parquet
            pasta = str(dir_dados / nome / "*.parquet").replace("'", "''")
            return f"read_parquet('{pasta}')"
        flat = dir_dados / f"{nome}.parquet"
        if flat.is_file():
            return f"read_parquet('{str(flat).replace(chr(39), chr(39) * 2)}')"
        return None

    def _view(self, nome: str, select: str) -> None:
        # DDL não aceita parâmetros: nome vem de listas fixas e fontes da configuração.
        self._con.execute(f"CREATE VIEW {nome} AS {select}")

    def _criar_views_compostas(self, fontes: dict[str, str | None]) -> None:
        """`municipios` (IBGE + área/AMC) e `locais_votacao` (local + célula H3)."""
        if fontes["municipio_tse_ibge"]:
            if fontes["municipios_extra"]:
                self._view(
                    "municipios",
                    "SELECT b.cd_mun_ibge, COALESCE(x.cd_amc, b.cd_mun_ibge) AS cd_amc, b.nome,"
                    " b.uf, x.area_km2 FROM municipios_base b"
                    " LEFT JOIN municipios_extra x USING (cd_mun_ibge)",
                )
            else:
                # Sem crosswalk de AMC/área: AMC = o próprio município (desmembrados NÃO agregados).
                self._view(
                    "municipios",
                    "SELECT cd_mun_ibge, cd_mun_ibge AS cd_amc, nome, uf,"
                    " NULL::DOUBLE AS area_km2 FROM municipios_base",
                )
        if fontes["eleitorado_local_votacao"]:
            h3 = "h.h3" if self._tem_h3 else "NULL::VARCHAR AS h3"
            juncao = (
                " LEFT JOIN locais_h3 h ON h.ano = l.ano AND h.cd_mun_ibge = l.cd_mun_ibge"
                " AND h.nr_zona = l.nr_zona AND h.nr_local = l.nr_local_votacao"
                if self._tem_h3
                else ""
            )
            select = (
                "SELECT l.ano, l.sg_uf, l.cd_mun_ibge, l.nr_zona,"  # noqa: S608
                " l.nr_local_votacao AS nr_local, l.nr_latitude AS lat, l.nr_longitude AS lon,"
                f" {h3}, l.qt_eleitor_secao AS aptos FROM {fontes['eleitorado_local_votacao']} l"
                f"{juncao} WHERE l.nr_turno = 1"
            )
            self._view("locais_votacao", select)

    def _criar_views_prestacao(self, fontes: dict[str, str | None]) -> None:
        """`receitas` e `despesas` a partir dos datasets de prestação de contas do ETL."""
        receitas = fontes["receitas_candidatos"]
        if receitas:
            existentes = {
                str(c[0])
                for c in self._con.execute(f"DESCRIBE SELECT * FROM {receitas}").fetchall()  # noqa: S608
            }
            # O agregado do TSE não traz o doador; sem ele, transferências entre candidatos
            # não são abatidas do grupo (o serviço de contas trata `None` como doador externo).
            doador = (
                "sq_candidato_doador" if "sq_candidato_doador" in existentes else "NULL::BIGINT"
            )
            self._view(
                "receitas",
                "SELECT ano, sq_candidato, ds_fonte_receita, ds_origem_receita,"  # noqa: S608
                " ds_natureza_receita, vr_receita,"
                f" {doador} AS sq_candidato_doador"
                f" FROM {receitas} WHERE nr_turno = 1"
                # "Sem movimento": fonte e origem nulas com valor 0 (não é receita).
                " AND NOT (ds_fonte_receita IS NULL AND ds_origem_receita IS NULL"
                " AND vr_receita = 0)",
            )
            self._prestacao_dados = self._prestacao_da_base(receitas)
        contratadas, pagas = (
            fontes["despesas_contratadas_candidatos"],
            fontes["despesas_pagas_candidatos"],
        )
        if contratadas and pagas:
            # Paga ausente = 0 (spec): contratada sem pagamento registrado não é dado faltante.
            self._view(
                "despesas",
                "WITH c AS (SELECT ano, sq_candidato, ds_origem_despesa,"  # noqa: S608
                f" SUM(vr_despesa_contratada) AS contratada FROM {contratadas}"
                # "Sem movimento" (origem nula, valor 0) não é despesa; origem nula com valor
                # continua passando e a biblioteca de indicadores falha alto.
                " WHERE nr_turno = 1 AND NOT (ds_origem_despesa IS NULL"
                " AND vr_despesa_contratada = 0) GROUP BY ALL),"
                " p AS (SELECT ano, sq_candidato, ds_origem_despesa,"
                f" SUM(vr_pagto_despesa) AS paga FROM {pagas} WHERE nr_turno = 1 GROUP BY ALL)"
                " SELECT ano, sq_candidato, ds_origem_despesa,"
                " COALESCE(c.contratada, 0) AS vr_despesa_contratada,"
                " COALESCE(p.paga, 0) AS vr_despesa_paga"
                " FROM c FULL JOIN p USING (ano, sq_candidato, ds_origem_despesa)",
            )

    def _prestacao_da_base(self, receitas: str) -> dict[int, str]:
        """Ano → FINAL se ≥ 95 % dos registros são prestação final; senão PARCIAL.

        O TSE mistura situações por candidato (FINAL, PARCIAL, RELATÓRIO FINANCEIRO…); em 2026 a
        quase totalidade ainda é parcial, e rotular o ano como FINAL esconderia isso.
        """
        linhas = self._con.execute(
            "SELECT ano, avg((upper(tp_prestacao_contas) = 'FINAL')::INT)"  # noqa: S608
            f" FROM {receitas} WHERE nr_turno = 1 GROUP BY ano"
        ).fetchall()
        return {int(a): "FINAL" if float(f) >= 0.95 else "PARCIAL" for a, f in linhas}

    def _dt_geracao_dos_dados(self, fontes: dict[str, str | None]) -> str:
        """Maior `dt_geracao` entre os datasets com contrato: o dado manda, não o manifesto."""
        datas = []
        for nome in CONTRATADOS:
            if fontes[nome]:
                linha = self._con.execute(f"SELECT max(dt_geracao) FROM {fontes[nome]}").fetchone()  # noqa: S608
                if linha and linha[0] is not None:
                    datas.append(linha[0])
        if not datas:
            raise DadosIndisponiveis("nenhum dataset traz dt_geracao")
        return str(max(datas).isoformat())

    def threads(self) -> int:
        """Threads efetivas da conexão."""
        linha = self._con.execute("SELECT current_setting('threads')").fetchone()
        if linha is None:
            raise DadosIndisponiveis("conexão sem configuração de threads")
        return int(linha[0])

    def _linhas(self, sql: str, params: Sequence[object] = ()) -> list[tuple[object, ...]]:
        # Rotas `def` rodam no threadpool: cada consulta usa um cursor próprio (conexão filha),
        # pois a conexão única não é segura para uso concorrente.
        cursor = self._con.cursor()
        try:
            return cursor.execute(sql, list(params)).fetchall()
        except duckdb.CatalogException as erro:
            raise DadosIndisponiveis("tabela do contrato ausente") from erro
        finally:
            cursor.close()

    def _coluna(self, sql: str) -> list[object]:
        return [linha[0] for linha in self._linhas(sql)]

    def ping(self) -> None:
        """Prova que os dados respondem; levanta DadosIndisponiveis se não."""
        try:
            self._coluna("SELECT 1 FROM candidatos LIMIT 1")
        except duckdb.Error as erro:
            raise DadosIndisponiveis("consulta de ping falhou") from erro

    def dt_geracao(self) -> str:
        """DT_GERACAO do manifesto."""
        return self._dt

    def tp_prestacao_contas(self, ano: int) -> str:
        """Situação da prestação de contas no ano (manifesto)."""
        # Manifesto manda (decisão humana); senão a proporção real no dado; sem nenhum, PARCIAL
        # (o lado seguro: o front avisa que a prestação pode estar incompleta).
        return self._prestacao.get(ano) or self._prestacao_dados.get(ano, "PARCIAL")

    def anos(self) -> list[int]:
        """Anos distintos."""
        return [
            int(str(a)) for a in self._coluna("SELECT DISTINCT ano FROM candidatos ORDER BY ano")
        ]

    def ufs(self) -> list[str]:
        """UFs distintas."""
        return [str(u) for u in self._coluna("SELECT DISTINCT sg_uf FROM candidatos ORDER BY 1")]

    def cargos(self) -> list[str]:
        """Cargos distintos."""
        return [str(c) for c in self._coluna("SELECT DISTINCT ds_cargo FROM candidatos ORDER BY 1")]

    def candidaturas(
        self,
        ano: int,
        *,
        uf: str | None = None,
        cargo: str | None = None,
        partido: int | None = None,
        sqs: Sequence[int] | None = None,
    ) -> list[Candidatura]:
        """Candidaturas do ano, com os filtros de grupo em união."""
        condicoes = ["ano = ?"]
        params: list[object] = [ano]
        if uf is not None:
            # Presidente é gravado só com sg_uf = BR (BR.parquet): filtrar pela UF zeraria o cargo.
            presidente = cargo == "PRESIDENTE"
            condicoes.append("sg_uf IN (?, 'BR')" if presidente else "sg_uf = ?")
            params.append(uf)
        if cargo is not None:
            condicoes.append("ds_cargo = ?")
            params.append(cargo)
        if partido is not None or sqs is not None:
            uniao = []
            if partido is not None:
                uniao.append("nr_partido = ?")
                params.append(partido)
            if sqs is not None:
                uniao.append("sq_candidato IN (SELECT unnest(?::BIGINT[]))")
                params.append(list(sqs))
            condicoes.append("(" + " OR ".join(uniao) + ")")
        sql = (
            f"SELECT {_COLUNAS_CANDIDATURA} FROM candidatos WHERE "  # noqa: S608 - só fragmentos fixos
            + " AND ".join(condicoes)
            + " ORDER BY sg_uf, ds_cargo, nm_urna, sq_candidato"
        )
        return [Candidatura(*linha) for linha in self._linhas(sql, params)]  # type: ignore[arg-type]

    def candidatura(self, ano: int, sq_candidato: int) -> Candidatura | None:
        """Busca uma candidatura pela chave (ano, sq)."""
        linhas = self._linhas(
            f"SELECT {_COLUNAS_CANDIDATURA} FROM candidatos WHERE ano = ? AND sq_candidato = ?",  # noqa: S608
            [ano, sq_candidato],
        )
        return Candidatura(*linhas[0]) if linhas else None  # type: ignore[arg-type]

    def municipios(self, codigos: Sequence[int] | None = None) -> list[Municipio]:
        """Municípios (todos ou os pedidos), ordenados por código.

        A tabela (~5,6 mil linhas) é imutável durante o processo e a view varre Parquet de dois
        anos (~0,3 s): lê-se uma vez e filtra em memória.
        """
        if self._municipios is None:
            linhas = self._linhas(
                "SELECT cd_mun_ibge, cd_amc, nome, uf, area_km2 FROM municipios"
                " ORDER BY cd_mun_ibge"
            )
            self._municipios = [Municipio(*linha) for linha in linhas]  # type: ignore[arg-type]
        if codigos is None:
            return list(self._municipios)
        pedidos = set(codigos)
        return [m for m in self._municipios if m.cd_mun_ibge in pedidos]

    def votos_territorio(
        self,
        ano: int,
        sqs: Sequence[int],
        *,
        por_zona: bool,
        uf: str | None = None,
        cd_mun_ibge: int | None = None,
    ) -> list[VotosTerritorio]:
        """Σ votos por município ou município×zona."""
        zona = "v.nr_zona" if por_zona else "NULL"
        agrupa = "v.cd_mun_ibge, v.nr_zona" if por_zona else "v.cd_mun_ibge"
        params: list[object] = [ano, list(sqs)]
        filtro_uf = ""
        if uf is not None:
            filtro_uf = " AND v.sg_uf = ?"  # UF do local de votação (vale também para presidente)
            params.append(uf)
        if cd_mun_ibge is not None:
            filtro_uf += " AND v.cd_mun_ibge = ?"
            params.append(cd_mun_ibge)
        sql = (
            f"SELECT v.cd_mun_ibge, {zona}, SUM(v.votos)::BIGINT FROM votos_munzona v "  # noqa: S608
            f"WHERE v.ano = ? AND v.{_SQS}{filtro_uf} GROUP BY {agrupa} ORDER BY {agrupa}"
        )
        return [VotosTerritorio(*linha) for linha in self._linhas(sql, params)]  # type: ignore[arg-type]

    def votos_totais(self, ano: int, sqs: Sequence[int]) -> dict[int, int]:
        """Votos totais por candidato."""
        linhas = self._linhas(
            f"SELECT sq_candidato, SUM(votos)::BIGINT FROM votos_munzona WHERE ano = ? AND {_SQS} "  # noqa: S608
            "GROUP BY sq_candidato",
            [ano, list(sqs)],
        )
        return {int(str(s)): int(str(v)) for s, v in linhas}

    def base_eleitoral(
        self,
        ano: int,
        cargo: str,
        *,
        por_zona: bool,
        uf: str | None = None,
        cd_mun_ibge: int | None = None,
    ) -> list[BaseEleitoral]:
        """Aptos/válidos por município ou município×zona."""
        zona = "e.nr_zona" if por_zona else "NULL"
        agrupa = "e.cd_mun_ibge, e.nr_zona" if por_zona else "e.cd_mun_ibge"
        params: list[object] = [ano, cargo]
        filtro_uf = ""
        if uf is not None:
            filtro_uf = " AND e.sg_uf = ?"
            params.append(uf)
        if cd_mun_ibge is not None:
            filtro_uf += " AND e.cd_mun_ibge = ?"
            params.append(cd_mun_ibge)
        sql = (
            f"SELECT e.cd_mun_ibge, {zona}, SUM(e.aptos)::BIGINT, SUM(e.votos_validos)::BIGINT "  # noqa: S608
            f"FROM eleitorado_munzona e WHERE e.ano = ? AND e.ds_cargo = ?{filtro_uf} "
            f"GROUP BY {agrupa} ORDER BY {agrupa}"
        )
        return [BaseEleitoral(*linha) for linha in self._linhas(sql, params)]  # type: ignore[arg-type]

    def votos_h3(self, ano: int, sqs: Sequence[int], *, uf: str) -> list[CelulaH3]:
        """Votos e aptos por célula H3; aptos contam todos os locais da célula."""
        if not self._tem_h3:
            raise DadosIndisponiveis("locais_h3 ausente")
        linhas = self._linhas(
            """
            WITH votos AS (
              SELECT cd_mun_ibge, nr_zona, nr_local, SUM(votos) AS votos
              FROM votos_local WHERE ano = ? AND sq_candidato IN (SELECT unnest(?::BIGINT[]))
              GROUP BY ALL
            )
            SELECT l.h3, COALESCE(SUM(v.votos), 0)::BIGINT, SUM(l.aptos)::BIGINT
            FROM locais_votacao l
            LEFT JOIN votos v ON v.cd_mun_ibge = l.cd_mun_ibge AND v.nr_zona = l.nr_zona
                              AND v.nr_local = l.nr_local
            WHERE l.ano = ? AND l.sg_uf = ? AND l.h3 IS NOT NULL
            GROUP BY l.h3 ORDER BY l.h3
            """,
            [ano, list(sqs), ano, uf],
        )
        return [CelulaH3(*linha) for linha in linhas]  # type: ignore[arg-type]

    def pontos(
        self, ano: int, sqs: Sequence[int], *, uf: str, limite: int, offset: int
    ) -> tuple[int, list[PontoVotacao]]:
        """Locais com voto, ordenados por votos desc (desempate estável por coordenada)."""
        base = """
            FROM (
              SELECT cd_mun_ibge, nr_zona, nr_local, SUM(votos) AS votos
              FROM votos_local WHERE ano = ? AND sq_candidato IN (SELECT unnest(?::BIGINT[]))
              GROUP BY ALL
            ) v
            JOIN locais_votacao l ON l.ano = ? AND l.cd_mun_ibge = v.cd_mun_ibge
                                  AND l.nr_zona = v.nr_zona AND l.nr_local = v.nr_local
            WHERE l.sg_uf = ? AND v.votos > 0 AND l.lat IS NOT NULL AND l.lon IS NOT NULL
        """
        params: list[object] = [ano, list(sqs), ano, uf]
        total = self._linhas("SELECT COUNT(*) " + base, params)[0][0]
        linhas = self._linhas(
            "SELECT l.lat, l.lon, v.votos::BIGINT "
            + base
            + " ORDER BY v.votos DESC, l.lat, l.lon LIMIT ? OFFSET ?",
            [*params, limite, offset],
        )
        return int(str(total)), [PontoVotacao(*linha) for linha in linhas]  # type: ignore[arg-type]

    def votos_sem_coordenada(
        self, ano: int, sqs: Sequence[int], *, uf: str, por_h3: bool
    ) -> VotosSemCoordenada:
        """Votos em locais sem lat/lon (pontos) ou sem célula H3 (H3), e o total do recorte."""
        # O critério é fixo (não vem do usuário): cada rota perde os locais que ela não desenha.
        ausente = "l.h3 IS NULL" if por_h3 else "(l.lat IS NULL OR l.lon IS NULL)"
        if por_h3 and not self._tem_h3:
            raise DadosIndisponiveis("locais_h3 ausente")
        linha = self._linhas(
            f"""
            SELECT COALESCE(SUM(CASE WHEN {ausente} THEN v.votos END), 0)::BIGINT,
                   COALESCE(SUM(v.votos), 0)::BIGINT
            FROM (
              SELECT cd_mun_ibge, nr_zona, nr_local, SUM(votos) AS votos
              FROM votos_local WHERE ano = ? AND sq_candidato IN (SELECT unnest(?::BIGINT[]))
              GROUP BY ALL
            ) v
            JOIN locais_votacao l ON l.ano = ? AND l.cd_mun_ibge = v.cd_mun_ibge
                                  AND l.nr_zona = v.nr_zona AND l.nr_local = v.nr_local
            WHERE l.sg_uf = ?
            """,  # noqa: S608
            [ano, list(sqs), ano, uf],
        )[0]
        return VotosSemCoordenada(int(str(linha[0])), int(str(linha[1])))

    def receitas(self, ano: int, sqs: Sequence[int]) -> list[ReceitaBruta]:
        """Receitas agregadas por candidato × rótulos."""
        linhas = self._linhas(
            "SELECT sq_candidato, ds_fonte_receita, ds_origem_receita, ds_natureza_receita, "  # noqa: S608
            "sq_candidato_doador, SUM(vr_receita) FROM receitas "
            f"WHERE ano = ? AND {_SQS} GROUP BY ALL ORDER BY ALL",
            [ano, list(sqs)],
        )
        return [
            ReceitaBruta(sq, fonte, origem, natureza, valor, doador)  # type: ignore[arg-type]
            for sq, fonte, origem, natureza, doador, valor in linhas
        ]

    def despesas(self, ano: int, sqs: Sequence[int]) -> list[DespesaBruta]:
        """Despesas agregadas por candidato × origem."""
        linhas = self._linhas(
            "SELECT sq_candidato, ds_origem_despesa, SUM(vr_despesa_contratada), "  # noqa: S608
            f"SUM(vr_despesa_paga) FROM despesas WHERE ano = ? AND {_SQS} "
            "GROUP BY ALL ORDER BY ALL",
            [ano, list(sqs)],
        )
        return [DespesaBruta(*linha) for linha in linhas]  # type: ignore[arg-type]

    def ipca(self) -> list[VariacaoIpca]:
        """Série do IPCA."""
        if self._ipca is None:  # série pequena e imutável até a próxima carga: lê uma vez
            linhas = self._linhas("SELECT mes, variacao FROM ipca ORDER BY mes")
            self._ipca = [VariacaoIpca(*linha) for linha in linhas]  # type: ignore[arg-type]
        return list(self._ipca)

    def fechar(self) -> None:
        """Fecha a conexão."""
        self._con.close()
