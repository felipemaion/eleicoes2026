"""Nomes das colunas do TSE usadas pelos indicadores, conferidos contra `packages/contratos`.

Uma fonte de verdade por conceito: se o `dados` renomear uma coluna no contrato, o import
deste módulo falha alto em vez de o indicador procurar uma coluna que não existe mais.
Colunas financeiras (receitas/despesas) ficam literais em `financeiro.py` até haver contrato.
"""

from contratos import Contrato
from contratos.tse import CONSULTA_CAND, VOTACAO_CANDIDATO_MUNZONA, VOTACAO_PARTIDO_MUNZONA


def _de(contrato: Contrato, nome: str) -> str:
    """Devolve `nome` se o contrato o declara; senão falha no import."""
    if nome not in contrato.colunas:
        raise ImportError(f"coluna {nome!r} ausente do contrato {contrato.nome!r}")
    return nome


NR_TURNO = _de(VOTACAO_CANDIDATO_MUNZONA, "nr_turno")
CD_CARGO = _de(VOTACAO_CANDIDATO_MUNZONA, "cd_cargo")
NM_TIPO_DESTINACAO_VOTOS = _de(VOTACAO_CANDIDATO_MUNZONA, "nm_tipo_destinacao_votos")
QT_VOTOS_NOMINAIS = _de(VOTACAO_CANDIDATO_MUNZONA, "qt_votos_nominais")
QT_VOTOS_NOMINAIS_VALIDOS = _de(VOTACAO_CANDIDATO_MUNZONA, "qt_votos_nominais_validos")
QT_VOTOS_LEGENDA_VALIDOS = _de(VOTACAO_PARTIDO_MUNZONA, "qt_votos_legenda_validos")
QT_VOTOS_NOM_CONVR_LEG_VALIDOS = _de(VOTACAO_PARTIDO_MUNZONA, "qt_votos_nom_convr_leg_validos")
DS_SITUACAO_CANDIDATURA = _de(CONSULTA_CAND, "ds_situacao_candidatura")
