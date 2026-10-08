"""T-B13: `foto_url` (manifesto de fotos da T-D07) e `link_tse_candidato` verificado no navegador."""

from api import links
from api.repositorio.memoria import RepositorioMemoria
from fastapi.testclient import TestClient

# Padrão aberto no navegador em 2026-10-08 com Renan Santos 2026 (BR), Kim 2022 e 2026 (SP),
# Rafa Minato 2026 e Guto Zacarias 2022 (dep. estaduais SP): todos carregaram o perfil certo.
BASE = "https://divulgacandcontas.tse.jus.br/divulga/#/candidato"


def test_link_tse_padrao_verificado_2026_e_2022() -> None:
    a = links.link_tse_candidato(ano=2026, sq_candidato=250002546642, uf="SP")
    assert a.url == f"{BASE}/SP/SP/20322002026/250002546642/2026/SP"
    assert a.verificado is True and a.nota is None
    b = links.link_tse_candidato(ano=2022, sq_candidato=250001602048, uf="SP")
    assert b.url == f"{BASE}/SP/SP/2040602022/250001602048/2022/SP"


def test_link_tse_presidente_usa_br_em_todos_os_segmentos() -> None:
    p = links.link_tse_candidato(ano=2026, sq_candidato=280002540694, uf="BR")
    assert p.url == f"{BASE}/BR/BR/20322002026/280002540694/2026/BR"


def test_links_da_candidatura_traz_o_mesmo_link_verificado() -> None:
    ls = links.links_da_candidatura(ano=2026, sq_candidato=11, uf="BR", cargo="PRESIDENTE")
    cand = next(x for x in ls if x.tipo == "divulgacand_candidato")
    assert cand.url == f"{BASE}/BR/BR/20322002026/11/2026/BR"
    assert cand.verificado is True


def test_ficha_tem_foto_e_link(api: TestClient) -> None:
    c = api.get("/api/candidatos/2026/3").json()["candidato"]
    assert c["foto_url"] == "/fotos/2026/3.webp"
    assert c["link_tse_candidato"]["url"] == f"{BASE}/SP/SP/20322002026/3/2026/SP"
    assert c["link_tse_candidato"]["verificado"] is True


def test_foto_nula_quando_nao_esta_no_manifesto(api: TestClient) -> None:
    itens = api.get("/api/candidatos", params={"grupo": "missao_2026"}).json()["itens"]
    por_sq = {i["sq_candidato"]: i for i in itens}
    assert all("foto_url" in i and "link_tse_candidato" in i for i in itens)
    assert por_sq[3]["foto_url"] == "/fotos/2026/3.webp"
    assert [i for i in itens if i["sq_candidato"] != 3 and i["foto_url"]] == []


def test_gastos_por_candidato_tem_foto_e_link(api: TestClient) -> None:
    itens = api.get("/api/gastos", params={"grupo": "missao_2026"}).json()["por_candidato"]
    assert itens
    assert all(i["link_tse_candidato"]["url"].startswith(BASE) for i in itens)
    assert all(i["foto_url"] in (None, f"/fotos/2026/{i['sq_candidato']}.webp") for i in itens)


def test_busca_tem_foto_e_link(api: TestClient) -> None:
    itens = api.get("/api/busca", params={"q": "a", "limite": 50}).json()["itens"]
    assert itens
    for i in itens:
        assert i["link_tse_candidato"]["url"].startswith(BASE)
        esperado = {(2026, 3): "/fotos/2026/3.webp", (2022, 1): "/fotos/2022/1.webp"}
        assert i["foto_url"] == esperado.get((i["ano"], i["sq_candidato"]))


def test_repositorio_memoria_sem_fotos_devolve_vazio() -> None:
    assert RepositorioMemoria("2026-10-06", [2026], ["SP"], []).fotos() == frozenset()
