from pathlib import Path

import streamlit.components.v1 as components


# Dossier contenant le fichier index.html
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

# Déclaration du composant HTML
_composant_plateau = components.declare_component(
    "plateau",
    path=str(FRONTEND_DIR),
)


def afficher_plateau(*, key="plateau", default=None, **donnees):
    """
    Transmet les données Python au composant HTML.
    Renvoie la valeur éventuellement envoyée par le composant.
    """
    return _composant_plateau(
        key=key,
        default=default,
        **donnees,
    )