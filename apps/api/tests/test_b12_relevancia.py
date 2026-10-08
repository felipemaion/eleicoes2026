"""T-B12: relevância da busca (urna exata > começo do nome > palavra > trecho; votos desempatam)."""

from api.repositorio.memoria import DadosMemoria, RepositorioMemoria, VotoMemoria
from api.repositorio.modelos import Candidatura
from api.servicos.busca import buscar, listar_pessoas
from api.servicos.grupos import Catalogo, Comparacao, DefinicaoGrupo
from api.texto import nivel_relevancia

DF = "DEPUTADO FEDERAL"


def _c(ano: int, sq: int, pessoa: str, urna: str, civil: str, numero: int, partido: int = 14):
    return Candidatura(ano, sq, pessoa, urna, "SP", DF, partido, "X", "APTO", None, numero, civil)


# (sq, pessoa, urna, civil, numero) — 2026; ordem de inserção deliberadamente a pior possível
NOMES = [
    (1, "p1", "ELIKA TAKIMOTO", "ELIKA SATIE TAKIMOTO", 1001),  # "kim" só como trecho
    (2, "p2", "PEDRO KIMURA", "PEDRO KIMURA SILVA", 1002),  # começo de palavra
    (3, "p3", "KIMBERLY", "KIMBERLY DOS SANTOS", 1003),  # começo do nome
    (4, "p4", "KIM KATAGUIRI", "ARTHUR KIM KATAGUIRI", 1004),  # urna exata
    (5, "p5", "KIM", "KIM OUTRO", 1005),  # urna exata, menos votos
    (6, "p6", "RENAN SANTOS", "RENAN DOS SANTOS", 14),
    (7, "p7", "RENAN", "RENAN FILHO", 1407),
    (8, "p8", "GUTO ZACARIAS", "AUGUSTO ZACARIAS", 1408),
    (9, "p9", "GUTO", "AUGUSTO GUTO", 1409),
    (10, "p10", "AUGUSTO", "AUGUSTO", 1410),
]
VOTOS = {1: 900, 2: 500, 3: 100, 4: 300, 5: 50, 6: 10, 7: 20, 8: 800, 9: 5, 10: 600}


def _repo() -> RepositorioMemoria:
    cands = [_c(2026, sq, p, u, n, num) for sq, p, u, n, num in NOMES]
    cands += [_c(2022, 100 + sq, p, u, n, num) for sq, p, u, n, num in NOMES]
    votos = [VotoMemoria(2026, sq, 10, 1, v) for sq, v in VOTOS.items()]
    dados = DadosMemoria(candidaturas=cands, votos=votos)
    return RepositorioMemoria("dt", [2022, 2026], ["SP"], [DF], dados, {})


def _cat() -> Catalogo:
    g = DefinicaoGrupo(id="g", rotulo="G", ano=2026, partido=14, sqs=frozenset())
    return Catalogo({"g": g}, {"c": Comparacao(id="c", rotulo="C", de="g", para="g")})


def _busca(q: str) -> list[int]:
    r = buscar(_repo(), _cat(), q=q, ano=2026, cargo=None, uf=None, grupo_id=None, limite=20)
    return [i.sq_candidato for i in r.itens]


def _pessoas(q: str) -> list[int]:
    r = listar_pessoas(_repo(), _cat(), q=q, uf=None, cargo=None, limite=20)
    return [i.para.sq_candidato for i in r.itens]


def test_niveis() -> None:
    assert nivel_relevancia("KIM", None, "X", 1, 2, "kim") == 0
    assert nivel_relevancia("Kim Kataguiri", None, "X", 1, 2, "kim") == 1
    assert nivel_relevancia("X", "ARTHUR KIM", "X", 1, 2, "kim") == 2
    assert nivel_relevancia("ELIKA TAKIMOTO", None, "X", 1, 2, "kim") == 3


def test_kim_urna_exata_depois_comeco_depois_palavra_depois_trecho() -> None:
    # exata (5: 50 votos) vem antes de "KIM KATAGUIRI" (começo do nome), mesmo com menos votos
    assert _busca("kim") == [5, 4, 3, 2, 1]
    assert _busca("KIM") == [5, 4, 3, 2, 1]


def test_pessoas_kim_ordena_igual() -> None:
    assert _pessoas("kim") == [5, 4, 3, 2, 1]


def test_renan_e_guto_desempatam_por_votos() -> None:
    assert _busca("renan") == [7, 6]  # urna exata primeiro
    assert _busca("guto") == [9, 8]  # urna exata (5 votos) antes do começo do nome (800)
    assert _busca("augusto") == [10, 8, 9]  # exata; depois começo do nome civil por votos


def test_numero_exato_antes_de_prefixo_antes_de_partido() -> None:
    ordem = _busca("14")
    assert ordem[0] == 6  # número 14 exato
    assert ordem[1:5] == [8, 10, 7, 9]  # prefixo 14xx, por votos
    assert ordem[5:] == [1, 2, 4, 3, 5]  # só partido 14, por votos


def test_limite_mantem_o_melhor_mesmo_com_muitos_no_mesmo_nivel() -> None:
    r = buscar(_repo(), _cat(), q="kim", ano=2026, cargo=None, uf=None, grupo_id=None, limite=2)
    assert [i.sq_candidato for i in r.itens] == [5, 4]
    assert r.total == 5
