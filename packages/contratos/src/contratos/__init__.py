"""Schemas Parquet e enums compartilhados (papel dados)."""

from contratos.contas import CONTRATOS_CONTAS
from contratos.geo import MUNICIPIOS
from contratos.modelo import Contrato, ContratoViolado, validar
from contratos.tse import CONTRATOS as _TSE

CONTRATOS = {**_TSE, **CONTRATOS_CONTAS, MUNICIPIOS.nome: MUNICIPIOS}

__all__ = ["CONTRATOS", "Contrato", "ContratoViolado", "validar"]
