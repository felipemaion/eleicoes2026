"""Trava de segurança: o bundle de CAs do certifi não pode conter raízes removidas pela Mozilla."""

import certifi

# Raiz da eMudhra com intermediárias comprometidas; removida do programa da Mozilla em 20/10/2026.
RAIZES_REVOGADAS = ("emSign ECC Root CA - G3",)


def test_bundle_do_certifi_sem_raizes_revogadas() -> None:
    """O TLS de saída usa o certifi do lock; raiz revogada não pode voltar num `uv lock`."""
    bundle = certifi.contents()
    presentes = [raiz for raiz in RAIZES_REVOGADAS if raiz in bundle]
    assert not presentes, (
        f"certifi {certifi.__version__} confia em {presentes}: "
        "rode `uv lock --upgrade-package certifi`"
    )
