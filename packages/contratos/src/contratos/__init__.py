"""Schemas Parquet e enums compartilhados (papel dados)."""

from contratos.modelo import Contrato, ContratoViolado, validar
from contratos.tse import CONTRATOS

__all__ = ["CONTRATOS", "Contrato", "ContratoViolado", "validar"]
