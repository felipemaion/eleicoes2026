"""Schemas Parquet e enums compartilhados (papel dados)."""

from contratos.contas import CONTRATOS_CONTAS
from contratos.geo import MUNICIPIOS
from contratos.modelo import Contrato, ContratoViolado, validar
from contratos.redes import CONTRATOS_REDES
from contratos.tse import CONTRATOS as _TSE

CONTRATOS = {**_TSE, **CONTRATOS_CONTAS, **CONTRATOS_REDES, MUNICIPIOS.nome: MUNICIPIOS}

__all__ = ["CONTRATOS", "Contrato", "ContratoViolado", "validar"]
