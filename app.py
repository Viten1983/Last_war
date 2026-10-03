import copy
import heapq
import json
import math
import time
import uuid
import streamlit as st
import streamlit.components.v1 as components
from html import escape
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="The Four Realms",
    page_icon="⚔️",
    layout="wide",
)

BOARD_COMPONENT = components.declare_component(
    "the_four_realms_board",
    path=str(Path(__file__).resolve().parent / "plateau" / "frontend"),
)

SAVE_VERSION = 2
MAX_SAVE_BYTES = 5 * 1024 * 1024
AGE_COSTS = {
    2: {"gold": 600, "mana": 0},
    3: {"gold": 800, "mana": 2},
}
AGE_PREREQUISITES = {
    (0, 2): "Mare",
    (0, 3): "Galerie d'enragés",
    (1, 2): "Petite grotte",
    (1, 3): "Marché",
}
BASE_PF_BY_AGE = {
    (0, 1): 1.5,
    (0, 2): 3.5,
    (0, 3): 6.0,
    (1, 1): 2.0,
    (1, 2): 4.0,
    (1, 3): 6.0,
}
BASE_COST_BY_AGE = {
    (0, 1): 350,
    (0, 2): 400,
    (0, 3): 500,
    (1, 1): 450,
    (1, 2): 450,
    (1, 3): 450,
}
BUILDING_AGES = {
    (0, "Mare"): 1,
    (0, "Bassin de mutation"): 1,
    (0, "Galerie d'enragés"): 2,
    (0, "Marais d'aspergeurs"): 2,
    (1, "Petite grotte"): 1,
    (1, "Forêt enchantée"): 1,
    (1, "Marché"): 1,
    (1, "Grotte à molosse"): 3,
    (1, "Nid"): 3,
}

UPGRADES = {  
    # Déferlants  
    "2 pattes en plus": {  
        "owner": 0,  
        "cost": 250,  
        "mana": 0,  
        "building": "Bassin de mutation",  
        "age": 1,  
        "effect": "+1 mouvement pour tous les Déferlants.",  
    },  
    "Dents acérées": {  
        "owner": 0,  
        "cost": 250,  
        "mana": 0,  
        "building": "Bassin de mutation",  
        "age": 1,  
        "effect": "+0,5 PF pour tous les Déferlants.",  
    },  
    "Mutation kamikaze": {  
        "owner": 0,  
        "cost": 100,  
        "mana": 0,  
        "building": "Bassin de mutation",  
        "age": 1,  
        "effect": "Permet de muter un Déferlant en kamikaze.",  
    },  
  
    # Exilés  
    "Meute de tigres": {  
        "owner": 1,  
        "cost": 350,  
        "mana": 0,  
        "building": "Marché",  
        "age": 1,  
        "effect": "Permet de recruter 2 Tigres des forêts.",  
    },  
    "Instinct elfique": {  
        "owner": 1,  
        "cost": 200,  
        "mana": 0,  
        "building": "Marché",  
        "age": 1,  
        "effect": "L’Elfe inflige aussi 3 PF à la case derrière la cible.",  
    },  
    "Vengeance": {  
        "owner": 1,  
        "cost": 300,  
        "mana": 0,  
        "building": "Marché",  
        "age": 1,  
        "effect": "+0,5 PF de dégâts à l’unité qui tue l’unité. L’attaquant est immobilisé 1 tour supplémentaire.",  
    },  
    "Développement musculaire": {  
        "owner": 1,  
        "cost": 300,  
        "mana": 0,  
        "building": "Marché",  
        "age": 3,  
        "effect": "+3 PF pour les Mammouths domptés.",  
    },  
}  

START_BASE_COORDS = ("D3", "F2", "H1", "G6")
START_HABITATION_COORDS = ("R16", "T15", "V14", "S12")
START_COLUMNS = [9, 13, 17, 21]
LEGACY_START_COLUMNS = [1, 3, 7, 9]
PREVIOUS_START_COLUMNS = [1, 4, 7, 10]
PREVIOUS_GRID_HEIGHT = 28

# Dimensions du plateau hexagonal codé en dur.  
W, H = 25, 17  
  
DIRECTIONS = [  
    (1, 0), (-1, 0),  
    (0, 1), (0, -1),  
    (1, -1), (-1, 1),  
]  
  
  
def board_row(pos):  
    """Ligne visuelle pour une grille à colonnes décalées."""  
    q, r = pos  
    return r + q // 2  
  
  
# Coordonnées axiales : seules les cases du rectangle visuel existent.  
CELLS = [  
    (q, row - q // 2)  
    for q in range(W)  
    for row in range(H)  
]  
CELL_SET = set(CELLS)  
  
  
def blocked(g, pos):  
    return terrain(g, pos) in ("mountain", "sea")  


TECH_BUILDINGS = {  
    0: "Bassin de mutation",  # Déferlants  
    1: "Marché",              # Exilés  
}  

FACTIONS = {
    0: {
        "name": "Déferlants",
        "base": "Incubateur",
        "base_cost": 350,
        "base_pf": 1.5,
        "income": 130,
        "buildings": {
            "Mare": {
                "cost": 100,
                "pf": 2,
                "limit": 5,
                "units": ["Déferlant"],
            },
            "Bassin de mutation": {
                "cost": 150,
                "pf": 2,
                "limit": 1,
                "units": [],
            },
            "Galerie d'enragés": {
                "cost": 250,
                "pf": 3,
                "limit": 2,
                "units": [
                    "Déferlant", "Aspergeur", "Rampant", "Costaud",
                    "Molosse", "Carapace", "Dents acérées volants",
                    "Décimant",
                ],
            },
            "Marais d'aspergeurs": {
                "cost": 250,
                "pf": 3,
                "limit": 2,
                "units": ["Aspergeur", "Rampant"],
            },
        },
    },
    1: {
        "name": "Exilés",
        "base": "Habitations",
        "base_cost": 450,
        "base_pf": 2,
        "income": 150,
        "buildings": {
            "Petite grotte": {
                "cost": 200,
                "pf": 3,
                "limit": 3,
                "units": ["Tigre des forêts"],
            },
            "Forêt enchantée": {
                "cost": 250,
                "pf": 2,
                "limit": 2,
                "units": ["Elfe"],
            },
            "Marché": {
                "cost": 200,
                "pf": 2,
                "limit": 1,
                "units": ["Gobelin", "Mage des montagnes", "Dragon"],
            },
            "Grotte à molosse": {
                "cost": 400,
                "pf": 5,
                "limit": 2,
                "units": ["Mammouth dompté", "Nain des montagnes", "Golem de pierre"],
            },
            "Nid": {
                "cost": 400,
                "pf": 3,
                "limit": 1,
                "units": ["Daeron et Finwe"],
            },
        },
    },
}

DEFERLANTS, EXILES, DERNIERS_NES = 0, 1, 2


def faction_id(g, owner):
    """Faction jouée par un siège (0 = en haut, 1 = en bas)."""
    return g.get("factions", [DEFERLANTS, EXILES])[owner]


def faction_of(g, owner):
    return FACTIONS[faction_id(g, owner)]


def current_game():
    """Partie affichée, pour les fonctions d'interface sans paramètre g."""
    bundle = st.session_state.get("bundle")
    return bundle["game"] if isinstance(bundle, dict) else {}


UNITS = {
    "Déferlant": {
        "cost": 100, "mana": 0, "batch": 2,
        "pf": 1, "move": 3, "range": 0, "limit": 20,
    },
    "Tigre des forêts": {
        "cost": 200, "mana": 0, "batch": 1,
        "pf": 2, "move": 4, "range": 0, "limit": 8,
    },
    "Elfe": {
        "cost": 300, "mana": 1, "batch": 1,
        "pf": 3, "move": 3, "range": 3, "limit": 4,
    },
    "Aspergeur": {
        "cost": 350, "mana": 1, "batch": 1,
        "pf": 2, "move": 3, "range": 3, "limit": 8,
    },
    "Rampant": {
        "cost": 350, "mana": 2, "batch": 1,
        "pf": 2, "move": 4, "range": 0, "limit": 2,
    },
    "Costaud": {
        "cost": 500, "mana": 1, "batch": 1,
        "pf": 3, "move": 3, "range": 0, "limit": 1,
    },
    "Molosse": {
        "cost": 800, "mana": 3, "batch": 1,
        "pf": 5, "move": 3, "range": 0, "limit": 3,
    },
    "Carapace": {
        "cost": 700, "mana": 3, "batch": 1,
        "pf": 4, "move": 2, "range": 0, "limit": 3,
    },
    "Dents acérées volants": {
        "cost": 600, "mana": 3, "batch": 1,
        "pf": 3, "move": 4, "range": 0, "limit": 3,
    },
    "Décimant": {
        "cost": 650, "mana": 2, "batch": 1,
        "pf": 2, "move": 4, "range": 0, "limit": 2,
    },
    "Gobelin": {
        "cost": 150, "mana": 1, "batch": 1,
        "pf": 1, "move": 4, "range": 1, "limit": 1,
    },
    "Mage des montagnes": {
        "cost": 350, "mana": 1, "batch": 1,
        "pf": 3, "move": 3, "range": 4, "limit": 2,
    },
    "Dragon": {
        "cost": 400, "mana": 2, "batch": 1,
        "pf": 4, "move": 3, "range": 3, "limit": 5,
    },
    "Mammouth dompté": {
        "cost": 700, "mana": 3, "batch": 1,
        "pf": 10, "move": 3, "range": 0, "limit": 4,
    },
    "Nain des montagnes": {
        "cost": 500, "mana": 2, "batch": 1,
        "pf": 7, "move": 3, "range": 0, "limit": 6,
    },
    "Golem de pierre": {
        "cost": 550, "mana": 2, "batch": 1,
        "pf": 6, "move": 3, "range": 3, "limit": 3,
    },
    "Daeron et Finwe": {
        "cost": 650, "mana": 2, "batch": 1,
        "pf": 5, "move": 4, "range": 4, "limit": 2,
    },
}

UNIT_AGES = {
    **{name: 1 for name in ("Déferlant", "Tigre des forêts", "Elfe")},
    **{name: 2 for name in ("Aspergeur", "Rampant", "Gobelin", "Mage des montagnes", "Dragon")},
    **{name: 3 for name in ("Costaud", "Molosse", "Carapace", "Dents acérées volants", "Décimant", "Mammouth dompté", "Nain des montagnes", "Golem de pierre", "Daeron et Finwe")},
}

# ============================================================  
# CORRECTIONS DES RECRUTEMENTS  
# À placer après UNIT_AGES, avant AGE_REFERENCE.  
# ============================================================  
  
# Déferlants : les Aspergeurs se recrutent par deux.  
UNITS["Aspergeur"]["batch"] = 2  
  
# Portée indiquée sur la capture.  
UNITS["Aspergeur"]["range"] = 2  
  
# Exilés : âge II.  
UNIT_AGES["Gobelin"] = 2  
UNIT_AGES["Mage des montagnes"] = 2  
UNIT_AGES["Dragon"] = 2  
  
# La Petite grotte produit les unités de cette branche.  
FACTIONS[1]["buildings"]["Petite grotte"]["units"] = [  
    "Tigre des forêts",  
    "Gobelin",  
    "Mage des montagnes",  
]  
  
# La Forêt enchantée produit les Elfes puis les Dragons.  
FACTIONS[1]["buildings"]["Forêt enchantée"]["units"] = [  
    "Elfe",  
    "Dragon",  
]  
  
# Le Marché est un bâtiment d'échange, pas un producteur.  
FACTIONS[1]["buildings"]["Marché"]["units"] = []  
  
# Caractéristiques lisibles sur la capture des Exilés.  
UNITS["Gobelin"]["move"] = 8  
  
UNITS["Dragon"].update({  
    "cost": 400,  
    "mana": 0,  
    "pf": 3,  
    "move": 3,  
    "range": 2,  
    "limit": 5,  
})  
  
UNITS["Daeron et Finwe"]["move"] = 3  

def is_flying(unit):  
    return unit["name"] in {"Volant", "Dents acérées volants", "Dragon", "Daeron et Finwe"}  

# ============================================================  
# CARTES : CORRECTIONS DES DEUX FACTIONS  
# ============================================================  
  
# Bâtiments Déferlants.  
FACTIONS[0]["buildings"].update({  
    "Galerie d'enragés": {  
        "cost": 250,  
        "mana": 0,  
        "pf": 3,  
        "limit": 2,  
        "units": ["Enragé", "Costaud"],  
    },  
    "Marais d'aspergeurs": {  
        "cost": 250,  
        "mana": 0,  
        "pf": 3,  
        "limit": 2,  
        "units": ["Aspergeur", "Rampant"],  
    },  
    "Grotte à molosse": {  
        "cost": 400,  
        "mana": 1,  
        "pf": 5,  
        "limit": 2,  
        "units": ["Molosse"],  
    },  
    "Nid": {  
        "cost": 400,  
        "mana": 2,  
        "pf": 4,  
        "limit": 3,  
        "units": ["Volant", "Décimant"],  
    },  
})  
  
BUILDING_AGES.update({  
    (0, "Grotte à molosse"): 3,  
    (0, "Nid"): 3,  
})  
  
# Les deux anciennes entrées étaient des améliorations,  
# pas des unités recrutables.  
UNITS.pop("Carapace", None)  
UNITS.pop("Dents acérées volants", None)  
UNIT_AGES.pop("Carapace", None)  
UNIT_AGES.pop("Dents acérées volants", None)  
  
UNITS["Enragé"] = {  
    "cost": 400, "mana": 0, "batch": 1,  
    "pf": 3, "move": 5, "range": 0, "limit": 8,  
}  
  
UNITS["Costaud"].update({  
    "cost": 500, "mana": 0,  
    "pf": 10, "move": 3, "range": 0, "limit": 1,  
})  
  
UNITS["Aspergeur"].update({  
    "batch": 2,  
    "pf": 2,  
    "move": 3,  
    "range": 2,  
    "limit": 8,  
})  
  
UNITS["Rampant"].update({  
    "cost": 200, "mana": 1,  
    "pf": 4, "move": 4, "range": 3, "limit": 8,  
})  
  
UNITS["Molosse"].update({  
    "cost": 800, "mana": 3,  
    "pf": 8, "move": 3, "range": 0, "limit": 6,  
})  
  
UNITS["Volant"] = {  
    "cost": 600, "mana": 1, "batch": 2,  
    "pf": 2.5, "move": 5, "range": 0, "limit": 10,  
}  
  
UNITS["Décimant"].update({  
    "cost": 650, "mana": 3,  
    "pf": 2, "move": 4, "range": 4, "limit": 2,  
})  
  
UNIT_AGES.update({  
    "Enragé": 2,  
    "Costaud": 2,  
    "Aspergeur": 2,  
    "Rampant": 2,  
    "Molosse": 3,  
    "Volant": 3,  
    "Décimant": 3,  
})  
  
# Bâtiments Exilés.  
FACTIONS[1]["buildings"].pop("Grotte à molosse", None)  
FACTIONS[1]["buildings"].pop("Nid", None)  
  
FACTIONS[1]["buildings"].update({  
    "Petite grotte": {  
        "cost": 200,  
        "mana": 0,  
        "pf": 3,  
        "limit": 3,  
        "units": [  
            "Tigre des forêts",  
            "Réveil des morts",  
            "Gobelin",  
            "Mage des montagnes",  
        ],  
    },  
    "Forêt enchantée": {  
        "cost": 250,  
        "mana": 0,  
        "pf": 2,  
        "limit": 2,  
        "units": ["Elfe", "Dragon"],  
    },  
    "Marché": {  
        "cost": 200,  
        "mana": 0,  
        "pf": 2,  
        "limit": 1,  
        "units": [],  
    },  
    "Terre des Exilés": {  
        "cost": 400,  
        "mana": 0,  
        "pf": 3,  
        "limit": 2,  
        "units": ["Mammouth dompté"],  
    },  
    "Grande grotte": {  
        "cost": 400,  
        "mana": 0,  
        "pf": 5,  
        "limit": 2,  
        "units": ["Nain des montagnes", "Golem de pierre"],  
    },  
    "Repère elfique": {  
        "cost": 400,  
        "mana": 2,  
        "pf": 3,  
        "limit": 1,  
        "units": ["Daeron et Finwe"],  
    },  
})  
  
BUILDING_AGES.update({  
    (1, "Terre des Exilés"): 3,  
    (1, "Grande grotte"): 3,  
    (1, "Repère elfique"): 3,  
})  
  
UNITS["Réveil des morts"] = {  
    "cost": 300, "mana": 0, "batch": 4,  
    "pf": 1, "move": 3, "range": 0, "limit": 12,  
}  
  
UNITS["Gobelin"]["move"] = 8  
  
UNITS["Dragon"].update({  
    "cost": 400, "mana": 0,  
    "pf": 3, "move": 3, "range": 2, "limit": 5,  
})  
  
UNITS["Nain des montagnes"]["mana"] = 0  
UNITS["Daeron et Finwe"]["move"] = 3  
  
UNIT_AGES.update({  
    "Réveil des morts": 1,  
    "Gobelin": 2,  
    "Mage des montagnes": 2,  
    "Dragon": 2,  
})  
  
BASE_COST_BY_AGE[(1, 3)] = 400  

AGE_REFERENCE = {
    "Déferlants": {
        1: [
            ("Incubateur", "Base · 350 or · 1,5 PF · attente 2 tours"),
            ("Marée de Déferlant", "Bâtiment · 100 or · 2 PF · produit 2 Déferlants"),
            ("Bassin de mutation", "Bâtiment d'amélioration · condition des améliorations"),
            ("2 pattes en plus", "Amélioration · 250 or · +1 mouvement aux Déferlants"),
            ("Dents acérées", "Amélioration · 250 or · +0,5 PF aux Déferlants"),
            ("Mutation kamikaze", "Amélioration · 100 or · mutation individuelle avec 1 tour d'attente"),
        ],
        2: [
            ("Incubateur", "Base · 400 or · 3,5 PF · collecte 200 or ou 2 mana"),
            ("Galerie d'enragés", "Bâtiment · 250 or · produit 2 unités"),
            ("Marais d'aspergeurs", "Bâtiment · 250 or · produit les Aspergeurs"),
            ("Aspergeur", "Unité · portée 3 · attaque à distance"),
            ("Rampant", "Unité · se plante dans le sol (fin d'activation), puis tire en ligne : 4 PF sur la cible et les 2 cases derrière elle"),
        ],
        3: [
            ("Incubateur", "Base · 500 or · 6 PF · collecte 300 or ou 3 mana"),
            ("Grotte à molosse", "Bâtiment · 400 or · 5 PF · produit 2 unités"),
            ("Costaud", "Unité · 10 / 3 / 0"),
            ("Molosse", "Unité · 800 or · 3 PF"),
            ("Carapace", "Unité · 700 or · 3 PF"),
            ("Dents acérées volants", "Unité · 600 or · bonus contre les unités volantes"),
            ("Mutation kamikaze", "Amélioration · 100 or · 10 mana"),
            ("Décimant", "Unité · bloque la production ou inflige des dégâts"),
        ],
    },
    "Exilés": {
        1: [
            ("Habitations", "Base · 450 or · 2 PF · collecte automatique"),
            ("Petite grotte", "Bâtiment · 200 or · 3 PF · produit les Tigres"),
            ("Forêt enchantée", "Bâtiment · 250 or · 2 PF · produit les Elfes"),
            ("Marché", "Bâtiment · 200 or · 2 PF"),
        ],
        2: [
            ("Habitations", "Base · 450 or · 4 PF · collecte 200 or ou 2 mana"),
            ("Gobelin", "Unité · 150 or · 1 / 8 / 1"),
            ("Mage des montagnes", "Unité · 350 or · 3 / 3 / 4"),
            ("Aramil le sorcier bleu", "Unité · 350 or · pouvoirs de soutien"),
            ("Dragon", "Unité · 400 or · attaque à distance"),
        ],
        3: [
            ("Habitations", "Base · 400 or · 6 PF · collecte 300 or ou 3 mana"),
            ("Terre des Exilés", "Bâtiment · 400 or · 3 PF"),
            ("Mammouth dompté", "Unité · 700 or · 10 / 3 / 0"),
            ("Développement musculaire", "Amélioration · bonus de puissance"),
            ("Grande grotte", "Bâtiment · 400 or · 5 PF · produit 2 unités"),
            ("Nain des montagnes", "Unité · 500 or · 7 / 3 / 0"),
            ("Golem de pierre", "Unité · 550 or · 6 / 3 / 3"),
            ("Repère elfique", "Bâtiment · 400 or · 3 PF"),
            ("Daeron et Finwe", "Unité · 650 or · 5 / 3 / 4"),
        ],
    },
}

FACTION_DOSSIER_IMAGES = {
    "Déferlants": Path(__file__).resolve().parent / "plateau" / "factions" / "deferrlants.svg",
    "Exilés": Path(__file__).resolve().parent / "plateau" / "factions" / "exiles.svg",
}

NOTICE = """
Prototype âge I : Déferlants contre Exilés.

- Les Déferlants construisent à 4 cases maximum de leur base,
  sur toute la carte. Les Exilés construisent dans leur moitié.
- Les deux joueurs planifient séparément avant révélation.
- Déferlants : une construction par incubateur et par tour,
  à une distance maximale de 4 cases.
- Exilés : plusieurs constructions possibles par habitation.
- Base : attente de 2 tours.
- Bâtiment : attente de 1 tour, ou disponibilité immédiate avec +50 %.
- Chaque bâtiment de production recrute une fois par tour.
- Une activation permet un déplacement OU une attaque.
- Les unités, bases et bâtiments alliés peuvent être traversés (chaque case traversée compte comme un déplacement), mais pas occupés à l'arrivée.
- Un tir subit une riposte égale aux PF de la cible (au contact, c'est un corps à corps).
- Une unité de corps à corps (sans tir) ne riposte jamais contre un tireur, même au contact.
- Armes de siège (Catapulte, Trébuchet, Catapulte de l'enfer, Golem de pierre) : jamais de riposte contre elles.
- Catapulte, Trébuchet, Catapulte de l'enfer, Golem de pierre et Rampant ne peuvent pas viser les unités volantes, et leurs dégâts de zone ne les touchent pas.
- Une unité invisible non détectée attaque sans subir de riposte.
- Pile d'ouvriers (1 à 3 sur une case) : au corps à corps, ils se défendent ensemble avec leurs PF cumulés ; une attaque victorieuse les détruit tous d'un coup, l'attaquant perd ce total et prend la case.
- La Catapulte et la Catapulte de l'enfer ne ripostent jamais (ni au corps à corps, ni aux tirs). Seul le Trébuchet tire automatiquement sur les unités qui traversent sa zone.
- Bâtiment technique (Bassin de mutation, Marché, Forge) : seulement en J5 pour le joueur du haut, P12 pour celui du bas.
- Vagabonds : 3 héros mobiles servent de bases ; ils bougent, produisent et attaquent pendant la production (attaque immédiate, sans riposte ; l'adversaire la voit au dévoilement). Détruire 3 héros fait gagner.
- Les ennemis et les constructions bloquent le déplacement.
- Entrer sur une montagne coûte 2 mouvements.
- Tir depuis une montagne : portée +1.
- Pas d'obstruction de ligne de vue.
- Soutien réservé au corps à corps ; les tirs se font sans déplacement.
- Un groupe constitué uniquement d'unités à 0,5 PF ne peut pas attaquer.
- Les pertes des attaquants suivent leur ordre de sélection.
- Égalité attaque/défense : avantage de 0,5 PF aux attaquants.
- Une base riposte toujours à un tir.
- Unité détruite : PF initiaux en points de victoire.
- Base détruite : 6 PV ; bâtiment détruit : aucun PV.
- Victoire, choisie au lancement de la partie :
  meilleur score en PV à la fin du temps,
  ou premier à détruire 3 bases ennemies.
- Récolte automatique au début du tour suivant.
- Une base récolte automatiquement l'or et le mana adjacents.
- Le temps est vérifié à chaque interaction.
- Le temps écoulé entre sauvegarde et chargement n'est pas décompté.
- Confidentialité uniquement visuelle : les sauvegardes contiennent
  les planifications privées.
"""

CSS = """
<style>
/* Boutons de recrutement en vert, comme les cases de placement du plateau. */
[class*="_choose_recruit_"] button,
[class*="_workers_"] button {
    background: #15803d !important;
    border-color: #166534 !important;
    color: #ffffff !important;
}
[class*="_choose_recruit_"] button:hover,
[class*="_workers_"] button:hover {
    background: #16a34a !important;
    border-color: #15803d !important;
    color: #ffffff !important;
}
[class*="_choose_recruit_"] button:disabled,
[class*="_workers_"] button:disabled {
    background: #9ca3af !important;
    border-color: #9ca3af !important;
    color: #f3f4f6 !important;
}
[class*="_choose_recruit_"] button p,
[class*="_workers_"] button p {
    color: inherit !important;
}

/* Séparer le plateau des commandes et du bilan. */
.st-key-lw_page_board {
    position: relative !important;
    isolation: isolate;
    min-width: 0 !important;
}

/* Empêcher les éléments positionnés du plateau de déborder
   sur le menu pendant les changements de contenu. */
.st-key-lw_hex_scroll {
    position: relative !important;
    isolation: isolate;
    overflow: auto !important;
}

/* Utiliser toute la largeur disponible. */
.block-container {
    max-width: 100% !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

div.stButton > button,
div.stDownloadButton > button {
    border-radius: 10px;
    min-height: 42px;
    font-weight: 650;
}
</style>
"""

# ============================================================
# UTILITAIRES
# ============================================================

def key(pos):
    return f"{pos[0]},{pos[1]}"


def coord(pos):
    q, _ = pos
    value = q + 1
    letters = ""

    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters

    return f"{letters}{board_row(pos) + 1}"


def pos_from_coord(label):
    letters = ""
    digits = ""

    for char in label.strip().upper():
        if char.isalpha():
            letters += char
        elif char.isdigit():
            digits += char

    if not letters or not digits:
        raise ValueError(f"Coordonnée invalide : {label}")

    column = 0

    for char in letters:
        column = column * 26 + (ord(char) - ord("A") + 1)

    q = column - 1
    row = int(digits) - 1
    pos = (q, row - q // 2)

    if pos not in CELL_SET:
        raise ValueError(f"Coordonnée hors plateau : {label}")

    return pos


def valid_position(pos):
    return (
        isinstance(pos, (list, tuple))
        and len(pos) == 2
        and all(type(v) is int for v in pos)
        and tuple(pos) in CELL_SET
    )


def require_position(pos):
    if not valid_position(pos):
        raise ValueError("Case inexistante sur le plateau.")
    return tuple(pos)


def neighbors(pos):
    q, r = pos
    return [
        (q + dq, r + dr)
        for dq, dr in DIRECTIONS
        if (q + dq, r + dr) in CELL_SET
    ]


def distance(a, b):
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def home(owner, pos):
    row = board_row(pos)
    return row < H // 2 if owner == 0 else row >= H // 2


def terrain(g, pos):
    return g["terrain"].get(key(pos), "plain")


def at(g, pos):
    pos = tuple(pos)
    return next(
        (e for e in g["entities"] if tuple(e["pos"]) == pos),
        None,
    )


def entity(g, eid):
    result = next(
        (e for e in g["entities"] if e["id"] == eid),
        None,
    )
    if result is None:
        raise ValueError("Cette pièce n'existe plus.")
    return result


def turn_label(g):  
    """Numéro affiché : production N.1, manœuvres N.2."""  
    subphase = 1 if g["phase"] == "build" else 2  
    return f"{g['turn']}.{subphase}"  
  
  
def phase_label(g):  
    return (  
        "Phase de production"  
        if g["phase"] == "build"  
        else "Phase de manœuvres"  
    )  

def log(g, message):  
    g["log"].append(f"T{turn_label(g)} — {message}")  


def describe(e):
    return (
        f"#{e['id']} {e['name']} — {coord(e['pos'])}"
        f" — {e['pf']:g} PF"
        + (f" (+{e['attack_bonus']:g} en attaque)" if e.get("attack_bonus") else "")
    )


def require_phase(g, phase, owner=None):
    if g["winner"] is not None:
        raise ValueError("La partie est terminée.")
    if g["phase"] != phase:
        raise ValueError("Action impossible dans cette phase.")
    if owner is not None and g["active"] != owner:
        raise ValueError("Ce n'est pas à ce joueur d'agir.")


def add_entity(g, owner, name, kind, pos, pf, wait=0):
    pos = require_position(pos)
    if at(g, pos):
        raise ValueError("Cette case est déjà occupée.")

    result = {
        "id": g["next_id"],
        "owner": owner,
        "name": name,
        "kind": kind,
        "pos": list(pos),
        "pf": float(pf),
        "max_pf": float(pf),
        "wait": wait,
        "acted": False,
        "used": False,
    }
    g["next_id"] += 1
    g["entities"].append(result)
    return result


def add_unit(g, owner, name, pos):  
    unit = add_entity(  
        g,  
        owner,  
        name,  
        "unit",  
        pos,  
        UNITS[name]["pf"],  
    )  
  
    unit["kamikaze"] = False  
  
    if (  
        owner == 0  
        and name == "Déferlant"  
        and "Dents acérées" in g["players"][owner]["upgrades"]  
    ):  
        unit["max_pf"] += 0.5  
        unit["pf"] += 0.5  
  
    if (  
        owner == 1  
        and name == "Mammouth dompté"  
        and "Développement musculaire" in g["players"][owner]["upgrades"]  
    ):  
        unit["max_pf"] += 3  
        unit["pf"] += 3  
  
    return unit  

def pay(g, owner, gold, mana=0):
    player = g["players"][owner]
    if player["gold"] < gold or player["mana"] < mana:
        raise ValueError("Ressources insuffisantes.")
    player["gold"] -= gold
    player["mana"] -= mana


def advance_age(g, owner, target_age):
    require_phase(g, "build", owner)
    player = g["players"][owner]
    current_age = player["age"]

    if target_age != current_age + 1 or target_age not in AGE_COSTS:
        raise ValueError("Le passage d'âge doit être effectué dans l'ordre.")

    fid = faction_id(g, owner)
    prerequisite = AGE_PREREQUISITES.get((fid, target_age))
    if prerequisite is not None and not building_is_completed(
        g, owner, prerequisite
    ):
        raise ValueError(
            f"Construis complètement : {prerequisite}."
        )

    cost = AGE_COSTS[target_age]
    pay(g, owner, cost["gold"], cost["mana"])
    player["age"] = target_age

    # Derniers nés : chaque colonie s'améliore séparément.
    new_base_pf = BASE_PF_BY_AGE.get((fid, target_age))
    for entity in g["entities"]:
        if (
            new_base_pf is None
            or entity["owner"] != owner
            or entity["kind"] != "base"
        ):
            continue

        pf_gain = new_base_pf - entity["max_pf"]
        entity["max_pf"] = new_base_pf
        entity["pf"] = min(new_base_pf, entity["pf"] + pf_gain)

    log(g, f"{faction_of(g, owner)['name']} passe à l'âge {target_age}.")


def collect_coins(g, owner, route):
    total = sum(
        g["coins"].pop(key(pos), 0)
        for pos in dict.fromkeys(tuple(p) for p in route)
    )
    if total:
        g["players"][owner]["gold"] += total
        log(g, f"{faction_of(g, owner)['name']} trouve {total} or.")


# ============================================================
# CRÉATION ET CHRONOMÈTRE
# ============================================================

VICTORY_MODES = {
    "time": "⏱️ Victoire au temps — meilleur score en PV à la fin du chrono",
    "bases": "🏰 Destruction — le premier qui détruit 3 bases ennemies gagne",
}


def new_game(first, target, minutes, victory_mode="time", factions=(DEFERLANTS, EXILES)):
    g = {
        "version": 1,
        "turn": 1,
        "first": first,
        "active": first,
        "factions": list(factions),
        "phase": "build",
        "ready": [],
        "passed": [],
        "players": [
            {"gold": 1000, "mana": 0, "pv": 0.0, "bases": 0, "age": 1, "units_built": {}, "upgrades": []},
            {"gold": 1000, "mana": 0, "pv": 0.0, "bases": 0, "age": 1, "units_built": {}, "upgrades": []},
        ],
        "entities": [],
        "next_id": 1,
        "terrain": {},
        "resources": {},
        "coins": {},
        "log": [],
        "target": target,
        "victory_mode": victory_mode,
        "remaining": float(minutes * 60),
        "tick": time.time(),
        "winner": None,
        "curtain": False,
    }

    def set_resource(cell_coord, kind, multiplier):
        try:
            pos = pos_from_coord(cell_coord)
        except ValueError:
            return

        g["terrain"].pop(key(pos), None)
        g["resources"][key(pos)] = [kind, multiplier]

    def set_terrain(cell_coord, terrain_name):
        try:
            pos = pos_from_coord(cell_coord)
        except ValueError:
            return

        g["terrain"][key(pos)] = terrain_name

        if terrain_name in ("mountain", "sea"):
            g["resources"].pop(key(pos), None)

    base_positions = [
        pos_from_coord(cell_coord)
        for cell_coord in START_BASE_COORDS
    ]
    habitation_positions = [
        pos_from_coord(cell_coord)
        for cell_coord in START_HABITATION_COORDS
    ]

    for owner, positions in ((0, base_positions), (1, habitation_positions)):
        for pos in positions:
            add_entity(
                g,
                owner,
                faction_of(g, owner)["base"],
                "base",
                pos,
                faction_of(g, owner)["base_pf"],
            )

    for cell_coord in [
        "A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1", "E1",
    ]:
        set_terrain(cell_coord, "sea")

    for cell_coord in ["B3", "D2", "F1"]:
        set_terrain(cell_coord, "plain")

    for cell_coord in ["E4", "G3", "I2"]:
        set_resource(cell_coord, "gold", 1)

    for cell_coord in ["A6", "M2", "Q2"]:
        set_resource(cell_coord, "gold", 2)

    for cell_coord in ["B9", "O5"]:
        set_resource(cell_coord, "mana", 1)

    for cell_coord in ["K7"]:
        set_resource(cell_coord, "mana", 2)

    for cell_coord in ["V16", "X15", "T17", "U17", "W16", "Y15", "V17", "W17", "X16", "Y16", "X17", "Y17"]:
        set_terrain(cell_coord, "sea")

    # Montagnes et forêts calées sur l'image de fond du plateau.
    for cell_coord in [
        "C5", "C6", "D5",
        "M3",
        "O2",
        "S2",
        "P4", "P5", "O6",
        "K6", "L6", "L7",
        "N8",
        "C9", "E8", "I9", "I10", "H10",
        "L9",
        "G16", "K16", "W12", "W13", "V12", "W9", "T11",
        "F6", "J12", "J13", "K12", "N10", "N11", "O12",
        "R7", "Q8", "Q9", "U10", "U3",
        "D15", "E15", "M15",
    ]:
        set_terrain(cell_coord, "mountain")

    for cell_coord in [
        "K2", "N2", "T2",
        "U5", "R6", "N6", "X7",
        "L8", "M9", "N9",
        "B10", "H11", "L11",
        "E13", "F15", "J15", "O16",
    ]:
        set_terrain(cell_coord, "forest")

    g["resources"].pop(key(pos_from_coord("H1")), None)

    for cell_coord in [
        "H6",
        "Q16",
        "S15",
        "U14",
        "R11",
    ]:
        set_resource(cell_coord, "gold", 1)

    for cell_coord in [
        "M16",
        "I16",
        "Y12",
        "D12",
        "V5",
    ]:
        set_resource(cell_coord, "gold", 2)

    for cell_coord in [
        "R8",
        "E16",
        "H9",
        "U2",
    ]:
        set_resource(cell_coord, "gold", 3)

    for cell_coord in [
        "K13",
        "X8",
    ]:
        set_resource(cell_coord, "mana", 1)

    for cell_coord in [
        "O11",
    ]:
        set_resource(cell_coord, "mana", 2)

    log(g, "Début de la partie.")

    return g


def new_bundle(first, target, minutes, victory_mode="time", factions=(DEFERLANTS, EXILES)):
    game = new_game(first, target, minutes, victory_mode, factions)
  
    if not isinstance(game, dict):  
        raise ValueError(  
            "new_game() n'a pas renvoyé le dictionnaire de la partie. "  
            "Vérifie le « return g » à la fin de cette fonction."  
        )  
  
    return {  
        "save_version": SAVE_VERSION,  
        "game": game,  
        "draft": None,  
        "committed": None,  
    }  


def normalize_starting_layout(bundle):
    g = bundle.get("game")
    if not isinstance(g, dict):
        return False

    if (
        g.get("turn") != 1
        or g.get("phase") != "build"
        or g.get("winner") is not None
        or g.get("ready")
        or g.get("passed")
    ):
        return False

    def visual_position(column, row):
        return column, row - column // 2

    def mirror_position(pos, height=H):
        q, _ = pos
        mirrored_q = W - 1 - q
        mirrored_row = height - 1 - board_row(pos)
        return mirrored_q, mirrored_row - mirrored_q // 2

    position_map = {}
    target_bases = [pos_from_coord(cell_coord) for cell_coord in START_BASE_COORDS]
    target_habitations = [pos_from_coord(cell_coord) for cell_coord in START_HABITATION_COORDS]

    legacy_layouts = (
        (LEGACY_START_COLUMNS, PREVIOUS_GRID_HEIGHT),
        (PREVIOUS_START_COLUMNS, PREVIOUS_GRID_HEIGHT),
        (START_COLUMNS, H),
    )

    for old_columns, old_height in legacy_layouts:
        for legacy_column, current_base in zip(old_columns, target_bases):
            legacy_base = visual_position(legacy_column, 1)
            legacy_gold = visual_position(legacy_column, 0)

            position_map[legacy_base] = current_base
            position_map[mirror_position(legacy_base, old_height)] = mirror_position(current_base)

    for old_column, new_column in ((3, 11), (7, 15)):
        old_unit = visual_position(old_column, 2)
        new_unit = visual_position(new_column, 2)

        position_map[old_unit] = new_unit
        position_map[mirror_position(old_unit, PREVIOUS_GRID_HEIGHT)] = mirror_position(new_unit)

    moved = False
    # Instantané : ne journaliser que si la partie a réellement changé.
    snapshot = copy.deepcopy((g.get("entities"), g.get("resources")))

    for entity in g.get("entities", []):
        pos = tuple(entity.get("pos", ()))
        new_pos = position_map.get(pos)
        if new_pos is not None and tuple(new_pos) != tuple(pos):
            entity["pos"] = list(new_pos)
            moved = True

    for owner, targets in ((0, target_bases), (1, target_habitations)):
        faction_base = faction_of(g, owner)["base"]
        bases = [
            entity
            for entity in sorted(g.get("entities", []), key=lambda item: item.get("id", 0))
            if entity.get("owner") == owner
            and entity.get("kind") == "base"
            and entity.get("name") == faction_base
        ]

        for entity, target in zip(bases[:4], targets):
            if tuple(entity.get("pos", ())) != target:
                entity["pos"] = list(target)
                moved = True

    resources = g.get("resources", {})
    if isinstance(resources, dict):
        updated_resources = {}
        for cell_key, value in resources.items():
            try:
                pos = tuple(int(value) for value in cell_key.split(","))
            except ValueError:
                updated_resources[cell_key] = value
                continue

            new_pos = position_map.get(pos)
            if new_pos is not None and tuple(new_pos) != tuple(pos):
                updated_resources[key(new_pos)] = value
                moved = True
            else:
                updated_resources[cell_key] = value

        if moved:
            g["resources"] = updated_resources
        if moved and (g.get("entities"), g.get("resources")) != snapshot:
            g["log"].append("T1.1 — Calage de départ ajusté sur le fond du plateau.")

    return moved


def check_victory(g):
    if g["winner"] is not None:
        return

    mode = g.get("victory_mode")

    if mode == "bases":
        # Pas de chrono : seules 3 bases détruites font gagner.
        candidates = [
            owner for owner in (0, 1)
            if g["players"][owner]["bases"] >= 3
        ]
        if candidates:
            g["winner"] = candidates[0] if len(candidates) == 1 else -1
        return

    if mode == "time":
        # Seul le score en PV à la fin du chrono compte.
        if g["remaining"] <= 0:
            a, b = [p["pv"] for p in g["players"]]
            g["winner"] = -1 if a == b else (0 if a > b else 1)
        return

    # Anciennes sauvegardes sans mode : toutes les conditions.
    candidates = [
        owner for owner in (0, 1)
        if (
            g["players"][owner]["bases"] >= 3
            or (
                g["target"] > 0
                and g["players"][owner]["pv"] >= g["target"]
            )
        )
    ]

    if candidates:
        g["winner"] = candidates[0] if len(candidates) == 1 else -1
    elif g["remaining"] <= 0:
        a, b = [p["pv"] for p in g["players"]]
        g["winner"] = -1 if a == b else (0 if a > b else 1)


def tick(g):
    now = time.time()
    if g["winner"] is None and g.get("victory_mode") != "bases":
        g["remaining"] = max(
            0.0,
            g["remaining"] - max(0.0, now - g["tick"]),
        )
    g["tick"] = now
    check_victory(g)


# ============================================================
# CONSTRUCTION, RECRUTEMENT ET RÉCOLTE
# ============================================================

def building_is_completed(g, owner, name):
    return any(
        entity["owner"] == owner
        and entity["name"] == name
        and entity["kind"] == "building"
        and entity["wait"] == 0
        for entity in g["entities"]
    )


def building_is_available(g, owner, name):
    return (
        BUILDING_AGES.get((faction_id(g, owner), name), 1)
        <= g["players"][owner]["age"]
    )


def base_cost_for_age(g, owner):
    return BASE_COST_BY_AGE.get(
        (faction_id(g, owner), g["players"][owner]["age"]),
        faction_of(g, owner)["base_cost"],
    )


def above_black_line(pos):
    column, row = pos
    return board_row(pos) < 16 - (2 * column / 3)


def enemy_side_of_line(owner, pos):
    """Côté adverse de la ligne noire A17-Y1 pour ce siège."""
    return above_black_line(pos) if owner == 1 else not above_black_line(pos)


def exile_gold_cost(g, owner, pos, amount):
    if faction_id(g, owner) == EXILES and enemy_side_of_line(owner, pos):
        return int(amount * 1.5)
    return amount


def placement_cost(  
    view,  
    owner,  
    mode,  
    name,  
    positions,  
    accelerated=False,  
):  
    faction = faction_of(view, owner)

    if mode == "build":
        if name == faction["base"]:
            gold = base_cost_for_age(view, owner)
            mana = 0
        else:
            data = faction["buildings"][name]
            gold = int(
                data["cost"] * (1.5 if accelerated else 1)
            )
            mana = data.get("mana", 0)

        if positions:
            gold = exile_gold_cost(view, owner, positions[0], gold)
  
        return gold, mana  
  
    if mode == "recruit":  
        data = UNITS[name]  
  
        gold = recruitment_gold_cost(  
            view,  
            owner,  
            name,  
            positions,  
        )  
  
        return gold, data["mana"]  
  
    raise ValueError("Mode de placement inconnu.")  

def purchase_upgrade(g, owner, name):  
    require_phase(g, "build", owner)  
  
    upgrade = UPGRADES.get(name)  
    if upgrade is None:  
        raise ValueError("Amélioration inconnue.")  
  
    if upgrade["owner"] != faction_id(g, owner):
        raise ValueError("Cette amélioration ne t'appartient pas.")
  
    if name in g["players"][owner].get("upgrades", []):  
        raise ValueError("Cette amélioration a déjà été achetée.")  
  
    required_building = upgrade.get("building")  
    if required_building and not building_is_completed(g, owner, required_building):  
        raise ValueError(f"Construis d'abord complètement : {required_building}.")  
  
    if g["players"][owner]["age"] < upgrade.get("age", 1):  
        raise ValueError("Cette amélioration est débloquée à un âge supérieur.")  
  
    pay(g, owner, upgrade["cost"], upgrade["mana"])  
    g["players"][owner].setdefault("upgrades", []).append(name)  
  
    log(g, f"{faction_of(g, owner)['name']} achète l’amélioration {name}.")


TECH_BUILDINGS = {  
    0: "Bassin de mutation",  # Déferlants  
    1: "Marché",              # Exilés  
}  

def available_upgrades(g, owner):  
    if not isinstance(owner, int):  
        return []  
  
    fid = faction_id(g, owner)
    tech = TECH_BUILDINGS.get(fid)
    if tech is None:
        return []

    age = g["players"][owner]["age"]

    return [
        name for name, data in UPGRADES.items()
        if data["owner"] == fid
        and data.get("building") == tech  
        and data.get("age", 1) <= age  
        and name not in g["players"][owner]["upgrades"]  
    ]  
  
def mutate_kamikaze(g, owner, unit_id):
    require_phase(g, "build", owner)
    if "Mutation kamikaze" not in g["players"][owner]["upgrades"]:
        raise ValueError("Construis d'abord l'amélioration Mutation kamikaze.")

    unit = entity(g, unit_id)
    if (
        unit["owner"] != owner
        or unit["kind"] != "unit"
        or unit["name"] != "Déferlant"
    ):
        raise ValueError("Seul un Déferlant peut devenir kamikaze.")
    if unit.get("kamikaze"):
        raise ValueError("Cette unité est déjà kamikaze.")
    if unit["wait"]:
        raise ValueError("Cette unité est déjà en attente.")

    pay(g, owner, 100)
    unit["kamikaze"] = True
    unit["wait"] = 1
    log(g, f"Déferlant #{unit['id']} muté en kamikaze.")


def build(g, owner, source_id, name, pos, accelerated):  
    require_phase(g, "build", owner)  
  
    pos = require_position(pos)  
    source = entity(g, source_id)
    faction = faction_of(g, owner)
    deferlants = faction_id(g, owner) == DEFERLANTS

    if source["owner"] != owner or source["kind"] != "base":
        raise ValueError("Choisis une base alliée.")

    if source["wait"]:
        raise ValueError("Cette base est inactive.")

    if deferlants and source["used"]:
        raise ValueError("Cet incubateur a déjà construit ce tour.")

    if at(g, pos) or terrain(g, pos) in ("mountain", "sea"):
        raise ValueError("Case occupée, montagne ou mer.")

    if key(pos) in g["resources"]:
        raise ValueError("Construction interdite sur une ressource.")

    if deferlants and distance(source["pos"], pos) > 4:
        raise ValueError("Construction limitée à 4 cases de la base.")  
  
    if name == faction["base"]:  
        if accelerated:  
            raise ValueError("Les bases ne peuvent pas être accélérées.")  
  
        pf = BASE_PF_BY_AGE.get(
            (faction_id(g, owner), g["players"][owner]["age"]),
            faction["base_pf"],
        )
        wait = 2
        kind = "base"  
  
    else:  
        data = faction["buildings"].get(name)  
  
        if data is None:  
            raise ValueError("Construction inconnue.")  
  
        if not building_is_available(g, owner, name):  
            raise ValueError(  
                "Ce bâtiment est débloqué à un âge supérieur."  
            )  
  
        count = sum(  
            piece["owner"] == owner and piece["name"] == name  
            for piece in g["entities"]  
        )  
  
        if count >= data["limit"]:  
            raise ValueError("Limite de bâtiments atteinte.")  
  
        pf = data["pf"]  
        wait = 0 if accelerated else 1  
        kind = "building"  
  
    # Calcul commun aux bases ET aux bâtiments.  
    # Même fonction que celle utilisée pour afficher le prix.  
    cost, mana_cost = placement_cost(  
        g,  
        owner,  
        "build",  
        name,  
        [pos],  
        accelerated,  
    )  
  
    pay(g, owner, cost, mana_cost)  
  
    add_entity(  
        g,  
        owner,  
        name,  
        kind,  
        pos,  
        pf,  
        wait,  
    )  
  
    source["used"] = True  
  
    log(  
        g,  
        f"{faction['name']} construit {name} en {coord(pos)}.",  
    ) 

def recruitment_slots(g, producer):  
    """Cases adjacentes libres, quelle que soit la faction."""  
    return [  
        pos  
        for pos in neighbors(producer["pos"])  
        if (  
            at(g, pos) is None  
            and terrain(g, pos) not in ("mountain", "sea")  
        )  
    ]  

def recruit(g, owner, producer_id, name, positions):  
    require_phase(g, "build", owner)  
    producer = entity(g, producer_id)  
    data = UNITS.get(name)  
  
    if data is None:  
        raise ValueError("Unité inconnue.")  
  
    if UNIT_AGES.get(name, 1) > g["players"][owner]["age"]:  
        raise ValueError("Cette unité est débloquée à un âge supérieur.")  
  
    allowed = faction_of(g, owner)["buildings"].get(producer["name"], {})
    if (
        producer["owner"] != owner  
        or producer["kind"] != "building"  
        or name not in allowed.get("units", [])  
    ):  
        raise ValueError("Bâtiment de production incorrect.")  
  
    if producer["wait"] or producer["used"]:  
        raise ValueError("Bâtiment inactif ou déjà utilisé.")  
  
    positions = [require_position(p) for p in positions]  
    batch = recruitment_batch(g, owner, name)  
  
    if len(positions) != batch or len(set(positions)) != len(positions):  
        raise ValueError(f"Sélectionne {batch} case(s) distincte(s).")  
  
    allowed_positions = set(recruitment_slots(g, producer))  
    for pos in positions:  
        if pos not in allowed_positions:  
            raise ValueError(  
                "Choisis une case adjacente libre dans ta moitié "  
                "du plateau, qui n'est pas une montagne."  
            )  
  
    count = g["players"][owner]["units_built"].get(name, 0)  
    if count + batch > data["limit"]:  
        raise ValueError("Limite d'unités atteinte.")  
  
    gold_cost, mana_cost = placement_cost(  
        g,  
        owner,  
        "recruit",  
        name,  
        positions,  
    )  
    
    pay(g, owner, gold_cost, mana_cost)  
  
    for pos in positions:  
        unit = add_unit(g, owner, name, pos)  
        unit["producer_id"] = producer_id  
  
    g["players"][owner]["units_built"][name] = count + batch  
    producer["used"] = True  
    log(g, f"{faction_of(g, owner)['name']} recrute {batch} × {name}.")


def collect_adjacent_resources(g, base):  
    owner = base["owner"]  
    age = g["players"][owner]["age"]  
  
    # Barème par faction et par âge (voir HARVEST_BY_AGE en fin de fichier).
    gold_income, mana_income = harvest_income(g, owner)
  
    resources = []  
  
    for pos in neighbors(base["pos"]):  
        resource = g["resources"].get(key(pos))  
  
        if resource is None:  
            continue  
  
        occupant = at(g, pos)  
  
        if (  
            occupant is not None  
            and occupant["kind"] == "unit"  
            and occupant["owner"] != owner  
        ):  
            continue  
  
        resources.append(resource)  
  
    for kind, income in (  
        ("gold", gold_income),  
        ("mana", mana_income),  
    ):  
        multipliers = [  
            multiplier  
            for resource_kind, multiplier in resources  
            if resource_kind == kind  
        ]  
  
        if multipliers:  
            g["players"][owner][kind] += (  
                income * max(multipliers)  
            )  

def harvest(g):
    for base in g["entities"]:
        if base["kind"] != "base" or base["wait"]:
            continue

        collect_adjacent_resources(g, base)

    log(g, "Récolte effectuée pour les deux peuples.")


# ============================================================
# DÉPLACEMENTS : DIJKSTRA ET VALIDATION SERVEUR
# ============================================================

def paths(g, unit, allow_attack=False):
    """Chemins minimaux. Un ennemi est éventuellement une destination finale."""
    start = tuple(unit["pos"])
    budget = UNITS[unit["name"]]["move"]
    if (  
        unit["name"] == "Déferlant"  
        and "2 pattes en plus" in g["players"][unit["owner"]]["upgrades"]  
    ):  
        budget += 1  
    occupants = {tuple(e["pos"]): e for e in g["entities"]}

    costs = {start: 0}
    routes = {start: [start]}
    queue = [(0, start)]

    while queue:
        cost, pos = heapq.heappop(queue)

        if cost != costs[pos]:
            continue

        for nxt in neighbors(pos):
            if terrain(g, nxt) == "sea":
                continue
            occupant = occupants.get(nxt)
            enemy = (
                occupant is not None
                and occupant["owner"] != unit["owner"]
            )

            if occupant is not None:
                if enemy:
                    if not allow_attack:
                        continue
                elif occupant["kind"] not in ("unit", "base", "building"):
                    # Unités, bases et bâtiments alliés se traversent.
                    continue

            step = 2 if terrain(g, nxt) == "mountain" else 1
            new_cost = cost + step

            if (
                new_cost > budget
                or new_cost >= costs.get(nxt, math.inf)
            ):
                continue

            costs[nxt] = new_cost
            routes[nxt] = routes[pos] + [nxt]

            # Un ennemi peut être atteint, mais jamais traversé.
            if not enemy:
                heapq.heappush(queue, (new_cost, nxt))

    return costs, routes


def available(g, owner):
    return [
        e for e in g["entities"]
        if (
            e["owner"] == owner
            and e["kind"] == "unit"
            and e["wait"] == 0
            and not e["acted"]
        )
    ]


def can_move(g, unit):
    return (
        unit is not None
        and g["winner"] is None
        and g["phase"] == "move"
        and not g["curtain"]
        and g["active"] not in g["passed"]
        and unit["kind"] == "unit"
        and unit["owner"] == g["active"]
        and not unit["wait"]
        and not unit["acted"]
    )


def move_preview(g, unit):
    if not can_move(g, unit):
        return {}, {}

    costs, routes = paths(g, unit)
    destinations = {
        pos: cost
        for pos, cost in costs.items()
        if pos != tuple(unit["pos"]) and at(g, pos) is None
    }
    return destinations, {
        pos: routes[pos] for pos in destinations
    }


def end_round(g):
    for e in g["entities"]:
        e["wait"] = max(0, e["wait"] - 1)
        e["acted"] = False
        e["used"] = False

    g["turn"] += 1
    g["first"] = 1 - g["first"]
    g["active"] = g["first"]
    g["phase"] = "build"
    g["ready"] = []
    g["passed"] = []
    g["curtain"] = False
    harvest(g)
    log(g, "Nouvelle phase de planification.")


def next_activation(g, switch=True):
    check_victory(g)
    if g["winner"] is not None:
        return

    for owner in (0, 1):
        if not available(g, owner) and owner not in g["passed"]:
            g["passed"].append(owner)

    if len(g["passed"]) == 2:
        end_round(g)
        return

    previous = g["active"]
    order = [1 - previous, previous] if switch else [previous, 1 - previous]

    for owner in order:
        if owner not in g["passed"]:
            g["active"] = owner
            break

    if g["active"] != previous:
        g["curtain"] = False


def movement_spent(g, unit):  
    """Points de déplacement déjà consommés pendant ce tour."""  
    if unit.get("movement_spent_turn") != g["turn"]:  
        return 0  
  
    return unit.get("movement_spent", 0)  
  
  
def remaining_actions(g, unit):  
    """Budget restant pour se déplacer et garder une action d'attaque."""  
    budget = UNITS[unit["name"]]["move"]  
  
    if (  
        unit["name"] == "Déferlant"  
        and "2 pattes en plus" in g["players"][unit["owner"]]["upgrades"]  
    ):  
        budget += 1  
  
    return max(0, budget - movement_spent(g, unit))  


def move_unit(g, eid, destination):  
    require_phase(g, "move")  
  
    destination = require_position(destination)  
    unit = entity(g, eid)  
  
    if not can_move(g, unit):  
        raise ValueError("Cette unité ne peut pas être déplacée.")  
  
    costs, routes = paths(g, unit)  
  
    if (  
        destination == tuple(unit["pos"])  
        or destination not in routes  
        or at(g, destination) is not None  
    ):  
        raise ValueError("Destination inaccessible ou occupée.")  
  
    movement_cost = costs[destination]  
    spent_before = movement_spent(g, unit)  
    route = routes[destination]  
  
    collect_coins(g, unit["owner"], route[1:])  
  
    unit["pos"] = list(destination)  
    unit["movement_spent_turn"] = g["turn"]  
    unit["movement_spent"] = spent_before + movement_cost  
  
    remaining = remaining_actions(g, unit)  
  
    log(  
        g,  
        f"{unit['name']} #{unit['id']} se déplace en "  
        f"{coord(destination)} : {movement_cost} point(s) consommé(s), "  
        f"{remaining} restant(s).",  
    )  
  
    if remaining <= 0:  
        # Tout le budget a été dépensé : aucune attaque possible.  
        unit["acted"] = True  
        next_activation(g)  
        return  
  
    # Le même joueur termine l'activation de cette unité.  
    # Il peut encore la déplacer, attaquer, ou terminer son activation.  
    unit["acted"] = False  
    g["moving_unit_id"] = unit["id"]  
  
    g["_ui_message"] = (  
        f"{unit['name']} : {remaining} action(s) restante(s). "  
        "Tu peux continuer le déplacement, attaquer en gardant "  
        "au moins 1 action, ou terminer son activation."  
    )  

def selected_attackers(g):
    """Retourne uniquement les unités sélectionnées encore activables."""
    eligible = {
        e["id"]: e
        for e in g["entities"]
        if can_move(g, e)
    }

    return [
        eligible[eid]
        for eid in st.session_state.ui_attacker_ids
        if eid in eligible
    ]

def combat_values(attackers, target):  
    power = float(sum(attacker["pf"] for attacker in attackers))  
    defense = float(target["pf"])  
  
    # Conservation du bonus actuel en cas d'égalité.  
    bonus = 0.5 if power == defense else 0.0  
    winnable = power + bonus > defense  
  
    return {  
        "power": power,  
        "defense": defense,  
        "bonus": bonus,  
        "effective_power": power + bonus,  
        "winnable": winnable,  
  
        # Si victoire : pertes à répartir entre les attaquants.  
        # Sinon : destruction de tous les attaquants.  
        "losses": defense - bonus if winnable else power,  
  
        "defender_damage": defense if winnable else power,  
        "defender_remaining": 0.0 if winnable else defense - power,  
    }  

def attack_destinations(g, attackers):  
    if not attackers:  
        return {}  
  
    # Un tireur sélectionné seul : véritables cibles à portée.  
    if (  
        len(attackers) == 1  
        and UNITS[attackers[0]["name"]]["range"] > 0  
    ):  
        attacker = attackers[0]  
        result = {}  
  
        for target in g["entities"]:  
            if target["owner"] == attacker["owner"]:  
                continue  
  
            try:  
                values = ranged_attack_values(g, attacker, target)  
            except ValueError:  
                continue  
  
            result[tuple(target["pos"])] = {  
                "target_id": target["id"],  
                "costs": [  
                    distance(attacker["pos"], target["pos"])  
                ],  
                "winnable": values["remaining"] == 0,  
                "ranged": True,  
            }  
  
        return result  
  
    # Groupe : conservation du corps à corps actuel.  
    cost_maps = [  
        paths(g, attacker, allow_attack=True)[0]  
        for attacker in attackers  
    ]  
  
    result = {}  
  
    for target in g["entities"]:  
        if target["owner"] == attackers[0]["owner"]:  
            continue  
  
        pos = tuple(target["pos"])  
  
        if all(pos in costs for costs in cost_maps):  
            result[pos] = {  
                "target_id": target["id"],  
                "costs": [costs[pos] for costs in cost_maps],  
                "winnable": combat_values(  
                    attackers, target  
                )["winnable"],  
            }  
  
    return result  

def pass_turn(g):
    require_phase(g, "move")
    owner = g["active"]
    if owner not in g["passed"]:
        g["passed"].append(owner)
    log(g, f"{faction_of(g, owner)['name']} passe pour le reste du tour.")
    next_activation(g)


# ============================================================
# COMBATS
# ============================================================

def destroy(g, victim, credited_owner, killer=None):  
    player = g["players"][credited_owner]  
  
    if victim["kind"] == "base":  
        player["pv"] += 6  
        player["bases"] += 1  
    elif victim["kind"] == "unit":  
        player["pv"] += victim["max_pf"]  
  
    # Effet Vengeance  
    if (  
        victim["kind"] == "unit"  
        and "Vengeance" in g["players"][victim["owner"]]["upgrades"]  
        and killer is not None  
    ):  
        killer["pf"] = max(0.0, killer["pf"] - 0.5)  
        killer["wait"] = killer.get("wait", 0) + 1  
  
    g["entities"].remove(victim)  
    log(g, f"{victim['name']} de {faction_of(g, victim['owner'])['name']} détruit.")  


def prepare_attack(g, attacker_ids, target_id):  
    require_phase(g, "move")  
    if g["curtain"]:  
        raise ValueError("Confirme d'abord que tu es prêt.")  
  
    attackers = [entity(g, eid) for eid in attacker_ids]  
    target = entity(g, target_id)  
  
    if target["owner"] == g["active"]:  
        raise ValueError("Choisis une cible ennemie.")  
  
    for attacker in attackers:  
        if attacker["name"] == "Costaud" and target["kind"] not in ("building", "base"):  
            raise ValueError("Le Costaud ne peut attaquer que les bâtiments et les bases.")  
    """Valide une attaque, même si les attaquants sont moins forts."""  
    require_phase(g, "move")  

    if UNITS[attacker["name"]]["range"] == 0 and is_flying(target):  
        raise ValueError("Une unité de corps à corps ne peut pas attaquer une unité volante.")  
  
    if g["curtain"]:  
        raise ValueError("Confirme d'abord que tu es prêt.")  
  
    if not attacker_ids:  
        raise ValueError("Sélectionne au moins une unité.")  
  
    if len(attacker_ids) != len(set(attacker_ids)):  
        raise ValueError("Une unité est sélectionnée plusieurs fois.")  
  
    attackers = [entity(g, eid) for eid in attacker_ids]  
    target = entity(g, target_id)  
  
    if target["owner"] == g["active"]:  
        raise ValueError("Choisis une cible ennemie.")  
  
    if any(not can_move(g, attacker) for attacker in attackers):  
        raise ValueError("Au moins une unité est indisponible.")  
  
    destination = tuple(target["pos"])  
    routes_by_id = {}  
  
    for attacker in attackers:  
        _, routes = paths(g, attacker, allow_attack=True)  
  
        if destination not in routes:  
            raise ValueError(  
                f"{describe(attacker)} ne peut pas atteindre "  
                f"{coord(destination)} avec son déplacement."  
            )  
  
        routes_by_id[attacker["id"]] = routes[destination]  
  
    return attackers, target, routes_by_id  

def ranged_attack_values(g, attacker, target):  
    if attacker["name"] in MAGES:  
        raise ValueError(  
            "Le Mage ne possède pas de tir normal. "  
            "Utilise le panneau « Sorts du Mage »."  
        )  
  
    if attacker["name"] != STONE_GOLEM:  
        require_phase(g, "move")  
  
        if not can_move(g, attacker):  
            raise ValueError("Cette unité ne peut pas agir.")  
        if target["owner"] == attacker["owner"]:  
            raise ValueError("Choisis une cible ennemie.")  
  
        data = UNITS[attacker["name"]]  
        attack_range = data["range"]  
  
        if attack_range <= 0:  
            raise ValueError("Cette unité ne possède pas de tir.")  
  
        if terrain(g, attacker["pos"]) == "mountain":  
            attack_range += 1  
  
        if distance(attacker["pos"], target["pos"]) > attack_range:  
            raise ValueError(  
                f"Cible hors de portée : portée maximale {attack_range}."  
            )  
  
        damage = float(attacker["pf"])  
  
        if damage <= 0:  
            raise ValueError("Ce tir n'inflige aucun dégât.")  
  
        result = {  
            "range": attack_range,  
            "damage": damage,  
            "remaining": max(0.0, float(target["pf"]) - damage),  
        }  
  
        if (  
            attacker["name"] == "Elfe"  
            and "Instinct elfique" in g["players"][attacker["owner"]]["upgrades"]  
        ):  
            direction = golem_direction(attacker["pos"], target["pos"])  
            if direction is None:  
                raise ValueError("L’Elfe doit tirer en ligne droite.")  
            behind = (  
                target["pos"][0] + direction[0],  
                target["pos"][1] + direction[1],  
            )  
            result["elfique_back"] = behind if behind in CELL_SET else None  
  
        return result  
  
    # Golem  
    require_phase(g, "move")  
    if not can_move(g, attacker):  
        raise ValueError("Ce Golem ne peut pas agir.")  
    if target["owner"] == attacker["owner"]:  
        raise ValueError("Choisis une cible ennemie.")  
    if target["kind"] != "unit":  
        raise ValueError("Le Golem de pierre vise uniquement des unités.")  
  
    gap = distance(attacker["pos"], target["pos"])  
    if gap not in (3, 4):  
        raise ValueError("Le Golem vise uniquement à 3 ou 4 cases.")  
  
    impacts = golem_impact_cells(attacker, target)  
    damage = float(attacker["pf"])  
  
    if damage <= 0:  
        raise ValueError("Ce tir n'inflige aucun dégât.")  
  
    return {  
        "range": 4,  
        "damage": damage,  
        "remaining": max(0.0, target["pf"] - damage),  
        "impact_cells": impacts,  
    }  
  
def ranged_attack(g, attacker_id, target_id):  
    attacker = entity(g, attacker_id)  
    target = entity(g, target_id)  
  
    if attacker["name"] != STONE_GOLEM:  
        values = ranged_attack_values(g, attacker, target)  
  
        attacker_before = float(attacker["pf"])  
        target_before = float(target["pf"])  
        actual_damage = min(target_before, values["damage"])  
  
        target["pf"] = values["remaining"]  
        attacker["acted"] = True  
  
        report = {  
            "turn": turn_label(g),  
            "position": coord(target["pos"]),  
            "power": values["damage"],  
            "bonus": 0.0,  
            "defense": target_before,  
            "occupier_id": None,  
            "participants": [  
                {  
                    "id": attacker["id"],  
                    "owner": attacker["owner"],  
                    "name": attacker["name"],  
                    "role": "Tireur",  
                    "before": attacker_before,  
                    "damage": 0.0,  
                    "after": attacker_before,  
                },  
                {  
                    "id": target["id"],  
                    "owner": target["owner"],  
                    "name": target["name"],  
                    "role": "Cible",  
                    "before": target_before,  
                    "damage": actual_damage,  
                    "after": target["pf"],  
                },  
            ],  
        }  
  
        log(  
            g,  
            f"{attacker['name']} #{attacker['id']} tire sur "  
            f"{target['name']} #{target['id']} : "  
            f"{actual_damage:g} PF de dégâts, sans riposte."  
        )  
  
        if target["pf"] <= 0:  
            destroy(g, target, attacker["owner"], killer=attacker)  
  
        if (  
            attacker["name"] == "Elfe"  
            and "Instinct elfique" in g["players"][attacker["owner"]]["upgrades"]  
            and values.get("elfique_back") is not None  
        ):  
            back_pos = values["elfique_back"]  
            back_target = at(g, back_pos)  
            if back_target is not None and back_target["owner"] != attacker["owner"]:  
                before = float(back_target["pf"])  
                dmg = min(before, values["damage"])  
                back_target["pf"] = before - dmg  
                report["participants"].append({  
                    "id": back_target["id"],  
                    "owner": back_target["owner"],  
                    "name": back_target["name"],  
                    "role": "Cible arrière",  
                    "before": before,  
                    "damage": dmg,  
                    "after": back_target["pf"],  
                })  
                if back_target["pf"] <= 0:  
                    destroy(g, back_target, attacker["owner"])  
  
        g["_combat_report"] = report  
        next_activation(g)  
        return  
  
    # Golem  
    values = ranged_attack_values(g, attacker, target)  
    owner = attacker["owner"]  
    impact_set = set(values["impact_cells"])  
  
    victims = [  
        piece  
        for piece in list(g["entities"])  
        if (  
            piece["owner"] != owner  
            and piece["kind"] == "unit"  
            and tuple(piece["pos"]) in impact_set  
        )  
    ]  
  
    report = {  
        "turn": turn_label(g),  
        "position": coord(target["pos"]),  
        "power": values["damage"],  
        "bonus": 0.0,  
        "defense": float(target["pf"]),  
        "occupier_id": None,  
        "participants": [{  
            "id": attacker["id"],  
            "owner": owner,  
            "name": attacker["name"],  
            "role": "Tireur",  
            "before": float(attacker["pf"]),  
            "damage": 0.0,  
            "after": float(attacker["pf"]),  
        }],  
    }  
  
    attacker["acted"] = True  
  
    for victim in victims:  
        before = float(victim["pf"])  
        damage = min(before, values["damage"])  
        victim["pf"] = before - damage  
  
        report["participants"].append({  
            "id": victim["id"],  
            "owner": victim["owner"],  
            "name": victim["name"],  
            "role": "Cible du tir en ligne",  
            "before": before,  
            "damage": damage,  
            "after": victim["pf"],  
        })  
  
        if victim["pf"] <= 0:  
            destroy(g, victim, owner)  
  
    log(  
        g,  
        "Le Golem tire sur la ligne : "  
        + ", ".join(coord(pos) for pos in values["impact_cells"])  
        + "."  
    )  
  
    g["_combat_report"] = report  
    next_activation(g)  

def default_losses(attackers, defense, occupier_id):
    """
    Proposition initiale :
    absorber les pertes avec les autres unités avant l'occupant.
    Le joueur peut ensuite modifier chaque valeur.
    """
    losses = {attacker["id"]: 0.0 for attacker in attackers}
    remaining = float(defense)

    ordered = [
        attacker for attacker in attackers
        if attacker["id"] != occupier_id
    ] + [
        attacker for attacker in attackers
        if attacker["id"] == occupier_id
    ]

    for attacker in ordered:
        taken = min(float(attacker["pf"]), remaining)
        losses[attacker["id"]] = taken
        remaining -= taken

    return losses


def validate_losses(attackers, defense, occupier_id, losses):
    ids = {attacker["id"] for attacker in attackers}

    if occupier_id not in ids:
        raise ValueError("L'occupant doit appartenir au groupe attaquant.")

    if not isinstance(losses, dict) or set(losses) != ids:
        raise ValueError("Indique les pertes de chaque attaquant.")

    for attacker in attackers:
        value = losses[attacker["id"]]

        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
            or value > attacker["pf"]
            or not float(value * 2).is_integer()
        ):
            raise ValueError(
                f"Pertes invalides pour {attacker['name']} "
                f"#{attacker['id']} : utilise des pas de 0,5 PF, "
                f"entre 0 et {attacker['pf']:g}."
            )

    if sum(losses.values()) != defense:
        raise ValueError(
            f"Il faut répartir exactement {defense:g} PF de dégâts."
        )

    occupier = next(
        attacker for attacker in attackers
        if attacker["id"] == occupier_id
    )

    if losses[occupier_id] >= occupier["pf"]:
        raise ValueError(
            "L'unité qui prend la case doit survivre."
        )


def attack(  
    g,  
    attacker_ids,  
    target_id,  
    occupier_id=None,  
    losses=None,  
):  
    attackers, target, routes = prepare_attack(  
        g, attacker_ids, target_id  
    )  
  
    values = combat_values(attackers, target)  
    owner = g["active"]  
    defender_owner = target["owner"]  
    destination = tuple(target["pos"])  
  
    if values["winnable"]:  
        # Validation avant toute modification de la partie.  
        validate_losses(  
            attackers,  
            values["losses"],  
            occupier_id,  
            losses,  
        )  
        applied_losses = dict(losses)  
    else:  
        # Attaque sacrificielle : tous les participants sont détruits.  
        occupier_id = None  
        applied_losses = {  
            attacker["id"]: float(attacker["pf"])  
            for attacker in attackers  
        }  
  
    report = {  
        "turn": turn_label(g),    
        "position": coord(destination),  
        "power": values["power"],  
        "bonus": values["bonus"],  
        "defense": values["defense"],  
        "occupier_id": occupier_id,  
        "participants": [],  
    }  
  
    log(  
        g,  
        f"Attaque en {coord(destination)} : "  
        f"{values['power']:g} PF contre {values['defense']:g} PF."  
    )  
  
    # Dégâts au défenseur.  
    target["pf"] = values["defender_remaining"]  
  
    report["participants"].append({  
        "id": target["id"],  
        "owner": defender_owner,  
        "name": target["name"],  
        "role": "Défenseur",  
        "before": values["defense"],  
        "damage": values["defender_damage"],  
        "after": target["pf"],  
    })  
  
    if target["pf"] <= 0:  
        destroy(g, target, owner)  
    else:  
        log(  
            g,  
            f"{target['name']} #{target['id']} est affaibli : "  
            f"-{values['defender_damage']:g} PF, "  
            f"reste {target['pf']:g} PF."  
        )  

    kamikaze_attackers = [
        attacker
        for attacker in attackers
        if attacker.get("kamikaze")
    ]
    if kamikaze_attackers:
        if target in g["entities"]:
            target["pf"] -= 2
            log(g, f"Kamikaze : -2 PF supplémentaires à {target['name']}.")
            if target["pf"] <= 0:
                destroy(g, target, owner)

        adjacent_targets = [
            entity
            for entity in list(g["entities"])
            if entity["owner"] != owner
            and entity["id"] != target_id
            and entity["kind"] in ("unit", "base", "building")
            and distance(tuple(entity["pos"]), destination) == 1
        ][:2]
        for adjacent in adjacent_targets:
            adjacent["pf"] -= 1
            log(g, f"Kamikaze : -1 PF à {adjacent['name']} en case adjacente.")
            if adjacent["pf"] <= 0:
                destroy(g, adjacent, owner)
  
    # Dégâts aux attaquants.  
    for attacker in attackers:  
        before = float(attacker["pf"])  
        damage = float(applied_losses[attacker["id"]])  
  
        attacker["pf"] = before - damage  
        attacker["acted"] = True  
  
        report["participants"].append({  
            "id": attacker["id"],  
            "owner": attacker["owner"],  
            "name": attacker["name"],  
            "role": "Attaquant",  
            "before": before,  
            "damage": damage,  
            "after": attacker["pf"],  
        })  
  
        log(  
            g,  
            f"{attacker['name']} #{attacker['id']} : "  
            f"-{damage:g} PF, reste {attacker['pf']:g} PF."  
        )  
  
        if attacker["pf"] <= 0:  
            destroy(g, attacker, defender_owner)  
    if values["winnable"]:  
        # Le défenseur a été retiré par destroy().  
        # L'attaquant choisi, dont la survie a été validée,  
        # prend exactement son ancienne position.  
        occupier = entity(g, occupier_id)  
        occupier["pos"] = list(destination)  
        occupier["acted"] = True  
  
        collect_coins(  
            g,  
            owner,  
            routes[occupier_id][1:],  
        )  
  
        log(  
            g,  
            f"{occupier['name']} #{occupier_id} "  
            f"prend la place du défenseur en {coord(destination)}."  
        )  
    else:  
        log(  
            g,  
            "Attaque sacrificielle : les attaquants sont détruits. "  
            "Le défenseur affaibli conserve sa case."  
        )  
        
  
    g["_combat_report"] = report  
  
    # Change de joueur ou démarre le tour suivant.  
    # Le nouveau main() garde désormais le plateau visible.  
    next_activation(g)  

# ============================================================
# PLANIFICATIONS PRIVÉES
# ============================================================

def ensure_draft(bundle):
    g = bundle["game"]
    if (
        g["phase"] == "build"
        and g["winner"] is None
        and bundle["draft"] is None
    ):
        bundle["draft"] = copy.deepcopy(g)
        bundle["draft"]["curtain"] = False


def draft_action(bundle, fn, *args):
    g = bundle["game"]
    require_phase(g, "build")
    if g["curtain"]:
        raise ValueError("Confirme d'abord que tu es prêt.")

    ensure_draft(bundle)
    draft = bundle["draft"]
    draft["remaining"] = g["remaining"]
    draft["tick"] = g["tick"]
    draft["active"] = g["active"]
    fn(draft, g["active"], *args)


def game_action(bundle, fn, *args):
    if bundle["game"]["curtain"]:
        raise ValueError("Confirme d'abord que tu es prêt.")
    fn(bundle["game"], *args)


def open_curtain(bundle):
    bundle["game"]["curtain"] = True

def restart_production_plans(bundle):  
    """Annule les deux productions privées du tour courant."""  
    g = bundle["game"]  
    require_phase(g, "build")  
  
    # La partie publique est encore celle d'avant les productions :  
    # les dépenses et créations privées sont donc annulées  
    # simplement en supprimant les brouillons.  
    bundle["draft"] = None  
    bundle["committed"] = None  
  
    g["ready"] = []  
    g["active"] = g["first"]  
    g["curtain"] = False  
  
    log(  
        g,  
        "Les deux planifications de production ont été annulées "  
        "pour recommencer ce tour sans collision."  
    )  

class PlanningCollision(ValueError):  
    pass  
  
  
def production_conflicts(bundle):  
    """Conflits du second joueur avec la production prioritaire."""  
    g = bundle["game"]  
    first_draft = bundle.get("committed")  
    second_draft = bundle.get("draft")  
  
    if (  
        g["phase"] != "build"  
        or not g["ready"]  
        or first_draft is None  
        or second_draft is None  
    ):  
        return {}  
  
    first_owner = g["ready"][0]  
    second_owner = g["active"]  
  
    occupied = {  
        tuple(e["pos"])  
        for e in first_draft["entities"]  
        if e["owner"] == first_owner  
    }  
  
    return {  
        tuple(e["pos"]): e["id"]  
        for e in second_draft["entities"]  
        if (  
            e["owner"] == second_owner  
            and tuple(e["pos"]) in occupied  
        )  
    }  
  
  
def repair_slots(bundle, unit_id):  
    """Destinations autorisées pour une recrue en conflit."""  
    g = bundle["game"]  
    draft = bundle["draft"]  
    unit = entity(draft, unit_id)  
  
    if (  
        unit["kind"] != "unit"  
        or unit_id not in production_conflicts(bundle).values()  
    ):  
        return []  
  
    public_ids = {e["id"] for e in g["entities"]}  
  
    if unit_id in public_ids:  
        return []  
  
    producers = [  
        e for e in draft["entities"]  
        if (  
            e["owner"] == g["active"]  
            and e["kind"] == "building"  
            and e["wait"] == 0  
            and unit["name"] in faction_of(g, e["owner"])["buildings"]  
                .get(e["name"], {}).get("units", [])  
        )  
    ]  
  
    if "producer_id" in unit:  
        producers = [  
            e for e in producers  
            if e["id"] == unit["producer_id"]  
        ]  
    else:  
        # Compatibilité avec les recrues déjà créées avant  
        # ce correctif : leur origine n'était pas enregistrée.  
        producers = [  
            e for e in producers  
            if e["used"] and distance(e["pos"], unit["pos"]) == 1  
        ]  
  
    first_owner = g["ready"][0]  
    reserved = {  
        tuple(e["pos"])  
        for e in bundle["committed"]["entities"]  
        if e["owner"] == first_owner  
    }  
  
    return sorted({  
        pos  
        for producer in producers  
        for pos in recruitment_slots(draft, producer)  
        if pos not in reserved  
    })  
  
  
def relocate_conflicting_recruit(bundle, unit_id, destination):  
    g = bundle["game"]  
    require_phase(g, "build")  
    destination = require_position(destination)  
  
    if destination not in repair_slots(bundle, unit_id):  
        raise ValueError(  
                "Choisis une case adjacente au bâtiment producteur, "  
                "libre et située hors des montagnes et de la mer."  
        )  
  
    unit = entity(bundle["draft"], unit_id)  
    previous = tuple(unit["pos"])  
    unit["pos"] = list(destination)  
  
    log(  
        bundle["draft"],  
        f"{unit['name']} #{unit_id} replacé de "  
        f"{coord(previous)} vers {coord(destination)} "  
        "après un conflit de production, sans coût supplémentaire."  
    )  

def commit_plan(bundle):
    g = bundle["game"]
    require_phase(g, "build")
    if g["curtain"]:
        raise ValueError("Confirme d'abord que tu es prêt.")

    ensure_draft(bundle)
    draft = bundle["draft"]
    owner = g["active"]

    if not g["ready"]:
        bundle["committed"] = copy.deepcopy(draft)
        bundle["draft"] = None
        g["ready"] = [owner]
        g["active"] = 1 - owner
        g["curtain"] = False
        g["_ui_message"] = (
            f"Production des {faction_of(g, owner)['name']} validée. "
            f"Au tour des {faction_of(g, g['active'])['name']} de planifier."
        )
        return

    first_owner = g["ready"][0]
    first_draft = bundle["committed"]
    if first_draft is None or first_owner == owner:
        raise ValueError("Planifications incohérentes.")

    first_entities = [
        copy.deepcopy(e)
        for e in first_draft["entities"]
        if e["owner"] == first_owner
    ]
    second_entities = [
        copy.deepcopy(e)
        for e in draft["entities"]
        if e["owner"] == owner
    ]

    used_ids = {e["id"] for e in first_entities}
    next_id = max(
        g["next_id"], first_draft["next_id"], draft["next_id"]
    )

    for e in second_entities:
        if e["id"] in used_ids:
            while next_id in used_ids:
                next_id += 1
            e["id"] = next_id
            next_id += 1
        used_ids.add(e["id"])

    merged = first_entities + second_entities

    if not stacking_valid(g, merged):    
        raise PlanningCollision(  
            "Impossible de poser une unité sur cette case : "  
            "elle est déjà occupée par la production du premier "  
            "joueur du tour, qui est prioritaire. "  
            "Clique sur une case gris foncé, puis sur une case "  
            "verte pour replacer ta recrue gratuitement."  
        )  
    
    public_log_size = len(g["log"])
    g["log"].extend(first_draft["log"][public_log_size:])
    g["log"].extend(draft["log"][public_log_size:])

    g["entities"] = merged
    g["next_id"] = max(next_id, max(used_ids, default=0) + 1)
    g["players"][first_owner] = copy.deepcopy(
        first_draft["players"][first_owner]
    )
    g["players"][owner] = copy.deepcopy(draft["players"][owner])

    g["phase"] = "move"
    g["active"] = g["first"]
    g["ready"] = []
    g["passed"] = []
    g["curtain"] = False
    bundle["draft"] = None
    bundle["committed"] = None

    log(g, "Les deux productions sont révélées.")
    g["_ui_message"] = "Les deux productions sont validées : phase de manœuvres."
    next_activation(g, switch=False)


# ============================================================
# TRANSACTIONS ET ÉTAT DE L'INTERFACE
# ============================================================

def init_ui():  
    bundle = st.session_state.get("bundle")  
  
    if "bundle" in st.session_state and (  
        not isinstance(bundle, dict)  
        or not isinstance(bundle.get("game"), dict)  
    ):  
        reset_session()  
        st.session_state.ui_message = (  
            "La partie précédente était invalide. "  
            "Commence une nouvelle partie."  
        )  
        st.rerun()  
    st.session_state.setdefault("ui_selected_id", None)  
    st.session_state.setdefault("ui_attacker_ids", [])  
    st.session_state.setdefault("ui_target_id", None)  
    st.session_state.setdefault("ui_combat_report", None)  
    st.session_state.setdefault("ui_revision", 0)  
    st.session_state.setdefault("ui_last_event", None)  
    st.session_state.setdefault("ui_board_key", uuid.uuid4().hex)  
    st.session_state.setdefault("ui_plan_accelerated", False)  
    st.session_state.setdefault("ui_pending_move", None)  
    st.session_state.setdefault("ui_attack_confirmation", None)  
  
    # Placement interactif pendant la planification.  
    st.session_state.setdefault("ui_plan_mode", None)  
    st.session_state.setdefault("ui_plan_name", None)  
    st.session_state.setdefault("ui_plan_positions", [])  
    st.session_state.setdefault("ui_faction_view", None)  
  
  
def clear_placement():  
    st.session_state.ui_plan_mode = None  
    st.session_state.ui_plan_name = None  
    st.session_state.ui_plan_positions = []  


def open_faction_dossier(faction_name):
    st.session_state.ui_faction_view = faction_name
    st.rerun()


def close_faction_dossier():
    st.session_state.ui_faction_view = None
    st.rerun()
  
  
def bump_ui(clear_selection=False):  
    st.session_state.ui_revision += 1  
  
    if clear_selection:  
        st.session_state.ui_selected_id = None  
        st.session_state.ui_attacker_ids = []  
        st.session_state.ui_target_id = None  
        st.session_state.ui_pending_move = None  
        st.session_state.ui_attack_confirmation = None  
        clear_placement()  

def reset_session(bundle=None):
    st.session_state.clear()
    init_ui()
    if bundle is not None:
        st.session_state.bundle = bundle


def perform(fn, *args):
    """Une action n'est publiée que si elle réussit complètement."""
    current = st.session_state.get("bundle")

    if not isinstance(current, dict) or not isinstance(current.get("game"), dict):
        st.session_state.ui_message = "Aucune partie active. Reviens à l'accueil et commence une partie."
        bump_ui(clear_selection=True)
        st.rerun()

    tick(current["game"])

    if current["game"]["winner"] is not None:
        bump_ui(clear_selection=True)
        st.rerun()

    candidate = copy.deepcopy(current)

    try:
        fn(candidate, *args)
    except ValueError as exc:
        st.session_state.ui_message = str(exc)
        bump_ui()
        st.rerun()
    except (KeyError, TypeError, IndexError) as exc:
        st.session_state.ui_message = f"Action impossible dans l'état actuel : {exc}"
        bump_ui()
        st.rerun()

    report = candidate["game"].pop("_combat_report", None)
    ui_message = candidate["game"].pop("_ui_message", None)

    if report is not None:
        st.session_state.ui_combat_report = report

    if ui_message is not None:
        st.session_state.ui_message = ui_message

    st.session_state.bundle = candidate
    bump_ui(clear_selection=True)
    st.rerun()

def recruitment_batch(g, owner, name):  
    batch = UNITS[name]["batch"]  
  
    if faction_id(g, owner) == EXILES and name == "Tigre des forêts":  
        if "Meute de tigres" in g["players"][owner].get("upgrades", []):  
            batch = 2  
  
    return batch  

def recruitment_gold_cost(view, owner, name, positions):  
    # Cas spécial : Meute de tigres  
    if faction_id(view, owner) == EXILES and name == "Tigre des forêts":  
        if "Meute de tigres" in view["players"][owner].get("upgrades", []):  
            return 350  
  
    data = UNITS[name]  
    batch = recruitment_batch(view, owner, name)  
  
    per_unit, remainder = divmod(data["cost"], batch)  
    return sum(  
        exile_gold_cost(  
            view, owner,  
            pos,  
            per_unit + (1 if index < remainder else 0),  
        )  
        for index, pos in enumerate(positions)  
    )  

def render_combat_report():
    report = st.session_state.get("ui_combat_report")

    if not report:
        return

    st.subheader(
        f"Bilan du combat — tour {report['turn']} "
        f"— {report['position']}"
    )

    bonus = report.get("bonus", 0.0)
    bonus_text = f" + {bonus:g} PF de bonus" if bonus else ""

    st.caption(
        f"Attaque : {report['power']:g} PF{bonus_text} · "
        f"Défense : {report['defense']:g} PF"
    )
    for participant in report["participants"]:
        color = (
            "#15803d"
            if participant["owner"] == 0
            else "#2563eb"
        )

        name = escape(participant["name"])
        faction = escape(
            faction_of(current_game(), participant["owner"])["name"]
        )

        outcome = (
            "Détruit"
            if participant["after"] == 0
            else f"Survit avec {participant['after']:g} PF"
        )

        if participant["id"] == report["occupier_id"]:
            outcome += " — occupe la case conquise"

        st.markdown(
            f"""
            <div style="
                border-left: 5px solid {color};
                padding: 10px 14px;
                margin-bottom: 8px;
                background: {color}12;
            ">
                <strong style="color:{color}">
                    {participant['role']} — {name}
                    #{participant['id']} — {faction}
                </strong><br>
                {participant['before']:g} PF
                → <strong style="color:{color}">
                    −{participant['damage']:g} PF
                </strong>
                → {participant['after']:g} PF<br>
                {outcome}
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("Fermer le bilan", key="dismiss_combat_report"):
        st.session_state.ui_combat_report = None
        st.rerun()

def selected_entity(view):
    eid = st.session_state.get("ui_selected_id")
    return next(
        (e for e in view["entities"] if e["id"] == eid),
        None,
    )


def select_entity_from_sidebar(eid, kind, phase):
    st.session_state.ui_selected_id = eid
    st.session_state.ui_target_id = None
    st.session_state.ui_pending_move = None
    st.session_state.ui_attack_confirmation = None

    if phase == "move" and kind == "unit":
        st.session_state.ui_attacker_ids = [eid]
    elif phase == "build" and kind in ("base", "building"):
        clear_placement()
    else:
        st.session_state.ui_attacker_ids = []

    bump_ui()
    st.rerun()


# ============================================================
# VALIDATION ET CHARGEMENT DES SAUVEGARDES
# ============================================================

def require(condition, message):
    if not condition:
        raise ValueError(message)


def is_int(value, minimum=0):
    return type(value) is int and value >= minimum


def is_number(value, minimum=0):
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and value >= minimum
    )


def validate_cell_key(value):
    require(isinstance(value, str), "Coordonnée invalide.")
    parts = value.split(",")
    require(len(parts) == 2, "Coordonnée invalide.")
    try:
        pos = tuple(int(part) for part in parts)
    except ValueError:
        raise ValueError("Coordonnée invalide.") from None
    require(
        pos in CELL_SET and key(pos) == value,
        "Coordonnée hors plateau.",
    )


def validate_game(g):
    require(isinstance(g, dict), "Partie invalide.")
    fields = {
        "version", "turn", "first", "active", "phase",
        "ready", "passed", "players", "entities", "next_id",
        "terrain", "resources", "coins", "log", "target",
        "remaining", "tick", "winner", "curtain",
    }
    require(fields <= set(g), "Champs de partie manquants.")
    require(type(g["version"]) is int and g["version"] == 1,
            "Version de moteur incompatible.")
    require(is_int(g["turn"], 1), "Tour invalide.")
    require(is_int(g["next_id"], 1), "Compteur d'identifiants invalide.")

    for field in ("first", "active"):
        require(
            type(g[field]) is int and g[field] in (0, 1),
            "Joueur invalide.",
        )

    require(g["phase"] in ("build", "move"), "Phase invalide.")
    require(type(g["curtain"]) is bool, "Écran de passage invalide.")
    require(
        g["winner"] is None
        or (
            type(g["winner"]) is int
            and g["winner"] in (-1, 0, 1)
        ),
        "Résultat invalide.",
    )
    require(is_int(g["target"]), "Seuil de victoire invalide.")
    require(
        g.get("victory_mode") in (None, *VICTORY_MODES),
        "Condition de victoire invalide.",
    )
    factions = g.get("factions", [DEFERLANTS, EXILES])
    require(
        isinstance(factions, list)
        and len(factions) == 2
        and all(type(f) is int and f in FACTIONS for f in factions)
        and factions[0] != factions[1],
        "Factions invalides.",
    )
    require(is_number(g["remaining"]), "Temps restant invalide.")
    require(is_number(g["tick"]), "Horodatage invalide.")

    for field in ("ready", "passed"):
        values = g[field]
        require(isinstance(values, list), "Liste de joueurs invalide.")
        require(
            all(type(v) is int and v in (0, 1) for v in values),
            "Liste de joueurs invalide.",
        )
        require(len(values) == len(set(values)), "Joueur dupliqué.")

    require(
        isinstance(g["players"], list) and len(g["players"]) == 2,
        "Il faut deux joueurs.",
    )
    for seat, player in enumerate(g["players"]):
        require(isinstance(player, dict), "Joueur invalide.")
        require(
            {"gold", "mana", "pv", "bases", "age", "units_built"} <= set(player),
            "Données de joueur manquantes.",
        )
        for field in ("gold", "mana", "bases", "age"):
            require(is_int(player[field]), "Ressource ou score invalide.")
        require(player["age"] in (1, 2, 3), "Âge invalide.")
        require(isinstance(player["units_built"], dict), "Compteur d'unités invalide.")
        require(
            all(
                name in UNITS
                and is_int(count, 1)
                and count <= UNITS[name]["limit"]
                for name, count in player["units_built"].items()
            ),
            "Compteur d'unités invalide.",
        )
        require(isinstance(player["upgrades"], list), "Améliorations invalides.")
        require(
            len(player["upgrades"]) == len(set(player["upgrades"]))
            and all(
                name in UPGRADES
                and UPGRADES[name]["owner"]
                == faction_id(g, seat)
                for name in player["upgrades"]
            ),
            "Améliorations invalides.",
        )
        require(is_number(player["pv"]), "Score invalide.")

    require(
        isinstance(g["log"], list)
        and all(isinstance(line, str) for line in g["log"]),
        "Journal invalide.",
    )

    for field in ("terrain", "resources", "coins"):
        require(isinstance(g[field], dict), "Carte invalide.")
        for cell_key in g[field]:
            validate_cell_key(cell_key)

    require(
        all(t in ("plain", "forest", "mountain", "sea") 
            for t in g["terrain"].values()),
        "Terrain inconnu.",
    )

    for cell_key, resource in g["resources"].items():
        require(
            isinstance(resource, list)
            and len(resource) == 2
            and resource[0] in ("gold", "mana")
            and is_int(resource[1], 1),
            "Ressource invalide.",
        )
        require(
            g["terrain"].get(cell_key, "plain") == "plain",
            "Une ressource doit être sur une plaine.",
        )

    require(
        all(is_int(v, 1) for v in g["coins"].values()),
        "Pièces d'or invalides.",
    )
    require(
        isinstance(g["entities"], list)
        and len(g["entities"]) <= len(CELLS),
        "Liste de pièces invalide.",
    )

    ids, positions = set(), set()
    entity_fields = {
        "id", "owner", "name", "kind", "pos", "pf", "max_pf",
        "wait", "acted", "used",
    }

    for e in g["entities"]:
        require(isinstance(e, dict), "Pièce invalide.")
        require(entity_fields <= set(e), "Pièce incomplète.")
        require(is_int(e["id"], 1), "Identifiant invalide.")
        require(e["id"] not in ids, "Identifiant dupliqué.")
        require(
            type(e["owner"]) is int and e["owner"] in (0, 1),
            "Propriétaire invalide.",
        )
        require(valid_position(e["pos"]), "Position invalide.")
        pos = tuple(e["pos"])
        # Les unités peuvent s'arrêter sur une montagne (portée +1) ;
        # seules les unités volantes peuvent survoler la mer.
        require(
            terrain(g, pos) != "sea" or (e.get("kind") == "unit" and is_flying(e)),
            "Une pièce est placée dans la mer.",
        )
        require(
            e.get("kind") == "unit" or e.get("hero") or terrain(g, pos) != "mountain",
            "Un bâtiment est placé sur une montagne.",
        )  
        ids.add(e["id"])
        positions.add(pos)

        require(
            isinstance(e["name"], str)
            and e["kind"] in ("unit", "base", "building"),
            "Type de pièce invalide.",
        )

        faction = faction_of(g, e["owner"])
        if e["kind"] == "base":
            require(e["name"] in faction_base_names(faction), "Base incorrecte.")
            initial_pf = base_initial_pf(g, e)
        elif e["kind"] == "building":
            require(e["name"] in faction["buildings"], "Bâtiment incorrect.")
            initial_pf = faction["buildings"][e["name"]]["pf"]
        else:
            allowed = {
                name
                for b in faction["buildings"].values()
                for name in b["units"]
            } | set(faction.get("extra_units", []))
            # Unités issues d'une mutation ou nommées individuellement.
            allowed |= {
                name
                for name, source in UNIT_ENTITY_SOURCES.items()
                if source in allowed
            }
            require(e["name"] in allowed, "Unité incorrecte.")
            initial_pf = UNITS[e["name"]]["pf"]

        # Les améliorations de PF s'ajoutent aux PF initiaux.
        max_bonus = (
            max_upgrade_pf_bonus(e["name"]) + float(e.get("boost", 0))
            if e["kind"] == "unit"
            else 0.0
        )
        require(
            is_number(e["max_pf"])
            and initial_pf <= e["max_pf"] <= initial_pf + max_bonus,
            "PF initiaux invalides.",
        )
        require(
            is_number(e["pf"])
            and 0 < e["pf"] <= e["max_pf"]
            and float(e["pf"] * 2).is_integer(),
            "PF invalides.",
        )
        require(is_int(e["wait"]) and e["wait"] <= 2, "Attente invalide.")
        require(
            type(e["acted"]) is bool and type(e["used"]) is bool,
            "Disponibilité invalide.",
        )
        # Les héros vagabonds sont des bases mobiles : ils vont sur les ressources.
        if e["kind"] != "unit" and not e.get("hero"):
            require(terrain(g, pos) != "mountain", "Construction en montagne.")
            require(key(pos) not in g["resources"], "Construction sur ressource.")

    require(
        stacking_valid(g, g["entities"]),
        "Deux pièces occupent la même case.",
    )
    require(g["next_id"] > max(ids, default=0), "Compteur incohérent.")

    for owner in (0, 1):
        faction = faction_of(g, owner)
        limits = {
            name: data["limit"]
            for name, data in faction["buildings"].items()
        }
        for building in faction["buildings"].values():
            for name in building["units"]:
                limits[name] = UNITS[name]["limit"]
        for name in faction.get("extra_units", []):
            limits[name] = UNITS[name]["limit"]

        for name, limit in limits.items():
            count = sum(
                e["owner"] == owner and e["name"] == name
                for e in g["entities"]
            )
            require(count <= limit, "Limite de pièces dépassée.")


def validate_private_state(private, public, owner):
    validate_game(private)
    require(
        private["phase"] == "build" and private["active"] == owner,
        "Brouillon incompatible.",
    )

    for field in ("turn", "first", "target", "terrain", "resources", "coins"):
        require(private[field] == public[field], "Brouillon incompatible.")
    require(
        private.get("victory_mode") == public.get("victory_mode")
        and private.get("factions") == public.get("factions"),
        "Brouillon incompatible.",
    )

    require(
        private["log"][:len(public["log"])] == public["log"],
        "Journal privé incohérent.",
    )

    enemy = 1 - owner
    require(
        private["players"][enemy] == public["players"][enemy],
        "Le brouillon modifie l'adversaire.",
    )
    require(
        [e for e in private["entities"] if e["owner"] == enemy]
        == [e for e in public["entities"] if e["owner"] == enemy],
        "Le brouillon modifie les pièces adverses.",
    )

    for field in ("pv", "bases"):
        require(
            private["players"][owner][field]
            == public["players"][owner][field],
            "Le brouillon modifie les scores.",
        )
    require(
        public["players"][owner]["age"]
        <= private["players"][owner]["age"]
        <= public["players"][owner]["age"] + 1,
        "Le brouillon change l'âge de façon invalide.",
    )
    for field in ("gold", "mana"):
        require(
            private["players"][owner][field]
            <= public["players"][owner][field],
            "Le brouillon crée des ressources.",
        )
    for name, count in private["players"][owner]["units_built"].items():
        require(
            count >= public["players"][owner]["units_built"].get(name, 0),
            "Le brouillon diminue le compteur d'unités.",
        )
    require(
        set(private["players"][owner]["upgrades"])
        >= set(public["players"][owner]["upgrades"]),
        "Le brouillon retire une amélioration.",
    )

    private_by_id = {e["id"]: e for e in private["entities"]}
    for old in public["entities"]:
        if old["owner"] != owner:
            continue
        current = private_by_id.get(old["id"])
        require(current is not None, "Pièce publique manquante.")
        for field in old:
            if field != "used":
                require(
                    current.get(field) == old[field],
                    "Le brouillon altère une pièce publique.",
                )
        require(
            not old["used"] or current["used"],
            "Le brouillon réactive une pièce.",
        )

    public_ids = {e["id"] for e in public["entities"]}
    for e in private["entities"]:
        if e["id"] not in public_ids:
            require(  
                e["owner"] == owner  
                and e["id"] >= public["next_id"],
                "Création privée invalide.",  
            )  

def validate_bundle(bundle):
    require(isinstance(bundle, dict), "Sauvegarde invalide.")
    require(
        type(bundle.get("save_version")) is int
        and bundle["save_version"] == SAVE_VERSION,
        "Version incompatible : une sauvegarde au format 2 est nécessaire.",
    )
    require(
        {"game", "draft", "committed"} <= set(bundle),
        "Sauvegarde incomplète.",
    )

    g = bundle["game"]
    validate_game(g)

    if g["phase"] == "move":
        require(
            bundle["draft"] is None and bundle["committed"] is None,
            "Brouillon inattendu.",
        )
        require(not g["ready"], "Planification incohérente.")
        if g["winner"] is None:
            require(
                len(g["passed"]) < 2
                and g["active"] not in g["passed"]
                and bool(available(g, g["active"])),
                "Joueur actif incohérent.",
            )
        return

    require(not g["passed"], "Planification incohérente.")
    require(len(g["ready"]) <= 1, "Trop de planifications.")

    if g["ready"]:
        require(
            g["ready"] == [g["first"]]
            and g["active"] == 1 - g["first"],
            "Ordre de planification incohérent.",
        )
        require(bundle["committed"] is not None, "Planification manquante.")
        validate_private_state(bundle["committed"], g, g["first"])
    else:
        require(g["active"] == g["first"], "Premier joueur incohérent.")
        require(bundle["committed"] is None, "Planification inattendue.")

    if bundle["draft"] is not None:
        validate_private_state(bundle["draft"], g, g["active"])


def load_bundle(uploaded):
    raw = uploaded.getvalue()
    require(len(raw) <= MAX_SAVE_BYTES, "Sauvegarde trop volumineuse.")
    bundle = json.loads(raw.decode("utf-8-sig"))
    for player in bundle.get("game", {}).get("players", []):
        player.setdefault("age", 1)
        player.setdefault("units_built", {})
        player.setdefault("upgrades", [])
    validate_bundle(bundle)
    bundle["game"]["tick"] = time.time()
    bundle["game"]["curtain"] = True
    return bundle


# ============================================================
# PLATEAU INTERACTIF
# ============================================================

def piece_status(e):  
    if e["wait"]:  
        return f"ATTENTE {e['wait']}"  
  
    if e["kind"] == "unit":  
        return "ACTIVÉE" if e["acted"] else "PRÊTE"  
  
    if e["used"]:  
        if e["kind"] == "base" and faction_id(current_game(), e["owner"]) == EXILES:  
            return "A CONSTRUIT — PEUT ENCORE CONSTRUIRE"  
  
        return "UTILISÉ"  
  
    return "PRÊT"  

def planning_slots(g, view):  
    source = selected_entity(view)  
    owner = g["active"]  
    mode = st.session_state.ui_plan_mode  
    name = st.session_state.ui_plan_name  
  
    if (  
        g["phase"] != "build"  
        or g["winner"] is not None  
        or g["curtain"]  
        or source is None  
        or source["owner"] != owner  
        or source["wait"]  
    ):  
        return []  
  
    if mode == "build":  
        faction = faction_of(view, owner)  
  
        if source["kind"] != "base":  
            return []  
  
        if faction_id(view, owner) == DEFERLANTS and source["used"]:  
            return []  
  
        if name not in [faction["base"], *faction["buildings"]]:  
            return []  
  
        if (  
            name != faction["base"]  
            and not building_is_available(view, owner, name)  
        ):  
            return []  
  
        return [  
            pos  
            for pos in CELLS  
            if (  
                at(view, pos) is None  
                and not blocked(view, pos)  
                and key(pos) not in view["resources"]  
                and (  
                    faction_id(view, owner) != DEFERLANTS  
                    or distance(source["pos"], pos) <= 4  
                )  
            )  
        ]  
  
    if mode == "recruit":  
        allowed = [  
            unit_name  
            for unit_name in faction_of(view, owner)["buildings"]  
                .get(source["name"], {})  
                .get("units", [])  
            if UNIT_AGES.get(unit_name, 1)
            <= view["players"][owner]["age"]
            and unit_requirement_met(view, owner, unit_name)
        ]

        if (
            source["kind"] != "building"
            or source["used"]
            or name not in allowed
            or production_blocked_until(view, source) is not None
        ):
            return []
  
        return recruitment_slots(view, source)  
  
    return []  
  
def start_placement(mode, name):  
    st.session_state.ui_plan_mode = mode  
    st.session_state.ui_plan_name = name  
    st.session_state.ui_plan_positions = []  
    st.session_state.ui_plan_accelerated = False  
  
    bump_ui()  

def handle_empty_move_click(g, pos):  
    """Prépare un déplacement après un clic sur une case vide."""  
    if g["phase"] != "move":  
        return  
  
    attackers = selected_attackers(g)  
  
    st.session_state.ui_pending_move = None  
    st.session_state.ui_attack_confirmation = None  
    st.session_state.ui_target_id = None  
  
    if len(attackers) != 1:  
        st.session_state.ui_message = (  
            "Sélectionne une seule unité pour la déplacer."  
        )  
        bump_ui()  
        st.rerun()  
        return  
  
    unit = attackers[0]  
    destinations, _ = move_preview(g, unit)  
  
    if pos not in destinations:  
        st.session_state.ui_message = (  
            "Cette destination n'est pas accessible."  
        )  
    else:  
        st.session_state.ui_pending_move = {  
            "unit_id": unit["id"],  
            "destination": list(pos),  
        }  
        st.session_state.ui_message = (  
            f"Déplacement vers {coord(pos)}."  
        )  
  
    bump_ui()  
    st.rerun()  

def board_event(event, g, view):  
    if not isinstance(event, dict):  
        return  
  
    event_id = event.get("event_id")  
  
    if not isinstance(event_id, str):  
        return  
  
    if event_id == st.session_state.ui_last_event:  
        return  
  
    st.session_state.ui_last_event = event_id  
  
    if g["winner"] is not None or g["curtain"]:  
        return  
  
    if event.get("type") != "cell_click":  
        return  
  
    try:  
        pos = require_position(event.get("pos"))  
    except ValueError:  
        return  
  
    clicked = at(view, pos)  
    # Traiter la destination avant les autres branches :  
    # elles ne doivent pas effacer le déplacement préparé.  
    if g["phase"] == "move" and clicked is None:  
        handle_empty_move_click(g, pos)  
        return  
    # Correction des collisions après la tentative de révélation.  
    if (  
        g["phase"] == "build"  
        and st.session_state.get("ui_collision_repair", False)  
    ):  
        bundle = st.session_state.bundle  
        conflicts = production_conflicts(bundle)  
  
        if conflicts:  
            if pos in conflicts:  
                st.session_state.ui_repair_unit_id = conflicts[pos]  
                st.session_state.ui_message = (  
                    "Recrue sélectionnée. Clique sur une case verte "  
                    "pour la replacer sans payer à nouveau."  
                )  
                bump_ui()  
                st.rerun()  
                return  
  
            unit_id = st.session_state.get("ui_repair_unit_id")  
  
            if unit_id is not None:  
                perform(  
                    relocate_conflicting_recruit,  
                    unit_id,  
                    pos,  
                )  
                return  
  
            st.session_state.ui_message = (  
                "Clique d'abord sur une case gris foncé."  
            )  
            bump_ui()  
            st.rerun()  
            return  
    # Un nouveau clic abandonne l'ancienne proposition de déplacement.  
    if g["phase"] == "move":  
        st.session_state.ui_pending_move = None  
        st.session_state.ui_attack_confirmation = None 
  
    # ========================================================  
    # PRODUCTION : sélection et placement provisoire  
    # ========================================================  
    if g["phase"] == "build":  
        if clicked is not None:  
            if (  
                clicked["owner"] != g["active"]  
                or (
                    clicked["kind"] not in ("base", "building")
                    and not (
                        clicked["kind"] == "unit"
                        and (
                            clicked["name"] in MUTATIONS
                            or clicked["name"] == WORKER
                        )
                    )
                )
            ):  
                st.session_state.ui_message = (  
                    "Sélectionne une base ou un bâtiment allié."  
                )  
            else:  
                old_id = st.session_state.ui_selected_id  
  
                st.session_state.ui_selected_id = (  
                    None  
                    if old_id == clicked["id"]  
                    else clicked["id"]  
                )  
  
                clear_placement()  

                if st.session_state.ui_selected_id is None:
                    st.session_state.ui_message = "Sélection annulée."
                else:
                    st.session_state.ui_message = (
                        f"{clicked['name']} #{clicked['id']} sélectionné "
                        f"en {coord(clicked['pos'])}."
                    )
  
            bump_ui()  
            st.rerun()  
            return  
  
        # La case est vide.  
        mode = st.session_state.ui_plan_mode  
        name = st.session_state.ui_plan_name  
  
        # Toujours initialiser positions, quel que soit le mode.  
        positions = [  
            tuple(p)  
            for p in st.session_state.ui_plan_positions  
        ]  
  
        placement_changed = False  
  
        if mode is None:  
            st.session_state.ui_message = (  
                "Sélectionne un bâtiment, puis une production."  
            )  
  
        elif pos not in planning_slots(g, view):  
            st.session_state.ui_message = (  
                "Cette case n'est pas disponible pour ce placement."  
            )  
  
        elif mode == "build":  
            # Une seule case pour un bâtiment.
            positions = [pos]
            placement_changed = True

        elif mode == "worker_move":
            # Une seule destination pour un ouvrier.
            positions = [pos]
            placement_changed = True

        elif mode == "recruit":    
            batch = recruitment_batch(view, g["active"], name)   
  
            if pos in positions:  
                positions.remove(pos)  
                placement_changed = True  
  
            elif len(positions) < batch:  
                positions.append(pos)  
                placement_changed = True  
  
            elif batch == 1:  
                positions = [pos]  
                placement_changed = True  
  
            else:  
                st.session_state.ui_message = (  
                    f"Les {batch} cases sont déjà choisies. "  
                    "Reclique sur une case pour la retirer."  
                )  
  
        if placement_changed:  
            st.session_state.ui_plan_positions = positions  
  
        bump_ui()  
        st.rerun()  
        return  
  
    # ========================================================  
    # MANŒUVRES : sélection des unités  
    # ========================================================  
    if clicked is not None and can_move(g, clicked):  
        ids = [  
            attacker["id"]  
            for attacker in selected_attackers(g)  
        ]  
  
        if clicked["id"] in ids:  
            ids.remove(clicked["id"])  
        else:  
            ids.append(clicked["id"])  
  
        st.session_state.ui_attacker_ids = ids  
        st.session_state.ui_selected_id = ids[-1] if ids else None  
        st.session_state.ui_target_id = None  

        st.session_state.ui_message = (
            f"{clicked['name']} #{clicked['id']} sélectionné."
            if clicked["id"] in ids
            else f"{clicked['name']} #{clicked['id']} retiré de la sélection."
        )
  
        bump_ui()  
        st.rerun()  
        return  
  
    attackers = selected_attackers(g)  
  
    # ========================================================  
    # MANŒUVRES : sélection d'une cible ennemie  
    # ========================================================  
    if clicked is not None and clicked["owner"] != g["active"]:  
        st.session_state.ui_target_id = clicked["id"]  
    
        # Le Mage utilise ses sorts, jamais un tir normal.  
        if (  
            len(attackers) == 1  
            and attackers[0]["name"] in MAGES  
        ):  
            mage = attackers[0]  
            _, spell_targets = attack_map_preview(g, [mage])  
    
            if tuple(clicked["pos"]) not in spell_targets:  
                st.session_state.ui_target_id = None  
                st.session_state.ui_message = (  
                    "Cette cible ne peut pas recevoir un sort : "  
                    "vérifie la portée de 4 cases, le type de cible "  
                    "et la disponibilité du Mage."  
                )  
            else:  
                st.session_state.ui_message = (  
                    f"{clicked['name']} présélectionné. "  
                    "Choisis le sort et confirme dans le menu "  
                    "« Sorts du Mage ». Tu peux y ajouter "  
                    "d'autres cibles."  
                )  
    
            bump_ui()  
            st.rerun()  
            return  
    
        try:  
            if (  
                len(attackers) == 1  
                and UNITS[attackers[0]["name"]]["range"] > 0  
            ):  
                ranged_attack_values(  
                    g, attackers[0], clicked  
                )  
  
                st.session_state.ui_message = (  
                    f"Tir possible sur {clicked['name']} "  
                    f"en {coord(clicked['pos'])}, sans riposte."  
                )  
            else:  
                prepare_attack(  
                    g,  
                    [attacker["id"] for attacker in attackers],  
                    clicked["id"],  
                )  
  
                st.session_state.ui_message = (  
                    f"Cible de corps à corps : "  
                    f"{clicked['name']} "  
                    f"en {coord(clicked['pos'])}."  
                )  
  
        except ValueError as exc:  
            st.session_state.ui_message = str(exc)  
  
        bump_ui()  
        st.rerun()  
        return  

def render_ranged_controls(g, attacker, target):  
    """Affiche uniquement les commandes d'une attaque à distance."""  
    st.markdown(f"### Tir sur {target['name']}")  
  
    try:  
        values = ranged_attack_values(g, attacker, target)  
  
    except ValueError as exc:  
        st.warning(str(exc))  
  
    else:  
        st.info(  
            f"Dégâts : {values['damage']:g} PF. "  
            f"La cible conservera {values['remaining']:g} PF. "  
            + ranged_riposte_text(g, attacker, target)    
        )  
  
        if st.button(  
            "🎯 Confirmer le tir",  
            type="primary",  
            key=(  
                f"shoot_{g['turn']}_{g['active']}_"  
                f"{attacker['id']}_{target['id']}"  
            ),  
        ):  
            perform(  
                game_action,  
                ranged_attack,  
                attacker["id"],  
                target["id"],  
            )  
  
    if st.button(  
        "Annuler la cible",  
        key="cancel_ranged_target",  
    ):  
        cancel_maneuver_confirmation()  
        st.rerun()  

def queue_board_click(pos, revision):  
    """Callback : mémorise le clic sans dessiner ni relancer la page."""  
    st.session_state.ui_queued_board_event = {  
        "type": "cell_click",  
        "pos": list(pos),  
        "event_id": uuid.uuid4().hex,  
    }  
  
  
def process_queued_board_event(g, view):  
    event = st.session_state.pop("ui_queued_board_event", None)  
  
    if event is not None:  
        board_event(event, g, view)  

def render_board_production_menu(  
    g,  
    view,  
    board_width,  
    board_height,  
    radius,  
    margin,  
):  
    source = selected_entity(view)  
  
    if (  
        g["phase"] != "build"  
        or g["winner"] is not None  
        or source is None  
        or source["owner"] != g["active"]
        or (
            source["kind"] not in ("base", "building")
            and source["name"] not in MUTATIONS
            and source["name"] != WORKER
        )
    ):
        return
    hex_width = math.sqrt(3) * radius
    q, r = source["pos"]  
  
    cell_left = margin + hex_width * (q + r / 2)  
    cell_top = margin + 1.5 * radius * r  
  
    panel_width = 390  
    panel_height = 460  
    gap = 12  
  
    # À droite de la pièce, ou à gauche si le bord est trop proche.  
    left = cell_left + hex_width + gap  
  
    if left + panel_width > board_width - margin:  
        left = cell_left - panel_width - gap  
  
    left = max(  
        margin,  
        min(left, board_width - panel_width - margin),  
    )  
  
    top = max(  
        margin,  
        min(cell_top, board_height - panel_height - margin),  
    )  
  
    st.markdown(  
        f"""  
        <style>  
        .st-key-lw_hex_board .st-key-lw_production_popup {{  
            position: absolute !important;  
            left: {left:.1f}px !important;  
            top: {top:.1f}px !important;  
  
            width: {panel_width}px !important;  
            min-width: {panel_width}px !important;  
            max-width: {panel_width}px !important;  
  
            height: {panel_height}px !important;  
            max-height: {panel_height}px !important;  
  
            z-index: 100 !important;  
            overflow: auto !important;  
            box-sizing: border-box !important;  
  
            padding: 14px !important;  
            margin: 0 !important;  
  
            background: var(--background-color, #ffffff) !important;  
            color: var(--text-color, #172033) !important;  
  
            border: 3px solid #dc2626 !important;  
            border-radius: 14px !important;  
            box-shadow: 0 10px 30px #00000055 !important;  
        }}  
  
        /* Les choix du menu sont présentés en liste verticale. */  
        .st-key-lw_production_popup  
        [data-testid="stHorizontalBlock"] {{  
            flex-direction: column !important;  
            gap: 8px !important;  
        }}  
  
        .st-key-lw_production_popup  
        [data-testid="stColumn"] {{  
            width: 100% !important;  
            min-width: 0 !important;  
            flex: 1 1 auto !important;  
        }}  
  
        .st-key-lw_production_popup button {{  
            white-space: normal !important;  
        }}  
        </style>  
        """,  
        unsafe_allow_html=True,  
    )  
  
    with st.container(key="lw_production_popup"):  
        st.markdown(f"### {source['name']}")  
        st.caption(  
            f"Case {coord(source['pos'])} · "  
            f"{source['pf']:g} PF"  
        )  
  
        if st.button(  
            "✕ Fermer le menu",  
            key="close_production_popup",  
        ):  
            bump_ui(clear_selection=True)  
            st.rerun()  
        render_build_controls(g, view, local=True, on_board=True)


def render_placement_confirmation(  
    g, view, board_width, board_height, radius, margin  
):  
    mode = st.session_state.ui_plan_mode  
    name = st.session_state.ui_plan_name  
    positions = [  
        tuple(pos)  
        for pos in st.session_state.ui_plan_positions  
    ]  
    source = selected_entity(view)  
  
    if (  
        g["phase"] != "build"  
        or g["winner"] is not None  
        or g["curtain"]  
        or mode not in ("build", "recruit")  
        or source is None  
        or not positions  
    ):  
        return  
  
    owner = g["active"]  
    faction = faction_of(g, owner)  
    
    accelerated = (  
        mode == "build"  
        and name != faction["base"]  
        and st.session_state.ui_plan_accelerated  
    )  
    
    expected = 1 if mode == "build" else recruitment_batch(view, owner, name)   
    
    cost, mana = placement_cost(  
        view,  
        owner,  
        mode,  
        name,  
        positions,  
        accelerated,  
    )  
    slots = set(planning_slots(g, view))  
    player = view["players"][owner]  
  
    affordable = (  
        player["gold"] >= cost  
        and player["mana"] >= mana  
    )  
  
    valid = (  
        len(positions) == expected  
        and len(set(positions)) == expected  
        and all(pos in slots for pos in positions)  
        and affordable  
    )  
  
    # Positionner les commandes près de la dernière case choisie.  
    q, r = positions[-1]  
    hex_width = math.sqrt(3) * radius  
    cell_left = margin + hex_width * (q + r / 2)  
    cell_top = margin + 1.5 * radius * r  
  
    panel_width = 170  
    panel_height = 150  
  
    left = cell_left + hex_width + 6  
  
    if left + panel_width > board_width - margin:  
        left = cell_left - panel_width - 6  
  
    left = max(  
        margin,  
        min(left, board_width - panel_width - margin),  
    )  
    top = max(  
        margin,  
        min(cell_top, board_height - panel_height - margin),  
    )  
  
    st.markdown(  
        f"""  
        <style>  
        .st-key-lw_hex_board .st-key-lw_placement_confirm {{  
            position: absolute !important;  
            left: {left:.1f}px !important;  
            top: {top:.1f}px !important;  
            width: {panel_width}px !important;  
            min-width: {panel_width}px !important;  
            max-width: {panel_width}px !important;  
            z-index: 120 !important;  
            padding: 8px !important;  
            margin: 0 !important;  
            background: #ffffff !important;  
            color: #172033 !important;  
            border: 2px solid #15803d !important;  
            border-radius: 12px !important;  
            box-shadow: 0 4px 14px #00000040 !important;  
        }}  
        </style>  
        """,  
        unsafe_allow_html=True,  
    )  
  
    with st.container(key="lw_placement_confirm"):  
        st.caption(  
            f"{len(positions)}/{expected} case(s) · "  
            f"{cost} or"  
            + (f" · {mana} mana" if mana else "")  
        )  
  
        if not affordable:  
            st.caption("Ressources insuffisantes.")  
  
        cancel_col = st.container()

        if True:
            # Plus de bouton ✓ : l'action part dès que le placement est complet.
            if valid and auto_confirm(
                "placement", mode, name, source["id"], positions, accelerated
            ):
                if mode == "build":
                    perform(  
                        draft_action,  
                        build,  
                        source["id"],  
                        name,  
                        positions[0],  
                        accelerated,  
                    )  
                else:  
                    perform(  
                        draft_action,  
                        recruit,  
                        source["id"],  
                        name,  
                        positions,  
                    )  
  
        with cancel_col:  
            if st.button(  
                "✕",  
                key="cancel_board_placement",  
                help="Annuler le placement",  
            ):  
                clear_placement()  
                bump_ui()  
                st.rerun()  


def queue_maneuver_confirmation(mode, payload, revision):  
    st.session_state.ui_queued_maneuver = {  
        "mode": mode,  
        "payload": copy.deepcopy(payload),  
        "revision": revision,  
    }  
  
  
def cancel_maneuver_confirmation():  
    st.session_state.pop("ui_queued_maneuver", None)  
    st.session_state.ui_pending_move = None  
    st.session_state.ui_attack_confirmation = None  
    st.session_state.ui_target_id = None  
    bump_ui()  
  
  
def process_queued_maneuver():  
    request = st.session_state.pop("ui_queued_maneuver", None)  
  
    if request is None:  
        return  
  
    if request["revision"] != st.session_state.ui_revision:  
        return  
  
    payload = request["payload"]  
  
    if request["mode"] == "move":  
        perform(  
            game_action,  
            move_unit,  
            payload["unit_id"],  
            payload["destination"],  
        )  
  
    elif request["mode"] == "attack":  
        perform(  
            game_action,  
            attack,  
            payload["attacker_ids"],  
            payload["target_id"],  
            payload["occupier_id"],  
            payload["losses"],  
        )  

def render_maneuver_confirmation(  
    g, board_width, board_height, radius, margin  
):  
    if (  
        g["phase"] != "move"  
        or g["winner"] is not None  
        or g["curtain"]  
    ):  
        return  
  
    pending_move = st.session_state.get("ui_pending_move")  
    pending_attack = st.session_state.get("ui_attack_confirmation")  
  
    mode = None  
    position = None  
    valid = False  
    description = ""  
  
    if pending_move:  
        unit = next(  
            (  
                e for e in g["entities"]  
                if e["id"] == pending_move["unit_id"]  
            ),  
            None,  
        )  
  
        if unit is None:  
            return  
  
        position = tuple(pending_move["destination"])  
        destinations, _ = move_preview(g, unit)  
  
        valid = position in destinations  
        mode = "move"  
        description = f"Déplacer vers {coord(position)}"  
  
    elif pending_attack:  
        target = next(  
            (  
                e for e in g["entities"]  
                if e["id"] == pending_attack["target_id"]  
            ),  
            None,  
        )  
  
        if target is None:  
            return  
  
        position = tuple(target["pos"])  
        valid = pending_attack["valid"]  
        mode = "attack"  
  
        description = (  
            "⚠️ Attaque sacrificielle"  
            if pending_attack["sacrificial"]  
            else "⚔️ Attaquer cette cible"  
        )  
  
    if mode is None:  
        return  
  
    # Position du petit panneau près de la destination/cible.  
    q, r = position  
    hex_width = math.sqrt(3) * radius  
    cell_left = margin + hex_width * (q + r / 2)  
    cell_top = margin + 1.5 * radius * r  
  
    panel_width = 185  
    panel_height = 150  
  
    left = cell_left + hex_width + 6  
  
    if left + panel_width > board_width - margin:  
        left = cell_left - panel_width - 6  
  
    left = max(  
        margin,  
        min(left, board_width - panel_width - margin),  
    )  
  
    top = max(  
        margin,  
        min(cell_top, board_height - panel_height - margin),  
    )  
  
    st.markdown(  
        f"""  
        <style>  
        .st-key-lw_hex_board .st-key-lw_action_confirm {{  
            position: absolute !important;  
            left: {left:.1f}px !important;  
            top: {top:.1f}px !important;  
  
            width: {panel_width}px !important;  
            min-width: {panel_width}px !important;  
            max-width: {panel_width}px !important;  
  
            z-index: 150 !important;  
            padding: 8px !important;  
            margin: 0 !important;  
  
            background: #ffffff !important;  
            color: #172033 !important;  
            border: 2px solid #15803d !important;  
            border-radius: 12px !important;  
            box-shadow: 0 4px 14px #00000040 !important;  
        }}  
        </style>  
        """,  
        unsafe_allow_html=True,  
    )  
  
    with st.container(key="lw_action_confirm"):  
        st.caption(description)  
  
        if not valid:  
            st.caption("Vérifie les paramètres de l'action.")  
  
        payload = (  
            pending_move  
            if mode == "move"  
            else pending_attack  
        )  
  
        confirm_col, cancel_col = st.columns(2)  
  
        with confirm_col:  
            st.button(  
                "✓",  
                key="confirm_maneuver_on_board",  
                type="primary",  
                disabled=not valid,  
                on_click=queue_maneuver_confirmation,  
                args=(  
                    mode,  
                    copy.deepcopy(payload),  
                    st.session_state.ui_revision,  
                ),  
            )  
  
        with cancel_col:  
            st.button(  
                "✕",  
                key="cancel_maneuver_on_board",  
                on_click=cancel_maneuver_confirmation,  
            )   
def flat_center(pos, radius, origin_x, origin_y):  
    q, r = pos  
  
    return (  
        origin_x + 1.5 * radius * q,  
        origin_y + math.sqrt(3) * radius * (r + q / 2),  
    )  


def render_board(g, view, readonly=False):  
    attackers = [] if readonly else selected_attackers(g)
    selected = selected_entity(view)
    moving = attackers[0] if len(attackers) == 1 else None

    destinations, routes = (
        move_preview(g, moving)
        if not readonly
        else ({}, {})
    )
    attack_zone, targets = (  
        attack_map_preview(g, attackers)  
        if g["phase"] == "move" and not readonly  
        else (set(), {})  
    )
    if g["phase"] == "build" and st.session_state.get("_lw_hero_targets"):
        # Cibles d'un héros vagabond sélectionné (attaque en production).
        targets = {tuple(int(v) for v in k.split(",")): d for k, d in st.session_state["_lw_hero_targets"].items()}
    if g["phase"] == "move" and st.session_state.get("_lw_spell_targets"):
        # Cibles alliées d'un sort (Dirigeable) : surlignées sur le plateau.
        targets = {tuple(int(v) for v in k.split(",")): d for k, d in st.session_state["_lw_spell_targets"].items()}
    if g["phase"] == "move" and st.session_state.get("_lw_siege_targets"):
        # Aperçu des cases touchées par un tir de siège.
        targets = {tuple(int(v) for v in k.split(",")): d for k, d in st.session_state["_lw_siege_targets"].items()}

    slots = (
        set(planning_slots(g, view))
        if g["phase"] == "build" and not readonly
        else set()
    )
    placements = {
        tuple(pos)
        for pos in st.session_state.ui_plan_positions
    }
    waypoint_view = st.session_state.get("_lw_waypoint_view")
    if waypoint_view and g["phase"] == "move" and not readonly:
        # Tracé case par case : cases suivantes possibles en vert, chemin en jaune.
        destinations = dict(waypoint_view["next"])
        placements = set(waypoint_view["path"])

    entities = []
    viewer_owner = g["active"] if not readonly else None  
    for piece in view["entities"]:  
        # Les unités invisibles restent affichées pour tout le monde (pas de
        # conflit de case) ; sans détection, l'ennemi ne peut toujours pas les viser.
        piece_data = dict(piece)
        piece_data["invisible"] = (
            piece["kind"] == "unit"
            and (is_hidden_unit(piece) or (
                piece["name"] == GRIFFON
                and owns_upgrade(view, piece["owner"], "Invisibilité griffons")
            ))
        )
        piece_data["pos"] = list(piece["pos"])
        piece_data["status"] = piece_status(piece)
        piece_data["dimmed"] = bool(piece.get("wait") or piece.get("acted") or piece.get("used"))
        piece_data["blocked"] = production_blocked_until(view, piece) is not None
        piece_data["stack"] = len(pieces_at(view, piece["pos"]))
        piece_data["faction"] = faction_id(view, piece["owner"])
        entities.append(piece_data)

    event = BOARD_COMPONENT(
        cells=[list(pos) for pos in CELLS],
        terrain=dict(view["terrain"]),
        resources=dict(view["resources"]),
        coins=dict(view.get("coins", {})),
        entities=entities,
        destinations={key(pos): cost for pos, cost in {**destinations, **{slot: 0 for slot in slots}}.items()},
        routes={key(pos): [list(step) for step in route] for pos, route in routes.items()},
        targets={key(pos): data for pos, data in targets.items()},
        attack_zone=[key(pos) for pos in sorted(attack_zone)], 
        placements=[key(pos) for pos in placements],
        selected_id=(selected["id"] if selected is not None else None),
        selected_ids=[a["id"] for a in attackers],
        readonly=readonly or g["curtain"],
        revision=st.session_state.ui_revision,
        turn=g["turn"],
        last_move=view.get("last_move"),
        ai_marks=st.session_state.get("_lw_ai_marks"),
        fx=st.session_state.get("_lw_fx"),
        banner=st.session_state.get("_lw_victory_banner"),
        cell_costs=st.session_state.get("_lw_cell_costs"),
        key=f"board_component_{st.session_state.ui_board_key}",
        default=None,
    )

    if event is not None:
        board_event(event, g, view)
# ============================================================
# COMMANDES DE PLANIFICATION
# ============================================================
@st.dialog("⛔ Passage d’âge impossible")  
def show_age_blocked(target_age, reasons):  
    st.error(  
        f"Tu ne peux pas encore passer à l’âge {target_age}."  
    )  
  
    for reason in reasons:  
        st.write(f"• {reason}")  
  
    st.info(  
        "Un bâtiment en cours de construction ne remplit pas "  
        "le prérequis. Il doit être terminé : ATTENTE = 0."  
    )  
  
    if st.button(  
        "Compris — revenir au plateau",  
        type="primary",  
        key="close_age_blocked_dialog",  
    ):  
        st.rerun()  

def render_build_controls(g, view, local=False, on_board=False):  
    if not local and g["ready"]:  
        with st.expander("🔧 Débloquer les productions"):  
            st.warning(  
                "Cette opération annule les constructions, "  
                "recrutements planifiés "
                "par les deux joueurs pendant ce tour. "  
                "Les dépenses correspondantes sont annulées. "  
                "Les tours précédents sont conservés."  
            )  
  
            if st.button(  
                "Recommencer les deux productions de ce tour",  
                key=f"restart_production_plans_{g['turn']}",  
            ):  
                perform(restart_production_plans)  
    # Hors du plateau : accès au placement et validation finale.  
    if not local:  
        st.caption(  
            "Clique sur une base ou un bâtiment pour préparer une "  
            "production. La validation finale se fait dans la barre "  
            "latérale."  
        )  

        pending = st.session_state.ui_plan_mode is not None  

        if pending:  
            name = st.session_state.ui_plan_name  
            positions = [  
                tuple(pos)  
                for pos in st.session_state.ui_plan_positions  
            ]  

            chosen = (  
                ", ".join(coord(pos) for pos in positions)  
                if positions  
                else "aucune"  
            )  

            st.info(  
                f"Placement en cours : {name} — "  
                f"Case(s) choisie(s) : {chosen}."  
            )  

            if st.button(  
                "✕ Annuler le placement",  
                key="cancel_pending_placement",  
            ):  
                clear_placement()  
                bump_ui()  
                st.rerun()  

        return  
  
    # Conserve ici toute la suite actuelle de ta fonction :  
    owner = g["active"]  
    faction = faction_of(view, owner)  
    source = selected_entity(view)  
    location = (  
        "board"  
        if on_board  
        else "sidebar"  
        if local  
        else "page"  
    )  
    prefix = f"plan_{location}_{g['turn']}_{owner}"  
    player = view["players"][owner]  
    current_age = player["age"]  
  
    st.markdown(f"#### Âge {current_age}")  
  
    if faction_id(view, owner) == EXILES:  
        st.caption(  
            "Côté adverse de la ligne noire A17-Y1 : construction ×3 en or "
            "+ 3 mana ; recrutement +50 % sur l'or."
        )  
  
    if current_age >= 3:  
        st.caption("Âge maximal atteint.")  
  
    else:  
        next_age = current_age + 1  
        age_cost = AGE_COSTS[next_age]  
        prerequisite = AGE_PREREQUISITES.get((faction_id(view, owner), next_age))  
  
        completed = (  
            prerequisite is None  
            or building_is_completed(view, owner, prerequisite)  
        )  
  
        pending_buildings = [  
            piece  
            for piece in view["entities"]  
            if (  
                piece["owner"] == owner  
                and piece["kind"] == "building"  
                and piece["name"] == prerequisite  
                and piece["wait"] > 0  
            )  
        ]  
  
        st.caption(  
            f"Passer à l’âge {next_age} : "  
            f"{age_cost['gold']} or"  
            + (  
                f" et {age_cost['mana']} mana"  
                if age_cost["mana"]  
                else ""  
            )  
        )  
  
        if prerequisite:  
            if completed:  
                st.success(  
                    f"✓ Prérequis terminé : {prerequisite}."  
                )  
  
            elif pending_buildings:  
                remaining_wait = min(  
                    piece["wait"]  
                    for piece in pending_buildings  
                )  
  
                st.warning(  
                    f"⏳ {prerequisite} en construction : "  
                    f"encore {remaining_wait} fin(s) de tour."  
                )  
  
            else:  
                st.warning(  
                    f"⛔ Bâtiment requis : {prerequisite}."  
                )  
  
        # Aucune action automatique :  
        # la tentative de passage d’âge nécessite un clic.  
        if st.button(  
            f"Passer à l’âge {next_age}",
            key=f"{prefix}_advance_age_{'ok' if age_advance_possible(view, owner, next_age) else 'ko'}_{next_age}",
        ):  
            reasons = []  
  
            if not completed:  
                if pending_buildings:  
                    remaining_wait = min(  
                        piece["wait"]  
                        for piece in pending_buildings  
                    )  
  
                    reasons.append(  
                        f"Le bâtiment « {prerequisite} » "  
                        f"doit être terminé. Encore "  
                        f"{remaining_wait} fin(s) de tour."  
                    )  
  
                else:  
                    reasons.append(  
                        f"Construis et termine "  
                        f"le bâtiment « {prerequisite} »."  
                    )  
  
            missing_gold = max(  
                0,  
                age_cost["gold"] - player["gold"],  
            )  
  
            missing_mana = max(  
                0,  
                age_cost["mana"] - player["mana"],  
            )  
  
            if missing_gold:  
                reasons.append(  
                    f"Il manque {missing_gold} or."  
                )  
  
            if missing_mana:  
                reasons.append(  
                    f"Il manque {missing_mana} mana."  
                )  
  
            if reasons:  
                show_age_blocked(next_age, reasons)  
  
            else:  
                perform(  
                    draft_action,  
                    advance_age,  
                    next_age,  
                )  
   
    if source is None:  
        st.info("Sélectionne une de tes bases ou un bâtiment producteur.")  
  
    elif source["owner"] != owner:  
        st.info("Sélectionne une pièce de ton peuple.")  
  
    elif source["kind"] == "unit":  
        st.write(f"**{describe(source)}**")
        render_mutation_button(view, source, prefix)
        render_worker_controls(view, source, prefix)
        st.info(
            "Les unités militaires se déplacent pendant la phase "  
            "de manœuvres. Sélectionne une base pour construire "  
            "ou un bâtiment pour recruter."  
        )  
  
    else:  
        st.write(f"**{describe(source)}**")

        if (
            source["kind"] == "base"
            and faction_id(view, owner) == DERNIERS_NES
        ):
            render_colony_controls(view, source, prefix)

        elif source["kind"] == "base" and faction_id(view, owner) == VAGABONDS:
            render_hero_controls(view, source, prefix)

        elif source["kind"] == "base":    
            adjacent = [  
                view["resources"][key(pos)]  
                for pos in neighbors(source["pos"])  
                if key(pos) in view["resources"]  
            ]  
  
            st.caption(  
                "Récolte automatique des ressources adjacentes : "
                + (  
                    ", ".join(  
                        f"{'Or' if kind == 'gold' else 'Mana'} ×{multiplier}"  
                        for kind, multiplier in adjacent  
                    )  
                    or "aucune"  
                )  
            )  
  
            st.markdown("#### Construire")  
  
            if source["wait"]:  
                st.info(  
                    f"Cette base est inactive pendant encore "  
                    f"{source['wait']} fin(s) de tour."  
                )  
  
            elif faction_id(view, owner) == DEFERLANTS and source["used"]:  
                st.info("Cet incubateur a déjà construit ce tour.")  
  
            else:  
                names = [
                    faction["base"],
                    *[
                        name
                        for name in faction["buildings"]
                        if building_is_available(view, owner, name)
                    ],
                ]
                # Toutes les factions : les choix les uns sous les autres, encadrés.
                columns = [st.container(border=True) for _ in names]
  
                for column, name in zip(columns, names):  
                    is_base = name == faction["base"]  
                    data = (  
                        {  
                            "cost": base_cost_for_age(view, owner),  
                            "pf": faction["base_pf"],  
                        }  
                        if is_base  
                        else faction["buildings"][name]  
                    )  
  
                    with column:  
                        st.write(f"**{name}**")  
                        st.caption(  
                            f"{data['cost']} or · {data['pf']:g} PF · "
                            + building_limit_text(view, owner, name)
                            + ("" if is_base else f" · ⚡ immédiat : {int(data['cost'] * 1.5)} or")
                        )    
  
                        # Deux façons de construire : normale, ou accélérée (+50 %).
                        limit_hit = building_limit_reached(view, owner, name)
                        # L'un sous l'autre, en pleine largeur : libellés lisibles dans le menu.
                        normal_col = fast_col = st.container()
                        with normal_col:
                            if st.button(
                                "🔨 Construire",
                                key=f"{prefix}_choose_build_{source['id']}_{name}",
                                disabled=limit_hit or not can_pay(view, owner, data["cost"], data.get("mana", 0)),
                                use_container_width=True,
                                type=build_button_type(name, False),
                            ):
                                start_build(name, False)
                        if not is_base:
                            with fast_col:
                                if st.button(
                                    "⚡ Immédiat",
                                    key=f"{prefix}_choose_fast_{source['id']}_{name}",
                                    disabled=limit_hit or not can_pay(view, owner, int(data["cost"] * 1.5), data.get("mana", 0)),
                                    use_container_width=True,
                                    help="Disponible immédiatement, pour +50 % du prix.",
                                    type=build_button_type(name, True),
                                ):
                                    start_build(name, True)
  
        elif source["kind"] == "building":  
            st.markdown("#### Recruter")  
            # --------------------------------------------------------  
            # AMÉLIORATIONS TECHNIQUES  
            # --------------------------------------------------------  
            tech_building = TECH_BUILDINGS.get(faction_id(view, owner))  
  
            if source["name"] == tech_building:  
                st.markdown("#### Améliorations")  
            
                purchased = [  
                    up  
                    for up in view["players"][owner].get("upgrades", [])  
                    if UPGRADES[up]["building"] == tech_building  
                ]  
                available = available_upgrades(view, owner)  
            
                if purchased:  
                    st.success("Améliorations déjà achetées : " + ", ".join(purchased))  
                else:  
                    st.info("Aucune amélioration achetée pour le moment.")  
            
                st.markdown("##### Améliorations disponibles")  
            
                if not available:  
                    st.caption("Aucune nouvelle amélioration disponible.")  
                else:  
                    for upgrade_name in available:  
                        data = UPGRADES[upgrade_name]  
                        affordable = (  
                            view["players"][owner]["gold"] >= data["cost"]  
                            and view["players"][owner]["mana"] >= data["mana"]  
                        )  
            
                        cols = st.columns([3, 1])  
                        with cols[0]:  
                            st.write(f"**{upgrade_name}**")  
                            st.caption(data["effect"])  
                            st.caption(  
                                f"{data['cost']} or"  
                                + (f" · {data['mana']} mana" if data["mana"] else "")  
                            )  
                        with cols[1]:  
                            if st.button(  
                                "Acheter",  
                                key=f"{prefix}_upgrade_{upgrade_name}",  
                                disabled=not affordable,  
                            ):  
                                perform(draft_action, purchase_upgrade, upgrade_name)  
  
            if source["wait"]:  
                st.info("Ce bâtiment n'est pas encore disponible.")  
  
            elif source["used"]:  
                st.info("Ce bâtiment a déjà recruté ce tour.")  
  
            else:  
                names = [
                    name
                    for name in faction["buildings"][source["name"]]["units"]
                    if UNIT_AGES.get(name, 1) <= view["players"][owner]["age"]
                    and unit_requirement_met(view, owner, name)
                ]
                blocked_until = production_blocked_until(view, source)
                if blocked_until is not None:
                    st.error(
                        f"⛔ Production bloquée par un Décimant "
                        f"jusqu'au tour {blocked_until} inclus."
                    )
                    names = []
                if not names:
                    st.info("Ce bâtiment ne produit pas encore d'unité.")
                columns = [st.container(border=True) for _ in names]
  
                for column, name in zip(columns, names):  
                    data = UNITS[name]  
                    built_count = view["players"][owner]["units_built"].get(name, 0)
                    remaining_count = max(0, unit_limit(view, owner, name) - built_count)
  
                    with column:  
                        st.write(f"**{name}**")  
                        batch = recruitment_batch(view, owner, name)  
                        recruit_cost = 350 if (faction_id(view, owner) == EXILES and name == "Tigre des forêts" and "Meute de tigres" in view["players"][owner].get("upgrades", [])) else data["cost"]  
                        
                        st.caption(  
                            f"{batch} unité(s) · "  
                            f"{recruit_cost} or · "  
                            f"{data['mana']} mana"  
                        )  
  
                        st.caption(  
                            f"{data['pf']} PF · "  
                            f"MVT {data['move']} · "  
                            f"Portée {data['range']}"  
                        )  
                        st.caption(
                            f"Construites : {built_count}/{data['limit']} · "
                            f"Disponibles : {remaining_count}"
                        )
  
                        if st.button(  
                            f"Recruter : {name}",  
                            key=f"{prefix}_choose_recruit_{source['id']}_{name}",  
                            disabled=(
                                remaining_count < recruitment_batch(view, owner, name)
                                or not can_pay(view, owner, recruit_cost, data["mana"])
                            ),
                            type=(  
                                "primary"  
                                if (  
                                    st.session_state.ui_plan_mode  
                                    == "recruit"  
                                    and st.session_state.ui_plan_name  
                                    == name  
                                )  
                                else "secondary"  
                            ),  
                        ):  
                            start_placement("recruit", name)
                            st.rerun()
            # --------------------------------------------------------  
    # Placement et confirmation  
    # --------------------------------------------------------  
    mode = st.session_state.ui_plan_mode  
    name = st.session_state.ui_plan_name  
    positions = [  
        tuple(pos)  
        for pos in st.session_state.ui_plan_positions  
    ]  
  
    # Aucun placement : ne pas calculer ni afficher de coût.  
    if mode not in ("build", "recruit") or name is None:  
        return  
  
    if source is None or source["owner"] != owner:  
        return  
  
    if mode == "build":  
        if (
            (source["kind"] != "base" and source["name"] != WORKER)
            or name not in [faction["base"], *faction["buildings"]]
        ):
            return    
    else:  
        allowed_units = (  
            faction["buildings"]  
            .get(source["name"], {})  
            .get("units", [])  
        )  
        worker_production = (
            source["kind"] == "base" and name == WORKER
        )
        if not worker_production and (
            source["kind"] != "building" or name not in allowed_units
        ):
            return    
  
    st.divider()  
    st.markdown(f"#### Placement : {name}")  
  
    slots = set(planning_slots(g, view))  
  
    if not slots:  
        st.warning("Aucune case disponible pour ce placement.")  
  
    accelerated = False  
  
    if mode == "build":  
        expected = 1  
  
        if name == faction["base"]:  
            st.caption("Disponible après 2 fins de tour.")  
        else:  
            accelerated = bool(st.session_state.ui_plan_accelerated)
            if accelerated:
                st.success("⚡ Construction accélérée : disponible immédiatement (+50 % du prix).")
            else:
                st.caption("Construction normale : disponible au tour suivant.")
            if st.button(
                "Repasser en construction normale" if accelerated else "⚡ Accélérer cette construction (+50 %)",
                key=f"{prefix}_toggle_fast_{source['id']}_{name}",
                use_container_width=True,
                type="secondary" if accelerated else "primary",
            ):
                st.session_state.ui_plan_accelerated = not accelerated
                bump_ui()
                st.rerun()  
  
        st.session_state.ui_plan_accelerated = accelerated  
        st.info("Clique sur une case verte du plateau.")  
  
    else:  
        expected = recruitment_batch(view, owner, name)  
  
        st.info(  
            f"Clique sur {expected} case(s) verte(s) "  
            "autour du bâtiment producteur. "  
            "Reclique sur une case pour la retirer."  
        )  
  
    # Calcul systématique AVANT tout affichage de cost ou mana.  
    cost, mana = placement_cost(  
        view,  
        owner,  
        mode,  
        name,  
        positions,  
        accelerated,  
    )  
  
    st.write(  
        f"**Coût à confirmer : {cost} or"  
        + (f" · {mana} mana" if mana else "")  
        + "**"  
    )  
  
    if not positions:  
        st.caption(  
            "Prix indicatif avant choix des cases ; "  
            "le malus territorial éventuel sera ajouté."  
        )  
  
    if faction_id(view, owner) == EXILES and positions:  
        penalized = [  
            coord(pos)  
            for pos in positions  
            if enemy_side_of_line(owner, pos)  
        ]  
  
        if penalized:  
            st.caption(  
                "Malus territorial de +50 % inclus pour : "  
                + ", ".join(penalized)  
            )  
  
    # Ces commandes concernent les DEUX factions.  
    st.write(  
        "**Cases choisies :** "  
        + (  
            ", ".join(coord(pos) for pos in positions)  
            if positions  
            else "aucune"  
        )  
    )  
  
    affordable = (  
        view["players"][owner]["gold"] >= cost  
        and view["players"][owner]["mana"] >= mana  
    )  
  
    if not affordable:  
        st.warning("Ressources insuffisantes.")  
  
    valid = (  
        len(positions) == expected  
        and len(set(positions)) == expected  
        and all(pos in slots for pos in positions)  
        and affordable  
    )  
  
    cancel_col = st.container()

    if True:
        # Plus de bouton de confirmation : l'action part dès que le placement est complet.
        if valid and auto_confirm(
            "placement", mode, name, source["id"], positions, accelerated
        ):
            if mode == "build":
                perform(  
                    draft_action,  
                    build,  
                    source["id"],  
                    name,  
                    positions[0],  
                    accelerated,  
                )  
            else:  
                perform(  
                    draft_action,  
                    recruit,  
                    source["id"],  
                    name,  
                    positions,  
                )  
  
    with cancel_col:  
        if st.button(  
            "✕ Annuler",  
            key=f"{prefix}_cancel_placement",  
        ):  
            clear_placement()  
            bump_ui()  
            st.rerun()  
# ============================================================
# COMMANDES DE MANŒUVRES
# ============================================================

def render_move_controls(g):  
    st.session_state.ui_attack_confirmation = None  
  
    owner = g["active"]  
    revision = st.session_state.ui_revision  
    prefix = f"move_{g['turn']}_{owner}_{revision}"  
  
    st.subheader("⚔️ Manœuvres")  
  
    st.caption(  
        "1. Sélectionne tes unités sur le plateau ou dans la liste. "  
        "2. Clique sur une cible ennemie. "  
        "3. Choisis les pertes et le survivant qui prendra sa case. "  
        "4. Confirme l'attaque."  
    )  
  
    eligible = available(g, owner)  
    eligible_by_id = {unit["id"]: unit for unit in eligible}  
  
    current_ids = [  
        unit["id"]  
        for unit in selected_attackers(g)  
    ]  
  
    chosen_ids = st.multiselect(  
        "Unités participant à la même attaque",  
        options=list(eligible_by_id),  
        default=current_ids,  
        format_func=lambda eid: describe(eligible_by_id[eid]),  
        key=f"{prefix}_group",  
        help=(  
            "Aucune limite de taille du groupe. "  
            "Chaque unité doit être encore activable "  
            "et pouvoir atteindre la même cible."  
        ),  
    )  
  
    if chosen_ids != current_ids:  
        st.session_state.ui_attacker_ids = list(chosen_ids)  
        st.session_state.ui_selected_id = (  
            chosen_ids[-1] if chosen_ids else None  
        )  
        st.session_state.ui_pending_move = None  
        st.session_state.ui_attack_confirmation = None  
        bump_ui()  
        st.rerun()  
  
    attackers = selected_attackers(g)  
    attacker_ids = [unit["id"] for unit in attackers]  
  
    if attackers:  
        power = sum(unit["pf"] for unit in attackers)  
  
        st.write(  
            f"**Groupe : {len(attackers)} unité(s) "  
            f"— {power:g} PF au total**"  
        )  
  
        if st.button(  
            "Effacer toute la sélection",  
            key=f"{prefix}_clear",  
        ):  
            bump_ui(clear_selection=True)  
            st.rerun()  
    else:  
        st.info("Sélectionne au moins une unité disponible.")  
  
    # --------------------------------------------------------  
    # Déplacement simple  
    # --------------------------------------------------------  

    if len(attackers) > 1:  
        st.caption(  
            "Le groupe effectue une attaque commune. "  
            "Pour un déplacement simple, sélectionne une seule unité."  
        )  
  
    # --------------------------------------------------------  
    # Cible commune  
    # --------------------------------------------------------  
    target = next(  
        (  
            piece  
            for piece in g["entities"]  
            if (  
                piece["id"] == st.session_state.ui_target_id  
                and piece["owner"] != owner  
            )  
        ),  
        None,  
    )  
  
    if attackers and target is None:  
        st.info(  
            "Clique maintenant sur une unité, un bâtiment "  
            "ou une base ennemie."  
        )  
    if (  
        target is not None  
        and len(attackers) == 1  
        and UNITS[attackers[0]["name"]]["range"] > 0  
        and not contact_melee(g, attackers[0], target)  
    ):  
        render_ranged_controls(g, attackers[0], target)    
        return  

    if attackers and target is not None:  
        st.divider()  
        st.markdown(f"### Cible : {target['name']}")  
        st.write(  
            f"**{coord(target['pos'])} — "  
            f"{target['pf']:g} PF de défense**"  
        )  
  
        if st.button(  
            "Ajouter toutes les unités pouvant atteindre cette cible",  
            key=f"{prefix}_all_reachable_{target['id']}",  
        ):  
            destination = tuple(target["pos"])  
  
            reachable_ids = [  
                unit["id"]  
                for unit in eligible  
                if destination in paths(  
                    g, unit, allow_attack=True  
                )[0]  
            ]  
  
            st.session_state.ui_attacker_ids = reachable_ids  
            st.session_state.ui_selected_id = (  
                reachable_ids[-1] if reachable_ids else None  
            )  
            st.session_state.ui_pending_move = None  
            bump_ui()  
            st.rerun()  
  
        try:  
            checked, checked_target, _ = prepare_attack(  
                g,  
                attacker_ids,  
                target["id"],  
            )  
        except ValueError as exc:  
            st.warning(str(exc))  
        else:  
            values = combat_values(checked, checked_target)  
  
            st.write(  
                f"**Attaque : {values['power']:g} PF** "  
                f"contre **{values['defense']:g} PF**"  
            )  
  
            occupier_id = None  
            losses = None  
            valid = True  
  
            if values.get("hidden") and not values["winnable"]:  
                # Attaquant invisible et non détecté, ou cible qui ne
                # riposte jamais (catapultes) : aucune riposte.
                st.info(
                    (
                        f"🛡️ {values['no_riposte']} ne riposte pas. "
                        if values.get("no_riposte")
                        else "👻 Attaque invisible : l'ennemi n'a aucune "
                        "détection à portée. "
                    )
                    + "Tes unités infligent "
                    f"{values['defender_damage']:g} PF sans subir de dégâts. "  
                    f"Le défenseur gardera {values['defender_remaining']:g} PF."  
                )  
  
            elif not values["winnable"]:  
                st.error(  
                    "ATTAQUE SACRIFICIELLE : "    
                    "toutes les unités sélectionnées mourront."  
                )  
  
                st.write(  
                    f"Le défenseur conservera normalement "  
                    f"**{values['defender_remaining']:g} PF**."  
                )  
  
                st.caption(  
                    "Pour conserver un survivant et prendre la case, "  
                    "ajoute suffisamment d'unités au groupe."  
                )  
  
                valid = st.checkbox(  
                    "Je confirme vouloir sacrifier toutes ces unités.",  
                    key=f"{prefix}_sacrifice_{target['id']}",  
                )  
  
            else:  
                total_losses = values["losses"]  
  
                st.success(  
                    "Le défenseur sera détruit. "  
                    + (  
                        f"🛡️ {values['no_riposte']} ne riposte pas : "
                        "aucune perte pour tes unités."
                        if values.get("no_riposte")
                        else "👻 Attaque invisible : aucune perte pour tes unités."
                        if values.get("hidden")
                        else f"Tu dois répartir {total_losses:g} PF "  
                        "de pertes entre tes unités."  
                    )  
                )    
  
                if values["bonus"]:  
                    st.caption(  
                        "Égalité des forces : bonus attaquant "  
                        "de +0,5 PF appliqué."  
                    )  
  
                occupier_id = st.selectbox(  
                    "1. Unité survivante qui prendra la case",  
                    options=attacker_ids,  
                    format_func=lambda eid: describe(entity(g, eid)),  
                    key=f"{prefix}_occupier_{target['id']}",  
                )  
  
                proposed = default_losses(  
                    checked,  
                    total_losses,  
                    occupier_id,  
                )  
  
                st.markdown("**2. Choisis les pertes de chaque unité**")  
                st.caption(  
                    "0 = aucune perte. "  
                    "Toutes ses PF = unité détruite. "  
                    "Une valeur intermédiaire = unité blessée. "  
                    "L'occupant choisi doit conserver au moins 0,5 PF."  
                )  
  
                losses = {}  
  
                for unit in checked:  
                    eid = unit["id"]  
                    is_occupier = eid == occupier_id  
  
                    maximum = float(unit["pf"])  
                    if is_occupier:  
                        maximum = max(0.0, maximum - 0.5)  
  
                    loss_options = [  
                        step / 2  
                        for step in range(int(maximum * 2) + 1)  
                    ]  
  
                    initial = min(proposed[eid], maximum)  
                    initial_index = loss_options.index(float(initial))  
  
                    def loss_label(value, pf=float(unit["pf"])):  
                        remaining = pf - value  
                        if remaining == 0:  
                            return f"{value:g} PF perdus — DÉTRUITE"  
                        return (  
                            f"{value:g} PF perdus — "  
                            f"SURVIT avec {remaining:g} PF"  
                        )  
  
                    losses[eid] = st.selectbox(  
                        describe(unit)  
                        + (" — PRENDRA LA CASE" if is_occupier else ""),  
                        options=loss_options,  
                        index=initial_index,  
                        format_func=loss_label,  
                        key=(  
                            f"{prefix}_loss_{target['id']}_"  
                            f"{occupier_id}_{eid}"  
                        ),  
                    )  
  
                allocated = sum(losses.values())  
  
                st.write(  
                    f"**Pertes réparties : "  
                    f"{allocated:g} / {total_losses:g} PF**"  
                )  
  
                try:  
                    validate_losses(  
                        checked,  
                        total_losses,  
                        occupier_id,  
                        losses,  
                    )  
                except ValueError as exc:  
                    valid = False  
                    st.warning(str(exc))  
  
                if valid:  
                    st.markdown("**3. Résultat prévu**")  
  
                    for unit in checked:  
                        remaining = unit["pf"] - losses[unit["id"]]  
  
                        if remaining == 0:  
                            result = "💀 détruite"  
                        elif unit["id"] == occupier_id:  
                            result = (  
                                f"✅ survit avec {remaining:g} PF "  
                                f"et prend {coord(checked_target['pos'])}"  
                            )  
                        else:  
                            result = (  
                                f"✅ survit avec {remaining:g} PF "  
                                f"et reste en {coord(unit['pos'])}"  
                            )  
  
                        st.write(  
                            f"- {unit['name']} #{unit['id']} : {result}"  
                        )  
  
            if any(unit.get("kamikaze") for unit in checked):  
                st.warning(  
                    "Ce résumé présente le combat normal. "  
                    "Les dégâts spéciaux kamikazes s'ajoutent ensuite."  
                )  
  
            st.caption(  
                "Tous les participants dépensent leur activation, "  
                "y compris les survivants qui restent sur place."  
            )  
  
            if st.button(  
                "⚔️ Confirmer l’attaque du groupe",  
                type="primary",  
                disabled=not valid,  
                key=f"{prefix}_attack_{target['id']}",  
            ):  
                perform(  
                    game_action,  
                    attack,  
                    attacker_ids,  
                    checked_target["id"],  
                    occupier_id,  
                    losses,  
                )  
  
    # Fin des manœuvres : bouton rouge « Terminer mes manœuvres » du menu.
# ============================================================
# SCORES ET APPLICATION
# ============================================================

def render_scores(g, view):  
    for owner, column in enumerate(st.columns(2)):  
        with column:  
            finished = g["winner"] is not None  
            active = not finished and g["active"] == owner  
  
            if finished:  
                border = "#cbd5e1"  
                background = "#f8fafc"  
                label = "Partie terminée"  
                status_color = "#64748b"  
            elif active:  
                border = "#15803d"  
                background = "#f0fdf4"  
                label = "🟢 À TOI DE JOUER"  
                status_color = "#15803d"  
            else:  
                border = "#dc2626"  
                background = "#fef2f2"  
                label = "🔴 EN ATTENTE"  
                status_color = "#dc2626"  
  
            # HTML sans lignes vides ni indentation :  
            # évite l'affichage de balises comme du code Markdown.  
            card = (  
                f'<div style="'  
                f'border: 2px solid {border};'  
                f'border-radius: 12px;'  
                f'background: {background};'  
                f'padding: 12px 16px;'  
                f'margin-bottom: 10px;'  
                f'color: #172033;">'  
                f'<div style="font-size: 22px; font-weight: 800;">'  
                f'{escape(faction_of(g, owner)["name"])}'  
                f'</div>'  
                f'<div style="color: {status_color};'  
                f'font-weight: 800; margin-top: 6px;">'  
                f'{label}'  
                f'</div>'  
                f'</div>'  
            )  
  
            st.markdown(card, unsafe_allow_html=True)  
  
            public = g["players"][owner]  
  
            st.write(  
                f"**{public['pv']:g} PV** · "  
                f"**{public['bases']}/3** bases détruites · "
                f"Âge **{public['age']}**"
            )  
  
            private_phase = (  
                g["phase"] == "build"  
                and not finished  
            )  
  
            hidden = private_phase and (  
                g["curtain"] or owner != g["active"]  
            )  
  
            if hidden:  
                st.caption("Trésorerie masquée.")  
            else:  
                player = (  
                    view["players"][owner]  
                    if private_phase  
                    else public  
                )  
  
                st.write(  
                    f"Or : **{player['gold']}** · "  
                    f"Mana : **{player['mana']}**"  
                )  

def render_log(view):
    with st.expander("Journal de la partie"):
        for line in reversed(view["log"]):
            st.text(line)


def render_last_combat():  
    if st.session_state.get("ui_combat_report"):  
        with st.expander("⚔️ Voir le bilan du dernier combat", expanded=False):  
            render_combat_report()  


def render_home():  
    st.info("Partie locale à deux joueurs sur le même ordinateur.")    
  
    with st.expander("Règles du prototype"):
        st.markdown(NOTICE)

    with st.expander("📖 Fiches des factions"):
        sheet = st.radio(
            "Faction",
            list(FACTION_SHEETS),
            horizontal=True,
            key="home_faction_sheet",
            label_visibility="collapsed",
        )
        st.image(str(FACTION_SHEETS[sheet]), width="stretch")

    faction_ids = list(FACTIONS)
    top_col, bottom_col = st.columns(2)

    with top_col:
        top = st.selectbox(
            "Faction du joueur en haut du plateau",
            faction_ids,
            index=faction_ids.index(DEFERLANTS),
            format_func=lambda fid: FACTIONS[fid]["name"],
            key="home_faction_top",
        )

    with bottom_col:
        bottom = st.selectbox(
            "Faction du joueur en bas du plateau",
            faction_ids,
            index=faction_ids.index(EXILES),
            format_func=lambda fid: FACTIONS[fid]["name"],
            key="home_faction_bottom",
        )

    factions = (top, bottom)
    same_faction = top == bottom

    if same_faction:
        st.error("Les deux joueurs doivent choisir des factions différentes.")

    first = st.selectbox(
        "Premier joueur",
        [0, 1],
        format_func=lambda owner: FACTIONS[factions[owner]]["name"],
        key="home_first_player",
    )    
  
    victory_mode = st.radio(
        "Condition de victoire",
        options=list(VICTORY_MODES),
        format_func=VICTORY_MODES.get,
        key="home_victory_mode",
    )

    if victory_mode == "time":
        minutes = st.number_input(
            "Durée en minutes",
            min_value=5,
            max_value=180,
            value=60,
            step=1,
            key="home_duration",
        )
    else:
        # Pas de chrono en mode destruction.
        minutes = 0
        st.caption("Pas de limite de temps : la partie continue jusqu'à la 3ᵉ base détruite.")

    if st.button(
        "Commencer",
        type="primary",
        disabled=same_faction,
        key="home_start",
    ):
        reset_session(
            new_bundle(
                int(first),
                0,
                int(minutes),
                victory_mode,
                factions,
            )
        )  
        st.rerun()
  
    st.divider()  
  
    uploaded = st.file_uploader(  
        "Recharger une sauvegarde — format 2",  
        type=["json"],  
        key="home_save_upload",  
    )  
  
    if st.button(  
        "Charger",  
        disabled=uploaded is None,  
        key="home_load",  
    ):  
        try:  
            bundle = load_bundle(uploaded)  
  
        except (  
            ValueError,  
            KeyError,  
            TypeError,  
            UnicodeError,  
            OverflowError,  
            RecursionError,  
        ) as exc:  
            st.error(f"Sauvegarde invalide : {exc}")  
  
        else:  
            reset_session(bundle)  
            st.rerun()  

INVISIBLE_UNITS = {"Daeron et Finwe"}  
  
def has_detector_in_range(g, viewer_owner, pos):  
    for e in g["entities"]:  
        if e["owner"] != viewer_owner:  
            continue  
        if e["name"] != "Décimant":  
            continue  
        if distance(tuple(e["pos"]), pos) <= UNITS["Décimant"]["range"]:  
            return True  
    return False  
  
def visible_to_player(g, piece, viewer_owner):  
    if piece["owner"] == viewer_owner:  
        return True  
    if piece["name"] in INVISIBLE_UNITS:  
        return has_detector_in_range(g, viewer_owner, tuple(piece["pos"]))  
    return True  

def render_movement_validation(g):  
    """Validation directe du déplacement en attente."""  
    pending = st.session_state.get("ui_pending_move")  
  
    if not pending:  
        return  
  
    unit = next(  
        (  
            piece  
            for piece in g["entities"]  
            if piece["id"] == pending["unit_id"]  
        ),  
        None,  
    )  
  
    if unit is None or not can_move(g, unit):  
        st.session_state.ui_pending_move = None  
        return  
  
    destination = tuple(pending["destination"])  
    destinations, _ = move_preview(g, unit)  
    valid = destination in destinations  
  
    st.info(  
        f"Déplacer {unit['name']} #{unit['id']} "  
        f"de {coord(unit['pos'])} vers {coord(destination)}."  
    )  
  
    if not valid:  
        st.warning("Cette destination n'est plus accessible.")  
  
    cancel_col = st.container()

    if True:
        # Clic sur une case verte : le déplacement part aussitôt.
        if valid and auto_confirm("move", unit["id"], destination):
            perform(  
                game_action,  
                move_unit,  
                unit["id"],  
                destination,  
            )  
  
    with cancel_col:  
        if st.button(  
            "✕ Annuler",  
            key="sidebar_cancel_unit_movement",  
        ):  
            cancel_maneuver_confirmation()  
            st.rerun()  

def render_sidebar(bundle):  
    g = bundle["game"]  
    view = bundle["draft"] if g["phase"] == "build" and bundle.get("draft") is not None else g
  
    with st.sidebar:  
        st.header("Partie")  
        st.write(f"**Tour : {g['turn']}**")  
  
        phase = {  
            "build": "Planification privée",  
            "move": "Manœuvres",  
        }.get(g["phase"], g["phase"])  
  
        st.write(f"**Phase :** {phase}")  
  
        if g.get("victory_mode") == "bases":
            st.write("**Victoire :** 3 bases ennemies détruites")
            for owner in (0, 1):
                st.write(
                    f"{faction_of(g, owner)['name']} : "
                    f"{g['players'][owner]['bases']}/3 bases détruites"
                )
        else:
            if g.get("victory_mode") == "time":
                st.write("**Victoire :** meilleur score en PV à la fin du temps")

            seconds = max(0, math.ceil(g["remaining"]))
            st.write(
                f"**Temps restant :** "
                f"{seconds // 60:02d}:{seconds % 60:02d}"
            )

            st.button(
                "Actualiser le chronomètre",
                key="refresh_clock",
            )

        if st.button(
            "Terminer ma phase de production",
            type="primary",
            disabled=(g["phase"] != "build" or g["winner"] is not None),
            key="sidebar_finish_production",
        ):
            perform(commit_plan)

        st.divider()

        if g["winner"] is None:  
            st.subheader("Actions")  
  
            if g["phase"] == "build":  
                render_build_controls(  
                    g,  
                    view,  
                    local=True,  
                    on_board=False,  
                )  
  
            elif g["phase"] == "move":  
                # Ce bouton ne dépend pas de la sélection d'une unité.  
                if st.button(  
                    "🏁 Terminer mes manœuvres",  
                    key="sidebar_finish_maneuvers_always",  
                    disabled=(  
                        g["curtain"]  
                        or g["active"] in g["passed"]  
                    ),  
                ):  
                    perform(game_action, pass_turn)  
  
                st.caption(  
                    "Tu peux terminer sans déplacer ni attaquer. "  
                    "Tes activations restantes seront abandonnées "  
                    "pour ce tour."  
                )  
  
                st.divider()  
  
                render_movement_validation(g)  
  
                # Conserver les commandes existantes :  
                # sélection des unités, tirs et combats.  
                render_move_controls(g)  
        with st.expander("Règles de cette version"):  
            st.write(NOTICE)  

        with st.expander("📖 Fiches des factions", expanded=False):
            render_faction_sheet_menu("sidebar")

        st.download_button(  
            "Sauvegarder",  
            data=json.dumps(  
                bundle,  
                ensure_ascii=False,  
                indent=2,  
                allow_nan=False,  
            ),  
            file_name="the_four_realms.json",  
            mime="application/json",  
            key="download_save",  
        )  
  
        st.caption(  
            "La sauvegarde contient aussi les planifications privées."  
        )  
  
        confirm = st.checkbox(  
            "Confirmer le retour à l'accueil",  
            key="confirm_home",  
        )  
  
        if st.button(  
            "Retour à l'accueil",  
            disabled=not confirm,  
            key="go_home",  
        ):  
            reset_session()  
            st.rerun()  

def main():  
    init_ui()  
  
    # ========================================================  
    # TRAITEMENT DES ÉVÉNEMENTS AVANT TOUT AFFICHAGE  
    # ========================================================  
    if "bundle" in st.session_state:  
        bundle = st.session_state.bundle  
        g = bundle["game"]  

        normalize_starting_layout(bundle)
  
        # Conservation du fonctionnement actuel, sans rideau.  
        g["curtain"] = False  
        tick(g)  
  
        if g["winner"] is None:  
            # Peut appeler perform(), puis st.rerun().  
            # Aucun élément de la page n'a encore été dessiné.  
            process_queued_maneuver()  
  
            if g["phase"] == "build":  
                ensure_draft(bundle)  
                event_view = bundle["draft"]  
            else:  
                event_view = g  
  
            process_queued_board_event(g, event_view)  
        else:  
            st.session_state.pop("ui_queued_maneuver", None)  
            st.session_state.pop("ui_queued_board_event", None)  
  
    # ========================================================  
    # AFFICHAGE  
    # ========================================================  
    st.markdown(CSS, unsafe_allow_html=True)  
  
    with st.container(key="lw_page_header"):  
        render_logo_header(home="bundle" not in st.session_state)
  
    if "bundle" not in st.session_state:  
        render_home()  
        return  
  
    bundle = st.session_state.bundle  
    g = bundle["game"]  
  
    finished = g["winner"] is not None  
  
    if not finished and g["phase"] == "build":  
        ensure_draft(bundle)  
        view = bundle["draft"]  
    else:  
        view = g  
  
    render_sidebar(bundle)  
  
    # Les conteneurs restent présents même quand leur contenu  
    # est vide, afin de stabiliser la structure de la page.  
    with st.container(key="lw_page_messages"):  
        message = st.session_state.pop("ui_message", None)  
  
        if message:  
            st.warning(message)  
  
    with st.container(key="lw_page_phase"):  
        if finished:  
            if g["winner"] == -1:
                st.info("La partie se termine sur une égalité.")
            # Victoire : annoncée une seule fois, par la banderole sur le
            # plateau puis l'image de victoire de la faction (pas de doublon).
        else:  
            st.subheader(  
                f"Tour {turn_label(g)} — {phase_label(g)}"  
            )  
            st.caption(  
                f"Joueur actif : "  
                f"{faction_of(g, g['active'])['name']}"  
            )  
  
            if g["phase"] == "build":  
                st.caption(  
                    "Construis tes bâtiments, recrute tes unités "  
                    "et choisis tes récoltes."  
                )  
  
                if g["ready"]:  
                    st.info(  
                        "Le premier joueur a validé sa production. "  
                        "Ta validation révélera les deux productions "  
                        "et lancera les manœuvres."  
                    )  
            else:  
                st.caption(  
                    "Sélectionne une unité pour la déplacer, "  
                    "ou plusieurs unités pour attaquer "  
                    "une cible ennemie."  
                )  
  
    with st.container(key="lw_page_scores"):  
        render_scores(g, view)  
  
    with st.container(key="lw_page_legend"):  
        st.caption(  
            "Cadre rouge : faction qui doit jouer · "  
            "Pions ronds : unités militaires · "  
            "Pions carrés : bâtiments et bases · "  
            "Contour jaune : sélection · "  
            "Cases vertes : déplacement ou placement possible · "  
            "Cases rouges : cible ennemie accessible · "  
            "Pièce grise : action déjà effectuée · "
            "Attente N : pièce disponible dans N fins de tour · "
            "Numéros sur le plateau : combats du journal de bord · "
            "Case rouge et « −N PF » : dégâts subis · "
            "Rond vert : unité recrutée · Rond orange : bâtiment ou base construit"
        )  
  
    with st.container(key="lw_page_board"):  
        st.divider()
        if st.session_state.get("ui_faction_view") in FACTION_SHEETS:
            # Fiche ouverte : elle prend la place du plateau, la partie est intacte.
            render_faction_sheet()
        elif finished and g["winner"] != -1:
            # Plateau final avec la banderole et l'image de fin de partie.
            render_victory_screen(g)
        else:
            render_board(g, view, readonly=finished)
        if st.session_state.get("ui_faction_view") not in FACTION_SHEETS:
            render_placement_confirmation(
                g, view, 1600, 1000, 32, 40
            )
  
    with st.container(key="lw_page_combat_report"):  
        render_last_combat()  
  
    with st.container(key="lw_page_log"):  
        render_log(view)  
  
# ============================================================  
# POUVOIRS SPECIAUX — ETAPE 1 : MAGE ET GOLEM  
# A placer APRES toutes les fonctions existantes,  
# mais AVANT : if __name__ == "__main__":  
# ============================================================  
  
# Garder les versions précédentes pour les autres unités.  
_lw_previous_paths = paths  
_lw_previous_prepare_attack = prepare_attack  
_lw_previous_ranged_values = ranged_attack_values  
_lw_previous_ranged_attack = ranged_attack  
_lw_previous_attack_destinations = attack_destinations  
_lw_previous_render_move_controls = render_move_controls  
  
MOUNTAIN_MAGE = "Mage des montagnes"
ARAMIL = "Aramil"
# Aramil est un Mage des montagnes transformé : il garde tous les sorts du Mage.
MAGES = {MOUNTAIN_MAGE, ARAMIL}
STONE_GOLEM = "Golem de pierre"  
  
UNITS[STONE_GOLEM]["range"] = 4  
  
  
def mage_spell_ready(g, mage):  
    """Un sort au tour N autorise le suivant au tour N+2."""  
    return (  
        can_move(g, mage)  
        and mage["name"] in MAGES  
        and g["turn"] >= mage.get("next_spell_turn", 1)  
    )  
  
  
def paths(g, unit, allow_attack=False):  
    start = tuple(unit["pos"])  
    budget = remaining_actions(g, unit)  
    
    flying = is_flying(unit)  
    
    occupants = {tuple(e["pos"]): e for e in g["entities"]}  
    costs = {start: 0}  
    routes = {start: [start]}  
    queue = [(0, start)]  
  
    while queue:  
        cost, pos = heapq.heappop(queue)  
        if cost != costs[pos]:  
            continue  
  
        for nxt in neighbors(pos):  
            occupant = occupants.get(nxt)  
            enemy = occupant is not None and occupant["owner"] != unit["owner"]  
  
            # Terrain  
            if not flying and terrain(g, nxt) in ("sea", "mountain"):  
                if terrain(g, nxt) == "sea":  
                    continue  
                step = 2  
            else:  
                step = 1  
  
            if occupant is not None:  
                if enemy:  
                    if not allow_attack:  
                        continue  
                elif occupant["kind"] not in ("unit", "base", "building"):  
                    continue  
  
            new_cost = cost + step  
            if new_cost > budget or new_cost >= costs.get(nxt, math.inf):  
                continue  
  
            costs[nxt] = new_cost  
            routes[nxt] = routes[pos] + [nxt]  
            if not enemy:  
                heapq.heappush(queue, (new_cost, nxt))  
  
    return costs, routes  
  
def prepare_attack(g, attacker_ids, target_id):  
    require_phase(g, "move")  
    if g["curtain"]:  
        raise ValueError("Confirme d'abord que tu es prêt.")  
  
    attackers = [entity(g, eid) for eid in attacker_ids]  
    target = entity(g, target_id)  
  
    if target["owner"] == g["active"]:  
        raise ValueError("Choisis une cible ennemie.")  
  
    for attacker in attackers:  
        if attacker["name"] == "Costaud" and target["kind"] not in ("building", "base"):  
            raise ValueError("Le Costaud ne peut attaquer que les bâtiments et les bases.")  
        if attacker["name"] in MAGES:  
            raise ValueError(  
                "Le Mage des montagnes ne participe pas aux attaques normales. "  
                "Sélectionne-le seul pour utiliser ses sorts."  
            )  
        if attacker["name"] == STONE_GOLEM:  
            raise ValueError(  
                "Le Golem de pierre attaque seul avec son tir en ligne, uniquement à 3 ou 4 cases."  
            )  
  
    if not attacker_ids:  
        raise ValueError("Sélectionne au moins une unité.")  
    if len(attacker_ids) != len(set(attacker_ids)):  
        raise ValueError("Une unité est sélectionnée plusieurs fois.")  
    if any(not can_move(g, attacker) for attacker in attackers):  
        raise ValueError("Au moins une unité est indisponible.")  
  
    destination = tuple(target["pos"])  
    routes_by_id = {}  
  
    for attacker in attackers:  
        _, routes = paths(g, attacker, allow_attack=True)  
        if destination not in routes:  
            raise ValueError(  
                f"{describe(attacker)} ne peut pas atteindre {coord(destination)} avec son déplacement."  
            )  
        routes_by_id[attacker["id"]] = routes[destination]  
  
    return attackers, target, routes_by_id  
  
  
def golem_direction(origin, destination):  
    """Direction axiale si les deux cases sont alignées."""  
    length = distance(origin, destination)  
  
    if length == 0:  
        return None  
  
    dq = destination[0] - origin[0]  
    dr = destination[1] - origin[1]  
  
    for direction in DIRECTIONS:  
        if (  
            dq == direction[0] * length  
            and dr == direction[1] * length  
        ):  
            return direction  
  
    return None  
  
  
def golem_impact_cells(golem, target):  
    """  
    Cible principale, puis deux cases derrière.  
    Les cases derrière peuvent dépasser la portée de 4.  
    """  
    direction = golem_direction(  
        golem["pos"], target["pos"]  
    )  
  
    if direction is None:  
        raise ValueError(  
            "Le tir du Golem doit suivre une ligne droite "  
            "d'hexagones."  
        )  
  
    q, r = target["pos"]  
    dq, dr = direction  
  
    return [  
        (q + step * dq, r + step * dr)  
        for step in range(3)  
        if (q + step * dq, r + step * dr) in CELL_SET  
    ]  
  
  
def ranged_attack_values(g, attacker, target):  
    if attacker["name"] in MAGES:  
        raise ValueError(  
            "Le Mage ne possède pas de tir normal. "  
            "Utilise le panneau « Sorts du Mage »."  
        )  
  
    if attacker["name"] != STONE_GOLEM:  
        return _lw_previous_ranged_values(  
            g, attacker, target  
        )  
  
    require_phase(g, "move")  
  
    if not can_move(g, attacker):  
        raise ValueError("Ce Golem ne peut pas agir.")  
  
    if target["owner"] == attacker["owner"]:  
        raise ValueError("Choisis une cible ennemie.")  
  
    if target["kind"] != "unit":  
        raise ValueError(  
            "Le Golem de pierre vise uniquement des unités."  
        )  
  
    gap = distance(attacker["pos"], target["pos"])  
  
    if gap not in (3, 4):  
        raise ValueError(  
            "Le Golem vise uniquement à 3 ou 4 cases."  
        )  
  
    impacts = golem_impact_cells(attacker, target)  
  
    # Conservation du calcul de dégâts actuel :  
    # PF restants (les forêts sont décoratives : aucun malus).  
    damage = float(attacker["pf"])  
  
  
    if damage <= 0:  
        raise ValueError("Ce tir n'inflige aucun dégât.")  
  
    return {  
        "range": 4,  
        "damage": damage,  
        "remaining": max(0.0, target["pf"] - damage),  
        "impact_cells": impacts,  
    }  
  
  
def ranged_attack(g, attacker_id, target_id):  
    attacker = entity(g, attacker_id)  
    target = entity(g, target_id)  
  
    if attacker["name"] != STONE_GOLEM:  
        # La version précédente appelle la nouvelle validation :  
        # le tir normal du Mage est donc également bloqué.  
        return _lw_previous_ranged_attack(  
            g, attacker_id, target_id  
        )  
  
    values = ranged_attack_values(g, attacker, target)  
    owner = attacker["owner"]  
    impact_set = set(values["impact_cells"])  
  
    victims = [  
        piece  
        for piece in list(g["entities"])  
        if (  
            piece["owner"] != owner  
            and piece["kind"] == "unit"  
            and tuple(piece["pos"]) in impact_set  
        )  
    ]  
  
    report = {  
        "turn": turn_label(g),  
        "position": coord(target["pos"]),  
        "power": values["damage"],  
        "bonus": 0.0,  
        "defense": float(target["pf"]),  
        "occupier_id": None,  
        "participants": [{  
            "id": attacker["id"],  
            "owner": owner,  
            "name": attacker["name"],  
            "role": "Tireur",  
            "before": float(attacker["pf"]),  
            "damage": 0.0,  
            "after": float(attacker["pf"]),  
        }],  
    }  
  
    attacker["acted"] = True  
  
    for victim in victims:  
        before = float(victim["pf"])  
        damage = min(before, values["damage"])  
        victim["pf"] = before - damage  
  
        report["participants"].append({  
            "id": victim["id"],  
            "owner": victim["owner"],  
            "name": victim["name"],  
            "role": "Cible du tir en ligne",  
            "before": before,  
            "damage": damage,  
            "after": victim["pf"],  
        })  
  
        if victim["pf"] <= 0:  
            destroy(g, victim, owner)  
  
    log(  
        g,  
        "Le Golem tire sur la ligne : "  
        + ", ".join(  
            coord(pos) for pos in values["impact_cells"]  
        )  
        + "."  
    )  
  
    g["_combat_report"] = report  
    next_activation(g)  
  
  
def cast_mage_spell(g, mage_id, spell, target_ids):  
    """Validation complète avant de modifier les cibles."""  
    require_phase(g, "move")  
    mage = entity(g, mage_id)  
  
    if not mage_spell_ready(g, mage):  
        raise ValueError(  
            "Mage indisponible ou sort encore en recharge."  
        )  
  
    limits = {"slow": 3, "damage": 2}  
  
    if spell not in limits:  
        raise ValueError("Sort inconnu.")  
  
    if (  
        not isinstance(target_ids, list)  
        or not 1 <= len(target_ids) <= limits[spell]  
        or len(target_ids) != len(set(target_ids))  
    ):  
        raise ValueError(  
            f"Choisis entre 1 et {limits[spell]} "  
            "cible(s) distincte(s)."  
        )  
  
    targets = [entity(g, eid) for eid in target_ids]  
  
    for target in targets:  
        if (  
            target["owner"] == mage["owner"]  
            or target["kind"] != "unit"  
            or distance(mage["pos"], target["pos"]) > 4  
        ):  
            raise ValueError(  
                "Chaque cible doit être une unité ennemie "  
                "située à 4 cases maximum du Mage."  
            )  
  
    mage["acted"] = True  
    mage["next_spell_turn"] = g["turn"] + 2  
  
    for target in targets:  
        if spell == "slow":  
            # Actif pendant le tour courant et le suivant.  
            # Plusieurs ralentissements ne se cumulent pas.  
            target["slow_until_turn"] = max(  
                target.get("slow_until_turn", -1),  
                g["turn"] + 1,  
            )  
        else:  
            target["pf"] = max(0.0, target["pf"] - 2.0)  
  
            if target["pf"] <= 0:  
                destroy(g, target, mage["owner"])  
  
    log(  
        g,  
        "Le Mage lance "  
        + (  
            "un ralentissement de 2 mouvements"  
            if spell == "slow"  
            else "un sort de 2 PF de dégâts"  
        )  
        + f" sur {len(targets)} unité(s)."  
    )  
  
    next_activation(g)  
  
  
def attack_destinations(g, attackers):  
    if any(  
        unit["name"] in MAGES  
        for unit in attackers  
    ):  
        # Les sorts ont une sélection multiple dédiée.  
        return {}  
  
    if len(attackers) > 1 and any(  
        unit["name"] == STONE_GOLEM  
        for unit in attackers  
    ):  
        return {}  
  
    return _lw_previous_attack_destinations(g, attackers)  
  
  
def render_mage_controls(g, mage):  
    st.subheader("✨ Sorts du Mage")  
  
    st.caption(  
        "Aucune attaque normale. Portée fixe : 4 cases. "  
        "Un sort tous les deux tours."  
    )  
  
    next_turn = mage.get("next_spell_turn", 1)  
  
    if g["turn"] < next_turn:  
        st.info(  
            f"Prochain sort disponible au tour {next_turn}. "  
            "Le Mage peut encore se déplacer s'il n'a pas agi."  
        )  
        return  
  
    if not can_move(g, mage):  
        st.info("Ce Mage a déjà agi ou est indisponible.")  
        return  
  
    prefix = (  
        f"mage_{g['turn']}_{mage['id']}_"  
        f"{st.session_state.ui_revision}"  
    )  
  
    spell = st.radio(  
        "Sort",  
        options=["slow", "damage"],  
        format_func=lambda value: (  
            "Ralentissement : −2 MVT, jusqu'à 3 unités"  
            if value == "slow"  
            else "Dégâts : −2 PF, jusqu'à 2 unités"  
        ),  
        key=f"{prefix}_spell",  
    )  
  
    candidates = {  
        piece["id"]: piece  
        for piece in g["entities"]  
        if (  
            piece["owner"] != mage["owner"]  
            and piece["kind"] == "unit"  
            and distance(mage["pos"], piece["pos"]) <= 4  
        )  
    }  
  
    if not candidates:  
        st.info("Aucune unité ennemie à portée.")  
        return  
  
    limit = 3 if spell == "slow" else 2  
  
    clicked_target_id = st.session_state.get("ui_target_id")

    # Les cibles cliquées sur le plateau s'accumulent jusqu'au maximum.
    memory_key = f"{g['turn']}_{mage['id']}_{spell}"
    memory = st.session_state.setdefault("ui_spell_targets", {})
    entry = memory.setdefault(memory_key, {"ids": [], "last": None})
    chosen = [eid for eid in entry["ids"] if eid in candidates]
    if (
        clicked_target_id in candidates
        and clicked_target_id != entry["last"]
        and clicked_target_id not in chosen
    ):
        chosen.append(clicked_target_id)
    entry["last"] = clicked_target_id
    wanted = min(limit, len(candidates))
    st.caption(
        f"Clique sur {wanted} cible(s) sur le plateau : "
        "le sort part dès que la dernière est choisie."
    )

    selected = st.multiselect(
        f"Cibles — maximum {limit}",
        options=list(candidates),
        default=chosen[:limit],
        format_func=lambda eid: describe(candidates[eid]),  
        key=f"{prefix}_{spell}_targets",  
    )  
    
    entry["ids"] = list(selected)

    if len(selected) > limit:
        st.warning(f"Choisis au maximum {limit} cibles.")

    if len(selected) == wanted and auto_confirm(
        "mage", mage["id"], spell, sorted(selected)
    ):
        memory.pop(memory_key, None)
        perform(
            game_action,
            cast_mage_spell,
            mage["id"],
            spell,
            list(selected),
        )
  
    if spell == "slow":  
        st.caption(  
            "Effet jusqu'à la fin du tour suivant. "  
            "Le mouvement ne descend pas sous zéro."  
        )  
  
    # Seulement pour lancer le sort sur MOINS de cibles que le maximum.
    if 1 <= len(selected) < wanted and st.button(
        f"✨ Lancer sur {len(selected)} cible(s) seulement",
        key=f"{prefix}_confirm",
    ):
        perform(  
            game_action,  
            cast_mage_spell,  
            mage["id"],  
            spell,  
            list(selected),  
        )  
  
  
def render_move_controls(g):  
    attackers = selected_attackers(g)  
  
    if (  
        len(attackers) == 1  
        and attackers[0]["name"] in MAGES  
    ):  
        render_mage_controls(g, attackers[0])  
  
        st.caption(  
            "Pour déplacer ce Mage, clique sur une case verte "  
            "puis valide le déplacement."  
        )  
  
        if st.button(  
            "Désélectionner le Mage",  
            key="special_deselect_mage",  
        ):  
            bump_ui(clear_selection=True)  
            st.rerun()  
  
        return  
  
    if (  
        len(attackers) == 1  
        and attackers[0]["name"] == STONE_GOLEM  
    ):  
        st.caption(  
            "Golem : cible à 3 ou 4 cases, sur une ligne "  
            "droite. La cible et les deux cases derrière "  
            "sont touchées. Les alliés sont épargnés."  
        )  
  
    _lw_previous_render_move_controls(g)  


# ============================================================  
# ACTIVATION : DÉPLACEMENT PUIS ATTAQUE  
# À placer après toutes les autres définitions,  
# juste avant : if __name__ == "__main__":  
# ============================================================  
  
_lw_action_previous_can_move = can_move  
_lw_action_previous_available = available  
_lw_action_previous_next_activation = next_activation  
_lw_action_previous_ranged_values = ranged_attack_values  
_lw_action_previous_render_move_controls = render_move_controls  
  
  
def can_move(g, unit):  
    if not _lw_action_previous_can_move(g, unit):  
        return False  
  
    # Une unité ayant commencé à se déplacer doit terminer  
    # son activation avant de pouvoir en activer une autre.  
    moving_id = g.get("moving_unit_id")  
  
    if moving_id is not None and unit["id"] != moving_id:  
        return False  
  
    return remaining_actions(g, unit) > 0  
  
  
def available(g, owner):  
    units = _lw_action_previous_available(g, owner)  
  
    moving_id = g.get("moving_unit_id")  
  
    if moving_id is not None:  
        units = [  
            unit for unit in units  
            if unit["id"] == moving_id  
        ]  
  
    return units  
  
  
def next_activation(g, switch=True):  
    # Toute fin d'activation clôt également le déplacement  
    # commencé auparavant, même si des points restaient.  
    moving_id = g.pop("moving_unit_id", None)  
  
    if moving_id is not None:  
        moving_unit = next(  
            (  
                piece  
                for piece in g["entities"]  
                if piece["id"] == moving_id  
            ),  
            None,  
        )  
  
        if moving_unit is not None:  
            moving_unit["acted"] = True  
  
    return _lw_action_previous_next_activation(g, switch=switch)  
  
  
def ranged_attack_values(g, attacker, target):  
    # Une attaque à distance nécessite au moins 1 action restante.  
    if remaining_actions(g, attacker) < 1:  
        raise ValueError(  
            "Cette unité a utilisé tout son déplacement. "  
            "Il faut conserver au moins 1 action pour attaquer."  
        )  
  
    # La portée est calculée depuis la position ACTUELLE,  
    # donc après le déplacement éventuel.  
    # Les règles spéciales existantes restent appliquées.  
    return _lw_action_previous_ranged_values(g, attacker, target)  
  
  
def finish_unit_activation(g, unit_id):  
    require_phase(g, "move")  
  
    unit = entity(g, unit_id)  
  
    if (  
        g.get("moving_unit_id") != unit_id  
        or unit["owner"] != g["active"]  
        or unit["kind"] != "unit"  
    ):  
        raise ValueError(  
            "Cette unité n'a pas d'activation en cours."  
        )  
  
    unit["acted"] = True  
  
    log(  
        g,  
        f"{unit['name']} #{unit['id']} termine son activation.",  
    )  
  
    next_activation(g)  
  
  
def render_move_controls(g):  
    moving_id = g.get("moving_unit_id")  
  
    moving_unit = next(  
        (  
            piece  
            for piece in g["entities"]  
            if piece["id"] == moving_id  
        ),  
        None,  
    )  
  
    if moving_unit is not None:  
        # perform() efface la sélection après un déplacement :  
        # on restaure ici l'unité dont l'activation continue.  
        st.session_state.ui_selected_id = moving_unit["id"]  
        st.session_state.ui_attacker_ids = [moving_unit["id"]]  
  
        remaining = remaining_actions(g, moving_unit)  
  
        st.info(  
            f"Activation en cours : {moving_unit['name']} "  
            f"#{moving_unit['id']} — "  
            f"{remaining} action(s) restante(s)."  
        )  
  
        st.caption(  
            "Clique sur une cible pour attaquer depuis cette position, "  
            "ou sur une case verte pour continuer le déplacement. "  
            "Un tir nécessite au moins 1 action restante "  
            "et termine l'activation."  
        )  
  
        if st.button(  
            "✓ Terminer l’activation de cette unité",  
            key=(  
                f"finish_unit_activation_"  
                f"{g['turn']}_{moving_unit['id']}"  
            ),  
        ):  
            perform(  
                game_action,  
                finish_unit_activation,  
                moving_unit["id"],  
            )  
  
    _lw_action_previous_render_move_controls(g)  


def attack_map_preview(g, attackers):  
    """  
    Retourne :  
    - les cases dans la portée géométrique d'une unité ;  
    - les véritables cibles attaquables.  
  
    Aucun chemin de déplacement n'est utilisé pour un tir.  
    """  
    if not attackers:  
        return set(), {}  
  
    owner = attackers[0]["owner"]  
  
    # Groupes et corps à corps : conserver leur fonctionnement.  
    if (  
        len(attackers) != 1  
        or UNITS[attackers[0]["name"]]["range"] <= 0  
    ):  
        targets = attack_destinations(g, attackers)  
  
        # Ne pas révéler les ennemis invisibles.  
        targets = {  
            pos: data  
            for pos, data in targets.items()  
            if (  
                at(g, pos) is not None  
                and visible_to_player(g, at(g, pos), owner)  
            )  
        }  
  
        return set(), targets  
  
    attacker = attackers[0]  
  
    if not can_move(g, attacker):  
        return set(), {}  
  
    name = attacker["name"]  
    origin = tuple(attacker["pos"])  
  
    # --------------------------------------------------------  
    # Portée géométrique : indépendante du déplacement.  
    # --------------------------------------------------------  
    if name in MAGES:  
        if not mage_spell_ready(g, attacker):  
            return set(), {}  
  
        zone = {  
            pos  
            for pos in CELLS  
            if 1 <= distance(origin, pos) <= 4  
        }  
  
    elif name == STONE_GOLEM:  
        # Particularité déjà présente :  
        # uniquement à 3 ou 4 cases et en ligne droite.  
        zone = {  
            pos  
            for pos in CELLS  
            if (  
                distance(origin, pos) in (3, 4)  
                and golem_direction(origin, pos) is not None  
            )  
        }  
  
    else:  
        attack_range = UNITS[name]["range"]  
  
        # Conservation du bonus de tir existant.  
        # Ce bonus ne représente pas un coût de déplacement.  
        if terrain(g, origin) == "mountain":  
            attack_range += 1  
  
        zone = {  
            pos  
            for pos in CELLS  
            if 1 <= distance(origin, pos) <= attack_range  
        }  
  
    # --------------------------------------------------------  
    # Cibles réellement attaquables dans cette zone.  
    # --------------------------------------------------------  
    targets = {}  
  
    for target in g["entities"]:  
        if target["owner"] == owner:  
            continue  
  
        if not visible_to_player(g, target, owner):  
            continue  
  
        pos = tuple(target["pos"])  
  
        if pos not in zone:  
            continue  
  
        if name in MAGES:  
            # Les sorts du Mage ciblent uniquement les unités.  
            if target["kind"] != "unit":  
                continue  
  
            targets[pos] = {  
                "target_id": target["id"],  
                "spell": True,  
                "ranged": True,  
                "distance": distance(origin, pos),  
            }  
  
        else:  
            # Validation des particularités de chaque tireur :  
            # Golem, Instinct elfique, etc.  
            try:  
                values = ranged_attack_values(g, attacker, target)  
            except ValueError:  
                continue  
  
            targets[pos] = {  
                "target_id": target["id"],  
                "ranged": True,  
                "distance": distance(origin, pos),  
                "winnable": values["remaining"] == 0,  
            }  
  
    return zone, targets  

# ============================================================
# UNITÉS SPÉCIALES : DÉFERLANTS ET EXILÉS
# À laisser APRÈS toutes les autres définitions,
# juste avant : if __name__ == "__main__":
# ============================================================

KAMIKAZE = "Kamikaze"
ENRAGED = "Enragé"
MOLOSSE = "Molosse"
FLYER = "Volant"
DECIMANT = "Décimant"
RAMPANT = "Rampant"
DWARVES = "Nain des montagnes"
ELF_HEROES = "Daeron et Finwe"
ELF_HERO_NAMES = ("Daeron", "Finwe")

# Le Kamikaze devient une unité à part entière, recrutable à la Mare.
UNITS[KAMIKAZE] = {
    "cost": 100, "mana": 0, "batch": 1,
    "pf": 2, "move": 3, "range": 0, "limit": 10,
}
UNIT_AGES[KAMIKAZE] = 1
# Le Kamikaze ne se recrute pas : il vient de la mutation d'un Déferlant.
FACTIONS[0]["buildings"]["Mare"]["units"] = ["Déferlant"]
FACTIONS[0].setdefault("extra_units", []).append(KAMIKAZE)

# Repère elfique : le premier elfe s'appelle Daeron, le second Finwe.
for _hero_name in ELF_HERO_NAMES:
    UNITS[_hero_name] = dict(UNITS[ELF_HEROES], batch=1, limit=1)
    UNIT_AGES[_hero_name] = UNIT_AGES[ELF_HEROES]

# Nom d'une pièce sur le plateau -> nom de recrutement correspondant.
UNIT_ENTITY_SOURCES = {name: ELF_HEROES for name in ELF_HERO_NAMES}

UPGRADES["Mutation kamikaze"]["effect"] = (
    "Permet de muter un Déferlant en Kamikaze "
    "(le Kamikaze ne se recrute pas directement)."
)
UPGRADES["Rampants"] = {
    "owner": 0,
    "cost": 350,
    "mana": 2,
    "building": "Bassin de mutation",
    "age": 2,
    "effect": (
        "Débloque les Rampants : recrutement au Marais d'aspergeurs "
        "et mutation d'un Aspergeur en Rampant."
    ),
}
UPGRADES["Dents acérées volants"] = {
    "owner": 0,
    "cost": 400,
    "mana": 0,
    "building": "Bassin de mutation",
    "age": 3,
    "effect": "+1 PF pour chaque Volant, y compris ceux déjà en jeu.",
}

# Unité recrutable seulement après une amélioration.
UNIT_REQUIREMENTS = {
    KAMIKAZE: "Mutation kamikaze",
    RAMPANT: "Rampants",
}

# Unité -> (unité obtenue, amélioration requise, coût en or).
MUTATIONS = {
    "Déferlant": (KAMIKAZE, "Mutation kamikaze", 100),
    "Aspergeur": (RAMPANT, "Rampants", 100),
}

# Améliorations de PF, appliquées aussi aux unités déjà en jeu.
PF_UPGRADES = {
    "Dents acérées": ("Déferlant", 0.5),
    "Développement musculaire": ("Mammouth dompté", 3.0),
    "Dents acérées volants": (FLYER, 1.0),
}

FLYING_UNITS = {
    FLYER, "Dents acérées volants", "Dragon", DECIMANT,
    ELF_HEROES, *ELF_HERO_NAMES,
}
INVISIBLE_UNITS = {ELF_HEROES, *ELF_HERO_NAMES}
DETECTOR_RANGES = {DECIMANT: 4}

# Attaques qui touchent la cible + une case voisine choisie.
SECOND_CELL_UNITS = {MOLOSSE}

# Piétinement : None = contre toute cible ;
# N = seulement contre les unités d'âge N ou inférieur.
TRAMPLERS = {MOLOSSE: None, FLYER: 1}

DECIMANT_RANGE = 4
DECIMANT_BLOCK_TURNS = 2
DECIMANT_SPELLS = {
    "block": "⛔ Bloquer la production d'un bâtiment ennemi pendant 2 tours",
    "attract": "🧲 Attirer une unité ennemie près du Décimant, puis rejouer aussitôt",
}

AGE_REFERENCE["Déferlants"][1].append(
    ("Kamikaze", "Unité · Mare après Mutation kamikaze · explose : 2 PF sur la cible, 1 PF à gauche et à droite")
)
AGE_REFERENCE["Déferlants"][2].extend([
    ("Enragé", "Unité · 3 dégâts sur la cible et ses 2 voisines, alliés compris"),
    ("Rampants", "Amélioration · mutation Aspergeur → Rampant, recrutement au Marais"),
])
AGE_REFERENCE["Déferlants"][3].extend([
    ("Volant", "Unité volante · piétinement contre l'âge I"),
    ("Dents acérées volants", "Amélioration · +1 PF par Volant"),
])
AGE_REFERENCE["Exilés"][3].append(
    ("Nain des montagnes", "Accorde une attaque supplémentaire à 2 unités voisines")
)


def is_flying(unit):
    return unit["name"] in FLYING_UNITS


def unit_requirement_met(g, owner, name):
    required = UNIT_REQUIREMENTS.get(name)
    return (
        required is None
        or required in g["players"][owner].get("upgrades", [])
    )


def production_blocked_until(g, piece):
    """Dernier tour de blocage par un Décimant, ou None."""
    until = piece.get("blocked_until_turn")
    if until is None or g["turn"] > until:
        return None
    return until


def max_upgrade_pf_bonus(name):
    return sum(
        bonus
        for unit_name, bonus in PF_UPGRADES.values()
        if unit_name == name
    )


def sync_unit_upgrades(g, unit):
    """Ajoute à une unité les bonus de PF qu'elle n'a pas encore."""
    if unit["kind"] != "unit":
        return

    applied = unit.get("pf_bonuses")

    if applied is None:
        # Ancienne pièce : ses bonus sont déjà inclus dans max_pf.
        extra = unit["max_pf"] - UNITS[unit["name"]]["pf"]
        applied = []

        for upgrade, (unit_name, bonus) in PF_UPGRADES.items():
            if unit_name == unit["name"] and extra >= bonus:
                applied.append(upgrade)
                extra -= bonus

        unit["pf_bonuses"] = applied

    owned = g["players"][unit["owner"]].get("upgrades", [])

    for upgrade, (unit_name, bonus) in PF_UPGRADES.items():
        if (
            unit_name == unit["name"]
            and upgrade in owned
            and upgrade not in applied
        ):
            unit["max_pf"] += bonus
            unit["pf"] += bonus
            applied.append(upgrade)


def migrate_units(g):
    """Applique les règles actuelles aux pièces déjà en jeu."""
    for owner in (0, 1):
        taken = {
            e["name"]
            for e in g["entities"]
            if e["owner"] == owner and e["name"] in ELF_HERO_NAMES
        }
        legacy_heroes = sorted(
            (
                e for e in g["entities"]
                if e["owner"] == owner and e["name"] == ELF_HEROES
            ),
            key=lambda e: e["id"],
        )

        for hero in legacy_heroes:
            free = [n for n in ELF_HERO_NAMES if n not in taken]
            if not free:
                break
            hero["name"] = free[0]
            taken.add(free[0])

    for unit in g["entities"]:
        if unit["kind"] != "unit":
            continue

        # Ancien Déferlant marqué kamikaze : devient un vrai Kamikaze.
        if unit.get("kamikaze") and unit["name"] == "Déferlant":
            damage = unit["max_pf"] - unit["pf"]
            unit["name"] = KAMIKAZE
            unit["pf_bonuses"] = []
            unit["max_pf"] = float(UNITS[KAMIKAZE]["pf"])
            unit["pf"] = max(0.5, unit["max_pf"] - damage)

        # Ancienne sauvegarde : un Kamikaze à 1 PF passe à 2 PF.
        if unit["name"] == KAMIKAZE and unit["max_pf"] < UNITS[KAMIKAZE]["pf"]:
            gain = UNITS[KAMIKAZE]["pf"] - unit["max_pf"]
            unit["max_pf"] = float(UNITS[KAMIKAZE]["pf"])
            unit["pf"] = float(unit["pf"]) + gain

        sync_unit_upgrades(g, unit)


def add_unit(g, owner, name, pos):
    if name == ELF_HEROES:
        taken = {
            e["name"]
            for e in g["entities"]
            if e["owner"] == owner and e["name"] in ELF_HERO_NAMES
        }
        name = next(
            (n for n in ELF_HERO_NAMES if n not in taken),
            ELF_HERO_NAMES[-1],
        )

    unit = add_entity(g, owner, name, "unit", pos, UNITS[name]["pf"])
    unit["kamikaze"] = name == KAMIKAZE
    unit["pf_bonuses"] = []
    sync_unit_upgrades(g, unit)
    return unit


_lw_units_previous_tick = tick


def tick(g):
    migrate_units(g)
    _lw_units_previous_tick(g)


_lw_units_previous_purchase_upgrade = purchase_upgrade


def purchase_upgrade(g, owner, name):
    _lw_units_previous_purchase_upgrade(g, owner, name)

    for unit in g["entities"]:
        if unit["owner"] == owner:
            sync_unit_upgrades(g, unit)

    if name in PF_UPGRADES:
        unit_name, bonus = PF_UPGRADES[name]
        log(
            g,
            f"{name} : +{bonus:g} PF pour chaque {unit_name}, "
            "y compris ceux déjà en jeu.",
        )


_lw_units_previous_recruit = recruit


def recruit(g, owner, producer_id, name, positions):
    if not unit_requirement_met(g, owner, name):
        raise ValueError(
            f"Achète d'abord l'amélioration « {UNIT_REQUIREMENTS[name]} » "
            "dans ton bâtiment d'amélioration."
        )

    until = production_blocked_until(g, entity(g, producer_id))
    if until is not None:
        raise ValueError(
            f"Production bloquée par un Décimant jusqu'au tour {until} inclus."
        )

    _lw_units_previous_recruit(g, owner, producer_id, name, positions)


# ------------------------------------------------------------
# Mutations : Déferlant -> Kamikaze, Aspergeur -> Rampant
# ------------------------------------------------------------

def mutate_unit(g, owner, unit_id):
    unit = entity(g, unit_id)

    if unit["owner"] != owner or unit["kind"] != "unit":
        raise ValueError("Choisis une de tes unités.")

    rule = MUTATIONS.get(unit["name"])
    if rule is None:
        raise ValueError("Cette unité ne peut pas muter.")

    new_name, upgrade, cost = rule
    player = g["players"][owner]

    if upgrade not in player.get("upgrades", []):
        raise ValueError(
            f"Achète d'abord l'amélioration « {upgrade} » "
            "dans ton bâtiment d'amélioration."
        )
    if UNIT_AGES.get(new_name, 1) > player["age"]:
        raise ValueError(
            f"{new_name} : débloqué à l'âge {UNIT_AGES[new_name]}."
        )
    if unit["wait"]:
        raise ValueError("Cette unité est déjà en attente.")

    in_battle = g["phase"] == "move"

    if in_battle:
        require_phase(g, "move", owner)
        if not can_move(g, unit):
            raise ValueError("Cette unité a déjà agi ce tour.")
    else:
        require_phase(g, "build", owner)

    count = sum(
        e["owner"] == owner and e["name"] == new_name
        for e in g["entities"]
    )
    if count >= UNITS[new_name]["limit"]:
        raise ValueError(
            f"Limite de {new_name} atteinte "
            f"({UNITS[new_name]['limit']})."
        )

    pay(g, owner, cost)

    damage = unit["max_pf"] - unit["pf"]
    old_name = unit["name"]

    unit["name"] = new_name
    unit["kamikaze"] = new_name == KAMIKAZE
    unit["planted"] = False
    unit["pf_bonuses"] = []
    unit["max_pf"] = float(UNITS[new_name]["pf"])
    sync_unit_upgrades(g, unit)
    unit["pf"] = max(0.5, unit["max_pf"] - damage)

    # La mutation immobilise l'unité pendant un tour complet de manœuvres.
    unit["wait"] = 2 if in_battle else 1

    log(
        g,
        f"{old_name} #{unit['id']} mute en {new_name} : "
        "en attente pendant un tour.",
    )

    if in_battle:
        unit["acted"] = True
        if g.get("moving_unit_id") == unit["id"]:
            g.pop("moving_unit_id")
        next_activation(g)


def battle_mutation(g, unit_id):
    mutate_unit(g, g["active"], unit_id)


def render_mutation_button(view, unit, prefix):
    rule = MUTATIONS.get(unit["name"])
    if rule is None or unit["kind"] != "unit":
        return

    new_name, upgrade, cost = rule
    player = view["players"][unit["owner"]]

    if upgrade not in player.get("upgrades", []):
        st.caption(
            f"🧬 Mutation en {new_name} : achète d'abord "
            f"« {upgrade} » dans ton bâtiment d'amélioration."
        )
        return

    if UNIT_AGES.get(new_name, 1) > player["age"]:
        st.caption(
            f"🧬 Mutation en {new_name} : "
            f"disponible à l'âge {UNIT_AGES[new_name]}."
        )
        return

    if unit["wait"]:
        st.caption(
            f"🧬 Mutation impossible : unité en attente ({unit['wait']})."
        )
        return

    if st.button(
        f"🧬 Muter en {new_name} · {cost} or · attente 1 tour",
        key=f"{prefix}_mutate_{unit['id']}",
    ):
        if view["phase"] == "move":
            perform(game_action, battle_mutation, unit["id"])
        else:
            perform(draft_action, mutate_unit, unit["id"])


# ------------------------------------------------------------
# Dégâts directs et zones
# ------------------------------------------------------------

def flank_cells(target_pos, origin):
    """Cases à gauche et à droite de la cible, vues depuis l'attaquant."""
    target_pos = tuple(target_pos)
    origin = tuple(origin)
    gap = distance(origin, target_pos)

    return [
        pos
        for pos in neighbors(target_pos)
        if pos != origin and distance(origin, pos) == gap
    ]


def age_one_penalty(source, victim):
    """Les unités d'âge I font moitié moins de dégâts au Molosse."""
    return (
        victim.get("name") == MOLOSSE
        and source.get("kind") == "unit"
        and UNIT_AGES.get(source.get("name"), 1) == 1
    )


def halved(value):
    # Moitié arrondie au 0,5 supérieur : les PF restent des multiples de 0,5.
    return math.ceil(value) / 2


def adjusted_damage(source, victim, damage):
    return halved(damage) if age_one_penalty(source, victim) else damage


def apply_damage(g, victim, damage, source, report, role):
    """Dégâts directs, sans riposte."""
    if victim not in g["entities"] or damage <= 0:
        return

    damage = adjusted_damage(source, victim, damage)
    before = float(victim["pf"])
    dealt = min(before, damage)
    victim["pf"] = before - dealt

    report["participants"].append({
        "id": victim["id"],
        "owner": victim["owner"],
        "name": victim["name"],
        "role": role,
        "before": before,
        "damage": dealt,
        "after": victim["pf"],
    })

    if victim["pf"] > 0:
        log(
            g,
            f"{victim['name']} #{victim['id']} : -{dealt:g} PF, "
            f"reste {victim['pf']:g} PF.",
        )
    elif victim["owner"] != source["owner"]:
        destroy(g, victim, source["owner"])
    else:
        # Tir allié : aucun point de victoire pour personne.
        g["entities"].remove(victim)
        log(
            g,
            f"{victim['name']} #{victim['id']} est détruit "
            "par son propre camp.",
        )


_lw_units_previous_combat_values = combat_values


def combat_values(attackers, target):
    if target.get("name") != MOLOSSE:
        return _lw_units_previous_combat_values(attackers, target)

    adjusted = [
        dict(
            attacker,
            pf=adjusted_damage(attacker, target, float(attacker["pf"])),
        )
        for attacker in attackers
    ]
    return _lw_units_previous_combat_values(adjusted, target)


def is_hidden_unit(piece):
    return (
        piece["name"] in INVISIBLE_UNITS
        or (piece["name"] == RAMPANT and piece.get("planted"))
    )


def has_detector_in_range(g, viewer_owner, pos):
    return any(
        e["owner"] == viewer_owner
        and e["name"] in DETECTOR_RANGES
        and distance(tuple(e["pos"]), pos) <= DETECTOR_RANGES[e["name"]]
        for e in g["entities"]
    )


def visible_to_player(g, piece, viewer_owner):
    if piece["owner"] == viewer_owner:
        return True
    if is_hidden_unit(piece):
        return has_detector_in_range(g, viewer_owner, tuple(piece["pos"]))
    return True


_lw_units_previous_ranged_values = ranged_attack_values


def ranged_attack_values(g, attacker, target):
    if attacker["name"] == DECIMANT:
        raise ValueError("Le Décimant n'attaque pas : utilise ses sorts.")
    if attacker["name"] == RAMPANT and not attacker.get("planted"):
        raise ValueError(
            "Le Rampant doit d'abord se planter dans le sol pour attaquer."
        )
    if not visible_to_player(g, target, attacker["owner"]):
        raise ValueError("Cette cible est invisible.")

    values = _lw_units_previous_ranged_values(g, attacker, target)

    if age_one_penalty(attacker, target):
        values = dict(values)
        values["damage"] = halved(values["damage"])
        values["remaining"] = max(
            0.0, float(target["pf"]) - values["damage"]
        )

    return values


_lw_units_previous_prepare_attack = prepare_attack


def prepare_attack(g, attacker_ids, target_id):
    for eid in attacker_ids:
        piece = entity(g, eid)

        if piece["name"] == DECIMANT:
            raise ValueError(
                "Le Décimant n'attaque pas : sélectionne-le seul "
                "pour lancer un sort."
            )
        if piece["name"] == KAMIKAZE and len(attacker_ids) > 1:
            raise ValueError("Un Kamikaze attaque seul.")
        if piece["name"] == RAMPANT and not piece.get("planted"):
            raise ValueError(
                "Le Rampant doit d'abord se planter dans le sol pour attaquer."
            )

    target = entity(g, target_id)
    if not visible_to_player(g, target, g["active"]):
        raise ValueError("Cette cible est invisible.")

    return _lw_units_previous_prepare_attack(g, attacker_ids, target_id)


def second_cell_options(g, owner, flanks):
    return [
        pos
        for pos in flanks
        if at(g, pos) is not None and at(g, pos)["owner"] != owner
    ]


def session_second_cell(target_id):
    """Choix fait dans le menu d'attaque, s'il existe."""
    try:
        choice = st.session_state.get("ui_splash_choice")
    except Exception:
        return None

    if isinstance(choice, dict) and choice.get("target_id") == target_id:
        return choice.get("pos")
    return None


def choose_second_cell(g, owner, flanks, requested, target_id):
    options = second_cell_options(g, owner, flanks)
    if not options:
        return None

    if requested is None:
        requested = session_second_cell(target_id)

    if requested is not None and tuple(requested) in options:
        return tuple(requested)

    return options[0]


def can_trample(unit, target):
    if unit["name"] not in TRAMPLERS:
        return False

    max_age = TRAMPLERS[unit["name"]]
    if max_age is None:
        return True

    return (
        target["kind"] == "unit"
        and UNIT_AGES.get(target["name"], 1) <= max_age
    )


def kamikaze_attack(g, attacker_id, target_id):
    checked, target, routes = prepare_attack(g, [attacker_id], target_id)
    kamikaze = checked[0]
    owner = kamikaze["owner"]
    route = [tuple(p) for p in routes[attacker_id]]
    target_pos = tuple(target["pos"])
    flanks = flank_cells(target_pos, route[-2])

    report = {
        "turn": turn_label(g),
        "position": coord(target_pos),
        "power": 2.0,
        "bonus": 0.0,
        "defense": float(target["pf"]),
        "occupier_id": None,
        "participants": [{
            "id": kamikaze["id"],
            "owner": owner,
            "name": kamikaze["name"],
            "role": "Kamikaze — détruit par l'explosion",
            "before": float(kamikaze["pf"]),
            "damage": float(kamikaze["pf"]),
            "after": 0.0,
        }],
    }

    collect_coins(g, owner, route[1:-1])

    source = dict(kamikaze)
    g["entities"].remove(kamikaze)
    if g.get("moving_unit_id") == attacker_id:
        g.pop("moving_unit_id")

    log(g, f"Kamikaze #{kamikaze['id']} explose en {coord(target_pos)}.")

    apply_damage(g, target, 2.0, source, report, "Cible de l'explosion")

    for pos in flanks:
        for victim in pieces_at(g, pos):
            if victim["owner"] != owner:
                apply_damage(
                    g, victim, 1.0, source, report, "Case voisine de l'explosion"
                )

    g["_combat_report"] = report
    next_activation(g)


_lw_units_previous_attack = attack


def attack(
    g,
    attacker_ids,
    target_id,
    occupier_id=None,
    losses=None,
    second_cell=None,
):
    attackers = [entity(g, eid) for eid in attacker_ids]

    if any(a["name"] == KAMIKAZE for a in attackers):
        if len(attackers) != 1:
            raise ValueError("Un Kamikaze attaque seul.")
        kamikaze_attack(g, attacker_ids[0], target_id)
        return

    checked, target, routes = prepare_attack(g, attacker_ids, target_id)
    owner = g["active"]
    target_pos = tuple(target["pos"])
    splash = []

    for attacker in checked:
        origin = routes[attacker["id"]][-2]
        flanks = flank_cells(target_pos, origin)
        source = {
            "id": attacker["id"],
            "name": attacker["name"],
            "kind": "unit",
            "owner": attacker["owner"],
        }

        if attacker["name"] == ENRAGED:
            # 3 dégâts sur la cible et ses deux voisines, alliés compris.
            splash += [
                {"pos": list(pos), "damage": 3.0,
                 "friendly_fire": True, "source": source}
                for pos in flanks
            ]

        elif attacker["name"] in SECOND_CELL_UNITS:
            chosen = choose_second_cell(
                g, owner, flanks, second_cell, target_id
            )
            if chosen is not None:
                splash.append({
                    "pos": list(chosen),
                    "damage": float(attacker["pf"])
                    + attacker.get("attack_bonus", 0.0),
                    "friendly_fire": False,
                    "source": source,
                })

    trample = None
    if (
        occupier_id is not None
        and combat_values(checked, target)["winnable"]
    ):
        occupier = entity(g, occupier_id)
        if can_trample(occupier, target):
            cost = paths(g, occupier, allow_attack=True)[0].get(target_pos)
            if cost is not None:
                trample = {"unit_id": occupier_id, "cost": cost}

    g["_attack_effects"] = {
        "owner": owner,
        "attackers": list(attacker_ids),
        "splash": splash,
        "trample": trample,
        "dwarves": [a["id"] for a in checked if a["name"] == DWARVES],
        "occupier_id": occupier_id,
        "occupier_origin": (
            list(entity(g, occupier_id)["pos"])
            if occupier_id is not None
            else None
        ),
        # Chemin de l'occupant jusqu'à la cible (case de frappe en avant-dernier).
        "occupier_route": (
            [list(p) for p in routes.get(occupier_id) or []]
            if occupier_id is not None
            else None
        ),
        "destination": list(target_pos),
    }

    try:
        _lw_units_previous_attack(
            g, attacker_ids, target_id, occupier_id, losses
        )
    finally:
        g.pop("_attack_effects", None)


def grant_dwarf_attacks(g, dwarf_id, owner, excluded_ids):
    """Le Nain entraîne 2 unités voisines dans une attaque supplémentaire."""
    dwarf = next((e for e in g["entities"] if e["id"] == dwarf_id), None)
    if dwarf is None:
        return

    helpers = sorted(
        (
            e for e in g["entities"]
            if e["owner"] == owner
            and e["kind"] == "unit"
            and e["id"] not in excluded_ids
            and e["acted"]
            and not e["wait"]
            and distance(tuple(e["pos"]), tuple(dwarf["pos"])) == 1
        ),
        key=lambda e: -e["pf"],
    )[:2]

    for helper in helpers:
        helper["acted"] = False
        helper["extra_attack_turn"] = g["turn"]
        helper["movement_spent_turn"] = g["turn"]
        helper["movement_spent"] = 0
        log(
            g,
            f"Le Nain entraîne {helper['name']} #{helper['id']} "
            "dans une attaque supplémentaire.",
        )


def apply_attack_effects(g, effects):
    """Effets après le combat. Renvoie True si l'unité garde la main."""
    report = g.setdefault("_combat_report", {
        "turn": turn_label(g), "position": "", "power": 0.0,
        "bonus": 0.0, "defense": 0.0, "occupier_id": None,
        "participants": [],
    })
    owner = effects["owner"]

    # Un ouvrier tué dans une pile : l'attaquant ne peut pas rejoindre
    # les ouvriers restants. Il s'arrête sur la dernière case libre de
    # son chemin (au contact de la pile si possible), sinon sur sa case
    # de départ.
    occupier = next(
        (e for e in g["entities"] if e["id"] == effects.get("occupier_id")),
        None,
    )
    if (
        occupier is not None
        and effects.get("destination") is not None
        and tuple(occupier["pos"]) == tuple(effects["destination"])
        and len(pieces_at(g, occupier["pos"])) > 1
    ):
        origin = effects["occupier_origin"]
        route = effects.get("occupier_route") or []
        strike = next(
            (
                p for p in reversed(route[1:-1])
                if at(g, tuple(p)) is None and not blocked(g, tuple(p))
            ),
            origin,
        )
        occupier["pos"] = list(strike)
        log(
            g,
            "D'autres ouvriers tiennent encore la case : "
            f"{occupier['name']} s'arrête en {coord(strike)}.",
        )

    for hit in effects["splash"]:
        for victim in pieces_at(g, hit["pos"]):
            if not hit["friendly_fire"] and victim["owner"] == owner:
                continue
            apply_damage(
                g, victim, hit["damage"], hit["source"], report,
                f"Dégâts de zone ({hit['source']['name']})",
            )

    for dwarf_id in effects["dwarves"]:
        grant_dwarf_attacks(g, dwarf_id, owner, effects["attackers"])

    check_victory(g)
    trample = effects["trample"]

    if g["winner"] is not None or trample is None:
        return False

    unit = next(
        (e for e in g["entities"] if e["id"] == trample["unit_id"]),
        None,
    )
    if unit is None or unit["pf"] <= 0:
        return False

    unit["movement_spent"] = movement_spent(g, unit) + trample["cost"]
    unit["movement_spent_turn"] = g["turn"]
    remaining = remaining_actions(g, unit)

    if remaining <= 0:
        return False

    # Piétinement : l'unité continue tant qu'il lui reste
    # des déplacements et des PF.
    unit["acted"] = False
    g["moving_unit_id"] = unit["id"]
    g["_ui_message"] = (
        f"Piétinement : {unit['name']} #{unit['id']} peut encore agir "
        f"avec {remaining} déplacement(s) restant(s)."
    )
    log(g, f"{unit['name']} #{unit['id']} piétine et poursuit son action.")
    return True


_lw_units_previous_next_activation = next_activation


def next_activation(g, switch=True):
    effects = g.pop("_attack_effects", None)

    if effects is not None and apply_attack_effects(g, effects):
        return

    _lw_units_previous_next_activation(g, switch=switch)


_lw_units_previous_move_unit = move_unit


def move_unit(g, eid, destination):
    unit = entity(g, eid)

    if unit.get("planted"):
        raise ValueError(
            "Ce Rampant est planté : sors-le du sol pour le déplacer."
        )
    if unit.get("extra_attack_turn") == g["turn"]:
        raise ValueError(
            "Attaque supplémentaire du Nain : "
            "cette unité peut seulement attaquer."
        )

    _lw_units_previous_move_unit(g, eid, destination)


_lw_units_previous_move_preview = move_preview


def move_preview(g, unit):
    if unit is not None and (
        unit.get("planted")
        or unit.get("extra_attack_turn") == g["turn"]
    ):
        return {}, {}
    return _lw_units_previous_move_preview(g, unit)


# ------------------------------------------------------------
# Rampant : se planter pour devenir invisible
# ------------------------------------------------------------

def plant_rampant(g, unit_id):
    require_phase(g, "move")
    unit = entity(g, unit_id)

    if unit["name"] != RAMPANT or unit["owner"] != g["active"]:
        raise ValueError("Choisis un de tes Rampants.")
    if unit.get("planted"):
        raise ValueError("Ce Rampant est déjà planté.")
    if not can_move(g, unit):
        raise ValueError("Ce Rampant ne peut plus agir ce tour.")

    unit["planted"] = True
    # Se planter termine son activation : il ne pourra tirer qu'à une
    # activation suivante, déjà planté.
    unit["acted"] = True
    if g.get("moving_unit_id") == unit["id"]:
        g.pop("moving_unit_id")

    log(g, f"Rampant #{unit['id']} se plante dans le sol.")
    g["_ui_message"] = (
        "Rampant planté : invisible pour l'adversaire. "
        "Il pourra tirer à sa prochaine activation."
    )
    next_activation(g)


def unplant_rampant(g, unit_id):
    require_phase(g, "move")
    unit = entity(g, unit_id)

    if unit["name"] != RAMPANT or unit["owner"] != g["active"]:
        raise ValueError("Choisis un de tes Rampants.")
    if not unit.get("planted"):
        raise ValueError("Ce Rampant n'est pas planté.")
    if not can_move(g, unit):
        raise ValueError("Ce Rampant ne peut plus agir ce tour.")

    unit["planted"] = False
    unit["acted"] = True
    if g.get("moving_unit_id") == unit["id"]:
        g.pop("moving_unit_id")

    log(g, f"Rampant #{unit['id']} sort du sol et redevient visible.")
    next_activation(g)


# ------------------------------------------------------------
# Décimant : sorts, pas d'attaque
# ------------------------------------------------------------

def decimant_targets(g, decimant, spell):
    kind = "building" if spell == "block" else "unit"

    return [
        piece
        for piece in g["entities"]
        if piece["owner"] != decimant["owner"]
        and piece["kind"] == kind
        and distance(tuple(piece["pos"]), tuple(decimant["pos"]))
        <= DECIMANT_RANGE
        and visible_to_player(g, piece, decimant["owner"])
    ]


def attraction_cell(g, decimant, target):
    free = [
        pos
        for pos in neighbors(tuple(decimant["pos"]))
        if at(g, pos) is None
        and terrain(g, pos) != "sea"
        and (terrain(g, pos) != "mountain" or is_flying(target))
    ]
    if not free:
        return None
    return min(free, key=lambda pos: (distance(pos, tuple(target["pos"])), pos))


def cast_decimant_spell(g, decimant_id, spell, target_id):
    require_phase(g, "move")
    decimant = entity(g, decimant_id)

    if decimant["name"] != DECIMANT or decimant["owner"] != g["active"]:
        raise ValueError("Choisis un de tes Décimants.")
    if not can_move(g, decimant):
        raise ValueError("Ce Décimant ne peut plus agir ce tour.")
    if spell not in DECIMANT_SPELLS:
        raise ValueError("Sort inconnu.")

    target = entity(g, target_id)
    if target not in decimant_targets(g, decimant, spell):
        raise ValueError(
            "Cible invalide : ennemie, visible et à 4 cases maximum."
        )

    if spell == "block":
        decimant["acted"] = True
        if g.get("moving_unit_id") == decimant["id"]:
            g.pop("moving_unit_id")
        target["blocked_until_turn"] = g["turn"] + DECIMANT_BLOCK_TURNS
        log(
            g,
            f"Le Décimant bloque la production de {target['name']} "
            f"#{target['id']} jusqu'au tour {target['blocked_until_turn']}.",
        )
        next_activation(g)
        return

    destination = attraction_cell(g, decimant, target)
    if destination is None:
        raise ValueError("Aucune case libre à côté du Décimant.")

    decimant["acted"] = True
    if g.get("moving_unit_id") == decimant["id"]:
        g.pop("moving_unit_id")

    origin = coord(target["pos"])
    target["pos"] = list(destination)
    log(
        g,
        f"Le Décimant attire {target['name']} #{target['id']} "
        f"de {origin} vers {coord(destination)}.",
    )
    g["_ui_message"] = (
        f"{target['name']} attiré en {coord(destination)}. "
        "Rejoue immédiatement avec une autre unité pour l'achever."
    )
    # Le même joueur rejoue aussitôt.
    next_activation(g, switch=False)


_lw_units_previous_attack_map_preview = attack_map_preview


def attack_map_preview(g, attackers):
    if len(attackers) == 1 and attackers[0]["name"] == DECIMANT:
        decimant = attackers[0]
        if not can_move(g, decimant):
            return set(), {}

        origin = tuple(decimant["pos"])
        zone = {
            pos for pos in CELLS
            if 1 <= distance(origin, pos) <= DECIMANT_RANGE
        }
        targets = {}

        for spell in DECIMANT_SPELLS:
            for piece in decimant_targets(g, decimant, spell):
                targets[tuple(piece["pos"])] = {
                    "target_id": piece["id"],
                    "spell": True,
                    "ranged": True,
                    "distance": distance(origin, tuple(piece["pos"])),
                }

        return zone, targets

    return _lw_units_previous_attack_map_preview(g, attackers)


# ------------------------------------------------------------
# Interface des manœuvres
# ------------------------------------------------------------

def current_target(g):
    return next(
        (
            piece for piece in g["entities"]
            if piece["id"] == st.session_state.get("ui_target_id")
            and piece["owner"] != g["active"]
        ),
        None,
    )


def render_decimant_controls(g, decimant, prefix):
    st.subheader("🔮 Sorts du Décimant")
    st.caption(
        "Aucune attaque. Portée 4 cases. Il révèle aussi les unités "
        "invisibles à 4 cases."
    )

    if not can_move(g, decimant):
        st.info("Ce Décimant a déjà agi ce tour.")
        return

    # La cible cliquée choisit le sort : bâtiment -> blocage, unité -> attraction.
    clicked_piece = next(
        (e for e in g["entities"] if e["id"] == st.session_state.get("ui_target_id")),
        None,
    )
    spells = list(DECIMANT_SPELLS)
    spell = st.radio(
        "Sort",
        options=spells,
        index=spells.index("attract") if clicked_piece and clicked_piece["kind"] == "unit" else 0,
        format_func=DECIMANT_SPELLS.get,
        key=f"{prefix}_decimant_spell",
    )

    candidates = {
        piece["id"]: piece
        for piece in decimant_targets(g, decimant, spell)
    }
    if not candidates:
        st.info("Aucune cible à portée pour ce sort.")
        return

    options = list(candidates)
    clicked = st.session_state.get("ui_target_id")
    target_id = st.selectbox(
        "Cible",
        options=options,
        index=options.index(clicked) if clicked in candidates else 0,
        format_func=lambda eid: describe(candidates[eid]),
        key=f"{prefix}_decimant_{spell}_target",
    )

    disabled = False
    if spell == "attract":
        cell = attraction_cell(g, decimant, candidates[target_id])
        if cell is None:
            st.warning("Aucune case libre à côté du Décimant.")
            disabled = True
        else:
            st.caption(
                f"L'unité sera attirée en {coord(cell)}. "
                "Tu rejoues aussitôt avec une autre unité."
            )

    st.caption("Clique sur la cible sur le plateau : le sort part aussitôt.")
    if (
        not disabled
        and clicked in candidates
        and target_id == clicked
        and auto_confirm("decimant", decimant["id"], spell, target_id)
    ):
        perform(
            game_action,
            cast_decimant_spell,
            decimant["id"],
            spell,
            target_id,
        )


def render_rampant_controls(g, unit, prefix):
    if unit.get("planted"):
        st.success(
            "🌱 Rampant planté : invisible pour l'adversaire, "
            "sauf détecteur à portée. Il peut tirer."
        )
        if st.button(
            "Sortir du sol (termine son activation)",
            key=f"{prefix}_unplant_{unit['id']}",
        ):
            perform(game_action, unplant_rampant, unit["id"])
    else:
        st.info(
            "🌱 Le Rampant doit être planté pour attaquer. Planté, il ne "
            "peut plus se déplacer mais devient invisible. Il peut se "
            "planter et tirer dans le même tour."
        )
        if st.button(
            "🌱 Se planter dans le sol",
            type="primary",
            key=f"{prefix}_plant_{unit['id']}",
        ):
            perform(game_action, plant_rampant, unit["id"])


def render_kamikaze_controls(g, unit, target, prefix):
    st.markdown(f"### 💥 Explosion sur {target['name']}")

    try:
        _, _, routes = prepare_attack(g, [unit["id"]], target["id"])
    except ValueError as exc:
        st.warning(str(exc))
        return

    flanks = flank_cells(tuple(target["pos"]), routes[unit["id"]][-2])
    st.info(
        f"Le Kamikaze explose : -2 PF sur {target['name']} "
        f"({coord(target['pos'])}), -1 PF aux ennemis en "
        + (" et ".join(coord(pos) for pos in flanks) or "—")
        + ". Le Kamikaze est détruit."
    )

    if st.button(
        "💥 Confirmer l'explosion",
        type="primary",
        key=f"{prefix}_kamikaze_{target['id']}",
    ):
        perform(game_action, attack, [unit["id"]], target["id"])


def render_zone_preview(g, attackers, target, prefix):
    """Aperçu des dégâts de zone et choix de la 2ᵉ case."""
    if len(attackers) == 1 and UNITS[attackers[0]["name"]]["range"] > 0:
        # Un tireur seul : aperçu géré avec son tir.
        return

    try:
        _, _, routes = prepare_attack(
            g, [a["id"] for a in attackers], target["id"]
        )
    except ValueError:
        return

    st.session_state.ui_splash_choice = None

    for attacker in attackers:
        flanks = flank_cells(
            tuple(target["pos"]), routes[attacker["id"]][-2]
        )

        if attacker["name"] == ENRAGED:
            st.warning(
                "😡 Enragé : les cases "
                + " et ".join(coord(pos) for pos in flanks)
                + " subiront aussi 3 dégâts, alliés compris."
            )

        elif attacker["name"] in SECOND_CELL_UNITS:
            options = second_cell_options(g, g["active"], flanks)

            if not options:
                st.caption(
                    f"{attacker['name']} : aucune 2ᵉ case ennemie à côté "
                    "de la cible."
                )
            else:
                chosen = st.selectbox(
                    f"2ᵉ case touchée par {attacker['name']} "
                    f"({attacker['pf']:g} dégâts, ennemis uniquement)",
                    options=options,
                    format_func=lambda pos: (
                        f"{coord(pos)} — {at(g, pos)['name']}"
                    ),
                    key=(
                        f"{prefix}_second_cell_"
                        f"{attacker['id']}_{target['id']}"
                    ),
                )
                st.session_state.ui_splash_choice = {
                    "target_id": target["id"],
                    "pos": list(chosen),
                }

        if can_trample(attacker, target):
            st.caption(
                f"Piétinement : si {attacker['name']} gagne et prend la "
                "case, il pourra continuer avec ses déplacements restants."
            )

    if target.get("name") == MOLOSSE:
        st.caption(
            "Molosse : les unités d'âge I ne lui font que 50 % de dégâts."
        )


_lw_units_previous_render_move_controls = render_move_controls


def render_previous_move_controls_without_target(g):
    saved = st.session_state.get("ui_target_id")
    st.session_state.ui_target_id = None
    try:
        _lw_units_previous_render_move_controls(g)
    finally:
        st.session_state.ui_target_id = saved


def render_move_controls(g):
    attackers = selected_attackers(g)
    target = current_target(g)
    prefix = (
        f"units_{g['turn']}_{g['active']}_"
        f"{st.session_state.ui_revision}"
    )

    if len(attackers) == 1:
        unit = attackers[0]

        if unit.get("extra_attack_turn") == g["turn"]:
            st.info(
                "⚒️ Attaque supplémentaire accordée par le Nain "
                "des montagnes : cette unité peut seulement attaquer."
            )

        render_mutation_button(g, unit, prefix)

        if unit["name"] == DECIMANT:
            render_decimant_controls(g, unit, prefix)
            render_previous_move_controls_without_target(g)
            return

        if unit["name"] == RAMPANT:
            render_rampant_controls(g, unit, prefix)

        if unit["name"] == KAMIKAZE and target is not None:
            render_kamikaze_controls(g, unit, target, prefix)
            render_previous_move_controls_without_target(g)
            return

    if attackers and target is not None:
        render_zone_preview(g, attackers, target, prefix)

    _lw_units_previous_render_move_controls(g)


# ============================================================
# FACTION : LES DERNIERS NÉS
# À laisser APRÈS toutes les autres définitions,
# juste avant : if __name__ == "__main__":
# ============================================================

WORKER = "Ouvrier"
WARRIOR = "Guerrier"
SCOUT = "Éclaireur"
KNIGHT = "Chevalier"
ARCHER = "Archer"
CATAPULT = "Catapulte"
TREBUCHET = "Trébuchet"
HELL_CATAPULT = "Catapulte de l'enfer"
AIRSHIP = "Dirigeable"
GRIFFON = "Griffon"
KING = "Roi Théobald"

WORKER_LIMIT = 36
AIRSHIP_CAPACITY = 3
AIRSHIP_RANGE = 4
AIRSHIP_BOOST = 2.0

# Colonie -> Ville (âge II) -> Forteresse (âge III).
BASE_LEVEL_DATA = {
    "Colonie": {"level": 1, "pf": 2, "cost": 250, "age": 1, "workers": 1, "worker_cost": 50},
    "Ville": {"level": 2, "pf": 4, "cost": 250, "age": 2, "workers": 2, "worker_cost": 100},
    "Forteresse": {"level": 3, "pf": 6, "cost": 300, "age": 3, "workers": 3, "worker_cost": 150},
}
BASE_LEVELS = list(BASE_LEVEL_DATA)

# Récolte selon le nombre d'ouvriers sur les ressources voisines
# (plafonné par le niveau de la base).
DN_GOLD_BY_WORKERS = {1: 150, 2: 250, 3: 300}
DN_MANA_BY_WORKERS = {1: 1, 2: 2, 3: 3}

FACTIONS[DERNIERS_NES] = {
    "name": "Derniers nés",
    "base": "Colonie",
    "base_cost": 250,
    "base_pf": 2,
    "income": 150,
    "base_levels": BASE_LEVELS,
    "extra_units": [WORKER],
    "buildings": {
        "Caserne": {
            "cost": 100, "mana": 0, "pf": 2, "limit": 3,
            "units": [WARRIOR, SCOUT],
        },
        "Forge": {
            "cost": 200, "mana": 0, "pf": 2, "limit": 1,
            "units": [],
        },
        "Écurie": {
            "cost": 300, "mana": 0, "pf": 4, "limit": 2,
            "units": [KNIGHT, KING],
        },
        "Archerie": {
            "cost": 200, "mana": 0, "pf": 4, "limit": 2,
            "units": [ARCHER],
        },
        "Atelier de siège": {
            "cost": 250, "mana": 0, "pf": 4, "limit": 2,
            "units": [CATAPULT, AIRSHIP, HELL_CATAPULT],
        },
        "Réserve naturelle": {
            "cost": 500, "mana": 1, "pf": 4, "limit": 3,
            "units": [GRIFFON],
        },
    },
}

BUILDING_AGES.update({
    (DERNIERS_NES, "Caserne"): 1,
    (DERNIERS_NES, "Forge"): 1,
    (DERNIERS_NES, "Écurie"): 2,
    (DERNIERS_NES, "Archerie"): 2,
    (DERNIERS_NES, "Atelier de siège"): 2,
    (DERNIERS_NES, "Réserve naturelle"): 3,
})
AGE_PREREQUISITES[(DERNIERS_NES, 2)] = "Caserne"
AGE_PREREQUISITES[(DERNIERS_NES, 3)] = "Atelier de siège"
BASE_COST_BY_AGE.update({(DERNIERS_NES, age): 250 for age in (1, 2, 3)})
TECH_BUILDINGS[DERNIERS_NES] = "Forge"

UNITS.update({
    WORKER: {"cost": 50, "mana": 0, "batch": 1, "pf": 1, "move": 5, "range": 0, "limit": WORKER_LIMIT},
    WARRIOR: {"cost": 200, "mana": 0, "batch": 1, "pf": 2, "move": 3, "range": 0, "limit": 12},
    SCOUT: {"cost": 250, "mana": 0, "batch": 1, "pf": 1.5, "move": 7, "range": 0, "limit": 4},
    KNIGHT: {"cost": 400, "mana": 2, "batch": 1, "pf": 4, "move": 5, "range": 0, "limit": 5},
    ARCHER: {"cost": 300, "mana": 0, "batch": 1, "pf": 3, "move": 3, "range": 3, "limit": 6},
    CATAPULT: {"cost": 450, "mana": 1, "batch": 1, "pf": 3, "move": 2, "range": 4, "limit": 2},
    # Immobile : son unique point d'action sert à tirer.
    TREBUCHET: {"cost": 450, "mana": 1, "batch": 1, "pf": 3, "move": 1, "range": 5, "limit": 2},
    AIRSHIP: {"cost": 350, "mana": 2, "batch": 1, "pf": 6, "move": 5, "range": AIRSHIP_RANGE, "limit": 2},
    GRIFFON: {"cost": 600, "mana": 2, "batch": 1, "pf": 10, "move": 4, "range": 3, "limit": 6},
    HELL_CATAPULT: {"cost": 550, "mana": 2, "batch": 1, "pf": 6, "move": 2, "range": 5, "limit": 5},
    KING: {"cost": 1000, "mana": 5, "batch": 1, "pf": 8, "move": 5, "range": 0, "limit": 1},
})
UNIT_AGES.update({
    WORKER: 1, WARRIOR: 1, SCOUT: 1,
    KNIGHT: 2, ARCHER: 2, CATAPULT: 2, TREBUCHET: 2, AIRSHIP: 2,
    GRIFFON: 3, HELL_CATAPULT: 3, KING: 3,
})
# À l'âge III, l'Atelier de siège ne produit plus de Catapulte classique
# (Catapulte de l'enfer et Dirigeable seulement).
UNIT_MAX_AGES = {CATAPULT: 2}
UNIT_ENTITY_SOURCES[TREBUCHET] = CATAPULT

UPGRADES.update({
    "Marteau foudroyant": {
        "owner": DERNIERS_NES, "cost": 150, "mana": 0,
        "building": "Forge", "age": 1,
        "effect": "+0,5 PF pour les attaques des Guerriers.",
    },
    "Esquive": {
        "owner": DERNIERS_NES, "cost": 150, "mana": 0,
        "building": "Forge", "age": 1,
        "effect": "Un Éclaireur traverse les unités ennemies sans dégâts.",
    },
    "Flèches enflammées": {
        "owner": DERNIERS_NES, "cost": 300, "mana": 2,
        "building": "Forge", "age": 2,
        "effect": "Les Archers touchent 2 cases voisines au lieu d'une.",
    },
    "Trébuchet": {
        "owner": DERNIERS_NES, "cost": 350, "mana": 2,
        "building": "Forge", "age": 2,
        "effect": "La Catapulte peut se transformer en Trébuchet (tir à 4-5 cases, immobile).",
    },
    "Invisibilité griffons": {
        "owner": DERNIERS_NES, "cost": 600, "mana": 4,
        "building": "Forge", "age": 3,
        "effect": "Les Griffons deviennent invisibles, sauf détecteur à portée.",
    },
    "Pierres enflammées": {
        "owner": DERNIERS_NES, "cost": 600, "mana": 3,
        "building": "Forge", "age": 3,
        "effect": "+2 PF de dégâts pour les catapultes et catapultes de l'enfer.",
    },
})

# Bonus d'attaque (pas de défense), effectifs aussi pour les unités en jeu.
ATTACK_UPGRADES = {"Marteau foudroyant": (WARRIOR, 0.5)}

FLYING_UNITS.update({AIRSHIP, GRIFFON})
DETECTOR_RANGES[AIRSHIP] = AIRSHIP_RANGE
INVISIBLE_UNITS.add(KING)
SECOND_CELL_UNITS.add(WARRIOR)
TRAMPLERS.update({KNIGHT: None, KING: 2})
IMMOBILE_UNITS = {TREBUCHET}
NO_ATTACK_UNITS = {WORKER, AIRSHIP}

# Tir de siège : (portée minimale, portée maximale).
SIEGE_RANGES = {CATAPULT: (3, 4), TREBUCHET: (4, 5), HELL_CATAPULT: (3, 5)}
SIEGE_DAMAGE = 4.0
SIEGE_SIDE_DAMAGE = 2.0
SIEGE_RELOAD_TURNS = 2

AIRSHIP_SPELLS = {
    "boost": "💪 +2 PF sur une unité alliée et ses 2 voisines pendant 1 tour",
    "harvest": "💰 Doubler la prochaine récolte d'une de tes bases",
}

AGE_REFERENCE["Derniers nés"] = {
    1: [
        ("Colonie", "Base · 250 or · 2 PF · arrive avec 1 ouvrier · produit 1 ouvrier (50 or)"),
        ("Ouvrier", "1 PF · 5 cases · se déplace en production · construit bâtiments et bases · récolte"),
        ("Caserne", "Bâtiment · 100 or · 2 PF · ×3 · passage à l'âge II"),
        ("Guerrier", "200 or · 2 PF · 3 cases · touche 2 cases (ennemis)"),
        ("Éclaireur", "250 or · 1,5 PF · 7 cases · ×4 · sabote une base ennemie"),
        ("Forge", "Bâtiment technique · 200 or · améliorations"),
        ("Marteau foudroyant", "150 or · +0,5 PF aux attaques des Guerriers"),
        ("Esquive", "150 or · l'Éclaireur traverse les ennemis"),
    ],
    2: [
        ("Ville", "Amélioration de colonie · 250 or · 4 PF · produit 2 ouvriers (100 or)"),
        ("Écurie", "Bâtiment · 4 PF · ×2 · Chevaliers"),
        ("Chevalier", "400 or + 2 mana · 4 PF · 5 cases · piétinement"),
        ("Archerie", "Bâtiment · 200 or · 4 PF · ×2"),
        ("Archer", "300 or · 3 PF · portée 1 à 3"),
        ("Atelier de siège", "Bâtiment · 250 or · 4 PF · ×2 · passage à l'âge III"),
        ("Catapulte", "450 or + 1 mana · tir à 3-4 cases · 4 PF + 2 PF à gauche et à droite · 1 tir / 2 tours"),
        ("Dirigeable", "350 or + 2 mana · 6 PF · transporte 3 unités · sorts · détecte les invisibles"),
        ("Flèches enflammées", "300 or + 2 mana · les Archers touchent 2 cases"),
        ("Trébuchet", "350 or + 2 mana · Catapulte → Trébuchet (4-5 cases)"),
    ],
    3: [
        ("Forteresse", "Amélioration de ville · 300 or · 6 PF · produit 3 ouvriers (150 or)"),
        ("Réserve naturelle", "Bâtiment · 500 or + 1 mana · 4 PF · ×3"),
        ("Griffon", "600 or + 2 mana · volant · 10 PF · tir à 3 cases sur 2 cases"),
        ("Catapulte de l'enfer", "550 or + 2 mana · 6 PF · tir à 3-5 cases"),
        ("Roi Théobald", "1000 or + 5 mana · 8 PF · invisible · piétinement âges I et II"),
        ("Invisibilité griffons", "600 or + 4 mana"),
        ("Pierres enflammées", "600 or + 3 mana · +2 PF aux catapultes"),
    ],
}


def faction_base_names(faction):
    return faction.get("base_levels", [faction["base"]])


def base_initial_pf(g, base):
    if base["name"] in BASE_LEVEL_DATA:
        return BASE_LEVEL_DATA[base["name"]]["pf"]
    fid = faction_id(g, base["owner"])
    return BASE_PF_BY_AGE[(fid, g["players"][base["owner"]]["age"])]


def owns_upgrade(g, owner, name):
    return name in g["players"][owner].get("upgrades", [])


_lw_dn_previous_unit_requirement_met = unit_requirement_met


def unit_requirement_met(g, owner, name):
    return (
        _lw_dn_previous_unit_requirement_met(g, owner, name)
        and g["players"][owner]["age"] <= UNIT_MAX_AGES.get(name, 3)
    )


_lw_dn_previous_sync_unit_upgrades = sync_unit_upgrades


def sync_unit_upgrades(g, unit):
    _lw_dn_previous_sync_unit_upgrades(g, unit)

    if unit["kind"] != "unit":
        return

    bonus = sum(
        value
        for upgrade, (unit_name, value) in ATTACK_UPGRADES.items()
        if unit_name == unit["name"] and owns_upgrade(g, unit["owner"], upgrade)
    )
    if bonus:
        unit["attack_bonus"] = bonus


_lw_dn_previous_combat_values = combat_values


def combat_values(attackers, target):
    boosted = [
        dict(a, pf=float(a["pf"]) + a.get("attack_bonus", 0.0))
        if a.get("attack_bonus")
        else a
        for a in attackers
    ]
    return _lw_dn_previous_combat_values(boosted, target)


def is_hidden_unit(piece):
    return (
        piece["name"] in INVISIBLE_UNITS
        or (piece["name"] == RAMPANT and piece.get("planted"))
    )


def visible_to_player(g, piece, viewer_owner):
    if piece["owner"] == viewer_owner:
        return True

    hidden = is_hidden_unit(piece) or (
        piece["name"] == GRIFFON
        and owns_upgrade(g, piece["owner"], "Invisibilité griffons")
    )
    if hidden:
        return has_detector_in_range(g, viewer_owner, tuple(piece["pos"]))
    return True


# ------------------------------------------------------------
# Départ : 4 colonies + 4 ouvriers sur les cases d'or ×1
# ------------------------------------------------------------

def place_starting_workers(g, owner):
    bases = [
        tuple(e["pos"]) for e in g["entities"]
        if e["owner"] == owner and e["kind"] == "base"
    ]
    gold_cells = [
        pos for pos in CELLS
        if g["resources"].get(key(pos)) == ["gold", 1]
        and at(g, pos) is None
        and not blocked(g, pos)
    ]
    gold_cells.sort(
        key=lambda pos: (min(distance(pos, b) for b in bases), pos)
    )

    for pos in gold_cells[:4]:
        add_unit(g, owner, WORKER, pos)


_lw_dn_previous_new_game = new_game


def new_game(first, target, minutes, victory_mode="time", factions=(DEFERLANTS, EXILES)):
    g = _lw_dn_previous_new_game(first, target, minutes, victory_mode, factions)

    for owner in (0, 1):
        if faction_id(g, owner) == DERNIERS_NES:
            place_starting_workers(g, owner)

    return g


# ------------------------------------------------------------
# Ouvriers : déplacement en production, construction, récolte
# ------------------------------------------------------------

def worker_count(g, owner):
    return sum(
        e["owner"] == owner and e["name"] == WORKER
        for e in g["entities"]
    )


def worker_destinations(g, worker):
    # Bloqué tant que sa construction n'est pas finie.
    if worker["wait"] or remaining_actions(g, worker) <= 0:
        return {}

    costs, _ = paths(g, worker)
    return {
        pos: cost
        for pos, cost in costs.items()
        if pos != tuple(worker["pos"])
        and can_worker_stop(g, worker["owner"], pos, worker["id"])
    }


def move_worker(g, owner, unit_id, destination):
    require_phase(g, "build", owner)
    worker = entity(g, unit_id)
    destination = require_position(destination)

    if worker["owner"] != owner or worker["name"] != WORKER:
        raise ValueError("Choisis un de tes ouvriers.")
    if worker["wait"]:
        raise ValueError(
            f"Cet ouvrier construit encore : bloqué pendant "
            f"{worker['wait']} fin(s) de tour."
        )
    options = worker_destinations(g, worker)
    if destination not in options:
        raise ValueError("Destination inaccessible ou occupée.")

    origin = coord(worker["pos"])
    worker["pos"] = list(destination)
    worker["worker_moved_turn"] = g["turn"]
    # Déplacement en plusieurs fois : on décompte seulement ce qui a été utilisé.
    worker["movement_spent"] = movement_spent(g, worker) + options[destination]
    worker["movement_spent_turn"] = g["turn"]
    log(g, f"Ouvrier #{worker['id']} : {origin} → {coord(destination)}.")


def worker_build_slots(g, worker, name):
    owner = worker["owner"]
    faction = faction_of(g, owner)

    if worker["used"] or worker["wait"]:
        return []
    if name != faction["base"] and (
        name not in faction["buildings"]
        or not building_is_available(g, owner, name)
    ):
        return []

    return [
        pos for pos in neighbors(tuple(worker["pos"]))
        if at(g, pos) is None
        and not blocked(g, pos)
        and key(pos) not in g["resources"]
    ]


def spawn_colony_worker(g, owner, base):
    """La nouvelle colonie arrive avec un ouvrier posé sur l'or ou le mana."""
    if worker_count(g, owner) >= WORKER_LIMIT:
        return

    free = worker_slots(g, base)
    on_resource = sorted(
        (pos for pos in free if key(pos) in g["resources"]),
        key=lambda pos: (g["resources"][key(pos)][0] != "gold", pos),
    )
    choices = on_resource or free

    if choices:
        worker = add_unit(g, owner, WORKER, choices[0])
        log(g, f"Un ouvrier s'installe en {coord(worker['pos'])}.")


def worker_build(g, owner, worker, name, pos, accelerated):
    faction = faction_of(g, owner)

    if worker["name"] != WORKER or worker["owner"] != owner:
        raise ValueError("Chez les Derniers nés, ce sont les ouvriers qui construisent.")
    if worker["wait"]:
        raise ValueError("Cet ouvrier n'est pas encore disponible.")
    if worker["used"]:
        raise ValueError("Cet ouvrier a déjà construit ce tour.")
    if distance(tuple(worker["pos"]), pos) != 1:
        raise ValueError("L'ouvrier construit sur une case voisine.")
    if at(g, pos) or blocked(g, pos):
        raise ValueError("Case occupée, montagne ou mer.")
    if key(pos) in g["resources"]:
        raise ValueError("Construction interdite sur une ressource.")

    if name == faction["base"]:
        if accelerated:
            raise ValueError("Les bases ne peuvent pas être accélérées.")
        pf = BASE_LEVEL_DATA[name]["pf"]
        wait = 2
        kind = "base"
    else:
        data = faction["buildings"].get(name)
        if data is None:
            raise ValueError("Construction inconnue.")
        if not building_is_available(g, owner, name):
            raise ValueError("Ce bâtiment est débloqué à un âge supérieur.")
        count = sum(
            piece["owner"] == owner and piece["name"] == name
            for piece in g["entities"]
        )
        if count >= data["limit"]:
            raise ValueError("Limite de bâtiments atteinte.")
        pf = data["pf"]
        wait = 0 if accelerated else 1
        kind = "building"

    cost, mana_cost = placement_cost(g, owner, "build", name, [pos], accelerated)
    pay(g, owner, cost, mana_cost)
    piece = add_entity(g, owner, name, kind, pos, pf, wait)
    worker["used"] = True
    # L'ouvrier reste bloqué aussi longtemps que la construction.
    worker["wait"] = wait
    log(g, f"Un ouvrier construit {name} en {coord(pos)}.")

    if kind == "base":
        spawn_colony_worker(g, owner, piece)


_lw_dn_previous_build = build


def build(g, owner, source_id, name, pos, accelerated):
    require_phase(g, "build", owner)
    source = entity(g, source_id)

    until = production_blocked_until(g, source)
    if until is not None:
        raise ValueError(f"Production bloquée jusqu'au tour {until} inclus.")

    if faction_id(g, owner) != DERNIERS_NES:
        return _lw_dn_previous_build(g, owner, source_id, name, pos, accelerated)

    worker_build(g, owner, source, name, require_position(pos), accelerated)


def worker_batch(g, base):
    data = BASE_LEVEL_DATA.get(base["name"])
    if data is None:
        return 0
    free = WORKER_LIMIT - worker_count(g, base["owner"])
    return max(0, min(data["workers"], free))


def produce_workers(g, owner, base_id, positions):
    require_phase(g, "build", owner)
    base = entity(g, base_id)

    if (
        base["owner"] != owner
        or base["kind"] != "base"
        or base["name"] not in BASE_LEVEL_DATA
    ):
        raise ValueError("Seules les colonies, villes et forteresses produisent des ouvriers.")
    if base["wait"] or base["used"]:
        raise ValueError("Cette base est inactive ou a déjà produit ce tour.")

    until = production_blocked_until(g, base)
    if until is not None:
        raise ValueError(f"Production bloquée jusqu'au tour {until} inclus.")

    batch = worker_batch(g, base)
    if batch == 0:
        raise ValueError(f"Limite de {WORKER_LIMIT} ouvriers atteinte.")

    positions = [require_position(p) for p in positions]
    if len(positions) != batch or len(set(positions)) != batch:
        raise ValueError(f"Sélectionne {batch} case(s) distincte(s).")

    slots = set(worker_slots(g, base))
    if any(pos not in slots for pos in positions):
        raise ValueError("Choisis des cases libres à côté de la base.")

    pay(g, owner, UNITS[WORKER]["cost"] * batch)

    for pos in positions:
        add_unit(g, owner, WORKER, pos)

    base["used"] = True
    log(g, f"{base['name']} produit {batch} ouvrier(s).")


_lw_dn_previous_recruit = recruit


def recruit(g, owner, producer_id, name, positions):
    if name == WORKER:
        produce_workers(g, owner, producer_id, positions)
        return

    if not unit_requirement_met(g, owner, name):
        if name in UNIT_MAX_AGES:
            raise ValueError(f"{name} n'est plus produit à cet âge.")
    _lw_dn_previous_recruit(g, owner, producer_id, name, positions)


def selected_worker_source():
    try:
        view = st.session_state.bundle.get("draft") or st.session_state.bundle["game"]
        return selected_entity(view), view
    except Exception:
        return None, None


_lw_dn_previous_recruitment_batch = recruitment_batch


def recruitment_batch(g, owner, name):
    if name == WORKER:
        source, _ = selected_worker_source()
        if source is not None and source.get("name") in BASE_LEVEL_DATA:
            return max(1, worker_batch(g, source))
        return 1
    return _lw_dn_previous_recruitment_batch(g, owner, name)


_lw_dn_previous_recruitment_gold_cost = recruitment_gold_cost


def recruitment_gold_cost(view, owner, name, positions):
    if name == WORKER:
        return UNITS[WORKER]["cost"] * len(positions)
    return _lw_dn_previous_recruitment_gold_cost(view, owner, name, positions)


def dn_collect(g, base):
    owner = base["owner"]
    level = BASE_LEVEL_DATA.get(base["name"], {"level": 1})["level"]
    cells = {"gold": [], "mana": []}

    for pos in neighbors(tuple(base["pos"])):
        resource = g["resources"].get(key(pos))
        if resource is None:
            continue
        for occupant in pieces_at(g, pos):
            if occupant["owner"] == owner and occupant["name"] == WORKER:
                cells[resource[0]].append(resource[1])

    for kind, table in (("gold", DN_GOLD_BY_WORKERS), ("mana", DN_MANA_BY_WORKERS)):
        workers = min(level, len(cells[kind]))
        if workers:
            g["players"][owner][kind] += table[workers] * max(cells[kind])


_lw_dn_previous_collect = collect_adjacent_resources


def collect_adjacent_resources(g, base):
    owner = base["owner"]

    if base.get("sabotaged_until_turn", -1) >= g["turn"]:
        log(g, f"{base['name']} en {coord(base['pos'])} est sabotée : pas de récolte.")
        return

    double = base.pop("double_harvest", False)
    before = (g["players"][owner]["gold"], g["players"][owner]["mana"])

    if faction_id(g, owner) == DERNIERS_NES:
        dn_collect(g, base)
    else:
        _lw_dn_previous_collect(g, base)

    if double:
        gold = g["players"][owner]["gold"] - before[0]
        mana = g["players"][owner]["mana"] - before[1]
        g["players"][owner]["gold"] += gold
        g["players"][owner]["mana"] += mana
        log(g, f"Récolte doublée par le Dirigeable : +{gold} or, +{mana} mana.")


# ------------------------------------------------------------
# Manœuvres : restrictions de déplacement et d'attaque
# ------------------------------------------------------------

_lw_dn_previous_available = available


def available(g, owner):
    # Les ouvriers ne jouent qu'en phase de production.
    return [
        unit for unit in _lw_dn_previous_available(g, owner)
        if unit["name"] != WORKER
    ]


_lw_dn_previous_can_move = can_move


def can_move(g, unit):
    return (
        unit is not None
        and unit["name"] != WORKER
        and _lw_dn_previous_can_move(g, unit)
    )


_lw_dn_previous_move_preview = move_preview


def move_preview(g, unit):
    if unit is not None and unit["name"] in IMMOBILE_UNITS:
        return {}, {}
    return _lw_dn_previous_move_preview(g, unit)


def sabotage_from(g, scout):
    """Un Éclaireur arrêté sur une ressource sabote les bases ennemies voisines."""
    pos = tuple(scout["pos"])
    if key(pos) not in g["resources"]:
        return

    for base in g["entities"]:
        if (
            base["kind"] == "base"
            and base["owner"] != scout["owner"]
            and distance(tuple(base["pos"]), pos) == 1
        ):
            until = g["turn"] + 1
            base["sabotaged_until_turn"] = until
            base["blocked_until_turn"] = max(base.get("blocked_until_turn", 0), until)
            log(
                g,
                f"L'Éclaireur sabote {base['name']} en {coord(base['pos'])} "
                "pendant 1 tour.",
            )


_lw_dn_previous_move_unit = move_unit


def move_unit(g, eid, destination):
    unit = entity(g, eid)
    if unit["name"] in IMMOBILE_UNITS:
        raise ValueError("Le Trébuchet est immobile : redeviens Catapulte pour bouger.")
    if unit["name"] == WORKER:
        raise ValueError("Les ouvriers se déplacent pendant la phase de production.")

    _lw_dn_previous_move_unit(g, eid, destination)

    moved = next((e for e in g["entities"] if e["id"] == eid), None)
    if moved is not None and moved["name"] == SCOUT:
        sabotage_from(g, moved)


_lw_dn_previous_paths = paths


def paths(g, unit, allow_attack=False):
    if not (unit["name"] == SCOUT and owns_upgrade(g, unit["owner"], "Esquive")):
        return _lw_dn_previous_paths(g, unit, allow_attack)

    # Esquive : l'Éclaireur traverse les unités ennemies sans s'y arrêter.
    start = tuple(unit["pos"])
    budget = remaining_actions(g, unit)
    occupants = {tuple(e["pos"]): e for e in g["entities"]}
    costs = {start: 0}
    routes = {start: [start]}
    queue = [(0, start)]

    while queue:
        cost, pos = heapq.heappop(queue)
        if cost != costs[pos]:
            continue

        for nxt in neighbors(pos):
            if terrain(g, nxt) == "sea":
                continue

            occupant = occupants.get(nxt)
            passable = True

            if occupant is not None:
                if occupant["owner"] != unit["owner"]:
                    if occupant["kind"] != "unit":
                        if not allow_attack:
                            continue
                        passable = False
                elif occupant["kind"] not in ("unit", "base", "building"):
                    continue

            new_cost = cost + (2 if terrain(g, nxt) == "mountain" else 1)
            if new_cost > budget or new_cost >= costs.get(nxt, math.inf):
                continue

            costs[nxt] = new_cost
            routes[nxt] = routes[pos] + [nxt]
            if passable:
                heapq.heappush(queue, (new_cost, nxt))

    return costs, routes


_lw_dn_previous_prepare_attack = prepare_attack


def prepare_attack(g, attacker_ids, target_id):
    target = entity(g, target_id)

    for eid in attacker_ids:
        piece = entity(g, eid)
        if piece["name"] in NO_ATTACK_UNITS:
            raise ValueError(f"{piece['name']} : pas d'attaque.")
        if piece["name"] in SIEGE_RANGES:
            raise ValueError(f"{piece['name']} : attaque uniquement à distance.")
        if piece["name"] == SCOUT and target["kind"] == "base":
            raise ValueError("L'Éclaireur n'attaque pas les bases : il peut les saboter.")

    return _lw_dn_previous_prepare_attack(g, attacker_ids, target_id)


# ------------------------------------------------------------
# Tirs : catapultes, trébuchet, archers, griffons
# ------------------------------------------------------------

def siege_values(g, attacker, target):
    require_phase(g, "move")

    if not can_move(g, attacker):
        raise ValueError("Cette unité ne peut pas agir.")
    if remaining_actions(g, attacker) < 1:
        raise ValueError("Il faut conserver au moins 1 action pour tirer.")
    if target["owner"] == attacker["owner"]:
        raise ValueError("Choisis une cible ennemie.")
    if not visible_to_player(g, target, attacker["owner"]):
        raise ValueError("Cette cible est invisible.")

    low, high = SIEGE_RANGES[attacker["name"]]
    gap = distance(tuple(attacker["pos"]), tuple(target["pos"]))
    if not low <= gap <= high:
        raise ValueError(f"{attacker['name']} : tir uniquement de {low} à {high} cases.")

    ready = attacker.get("siege_ready_turn", 0)
    if g["turn"] < ready:
        raise ValueError(f"Rechargement : prochain tir au tour {ready}.")

    damage = SIEGE_DAMAGE
    if owns_upgrade(g, attacker["owner"], "Pierres enflammées"):
        damage += 2.0

    return {
        "range": high,
        "damage": damage,
        "remaining": max(0.0, float(target["pf"]) - damage),
        "siege": True,
    }


def ranged_second_cell(g, attacker):
    """Tireurs qui touchent aussi une case voisine de la cible."""
    return attacker["name"] == GRIFFON or (
        attacker["name"] == ARCHER
        and owns_upgrade(g, attacker["owner"], "Flèches enflammées")
    )


_lw_dn_previous_ranged_values = ranged_attack_values


def ranged_attack_values(g, attacker, target):
    if attacker["name"] in NO_ATTACK_UNITS:
        raise ValueError(f"{attacker['name']} : pas d'attaque, utilise ses sorts.")
    if attacker["name"] in SIEGE_RANGES:
        return siege_values(g, attacker, target)
    return _lw_dn_previous_ranged_values(g, attacker, target)


def siege_attack(g, attacker, target):
    values = siege_values(g, attacker, target)
    target_pos = tuple(target["pos"])
    flanks = siege_side_cells(tuple(attacker["pos"]), target_pos)

    report = {
        "turn": turn_label(g),
        "position": coord(target_pos),
        "power": values["damage"],
        "bonus": 0.0,
        "defense": float(target["pf"]),
        "occupier_id": None,
        "participants": [{
            "id": attacker["id"],
            "owner": attacker["owner"],
            "name": attacker["name"],
            "role": "Tir de siège",
            "before": float(attacker["pf"]),
            "damage": 0.0,
            "after": float(attacker["pf"]),
        }],
    }

    attacker["acted"] = True
    attacker["siege_ready_turn"] = g["turn"] + SIEGE_RELOAD_TURNS
    if g.get("moving_unit_id") == attacker["id"]:
        g.pop("moving_unit_id")

    log(g, f"{attacker['name']} #{attacker['id']} bombarde {coord(target_pos)}.")
    apply_damage(g, target, values["damage"], attacker, report, "Cible du tir de siège")

    # Les cases voisines sont touchées, alliés compris.
    for pos in flanks:
        for victim in pieces_at(g, pos):
            apply_damage(g, victim, SIEGE_SIDE_DAMAGE, attacker, report, "Case voisine du tir de siège")

    g["_combat_report"] = report
    next_activation(g)


_lw_dn_previous_ranged_attack = ranged_attack


def ranged_attack(g, attacker_id, target_id, second_cell=None):
    attacker = entity(g, attacker_id)
    target = entity(g, target_id)

    if attacker["name"] in SIEGE_RANGES:
        siege_attack(g, attacker, target)
        return

    if not ranged_second_cell(g, attacker):
        _lw_dn_previous_ranged_attack(g, attacker_id, target_id)
        return

    values = ranged_attack_values(g, attacker, target)
    flanks = flank_cells(tuple(target["pos"]), tuple(attacker["pos"]))
    chosen = choose_second_cell(g, attacker["owner"], flanks, second_cell, target_id)
    splash = []

    if chosen is not None:
        splash.append({
            "pos": list(chosen),
            "damage": values["damage"],
            "friendly_fire": False,
            "source": {
                "id": attacker["id"], "name": attacker["name"],
                "kind": "unit", "owner": attacker["owner"],
            },
        })

    g["_attack_effects"] = {
        "owner": attacker["owner"],
        "attackers": [attacker_id],
        "splash": splash,
        "trample": None,
        "dwarves": [],
    }
    try:
        _lw_dn_previous_ranged_attack(g, attacker_id, target_id)
    finally:
        g.pop("_attack_effects", None)


def transform_siege(g, unit_id):
    require_phase(g, "move")
    unit = entity(g, unit_id)

    if unit["owner"] != g["active"] or unit["name"] not in (CATAPULT, TREBUCHET):
        raise ValueError("Choisis une de tes catapultes ou un trébuchet.")
    if not owns_upgrade(g, unit["owner"], "Trébuchet"):
        raise ValueError("Achète d'abord l'amélioration « Trébuchet » à la Forge.")
    if not can_move(g, unit):
        raise ValueError("Cette unité ne peut plus agir ce tour.")

    new_name = TREBUCHET if unit["name"] == CATAPULT else CATAPULT
    damage = unit["max_pf"] - unit["pf"]
    unit["name"] = new_name
    unit["max_pf"] = float(UNITS[new_name]["pf"])
    unit["pf"] = max(0.5, unit["max_pf"] - damage)
    unit["acted"] = True
    if g.get("moving_unit_id") == unit["id"]:
        g.pop("moving_unit_id")

    log(g, f"Unité #{unit['id']} se transforme en {new_name}.")
    next_activation(g)


# ------------------------------------------------------------
# Dirigeable : transport, sorts, détection
# ------------------------------------------------------------

def check_airship(g, airship_id):
    require_phase(g, "move")
    airship = entity(g, airship_id)
    if airship["name"] != AIRSHIP or airship["owner"] != g["active"]:
        raise ValueError("Choisis un de tes Dirigeables.")
    if not can_move(g, airship):
        raise ValueError("Ce Dirigeable ne peut plus agir ce tour.")
    return airship


def boarding_candidates(g, airship):
    return [
        e for e in g["entities"]
        if e["owner"] == airship["owner"]
        and e["kind"] == "unit"
        and e["name"] not in (AIRSHIP, WORKER)
        and not e["wait"]
        and distance(tuple(e["pos"]), tuple(airship["pos"])) == 1
    ]


def board_airship(g, airship_id, unit_id):
    airship = check_airship(g, airship_id)
    unit = entity(g, unit_id)
    cargo = airship.setdefault("cargo", [])

    if unit not in boarding_candidates(g, airship):
        raise ValueError("L'unité doit être une unité alliée voisine du Dirigeable.")
    if len(cargo) >= AIRSHIP_CAPACITY:
        raise ValueError(f"Le Dirigeable transporte {AIRSHIP_CAPACITY} unités au maximum.")

    g["entities"].remove(unit)
    unit["acted"] = True
    unit["planted"] = False
    cargo.append(unit)

    # Le Dirigeable garde la main pour partir avec sa cargaison.
    g["moving_unit_id"] = airship["id"]
    log(g, f"{unit['name']} #{unit['id']} embarque dans le Dirigeable.")
    g["_ui_message"] = (
        f"{unit['name']} à bord ({len(cargo)}/{AIRSHIP_CAPACITY}). "
        "Déplace le Dirigeable puis débarque."
    )


def unload_airship(g, airship_id):
    airship = check_airship(g, airship_id)
    cargo = airship.get("cargo", [])

    if not cargo:
        raise ValueError("Personne à bord.")

    free = [
        pos for pos in neighbors(tuple(airship["pos"]))
        if at(g, pos) is None and not blocked(g, pos)
    ]
    if len(free) < len(cargo):
        raise ValueError("Pas assez de cases libres autour du Dirigeable.")

    for unit, pos in zip(cargo, free):
        unit["pos"] = list(pos)
        unit["acted"] = True
        g["entities"].append(unit)

    airship["cargo"] = []
    airship["acted"] = True
    if g.get("moving_unit_id") == airship["id"]:
        g.pop("moving_unit_id")

    log(g, f"Le Dirigeable débarque {len(cargo)} unité(s).")
    next_activation(g)


def airship_targets(g, airship, spell):
    kind = "unit" if spell == "boost" else "base"
    return [
        e for e in g["entities"]
        if e["owner"] == airship["owner"]
        and e["kind"] == kind
        and distance(tuple(e["pos"]), tuple(airship["pos"])) <= AIRSHIP_RANGE
    ]


def cast_airship_spell(g, airship_id, spell, target_id):
    airship = check_airship(g, airship_id)

    if spell not in AIRSHIP_SPELLS:
        raise ValueError("Sort inconnu.")

    target = entity(g, target_id)
    if target not in airship_targets(g, airship, spell):
        raise ValueError(f"Cible invalide : alliée et à {AIRSHIP_RANGE} cases maximum.")

    if spell == "boost":
        cells = [tuple(target["pos"])] + flank_cells(tuple(target["pos"]), tuple(airship["pos"]))
        for pos in cells:
            ally = at(g, pos)
            if (
                ally is not None
                and ally["owner"] == airship["owner"]
                and ally["kind"] == "unit"
                and not ally.get("boost")
            ):
                ally["boost"] = AIRSHIP_BOOST
                ally["max_pf"] += AIRSHIP_BOOST
                ally["pf"] += AIRSHIP_BOOST
                log(g, f"{ally['name']} #{ally['id']} : +2 PF jusqu'à la fin du tour.")
    else:
        target["double_harvest"] = True
        log(g, f"La prochaine récolte de {target['name']} en {coord(target['pos'])} sera doublée.")

    airship["acted"] = True
    if g.get("moving_unit_id") == airship["id"]:
        g.pop("moving_unit_id")
    next_activation(g)


_lw_dn_previous_end_round = end_round


def end_round(g):
    # Le bonus du Dirigeable dure un tour.
    for unit in g["entities"]:
        boost = unit.pop("boost", None)
        if boost:
            unit["max_pf"] -= boost
            unit["pf"] = max(0.5, min(unit["pf"], unit["max_pf"]))

    _lw_dn_previous_end_round(g)


# ------------------------------------------------------------
# Interface : production
# ------------------------------------------------------------

def render_worker_controls(view, worker, prefix):
    if worker["name"] != WORKER or view["phase"] != "build":
        return

    st.markdown("#### 👷 Ouvrier")

    if worker["wait"]:
        st.info(
            f"🔨 En construction : bloqué encore {worker['wait']} "
            "fin(s) de tour, comme son chantier."
        )
        return

    moved = remaining_actions(view, worker) <= 0
    plan_mode = st.session_state.ui_plan_mode
    positions = [tuple(p) for p in st.session_state.ui_plan_positions]

    if moved:
        st.caption("Déjà déplacé ce tour.")
    elif plan_mode == "worker_move":
        if positions:
            st.write(f"Destination : **{coord(positions[0])}**")
            if auto_confirm("worker_move", worker["id"], positions[0]):
                # Après le déplacement, l'ouvrier reste sélectionné pour continuer.
                st.session_state["_resume_plan"] = {"id": worker["id"], "mode": "worker_move", "name": WORKER}
                perform(draft_action, move_worker, worker["id"], positions[0])
        else:
            st.info(f"Clique sur une case verte ({remaining_actions(view, worker)} déplacement(s) restant(s)).")
        if st.button("✕ Annuler", key=f"{prefix}_worker_move_cancel_{worker['id']}"):
            clear_placement()
            st.session_state.ui_selected_id = None
            bump_ui()
            st.rerun()
    elif st.button("🚶 Déplacer l'ouvrier", key=f"{prefix}_worker_move_{worker['id']}"):
        start_placement("worker_move", WORKER)
        st.rerun()

    if worker["used"]:
        st.caption("A déjà construit ce tour.")
        return

    faction = faction_of(view, worker["owner"])
    names = [faction["base"]] + [
        name for name in faction["buildings"]
        if building_is_available(view, worker["owner"], name)
    ]

    st.markdown("#### Construire")
    st.caption("Sur une case voisine de l'ouvrier.")
    for name in names:
        is_base = name == faction["base"]
        cost = (
            base_cost_for_age(view, worker["owner"])
            if is_base
            else faction["buildings"][name]["cost"]
        )
        label = dn_base_label(view, worker["owner"], name)
        pf = (
            BASE_LEVEL_DATA.get(label, {}).get("pf", faction["base_pf"])
            if is_base
            else faction["buildings"][name]["pf"]
        )
        card = st.container(border=True)
        card.write(f"**{label}**")
        card.caption(
            f"{cost} or · {pf:g} PF · " + building_limit_text(view, worker["owner"], name)
            + ("" if is_base else f" · ⚡ immédiat : {int(cost * 1.5)} or")
        )
        limit_hit = building_limit_reached(view, worker["owner"], name)
        normal_col, fast_col = card.columns(2)
        if normal_col.button(
            "🔨 Construire",
            disabled=limit_hit,
            key=f"{prefix}_worker_build_{worker['id']}_{name}",
            use_container_width=True,
            type=build_button_type(name, False),
        ):
            start_build(name, False)
        if not is_base and fast_col.button(
            "⚡ Immédiat",
            disabled=limit_hit,
            key=f"{prefix}_worker_fast_{worker['id']}_{name}",
            use_container_width=True,
            help="Disponible immédiatement, pour +50 % du prix.",
            type=build_button_type(name, True),
        ):
            start_build(name, True)


def render_colony_controls(view, base, prefix):
    owner = base["owner"]
    data = BASE_LEVEL_DATA[base["name"]]

    workers_on_resources = [
        piece
        for pos in neighbors(tuple(base["pos"]))
        if key(pos) in view["resources"]
        for piece in pieces_at(view, pos)
        if piece["owner"] == owner and piece["name"] == WORKER
    ]
    st.caption(
        f"Récolte : {len(workers_on_resources)} ouvrier(s) sur l'or ou le mana "
        f"voisins — jusqu'à {data['level']} pris en compte."
    )

    until = production_blocked_until(view, base)
    if until is not None:
        st.error(f"⛔ Production bloquée jusqu'au tour {until} inclus.")

    st.markdown("#### Produire des ouvriers")
    batch = worker_batch(view, base)

    if base["wait"]:
        st.info(f"Base en construction : encore {base['wait']} fin(s) de tour.")
    elif base["used"]:
        st.info("Cette base a déjà produit ce tour.")
    elif batch == 0:
        st.info(f"Limite de {WORKER_LIMIT} ouvriers atteinte.")
    elif until is None:
        card = st.container(border=True)
        card.write(f"**{WORKER}**")
        card.caption(
            f"{batch} unité(s) · {UNITS[WORKER]['cost'] * batch} or · "
            f"{UNITS[WORKER]['pf']} PF · MVT {UNITS[WORKER]['move']}"
        )
        if card.button(
            f"Produire {batch} ouvrier(s)",
            key=f"{prefix}_workers_{base['id']}",
            type=(
                "primary"
                if st.session_state.ui_plan_mode == "recruit"
                and st.session_state.ui_plan_name == WORKER
                else "secondary"
            ),
        ):
            start_placement("recruit", WORKER)
            st.rerun()

    st.caption(
        "Les colonies deviennent automatiquement des villes à l'âge II, "
        "puis des forteresses à l'âge III."
    )


_lw_dn_previous_planning_slots = planning_slots


def planning_slots(g, view):
    source = selected_entity(view)
    mode = st.session_state.ui_plan_mode
    name = st.session_state.ui_plan_name

    if (
        source is not None
        and g["phase"] == "build"
        and g["winner"] is None
        and not g["curtain"]
        and source["owner"] == g["active"]
    ):
        if source["name"] == WORKER:
            if mode == "build":
                return worker_build_slots(view, source, name)
            if mode == "worker_move":
                return list(worker_destinations(view, source))
            return []

        if mode == "recruit" and name == WORKER:
            if (
                source["kind"] != "base"
                or source["wait"]
                or source["used"]
                or production_blocked_until(view, source) is not None
            ):
                return []
            return worker_slots(view, source)

    return _lw_dn_previous_planning_slots(g, view)


# ------------------------------------------------------------
# Interface : manœuvres
# ------------------------------------------------------------

def render_airship_controls(g, airship, prefix):
    st.subheader("🎈 Dirigeable")
    cargo = airship.get("cargo", [])
    st.caption(
        f"À bord ({len(cargo)}/{AIRSHIP_CAPACITY}) : "
        + (", ".join(f"{u['name']} #{u['id']}" for u in cargo) or "personne")
        + f". Pas d'attaque. Détecte les invisibles à {AIRSHIP_RANGE} cases."
    )

    if not can_move(g, airship):
        st.info("Ce Dirigeable a déjà agi ce tour.")
        return

    candidates = {u["id"]: u for u in boarding_candidates(g, airship)}
    if candidates and len(cargo) < AIRSHIP_CAPACITY:
        unit_id = st.selectbox(
            "Unité voisine à embarquer",
            options=list(candidates),
            format_func=lambda eid: describe(candidates[eid]),
            key=f"{prefix}_board_{airship['id']}",
        )
        if st.button("⬆️ Embarquer", key=f"{prefix}_board_ok_{airship['id']}"):
            perform(game_action, board_airship, airship["id"], unit_id)

    if cargo and st.button(
        "⬇️ Débarquer tout le monde (termine son activation)",
        key=f"{prefix}_unload_{airship['id']}",
    ):
        perform(game_action, unload_airship, airship["id"])

    spell = st.radio(
        "Sort",
        options=list(AIRSHIP_SPELLS),
        format_func=AIRSHIP_SPELLS.get,
        key=f"{prefix}_airship_spell_{airship['id']}",
    )
    targets = {e["id"]: e for e in airship_targets(g, airship, spell)}

    if not targets:
        st.caption("Aucune cible alliée à portée pour ce sort.")
        return

    target_id = st.selectbox(
        "Cible",
        options=list(targets),
        format_func=lambda eid: describe(targets[eid]),
        key=f"{prefix}_airship_target_{airship['id']}_{spell}",
    )
    if st.button(
        "✨ Lancer le sort",
        type="primary",
        key=f"{prefix}_airship_cast_{airship['id']}",
    ):
        perform(game_action, cast_airship_spell, airship["id"], spell, target_id)


def render_siege_controls(g, unit, prefix):
    low, high = SIEGE_RANGES[unit["name"]]
    ready = unit.get("siege_ready_turn", 0)
    st.caption(
        f"{unit['name']} : tir de {low} à {high} cases · "
        f"{SIEGE_DAMAGE:g} PF sur la cible (+2 avec Pierres enflammées), "
        f"{SIEGE_SIDE_DAMAGE:g} PF à gauche et à droite, alliés compris."
        + (f" Rechargement : prochain tir au tour {ready}." if g["turn"] < ready else "")
    )

    if (
        unit["name"] in (CATAPULT, TREBUCHET)
        and owns_upgrade(g, unit["owner"], "Trébuchet")
        and can_move(g, unit)
    ):
        label = (
            "🏗️ Devenir Trébuchet (immobile, tir à 4-5 cases)"
            if unit["name"] == CATAPULT
            else "🏗️ Redevenir Catapulte (peut bouger)"
        )
        if st.button(label, key=f"{prefix}_transform_{unit['id']}"):
            perform(game_action, transform_siege, unit["id"])


def render_ranged_second_cell(g, attacker, target, prefix):
    flanks = flank_cells(tuple(target["pos"]), tuple(attacker["pos"]))
    options = second_cell_options(g, attacker["owner"], flanks)
    st.session_state.ui_splash_choice = None

    if not options:
        st.caption(f"{attacker['name']} : aucune 2ᵉ case ennemie à côté de la cible.")
        return

    chosen = st.selectbox(
        f"2ᵉ case touchée par {attacker['name']} (ennemis uniquement)",
        options=options,
        format_func=lambda pos: f"{coord(pos)} — {at(g, pos)['name']}",
        key=f"{prefix}_ranged_second_{attacker['id']}_{target['id']}",
    )
    st.session_state.ui_splash_choice = {
        "target_id": target["id"],
        "pos": list(chosen),
    }


_lw_dn_previous_render_move_controls = render_move_controls


def render_move_controls(g):
    attackers = selected_attackers(g)
    target = current_target(g)
    prefix = f"dn_{g['turn']}_{g['active']}_{st.session_state.ui_revision}"

    if len(attackers) == 1:
        unit = attackers[0]

        if unit["name"] == AIRSHIP:
            render_airship_controls(g, unit, prefix)
            render_previous_move_controls_without_target(g)
            return

        if unit["name"] in SIEGE_RANGES:
            render_siege_controls(g, unit, prefix)

        if unit["name"] == SCOUT:
            st.caption(
                "Éclaireur : n'attaque pas les bases. S'il s'arrête sur l'or "
                "ou le mana voisin d'une base ennemie, il la sabote 1 tour."
            )

        if (
            target is not None
            and ranged_second_cell(g, unit)
            and not contact_melee(g, unit, target)
        ):
            render_ranged_second_cell(g, unit, target, prefix)

    _lw_dn_previous_render_move_controls(g)


# ============================================================
# DERNIERS NÉS : PILES D'OUVRIERS ET BASES PAR ÂGE
# À laisser APRÈS toutes les autres définitions,
# juste avant : if __name__ == "__main__":
# ============================================================

# Jusqu'à 3 ouvriers d'un même joueur sur une case d'or ou de mana.
WORKER_STACK = 3

# La base change de nom et de PF automatiquement à chaque âge.
DN_BASE_BY_AGE = {1: "Colonie", 2: "Ville", 3: "Forteresse"}
BASE_COST_BY_AGE.update({
    (DERNIERS_NES, age): BASE_LEVEL_DATA[name]["cost"]
    for age, name in DN_BASE_BY_AGE.items()
})
AGE_REFERENCE["Derniers nés"][2][0] = (
    "Ville", "Automatique au passage à l'âge II · 4 PF · produit 2 ouvriers (100 or) · nouvelle base : 250 or"
)
AGE_REFERENCE["Derniers nés"][3][0] = (
    "Forteresse", "Automatique au passage à l'âge III · 6 PF · produit 3 ouvriers (150 or) · nouvelle base : 300 or"
)


def pieces_at(g, pos):
    pos = tuple(pos)
    return [e for e in g["entities"] if tuple(e["pos"]) == pos]


def is_worker_stack(g, pieces):
    return (
        0 < len(pieces) <= WORKER_STACK
        and all(
            p["name"] == WORKER
            and p["owner"] == pieces[0]["owner"]
            and faction_id(g, p["owner"]) == DERNIERS_NES
            for p in pieces
        )
    )


def can_worker_stop(g, owner, pos, ignore_id=None):
    """Case libre, ou pile d'ouvriers alliés sur l'or ou le mana (3 maximum)."""
    pos = tuple(pos)
    if blocked(g, pos):
        return False

    others = [e for e in pieces_at(g, pos) if e["id"] != ignore_id]
    if not others:
        return True

    return (
        key(pos) in g["resources"]
        and len(others) < WORKER_STACK
        and faction_id(g, owner) == DERNIERS_NES
        and all(e["owner"] == owner and e["name"] == WORKER for e in others)
    )


def stacking_valid(g, entities):
    """Une pièce par case, sauf les piles d'ouvriers sur l'or ou le mana."""
    by_cell = {}
    for piece in entities:
        by_cell.setdefault(tuple(piece["pos"]), []).append(piece)

    return all(
        len(pieces) == 1
        or (key(pos) in g["resources"] and is_worker_stack(g, pieces))
        for pos, pieces in by_cell.items()
    )


def worker_slots(g, base):
    return [
        pos for pos in neighbors(tuple(base["pos"]))
        if can_worker_stop(g, base["owner"], pos)
    ]


def add_entity(g, owner, name, kind, pos, pf, wait=0):
    pos = require_position(pos)
    if name == WORKER:
        if not can_worker_stop(g, owner, pos):
            raise ValueError("Cette case est déjà occupée.")
    elif at(g, pos):
        raise ValueError("Cette case est déjà occupée.")

    result = {
        "id": g["next_id"],
        "owner": owner,
        "name": name,
        "kind": kind,
        "pos": list(pos),
        "pf": float(pf),
        "max_pf": float(pf),
        "wait": wait,
        "acted": False,
        "used": False,
    }
    g["next_id"] += 1
    g["entities"].append(result)
    return result


_lw_stack_previous_board_event = board_event


def board_event(event, g, view):
    """Production : placer sur une pile, ou choisir un ouvrier dans la pile."""
    if (
        not isinstance(event, dict)
        or event.get("type") != "cell_click"
        or g["phase"] != "build"
        or g["winner"] is not None
        or g["curtain"]
        or event.get("event_id") == st.session_state.ui_last_event
        or faction_id(g, g["active"]) != DERNIERS_NES
    ):
        return _lw_stack_previous_board_event(event, g, view)

    try:
        pos = require_position(event.get("pos"))
    except ValueError:
        return _lw_stack_previous_board_event(event, g, view)

    stack = [
        e for e in pieces_at(view, pos)
        if e["owner"] == g["active"] and e["name"] == WORKER
    ]
    if not stack:
        return _lw_stack_previous_board_event(event, g, view)

    mode = st.session_state.ui_plan_mode
    name = st.session_state.ui_plan_name
    in_slots = pos in planning_slots(g, view)

    if mode == "worker_move" and in_slots:
        st.session_state.ui_last_event = event["event_id"]
        st.session_state.ui_plan_positions = [pos]
        st.session_state.ui_message = f"Destination : {coord(pos)} (rejoint la pile d'ouvriers)."
        bump_ui()
        st.rerun()

    if mode == "recruit" and name == WORKER and in_slots:
        st.session_state.ui_last_event = event["event_id"]
        positions = [tuple(p) for p in st.session_state.ui_plan_positions]
        batch = recruitment_batch(view, g["active"], WORKER)
        if pos in positions:
            positions.remove(pos)
        elif len(positions) < batch:
            positions.append(pos)
        elif batch == 1:
            positions = [pos]
        st.session_state.ui_plan_positions = positions
        bump_ui()
        st.rerun()

    if len(stack) > 1:
        # Chaque clic sélectionne l'ouvrier suivant de la pile.
        st.session_state.ui_last_event = event["event_id"]
        ids = [e["id"] for e in stack]
        current = st.session_state.ui_selected_id
        index = (ids.index(current) + 1) % len(ids) if current in ids else 0
        st.session_state.ui_selected_id = ids[index]
        clear_placement()
        st.session_state.ui_message = (
            f"Ouvrier {index + 1}/{len(ids)} de la pile en {coord(pos)} sélectionné. "
            "Reclique pour passer au suivant."
        )
        bump_ui()
        st.rerun()

    return _lw_stack_previous_board_event(event, g, view)


# ------------------------------------------------------------
# Ville et Forteresse : automatiques au passage d'âge
# ------------------------------------------------------------

def dn_base_name(g, owner):
    return DN_BASE_BY_AGE[g["players"][owner]["age"]]


_lw_stack_previous_advance_age = advance_age


def advance_age(g, owner, target_age):
    _lw_stack_previous_advance_age(g, owner, target_age)

    if faction_id(g, owner) != DERNIERS_NES:
        return

    new_name = DN_BASE_BY_AGE[target_age]
    new_pf = float(BASE_LEVEL_DATA[new_name]["pf"])

    for base in g["entities"]:
        if base["owner"] != owner or base["kind"] != "base":
            continue
        damage = base["max_pf"] - base["pf"]
        base["name"] = new_name
        base["max_pf"] = new_pf
        base["pf"] = max(0.5, new_pf - damage)

    log(g, f"Toutes les bases des Derniers nés deviennent : {new_name}.")


_lw_stack_previous_worker_build = worker_build


def worker_build(g, owner, worker, name, pos, accelerated):
    _lw_stack_previous_worker_build(g, owner, worker, name, pos, accelerated)

    # Une nouvelle base naît directement au niveau de l'âge actuel.
    piece = at(g, pos)
    if piece is not None and piece["kind"] == "base":
        level_name = dn_base_name(g, owner)
        piece["name"] = level_name
        piece["max_pf"] = piece["pf"] = float(BASE_LEVEL_DATA[level_name]["pf"])


def spawn_colony_worker(g, owner, base):
    """La nouvelle base arrive avec 1, 2 ou 3 ouvriers selon l'âge,
    bloqués autant de tours que la construction de la base (2)."""
    count = g["players"][owner]["age"]
    placed = []

    for _ in range(count):
        if worker_count(g, owner) >= WORKER_LIMIT:
            break
        free = worker_slots(g, base)
        on_resource = sorted(
            (pos for pos in free if key(pos) in g["resources"]),
            key=lambda pos: (g["resources"][key(pos)][0] != "gold", pos),
        )
        choices = on_resource or free
        if not choices:
            break
        worker = add_unit(g, owner, WORKER, choices[0])
        worker["wait"] = base["wait"]
        placed.append(coord(worker["pos"]))

    if placed:
        log(
            g,
            f"{len(placed)} ouvrier(s) livré(s) avec la base en {', '.join(placed)} "
            f"(bloqué(s) {base['wait']} tour(s)).",
        )


# ============================================================
# ACTIONS SANS BOUTON DE CONFIRMATION
# Placement, déplacement sur une case verte et sorts ciblés
# partent dès que le choix est complet.
# ============================================================

def auto_confirm(*parts):
    """Vrai une seule fois par choix : évite de relancer en boucle
    une action refusée à chaque rafraîchissement."""
    signature = repr(parts)
    fired = st.session_state.setdefault("ui_auto_fired", [])
    if signature in fired:
        return False
    fired.append(signature)
    return True


_lw_auto_previous_bump_ui = bump_ui


def bump_ui(clear_selection=False):
    if clear_selection:
        st.session_state.ui_auto_fired = []
    _lw_auto_previous_bump_ui(clear_selection)


_lw_auto_previous_process_queued_board_event = process_queued_board_event


def process_queued_board_event(g, view):
    # Un nouveau clic sur le plateau autorise à retenter le même choix.
    if st.session_state.get("ui_queued_board_event") is not None:
        st.session_state.ui_auto_fired = []
    return _lw_auto_previous_process_queued_board_event(g, view)


# ============================================================
# RECRUTEMENT : CASES À 2 DE DISTANCE SI LE BÂTIMENT EST ENTOURÉ
# Seulement quand les cases adjacentes libres ne suffisent plus.
# ============================================================

def free_recruit_cell(g, pos):
    return at(g, pos) is None and terrain(g, pos) not in ("mountain", "sea")


def recruitment_slots(g, producer, batch=None):
    """Cases adjacentes libres ; si elles ne suffisent pas pour le lot,
    on ajoute les cases libres situées à 2 cases du bâtiment."""
    if batch is None:
        batch = g.get("_recruit_batch", 1)

    origin = tuple(producer["pos"])
    near = [pos for pos in neighbors(origin) if free_recruit_cell(g, pos)]
    if len(near) >= batch:
        return near

    far = [
        pos for pos in CELLS
        if distance(origin, pos) == 2 and free_recruit_cell(g, pos)
    ]
    return near + far


_lw_far_previous_recruit = recruit


def recruit(g, owner, producer_id, name, positions):
    producer = entity(g, producer_id)
    if name == WORKER or producer["kind"] != "building":
        return _lw_far_previous_recruit(g, owner, producer_id, name, positions)

    batch = recruitment_batch(g, owner, name)
    chosen = {tuple(require_position(p)) for p in positions}
    origin = tuple(producer["pos"])
    near = {pos for pos in neighbors(origin) if free_recruit_cell(g, pos)}
    if any(distance(origin, pos) == 2 for pos in chosen) and not near <= chosen:
        raise ValueError(
            "Utilise d'abord toutes les cases libres adjacentes au bâtiment."
        )

    g["_recruit_batch"] = batch
    try:
        _lw_far_previous_recruit(g, owner, producer_id, name, positions)
    finally:
        g.pop("_recruit_batch", None)


_lw_far_previous_planning_slots = planning_slots


def planning_slots(g, view):
    slots = _lw_far_previous_planning_slots(g, view)
    source = selected_entity(view)
    name = st.session_state.ui_plan_name

    if (
        st.session_state.ui_plan_mode != "recruit"
        or source is None
        or source["kind"] != "building"
        or name == WORKER
        or name is None
    ):
        return slots

    batch = recruitment_batch(view, g["active"], name)
    if len(slots) >= batch or not can_recruit_now(g, view, source, name):
        return slots
    return recruitment_slots(view, source, batch)


def can_recruit_now(g, view, source, name):
    """Le bâtiment peut-il produire cette unité maintenant ?"""
    allowed = faction_of(view, g["active"])["buildings"].get(source["name"], {}).get("units", [])
    return (
        source["owner"] == g["active"]
        and not source["used"]
        and not source["wait"]
        and name in allowed
        and UNIT_AGES.get(name, 1) <= view["players"][g["active"]]["age"]
        and unit_requirement_met(view, g["active"], name)
        and production_blocked_until(view, source) is None
    )


# ============================================================
# ÉCRAN DE VICTOIRE
# ============================================================

VICTORY_IMAGE = Path(__file__).parent / "assets" / "victoire.jpg"


@st.cache_data
def _file_base64(path_text, modified):
    """Fichier en base64, en cache. La date de modification fait partie de
    la clé : une image remplacée est relue sans redémarrer le serveur."""
    import base64
    try:
        return base64.b64encode(Path(path_text).read_bytes()).decode("ascii")
    except OSError:
        return None


def file_base64(path):
    try:
        modified = Path(path).stat().st_mtime
    except OSError:
        return None
    return _file_base64(str(path), modified)


def victory_image_data():
    return file_base64(VICTORY_IMAGE)


# Image de victoire propre à chaque faction (image générique sinon).
FACTION_VICTORY_IMAGES = {
    "Déferlants": "victoire_deferlants.jpg",
    "Exilés": "victoire_exiles.jpg",
    "Derniers nés": "victoire_derniers_nes.jpg",
    "Vagabonds": "victoire_vagabonds.jpg",
}


def faction_victory_image_data(faction_name):
    filename = FACTION_VICTORY_IMAGES.get(faction_name)
    return file_base64(VICTORY_IMAGE.parent / filename) if filename else None


def render_victory_screen(g):
    faction = faction_of(g, g["winner"])["name"]
    title = f"Le joueur des {faction} a gagné la partie !"
    image = faction_victory_image_data(faction) or victory_image_data()
    background = (
        f"url('data:image/jpeg;base64,{image}') center 30% / cover no-repeat"
        if image
        else "linear-gradient(135deg, #1e3a8a, #111827)"
    )

    st.markdown(
        f"""
        <div style="position: relative; width: min(100%, 760px); margin: 0 auto;
                    aspect-ratio: 4 / 3;
                    border-radius: 14px; overflow: hidden;
                    background: {background};
                    box-shadow: 0 8px 28px #00000066;">
          <div style="position: absolute; inset: 0;
                      background: linear-gradient(180deg, #00000099 0%, #00000022 45%, #00000000 70%);"></div>
          <div style="position: absolute; top: 6%; left: 0; right: 0;
                      text-align: center; padding: 0 4%;
                      color: #ffffff; font-weight: 900;
                      font-size: clamp(19px, 3vw, 38px); line-height: 1.15;
                      text-shadow: 0 3px 12px #000000, 0 0 4px #000000;">
            🏆 {escape(title)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TIREURS AU CONTACT : ATTAQUE AU CORPS À CORPS
# Un tireur qui attaque une cible voisine (1 case) combat comme
# au corps à corps : riposte et pertes comme une attaque normale.
# ============================================================

def contact_melee(g, attacker, target):
    """Vrai si l'attaque de ce tireur sur cette cible est un corps à corps."""
    name = attacker["name"]
    return (
        distance(tuple(attacker["pos"]), tuple(target["pos"])) == 1
        and UNITS.get(name, {}).get("range", 0) > 0
        # Unités sans combat rapproché : leurs règles de tir restent inchangées.
        and name not in (STONE_GOLEM, DECIMANT) and name not in MAGES
        and name not in SIEGE_RANGES
        and name not in NO_ATTACK_UNITS
    )


_lw_contact_previous_ranged_attack = ranged_attack


def ranged_attack(g, attacker_id, target_id, *args, **kwargs):
    attacker = entity(g, attacker_id)
    target = entity(g, target_id)
    if contact_melee(g, attacker, target):
        raise ValueError(
            "Cible au contact : c'est une attaque au corps à corps, "
            "avec riposte et pertes comme une attaque normale."
        )
    return _lw_contact_previous_ranged_attack(g, attacker_id, target_id, *args, **kwargs)


# ============================================================
# DÉCIMANT : ATTAQUE BONUS APRÈS UNE ATTRACTION
# Après avoir attiré une unité ennemie, le joueur rejoue aussitôt,
# mais uniquement pour attaquer l'unité attirée (ou il renonce).
# ============================================================

def decimant_hunt(g):
    """Bonus en cours pour le joueur actif, sinon None."""
    hunt = g.get("decimant_hunt")
    if (
        not hunt
        or hunt["owner"] != g["active"]
        or hunt["turn"] != g["turn"]
        or g["phase"] != "move"
        or not any(e["id"] == hunt["target_id"] for e in g["entities"])
    ):
        return None
    return hunt


def decimant_hunters(g, owner, target):
    """Unités du joueur capables d'attaquer la cible maintenant."""
    hunters = []
    for unit in g["entities"]:
        if unit["owner"] != owner or unit["kind"] != "unit" or not can_move(g, unit):
            continue
        try:
            _, targets = attack_map_preview(g, [unit])
        except ValueError:
            continue
        if tuple(target["pos"]) in targets:
            hunters.append(unit)
    return hunters


_lw_hunt_previous_cast_decimant_spell = cast_decimant_spell


def cast_decimant_spell(g, decimant_id, spell, target_id):
    owner = g["active"]
    _lw_hunt_previous_cast_decimant_spell(g, decimant_id, spell, target_id)

    if spell != "attract" or g["winner"] is not None:
        return

    target = entity(g, target_id)
    hunters = decimant_hunters(g, owner, target)
    if not hunters:
        # Personne ne peut l'attaquer : le tour passe normalement.
        g["_ui_message"] = (
            f"{target['name']} attiré en {coord(target['pos'])}, "
            "mais aucune de tes unités ne peut l'attaquer : le tour passe."
        )
        if g["active"] == owner:
            next_activation(g)
        return

    g["decimant_hunt"] = {"owner": owner, "target_id": target_id, "turn": g["turn"]}
    g["_ui_message"] = (
        f"{target['name']} attiré en {coord(target['pos'])}. Rejoue aussitôt : "
        "attaque-le avec une de tes unités, ou renonce au bonus."
    )


def renounce_decimant_hunt(g):
    if decimant_hunt(g) is None:
        raise ValueError("Aucune attaque bonus en cours.")
    g.pop("decimant_hunt", None)
    log(g, "Le joueur renonce à l'attaque bonus du Décimant.")
    next_activation(g)


_lw_hunt_previous_game_action = game_action


def game_action(bundle, fn, *args):
    g = bundle["game"]
    hunt = decimant_hunt(g)
    if hunt is None:
        g.pop("decimant_hunt", None)
        return _lw_hunt_previous_game_action(bundle, fn, *args)

    target_id = hunt["target_id"]
    name = getattr(fn, "__name__", "")
    allowed = (
        name in ("pass_turn", "renounce_decimant_hunt")
        or (name in ("attack", "ranged_attack") and len(args) > 1 and args[1] == target_id)
        or (name == "cast_mage_spell" and len(args) > 2 and target_id in args[2])
    )
    if not allowed:
        target = entity(g, target_id)
        raise ValueError(
            f"Bonus du Décimant : attaque {target['name']} en {coord(target['pos'])}, "
            "ou renonce au bonus."
        )

    _lw_hunt_previous_game_action(bundle, fn, *args)
    g.pop("decimant_hunt", None)


_lw_hunt_previous_render_move_controls = render_move_controls


def render_move_controls(g):
    hunt = decimant_hunt(g)
    if hunt is not None:
        target = entity(g, hunt["target_id"])
        hunters = decimant_hunters(g, g["active"], target)
        st.warning(
            f"🧲 Attaque bonus du Décimant : attaque **{target['name']}** "
            f"en {coord(target['pos'])} avec une de tes unités."
            + (
                " Unités possibles : "
                + ", ".join(f"{u['name']} ({coord(u['pos'])})" for u in hunters)
                + "."
                if hunters else ""
            )
        )
        if st.button(
            "Renoncer à l'attaque bonus",
            key=f"renounce_hunt_{g['turn']}_{hunt['target_id']}",
        ):
            perform(game_action, renounce_decimant_hunt)

    _lw_hunt_previous_render_move_controls(g)


# ============================================================
# INVISIBILITÉ EN ATTAQUE ET RIPOSTE SUR LES TIRS
# - Une attaque menée uniquement par des unités invisibles que
#   l'ennemi ne détecte pas : dégâts infligés, aucune perte subie.
# - Tout tir subit une riposte égale aux PF de la cible, comme
#   au corps à corps, sauf si le tireur est invisible et non détecté.
# ============================================================

_LW_COMBAT_GAME = None


def hidden_from(g, attacker, defender_owner):
    """Invisible pour ce défenseur, sans détection à portée."""
    return not visible_to_player(g, attacker, defender_owner)


def all_hidden(g, attackers, target):
    return bool(attackers) and all(
        hidden_from(g, a, target["owner"]) for a in attackers
    )


_lw_hidden_previous_prepare_attack = prepare_attack


def prepare_attack(g, attacker_ids, target_id):
    global _LW_COMBAT_GAME
    _LW_COMBAT_GAME = g
    return _lw_hidden_previous_prepare_attack(g, attacker_ids, target_id)


_lw_hidden_previous_combat_values = combat_values


def combat_values(attackers, target):
    values = _lw_hidden_previous_combat_values(attackers, target)
    g = _LW_COMBAT_GAME
    if g is None or not any(e is target or e.get("id") == target.get("id") for e in g["entities"]):
        return values
    if not all_hidden(g, attackers, target):
        return values

    values = dict(values, hidden=True, losses=0.0)
    if not values["winnable"]:
        # Pas de sacrifice : les attaquants survivent, la cible est affaiblie.
        values["defender_damage"] = values["power"]
        values["defender_remaining"] = values["defense"] - values["power"]
    return values


_lw_hidden_previous_attack = attack


def attack(g, attacker_ids, target_id, occupier_id=None, losses=None, *args, **kwargs):
    attackers, target, _ = prepare_attack(g, attacker_ids, target_id)
    values = combat_values(attackers, target)

    if not values.get("hidden"):
        return _lw_hidden_previous_attack(
            g, attacker_ids, target_id, occupier_id, losses, *args, **kwargs
        )

    if values["winnable"]:
        # Victoire invisible : aucune perte, l'occupant prend la case.
        if occupier_id is None:
            occupier_id = attackers[0]["id"]
        zero = {a["id"]: 0.0 for a in attackers}
        return _lw_hidden_previous_attack(
            g, attacker_ids, target_id, occupier_id, zero, *args, **kwargs
        )

    # Attaque invisible non décisive : la cible perd des PF, sans riposte.
    owner = g["active"]
    before = float(target["pf"])
    target["pf"] = values["defender_remaining"]
    report = {
        "turn": turn_label(g),
        "position": coord(target["pos"]),
        "power": values["power"],
        "bonus": 0.0,
        "defense": values["defense"],
        "occupier_id": None,
        "participants": [{
            "id": target["id"], "owner": target["owner"], "name": target["name"],
            "role": "Défenseur", "before": before,
            "damage": values["defender_damage"], "after": target["pf"],
        }],
    }
    for a in attackers:
        a["acted"] = True
        report["participants"].append({
            "id": a["id"], "owner": a["owner"], "name": a["name"],
            "role": "Attaquant" if values.get("no_riposte") else "Attaquant invisible",
            "before": float(a["pf"]), "damage": 0.0, "after": float(a["pf"]),
        })
    log(
        g,
        f"{'Attaque' if values.get('no_riposte') else 'Attaque invisible'} "
        f"en {coord(target['pos'])} : "
        f"{target['name']} perd {values['defender_damage']:g} PF, aucune riposte.",
    )
    g["_combat_report"] = report
    if g.get("moving_unit_id") in {a["id"] for a in attackers}:
        g.pop("moving_unit_id")
    next_activation(g)


def ranged_riposte(g, attacker, target):
    """PF perdus par le tireur en retour (0 s'il est invisible et non détecté)."""
    if hidden_from(g, attacker, target["owner"]):
        return 0.0
    return min(float(attacker["pf"]), float(target["pf"]))


def ranged_riposte_text(g, attacker, target):
    riposte = ranged_riposte(g, attacker, target)
    if riposte == 0:
        return "👻 Tireur invisible et non détecté : aucune riposte."
    if riposte >= attacker["pf"]:
        return f"⚠️ Riposte : {riposte:g} PF, le tireur sera détruit."
    return f"Riposte : le tireur perd {riposte:g} PF et reste sur sa case."


_lw_riposte_previous_ranged_attack = ranged_attack


def ranged_attack(g, attacker_id, target_id, *args, **kwargs):
    attacker = entity(g, attacker_id)
    target = entity(g, target_id)
    riposte = ranged_riposte(g, attacker, target)

    _lw_riposte_previous_ranged_attack(g, attacker_id, target_id, *args, **kwargs)

    shooter = next((e for e in g["entities"] if e["id"] == attacker_id), None)
    if not riposte or shooter is None:
        return

    before = float(shooter["pf"])
    shooter["pf"] = before - riposte
    log(
        g,
        f"Riposte de {target['name']} : {shooter['name']} #{shooter['id']} "
        f"perd {riposte:g} PF, reste {max(0.0, shooter['pf']):g} PF.",
    )
    report = g.get("_combat_report")
    if report:
        for p in report.get("participants", []):
            if p["id"] == shooter["id"]:
                p["damage"] = riposte
                p["after"] = max(0.0, shooter["pf"])
    if shooter["pf"] <= 0:
        destroy(g, shooter, target["owner"])


# ============================================================
# FICHES DES FACTIONS (pages du PDF « Fiches des factions »)
# Consultables à tout moment : la fiche prend la place du plateau
# sans toucher à la partie, puis « Retour au plateau ».
# ============================================================

FACTION_SHEETS_DIR = Path(__file__).resolve().parent / "assets" / "fiches"
FACTION_SHEETS = {
    "Déferlants": FACTION_SHEETS_DIR / "deferlants.jpg",
    "Exilés": FACTION_SHEETS_DIR / "exiles.jpg",
    "Derniers nés": FACTION_SHEETS_DIR / "derniers_nes.jpg",
    "Vagabonds": FACTION_SHEETS_DIR / "vagabonds.jpg",
}


def show_faction_sheet(name):
    st.session_state.ui_faction_view = name


def hide_faction_sheet():
    st.session_state.ui_faction_view = None


def render_faction_sheet_menu(location):
    current = st.session_state.get("ui_faction_view")
    for name in FACTION_SHEETS:
        st.button(
            f"{'📖' if name == current else '📄'} {name}",
            key=f"faction_sheet_{location}_{name}",
            type="primary" if name == current else "secondary",
            width="stretch",
            on_click=show_faction_sheet,
            args=(name,),
        )
    if current in FACTION_SHEETS:
        st.button(
            "↩ Retour au plateau",
            key=f"faction_sheet_{location}_close",
            width="stretch",
            on_click=hide_faction_sheet,
        )
    else:
        st.caption("La fiche s'affiche à la place du plateau, sans interrompre la partie.")


def render_faction_sheet():
    name = st.session_state.get("ui_faction_view")
    path = FACTION_SHEETS.get(name)

    title_col, back_col = st.columns([4, 1])
    with title_col:
        st.subheader(f"📖 Fiche de faction : {name}")
    with back_col:
        st.button(
            "↩ Retour au plateau",
            key="faction_sheet_main_close",
            type="primary",
            width="stretch",
            on_click=hide_faction_sheet,
        )

    # Passer d'une fiche à l'autre sans revenir au menu.
    for column, other in zip(st.columns(len(FACTION_SHEETS)), FACTION_SHEETS):
        with column:
            st.button(
                other,
                key=f"faction_sheet_tab_{other}",
                type="primary" if other == name else "secondary",
                width="stretch",
                disabled=other == name,
                on_click=show_faction_sheet,
                args=(other,),
            )

    if path is not None and path.exists():
        st.image(str(path), width="stretch")
    else:
        st.warning("Fiche introuvable dans assets/fiches.")

    if name in AGE_REFERENCE:
        with st.expander("Valeurs utilisées par le jeu, âge par âge"):
            for age in (1, 2, 3):
                st.markdown(f"**Âge {age}**")
                for card_name, details in AGE_REFERENCE[name][age]:
                    st.markdown(f"- **{card_name}** : {details}")

    st.caption("La partie est en pause visuelle seulement : le plateau et les actions reviennent tels quels.")


# ============================================================
# LOGO « THE FOUR REALMS — WARGAME »
# Grand logo sur l'accueil, bandeau compact pendant la partie.
# ============================================================

LOGO_FULL = Path(__file__).resolve().parent / "assets" / "logo.jpg"
LOGO_BANNER = Path(__file__).resolve().parent / "assets" / "logo_bandeau.jpg"
HOME_BATTLE = Path(__file__).resolve().parent / "assets" / "accueil.jpg"
LOGO_HOME = Path(__file__).resolve().parent / "assets" / "logo_sans_texte.jpg"
LOGO_TITLE = Path(__file__).resolve().parent / "assets" / "logo_titre.jpg"


def image_base64(path_text):
    return file_base64(path_text)


def render_logo_header(home):
    data = image_base64(str(LOGO_FULL if home else LOGO_BANNER))
    if data is None:
        st.title("⚔️ The Four Realms")
        return

    if home:
        # Menu principal : titre centré, puis « The Four Realms » et ses deux épées
        # dorées sur fond brun.
        title = image_base64(str(LOGO_TITLE)) or data
        st.markdown(
            f"""
            <h1 style="text-align:center; margin:0 0 .8rem;">Menu principal</h1>
            <div style="display:flex; justify-content:center; margin:0 0 1.2rem;">
              <div style="background:#18120e; border:1px solid #b8913f; border-radius:16px;
                          padding:14px 28px; width:100%; max-width:760px;
                          box-shadow:0 12px 34px #00000059, inset 0 0 0 4px #18120e, inset 0 0 0 5px #b8913f55;">
                <img src="data:image/jpeg;base64,{title}" alt="The Four Realms"
                     style="width:100%; display:block; border-radius:8px;">
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Partie : bandeau sombre et doré, peu haut pour laisser la place au plateau.
    # st.image sert le fichier une seule fois (mis en cache), au lieu de
    # renvoyer ~150 Ko de texte base64 à chaque clic.
    st.markdown(
        """
        <style>
        .st-key-lw_logo_banner {
            background: #16110d; border: 1px solid #b8913f; border-radius: 12px;
            padding: 6px 12px !important; margin: 0 0 .5rem;
            box-shadow: inset 0 0 0 3px #16110d, inset 0 0 0 4px #b8913f55;
            align-items: center;
        }
        .st-key-lw_logo_banner img {
            height: 88px !important; width: auto !important; max-width: 100%;
            object-fit: contain; display: block; margin: 0 auto;
            -webkit-mask-image: linear-gradient(to right, transparent, #000 10%, #000 90%, transparent);
            mask-image: linear-gradient(to right, transparent, #000 10%, #000 90%, transparent);
        }
        .st-key-lw_logo_banner [data-testid="stImage"],
        .st-key-lw_logo_banner [data-testid="stImageContainer"] { width: 100%; align-items: center; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="lw_logo_banner"):
        st.image(str(LOGO_BANNER))


# ============================================================
# FACTION : LES VAGABONDS
# Pas de bâtiments : des héros mobiles servent de bases, produisent
# les esprits, récoltent la dernière ressource traversée et attaquent
# pendant la production (résolu au dévoilement, sans riposte).
# ============================================================

VAGABONDS = 3

# Héros : stats par âge = (PF, déplacement, portée, or, mana).
HERO_STATS = {
    "De Marbourg": {1: (2, 3, 0, 250, 1), 2: (4, 3, 0, 300, 2), 3: (6, 3, 0, 400, 3)},
    "Sayn": {1: (4, 3, 0, 150, 1), 2: (6, 3, 0, 200, 2), 3: (9, 3, 0, 250, 3)},
    "Wulfoad": {1: (2, 4, 0, 150, 1), 2: (4, 5, 0, 200, 2), 3: (6, 6, 0, 250, 3)},
    "Campbell": {2: (4, 3, 3, 300, 2), 3: (6, 3, 3, 400, 3)},
    "Aalongue": {3: (6, 4, 4, 500, 3)},
}
# Héros sans attaque : points de défense seulement (Aalongue lance des sorts).
HERO_NO_ATTACK = {"De Marbourg", "Aalongue"}
HERO_INITIALS = {"De Marbourg": "M", "Sayn": "S", "Wulfoad": "W", "Campbell": "C", "Aalongue": "A"}
# Places de départ : joueur du haut (siège 0) et du bas (siège 1).
HERO_START = {
    0: {"De Marbourg": "E4", "Sayn": "G3", "Wulfoad": "I2", "Campbell": "H6", "Aalongue": "H6"},
    1: {"De Marbourg": "Q16", "Sayn": "S15", "Wulfoad": "U14", "Campbell": "R11", "Aalongue": "R11"},
}
HERO_ARRIVALS = {2: "Campbell", 3: "Aalongue"}
AALONGUE_TELEPORT = 4

ERRANT = "Errant"
RAVAGER = "Ravageur"
SUPER_ERRANT = "Super Errant"
SUPER_RAVAGER = "Super Ravageur"
SORCERER = "Sorcier"
AGILE = "Agile"
BARBARIAN = "Barbare"
SEER = "Voyant"
SILENT = "Silencieux"
DESTRUCTION = "Destruction"
PERFECT = "Parfait"

VAG_UNITS = {
    ERRANT: {"cost": 100, "mana": 0, "batch": 1, "pf": 1, "move": 3, "range": 2, "limit": 12},
    RAVAGER: {"cost": 150, "mana": 0, "batch": 1, "pf": 2, "move": 3, "range": 0, "limit": 12},
    SUPER_ERRANT: {"cost": 0, "mana": 0, "batch": 1, "pf": 7, "move": 3, "range": 2, "limit": 1},
    SUPER_RAVAGER: {"cost": 0, "mana": 0, "batch": 1, "pf": 10, "move": 3, "range": 0, "limit": 1},
    SORCERER: {"cost": 400, "mana": 2, "batch": 1, "pf": 3, "move": 3, "range": 3, "limit": 2},
    AGILE: {"cost": 550, "mana": 0, "batch": 1, "pf": 3, "move": 3, "range": 3, "limit": 6},
    BARBARIAN: {"cost": 750, "mana": 2, "batch": 1, "pf": 6, "move": 3, "range": 0, "limit": 3},
    SEER: {"cost": 700, "mana": 2, "batch": 1, "pf": 1, "move": 3, "range": 5, "limit": 2},
    SILENT: {"cost": 1300, "mana": 5, "batch": 1, "pf": 7, "move": 4, "range": 0, "limit": 6},
    DESTRUCTION: {"cost": 1400, "mana": 3, "batch": 1, "pf": 12, "move": 3, "range": 0, "limit": 4},
    PERFECT: {"cost": 3000, "mana": 7, "batch": 1, "pf": 20, "move": 3, "range": 2, "limit": 1},
}
UNITS.update(VAG_UNITS)
UNIT_AGES.update({
    ERRANT: 1, RAVAGER: 1, SUPER_ERRANT: 1, SUPER_RAVAGER: 1,
    SORCERER: 2, AGILE: 2, BARBARIAN: 2,
    SEER: 3, SILENT: 3, DESTRUCTION: 3, PERFECT: 3,
})

# Unités de production consommées chez un héros (production directe).
VAG_SLOTS = {
    ERRANT: 1, RAVAGER: 1, SORCERER: 2, AGILE: 2, BARBARIAN: 2,
    SEER: 1, SILENT: 4, DESTRUCTION: 4, PERFECT: 4,
}

# Fusions : esprits nécessaires, coût, âge minimal. Résultat en attente 1 tour.
FUSIONS = {
    SUPER_ERRANT: {"parts": {ERRANT: 5}, "gold": 0, "mana": 1, "age": 1},
    SUPER_RAVAGER: {"parts": {RAVAGER: 4}, "gold": 0, "mana": 1, "age": 1},
    SORCERER: {"parts": {ERRANT: 1, RAVAGER: 1}, "gold": 150, "mana": 2, "age": 2},
    AGILE: {"parts": {ERRANT: 2}, "gold": 350, "mana": 0, "age": 2},
    BARBARIAN: {"parts": {RAVAGER: 2}, "gold": 450, "mana": 2, "age": 2},
    SILENT: {"parts": {AGILE: 2}, "gold": 0, "mana": 5, "age": 3},
    DESTRUCTION: {"parts": {BARBARIAN: 2}, "gold": 0, "mana": 1, "age": 3},
}
FUSION_MAX_GAP = 6

FACTIONS[VAGABONDS] = {
    "name": "Vagabonds",
    # Aucune base fixe : ce nom ne correspond à aucune pièce.
    "base": "Héros",
    "base_cost": 0,
    "base_pf": 2,
    "income": 0,
    "buildings": {},
    "extra_units": list(VAG_UNITS),
}

UPGRADES.update({
    "Étroite communication I": {
        "owner": VAGABONDS, "cost": 450, "mana": 0, "building": None, "age": 1,
        "effect": "Chaque héros produit 2 unités de production par tour.",
    },
    "Multitâches": {
        "owner": VAGABONDS, "cost": 550, "mana": 0, "building": None, "age": 1,
        "effect": "Les héros peuvent produire et bouger le même tour. Obligatoire pour l'âge II.",
    },
    "Solidarité": {
        "owner": VAGABONDS, "cost": 50, "mana": 0, "building": None, "age": 1,
        "effect": "Les unités sur l'or ou le mana récoltent (après la perte d'un héros).",
    },
    "Étroite communication II": {
        "owner": VAGABONDS, "cost": 650, "mana": 2, "building": None, "age": 2,
        "effect": "Chaque héros produit 4 unités de production par tour. Obligatoire pour l'âge III.",
    },
    "Mutation imminente": {
        "owner": VAGABONDS, "cost": 550, "mana": 2, "building": None, "age": 2,
        "effect": "Tous les Agiles volent.",
    },
    "Endurance": {
        "owner": VAGABONDS, "cost": 700, "mana": 1, "building": None, "age": 2,
        "effect": "+1 PF et +1 déplacement à tous les Barbares.",
    },
})
VAG_AGE_UPGRADES = {2: "Multitâches", 3: "Étroite communication II"}
PF_UPGRADES["Endurance"] = (BARBARIAN, 1)
SOLIDARITY_GOLD = {1: 100, 2: 100, 3: 150}

FLYING_UNITS.add(PERFECT)
INVISIBLE_UNITS.add(SILENT)
DETECTOR_RANGES[SEER] = 5
DETECTOR_RANGES["Aalongue"] = 4
TRAMPLERS[BARBARIAN] = 1
NO_ATTACK_UNITS.add(SORCERER)

SORCERER_SPELLS = {
    "freeze": "❄️ Gel glaçant : gèle les ennemis de 3 cases pendant 1 tour complet",
    "stalactites": "🧊 Pluie de stalactites : −3 PF aux ennemis de 3 cases",
}
STALACTITE_DAMAGE = 3.0

AGE_REFERENCE["Vagabonds"] = {
    1: [
        ("De Marbourg", "Héros · 2 PF de défense · 3 MVT · récolte 250 or ou 1 mana × la case marquée"),
        ("Sayn", "Héros · 4 PF · 3 MVT · corps à corps · 150 or ou 1 mana"),
        ("Wulfoad", "Héros · 2 PF · 4 MVT · 150 or ou 1 mana"),
        ("Errant", "Esprit · 100 or · 1 PF · 3 MVT · portée 2 · 1 unité de production"),
        ("Ravageur", "Esprit · 150 or · 2 PF · 3 MVT · 1 unité de production"),
        ("Super Errant", "Fusion de 5 Errants · 1 mana · 7 PF · portée 2"),
        ("Super Ravageur", "Fusion de 4 Ravageurs · 1 mana · 10 PF"),
        ("Étroite communication I", "450 or · 2 unités de production par héros"),
        ("Multitâches", "550 or · produire et bouger le même tour · requis pour l'âge II"),
        ("Solidarité", "50 or · les unités récoltent, après la perte d'un héros"),
    ],
    2: [
        ("Campbell", "Nouveau héros · 4 PF · 3 MVT · portée 3 · 300 or ou 2 mana"),
        ("Sorcier", "Errant + Ravageur (150 or + 2 mana) ou 400 or + 2 mana · sorts"),
        ("Agile", "2 Errants (350 or) ou 550 or · 3 PF · portée 3"),
        ("Barbare", "2 Ravageurs (450 or + 2 mana) ou 750 or + 2 mana · 6 PF · piétinement âge I"),
        ("Étroite communication II", "650 or + 2 mana · 4 unités de production · requis pour l'âge III"),
        ("Mutation imminente", "550 or + 2 mana · les Agiles volent"),
        ("Endurance", "700 or + 1 mana · Barbares +1 PF et +1 MVT"),
    ],
    3: [
        ("Aalongue", "Nouveau héros · 6 PF de défense · détecteur · téléportation, motivation"),
        ("Voyant", "700 or + 2 mana · 1 PF · portée 5 · détecteur"),
        ("Silencieux", "2 Agiles (5 mana) ou 1300 or + 5 mana · invisible · 7 PF"),
        ("Destruction", "2 Barbares (1 mana) ou 1400 or + 3 mana · 12 PF"),
        ("Parfait", "3000 or + 7 mana · 20 PF · portée 2 · volant"),
    ],
}


def is_vagabond(g, owner):
    return faction_id(g, owner) == VAGABONDS


def is_hero(piece):
    return piece is not None and piece.get("kind") == "base" and piece.get("name") in HERO_STATS


def hero_stats(g, hero):
    """(PF, déplacement, portée, or, mana) du héros à l'âge actuel."""
    age = g["players"][hero["owner"]]["age"]
    table = HERO_STATS[hero["name"]]
    return table.get(age) or table[max(a for a in table if a <= age)]


def hero_can_attack(hero):
    return hero["name"] not in HERO_NO_ATTACK


def multitasking(g, owner):
    return owns_upgrade(g, owner, "Multitâches")


def hero_capacity(g, owner):
    if owns_upgrade(g, owner, "Étroite communication II"):
        return 4
    if owns_upgrade(g, owner, "Étroite communication I"):
        return 2
    return 1


def hero_slots_used(g, hero):
    return hero.get("prod_used", 0) if hero.get("prod_turn") == g["turn"] else 0


def hero_moved(g, hero):
    return hero.get("moved_turn") == g["turn"]


def hero_ordered(g, hero):
    order = hero.get("attack_order")
    return bool(order) and order.get("turn") == g["turn"]


def hero_produced(g, hero):
    return hero_slots_used(g, hero) > 0


def hero_spawn_cell(g, owner, name):
    target = pos_from_coord(HERO_START[owner][name])
    if at(g, target) is None and not blocked(g, target):
        return target
    free = [p for p in CELLS if at(g, p) is None and not blocked(g, p)]
    return min(free, key=lambda p: (distance(p, target), p))


def add_hero(g, owner, name):
    pos = hero_spawn_cell(g, owner, name)
    pf = hero_stats(g, {"owner": owner, "name": name})[0]
    hero = add_entity(g, owner, name, "base", pos, pf)
    hero["hero"] = True
    hero["marker"] = list(pos) if key(pos) in g["resources"] else None
    return hero


# ------------------------------------------------------------
# Création de partie, validation, âges
# ------------------------------------------------------------

_lw_vag_previous_new_game = new_game


def new_game(first, target, minutes, victory_mode="time", factions=(DEFERLANTS, EXILES)):
    g = _lw_vag_previous_new_game(first, target, minutes, victory_mode, factions)
    for owner in (0, 1):
        if is_vagabond(g, owner):
            g["entities"] = [
                e for e in g["entities"]
                if not (e["owner"] == owner and e["kind"] == "base")
            ]
            for name in ("De Marbourg", "Sayn", "Wulfoad"):
                add_hero(g, owner, name)
    return g


_lw_vag_previous_faction_base_names = faction_base_names


def faction_base_names(faction):
    if faction.get("name") == "Vagabonds":
        return list(HERO_STATS)
    return _lw_vag_previous_faction_base_names(faction)


_lw_vag_previous_base_initial_pf = base_initial_pf


def base_initial_pf(g, base):
    if base["name"] in HERO_STATS:
        return hero_stats(g, base)[0]
    return _lw_vag_previous_base_initial_pf(g, base)


_lw_vag_previous_advance_age = advance_age


def advance_age(g, owner, target_age):
    if is_vagabond(g, owner):
        required = VAG_AGE_UPGRADES.get(target_age)
        if required and not owns_upgrade(g, owner, required):
            raise ValueError(f"Achète d'abord l'amélioration « {required} ».")

    _lw_vag_previous_advance_age(g, owner, target_age)

    if not is_vagabond(g, owner):
        return

    # Les héros évoluent aussitôt, en gardant leurs blessures.
    for hero in g["entities"]:
        if hero["owner"] != owner or not is_hero(hero):
            continue
        new_pf = float(hero_stats(g, hero)[0])
        damage = hero["max_pf"] - hero["pf"]
        hero["max_pf"] = new_pf
        hero["pf"] = max(0.5, new_pf - damage)

    newcomer = HERO_ARRIVALS.get(target_age)
    if newcomer:
        hero = add_hero(g, owner, newcomer)
        log(g, f"Nouveau héros : {newcomer} arrive en {coord(hero['pos'])}.")


_lw_vag_previous_destroy = destroy


def destroy(g, victim, credited_owner, killer=None):
    if is_hero(victim):
        player = g["players"][victim["owner"]]
        player["heroes_lost"] = player.get("heroes_lost", 0) + 1
    _lw_vag_previous_destroy(g, victim, credited_owner, killer)


_lw_vag_previous_available_upgrades = available_upgrades


def available_upgrades(g, owner):
    if not isinstance(owner, int) or not is_vagabond(g, owner):
        return _lw_vag_previous_available_upgrades(g, owner)
    player = g["players"][owner]
    return [
        name for name, data in UPGRADES.items()
        if data["owner"] == VAGABONDS
        and data.get("age", 1) <= player["age"]
        and name not in player["upgrades"]
    ]


_lw_vag_previous_purchase_upgrade = purchase_upgrade


def purchase_upgrade(g, owner, name):
    if name == "Solidarité" and not g["players"][owner].get("heroes_lost"):
        raise ValueError("Solidarité : possible seulement après la perte d'un héros.")
    _lw_vag_previous_purchase_upgrade(g, owner, name)


_lw_vag_previous_sync_unit_upgrades = sync_unit_upgrades


def sync_unit_upgrades(g, unit):
    _lw_vag_previous_sync_unit_upgrades(g, unit)
    if unit.get("name") == AGILE and owns_upgrade(g, unit["owner"], "Mutation imminente"):
        unit["flies"] = True


_lw_vag_previous_is_flying = is_flying


def is_flying(unit):
    return bool(unit.get("flies")) or _lw_vag_previous_is_flying(unit)


_lw_vag_previous_remaining_actions = remaining_actions


def remaining_actions(g, unit):
    bonus = 0
    if unit.get("name") == BARBARIAN and owns_upgrade(g, unit["owner"], "Endurance"):
        bonus += 1
    if g["players"][unit["owner"]].get("motivation_turn") == g["turn"]:
        bonus += 1
    if not bonus:
        return _lw_vag_previous_remaining_actions(g, unit)
    # Le bonus s'ajoute au budget AVANT de retirer ce qui a été dépensé
    # (sinon il restait toujours 1 déplacement : déplacements infinis).
    fresh = dict(unit, movement_spent=0, movement_spent_turn=None)
    budget = _lw_vag_previous_remaining_actions(g, fresh) + bonus
    return max(0, budget - movement_spent(g, unit))


_lw_vag_previous_can_move = can_move


def can_move(g, unit):
    if unit is not None and unit.get("frozen_until_turn", 0) >= g["turn"]:
        return False
    return _lw_vag_previous_can_move(g, unit)


# ------------------------------------------------------------
# Héros : déplacement (production), marqueur de récolte
# ------------------------------------------------------------

def hero_paths(g, hero):
    """Déplacement du héros : traverse ses unités, ses bases et ses bâtiments, pas les ennemis."""
    start = tuple(hero["pos"])
    # Déplacements restants ce tour (on peut bouger en plusieurs fois).
    budget = hero_stats(g, hero)[1] - hero_spent(g, hero)
    occupants = {tuple(e["pos"]): e for e in g["entities"]}
    costs, routes, queue = {start: 0}, {start: [start]}, [(0, start)]

    while queue:
        cost, pos = heapq.heappop(queue)
        if cost != costs[pos]:
            continue
        for nxt in neighbors(pos):
            if terrain(g, nxt) == "sea":
                continue
            occupant = occupants.get(nxt)
            if occupant is not None and (
                occupant["owner"] != hero["owner"] or occupant["kind"] not in ("unit", "base", "building")
            ):
                continue
            new_cost = cost + (2 if terrain(g, nxt) == "mountain" else 1)
            if new_cost > budget or new_cost >= costs.get(nxt, math.inf):
                continue
            costs[nxt] = new_cost
            routes[nxt] = routes[pos] + [nxt]
            heapq.heappush(queue, (new_cost, nxt))

    return costs, routes


def hero_spent(g, hero):
    return hero.get("move_spent", 0) if hero.get("move_spent_turn") == g["turn"] else 0


def hero_destinations(g, hero):
    if hero_ordered(g, hero) or (hero_produced(g, hero) and not multitasking(g, hero["owner"])):
        return {}
    costs, _ = hero_paths(g, hero)
    return {
        pos: cost for pos, cost in costs.items()
        if pos != tuple(hero["pos"]) and at(g, pos) is None
    }


def require_own_hero(g, owner, hero_id):
    hero = entity(g, hero_id)
    if hero["owner"] != owner or not is_hero(hero):
        raise ValueError("Choisis un de tes héros.")
    return hero


def move_hero(g, owner, hero_id, destination):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    destination = require_position(destination)

    if hero_ordered(g, hero):
        raise ValueError("Ce héros a attaqué ce tour : il ne peut plus bouger.")
    if hero_produced(g, hero) and not multitasking(g, owner):
        raise ValueError("Ce héros a produit ce tour : il faut Multitâches pour aussi bouger.")
    if destination not in hero_destinations(g, hero):
        raise ValueError("Destination inaccessible ou occupée.")

    costs, routes = hero_paths(g, hero)
    route = routes[destination]
    origin = coord(hero["pos"])
    hero["move_spent"] = hero_spent(g, hero) + costs[destination]
    hero["move_spent_turn"] = g["turn"]
    hero["pos"] = list(destination)
    hero["moved_turn"] = g["turn"]

    # Le marqueur suit la dernière case d'or ou de mana traversée.
    crossed = [p for p in route[1:] if key(p) in g["resources"]]
    if crossed:
        hero["marker"] = list(crossed[-1])
    log(
        g,
        f"{hero['name']} : {origin} → {coord(destination)}"
        + (f", marqueur posé en {coord(hero['marker'])}." if crossed else "."),
    )


def hero_collect(g, hero):
    marker = hero.get("marker")
    if not marker:
        return
    resource = g["resources"].get(key(tuple(marker)))
    if resource is None:
        return
    kind, multiplier = resource
    _, _, _, gold, mana = hero_stats(g, hero)
    amount = (gold if kind == "gold" else mana) * multiplier
    g["players"][hero["owner"]][kind] += amount
    log(
        g,
        f"{hero['name']} récolte {amount} {'or' if kind == 'gold' else 'mana'} "
        f"(marqueur en {coord(marker)}).",
    )


_lw_vag_previous_collect = collect_adjacent_resources


def collect_adjacent_resources(g, base):
    if is_hero(base):
        hero_collect(g, base)
        return
    _lw_vag_previous_collect(g, base)


_lw_vag_previous_harvest = harvest


def harvest(g):
    _lw_vag_previous_harvest(g)
    # Solidarité : chaque unité posée sur l'or ou le mana récolte.
    for owner in (0, 1):
        if not is_vagabond(g, owner) or not owns_upgrade(g, owner, "Solidarité"):
            continue
        age = g["players"][owner]["age"]
        for unit in g["entities"]:
            if unit["owner"] != owner or unit["kind"] != "unit":
                continue
            resource = g["resources"].get(key(tuple(unit["pos"])))
            if resource is None:
                continue
            kind, multiplier = resource
            amount = (SOLIDARITY_GOLD[age] if kind == "gold" else 1) * multiplier
            g["players"][owner][kind] += amount


# ------------------------------------------------------------
# Héros : attaque pendant la production, résolue au dévoilement
# ------------------------------------------------------------

def hero_attack_targets(g, hero):
    if not hero_can_attack(hero):
        return []
    _, _, reach, _, _ = hero_stats(g, hero)
    reach = max(1, reach)
    targets = []
    for piece in g["entities"]:
        if piece["owner"] == hero["owner"]:
            continue
        if not visible_to_player(g, piece, hero["owner"]):
            continue
        gap = distance(tuple(hero["pos"]), tuple(piece["pos"]))
        if gap > reach:
            continue
        if hero_stats(g, hero)[2] == 0 and is_flying(piece):
            continue
        targets.append(piece)
    return targets


def set_hero_attack(g, owner, hero_id, target_id):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    if not hero_can_attack(hero):
        raise ValueError(f"{hero['name']} ne peut pas attaquer.")
    if hero_produced(g, hero) and not multitasking(g, owner):
        raise ValueError("Ce héros a produit ce tour : il faut Multitâches pour aussi attaquer.")
    if hero_ordered(g, hero):
        raise ValueError(f"{hero['name']} a déjà attaqué ce tour.")
    target = entity(g, target_id)
    if target not in hero_attack_targets(g, hero):
        raise ValueError("Cible hors de portée, alliée ou invisible.")

    # Attaque immédiate : les dégâts s'affichent aussitôt dans la production
    # du joueur, puis sont appliqués à la partie au dévoilement.
    damage = float(hero_stats(g, hero)[0])
    before = float(target["pf"])
    hero["attack_order"] = {"target_id": target_id, "turn": g["turn"], "damage": damage}
    target["pf"] = before - damage
    if target["pf"] <= 0:
        g["entities"].remove(target)
        result = f"{target['name']} est détruit"
    else:
        result = f"{target['name']} tombe à {target['pf']:g} PF"
    log(g, f"{hero['name']} frappe {target['name']} : −{min(before, damage):g} PF, sans riposte.")
    g["_ui_message"] = (
        f"{hero['name']} frappe : {result}. "
        "L'adversaire le découvrira au dévoilement des productions."
    )


def cancel_hero_attack(g, owner, hero_id):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    hero.pop("attack_order", None)


def resolve_hero_attacks(g, order):
    lines = []
    for owner in order:
        for hero in [e for e in g["entities"] if e["owner"] == owner and is_hero(e)]:
            plan = hero.pop("attack_order", None)
            if not plan or plan.get("turn") != g["turn"] or hero not in g["entities"]:
                continue
            target = next((e for e in g["entities"] if e["id"] == plan["target_id"]), None)
            if target is None:
                continue
            # L'attaque a déjà eu lieu pendant la production : pas de nouveau contrôle de portée.
            damage = float(plan.get("damage", hero_stats(g, hero)[0]))
            before = float(target["pf"])
            target["pf"] = before - damage
            lines.append(
                f"{hero['name']} frappe {target['name']} : −{min(before, damage):g} PF, "
                "sans riposte."
            )
            if target["pf"] <= 0:
                cell = list(target["pos"])
                destroy(g, target, owner)
                # Corps à corps : le héros prend la case libérée.
                if hero_stats(g, hero)[2] == 0 and at(g, tuple(cell)) is None and not blocked(g, tuple(cell)):
                    hero["pos"] = cell
    for line in lines:
        log(g, line)
    if lines:
        g["_ui_message"] = " ".join(lines)
    check_victory(g)


_lw_vag_previous_commit_plan = commit_plan


def commit_plan(bundle):
    _lw_vag_previous_commit_plan(bundle)
    g = bundle["game"]
    if g["phase"] == "move":
        resolve_hero_attacks(g, (g["first"], 1 - g["first"]))


# ------------------------------------------------------------
# Production par les héros
# ------------------------------------------------------------

def hero_can_produce(g, hero, name):
    owner = hero["owner"]
    return (
        name in VAG_SLOTS
        and UNIT_AGES.get(name, 1) <= g["players"][owner]["age"]
        and hero_slots_used(g, hero) + VAG_SLOTS[name] <= hero_capacity(g, owner)
        and not ((hero_moved(g, hero) or hero_ordered(g, hero)) and not multitasking(g, owner))
        and g["players"][owner]["units_built"].get(name, 0) < UNITS[name]["limit"]
    )


def hero_recruit(g, owner, hero_id, name, positions):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    if name not in VAG_SLOTS:
        raise ValueError("Unité inconnue pour un héros.")
    if UNIT_AGES.get(name, 1) > g["players"][owner]["age"]:
        raise ValueError("Cette unité est débloquée à un âge supérieur.")
    if (hero_moved(g, hero) or hero_ordered(g, hero)) and not multitasking(g, owner):
        raise ValueError("Ce héros a bougé ou attaqué : il faut Multitâches pour aussi produire.")
    needed = VAG_SLOTS[name]
    if hero_slots_used(g, hero) + needed > hero_capacity(g, owner):
        raise ValueError(
            f"{name} demande {needed} unité(s) de production : capacité du héros "
            f"{hero_capacity(g, owner)} par tour."
        )
    count = g["players"][owner]["units_built"].get(name, 0)
    if count + 1 > UNITS[name]["limit"]:
        raise ValueError("Limite d'unités atteinte.")

    positions = [require_position(p) for p in positions]
    if len(positions) != 1 or positions[0] not in recruitment_slots(g, hero, 1):
        raise ValueError("Choisis une case libre à côté du héros.")

    pay(g, owner, UNITS[name]["cost"], UNITS[name]["mana"])
    unit = add_unit(g, owner, name, positions[0])
    unit["producer_id"] = hero_id
    sync_unit_upgrades(g, unit)
    g["players"][owner]["units_built"][name] = count + 1
    hero["prod_turn"] = g["turn"]
    hero["prod_used"] = hero_slots_used(g, hero) + needed
    log(g, f"{hero['name']} produit {name} en {coord(positions[0])}.")


_lw_vag_previous_recruit = recruit


def recruit(g, owner, producer_id, name, positions):
    if is_hero(entity(g, producer_id)):
        return hero_recruit(g, owner, producer_id, name, positions)
    return _lw_vag_previous_recruit(g, owner, producer_id, name, positions)


_lw_vag_previous_recruitment_batch = recruitment_batch


def recruitment_batch(g, owner, name):
    if name in VAG_UNITS:
        return 1
    return _lw_vag_previous_recruitment_batch(g, owner, name)


# ------------------------------------------------------------
# Fusion des esprits (production)
# ------------------------------------------------------------

def fusion_cells(g, parts):
    """Cases entre deux esprits (sur un plus court chemin), libres ou occupées par eux."""
    positions = [tuple(p["pos"]) for p in parts]
    ids = {p["id"] for p in parts}
    cells = set()
    for i, a in enumerate(positions):
        for b in positions[i + 1:]:
            gap = distance(a, b)
            for pos in CELLS:
                if distance(a, pos) + distance(pos, b) != gap or blocked(g, pos):
                    continue
                occupant = at(g, pos)
                if occupant is None or occupant["id"] in ids:
                    cells.add(pos)
    return sorted(cells)


def fusion_problem(g, owner, result, parts):
    recipe = FUSIONS.get(result)
    if recipe is None:
        return "Fusion inconnue."
    if g["players"][owner]["age"] < recipe["age"]:
        return f"{result} : fusion disponible à l'âge {recipe['age']}."
    counts = {}
    for p in parts:
        counts[p["name"]] = counts.get(p["name"], 0) + 1
    if counts != recipe["parts"]:
        need = ", ".join(f"{n} × {name}" for name, n in recipe["parts"].items())
        return f"{result} demande exactement : {need}."
    if any(p["owner"] != owner or p["kind"] != "unit" or p["wait"] for p in parts):
        return "Les esprits doivent être à toi et disponibles."
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            if distance(tuple(a["pos"]), tuple(b["pos"])) > FUSION_MAX_GAP:
                return f"Les esprits doivent être à {FUSION_MAX_GAP} cases maximum les uns des autres."
    if g["players"][owner]["units_built"].get(result, 0) >= UNITS[result]["limit"]:
        return f"Limite atteinte pour {result}."
    return None


def fuse_spirits(g, owner, result, unit_ids, destination):
    require_phase(g, "build", owner)
    parts = [entity(g, uid) for uid in unit_ids]
    if len({p["id"] for p in parts}) != len(parts):
        raise ValueError("Un esprit est choisi plusieurs fois.")
    problem = fusion_problem(g, owner, result, parts)
    if problem:
        raise ValueError(problem)
    destination = require_position(destination)
    if destination not in fusion_cells(g, parts):
        raise ValueError("Choisis une case entre les esprits qui fusionnent.")

    recipe = FUSIONS[result]
    pay(g, owner, recipe["gold"], recipe["mana"])
    for p in parts:
        g["entities"].remove(p)
    unit = add_unit(g, owner, result, destination)
    unit["wait"] = 1
    sync_unit_upgrades(g, unit)
    built = g["players"][owner]["units_built"]
    built[result] = built.get(result, 0) + 1
    log(g, f"Fusion : {len(parts)} esprits deviennent {result} en {coord(destination)} (attente 1 tour).")


# ------------------------------------------------------------
# Sorts : Sorcier (manœuvres) et Aalongue (production)
# ------------------------------------------------------------

def sorcerer_targets(g, sorcerer):
    return [
        piece for piece in g["entities"]
        if piece["owner"] != sorcerer["owner"]
        and piece["kind"] == "unit"
        and distance(tuple(piece["pos"]), tuple(sorcerer["pos"])) <= UNITS[SORCERER]["range"]
        and visible_to_player(g, piece, sorcerer["owner"])
    ]


def spell_cells(sorcerer, target):
    return [tuple(target["pos"]), *flank_cells(tuple(target["pos"]), tuple(sorcerer["pos"]))]


def cast_sorcerer_spell(g, sorcerer_id, spell, target_id):
    require_phase(g, "move")
    sorcerer = entity(g, sorcerer_id)
    if sorcerer["name"] != SORCERER or sorcerer["owner"] != g["active"]:
        raise ValueError("Choisis un de tes Sorciers.")
    if not can_move(g, sorcerer):
        raise ValueError("Ce Sorcier ne peut plus agir ce tour.")
    if spell not in SORCERER_SPELLS:
        raise ValueError("Sort inconnu.")
    target = entity(g, target_id)
    if target not in sorcerer_targets(g, sorcerer):
        raise ValueError("Cible invalide : unité ennemie visible à 3 cases maximum.")

    victims = [
        piece for pos in spell_cells(sorcerer, target)
        for piece in pieces_at(g, pos)
        if piece["owner"] != sorcerer["owner"] and piece["kind"] == "unit"
    ]
    sorcerer["acted"] = True
    if g.get("moving_unit_id") == sorcerer["id"]:
        g.pop("moving_unit_id")

    if spell == "freeze":
        for victim in victims:
            victim["frozen_until_turn"] = g["turn"] + 1
        log(g, f"Gel glaçant : {len(victims)} unité(s) gelée(s) jusqu'à la fin du tour {g['turn'] + 1}.")
    else:
        for victim in victims:
            victim["pf"] -= STALACTITE_DAMAGE
            if victim["pf"] <= 0:
                destroy(g, victim, sorcerer["owner"])
        log(g, f"Pluie de stalactites : −{STALACTITE_DAMAGE:g} PF à {len(victims)} unité(s) ennemie(s).")
    next_activation(g)


def aalongue_spell_used(g, hero):
    return hero.get("spell_turn") == g["turn"]


def cast_motivation(g, owner, hero_id):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    if hero["name"] != "Aalongue" or aalongue_spell_used(g, hero):
        raise ValueError("Aalongue a déjà lancé un sort ce tour.")
    hero["spell_turn"] = g["turn"]
    g["players"][owner]["motivation_turn"] = g["turn"]
    log(g, "Motivation : +1 déplacement pour toutes les unités ce tour.")


def teleport_cells(g, hero):
    return [p for p in neighbors(tuple(hero["pos"])) if at(g, p) is None and not blocked(g, p)]


def cast_teleport(g, owner, hero_id, unit_ids):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    if hero["name"] != "Aalongue" or aalongue_spell_used(g, hero):
        raise ValueError("Aalongue a déjà lancé un sort ce tour.")
    if not 1 <= len(unit_ids) <= AALONGUE_TELEPORT:
        raise ValueError(f"Choisis de 1 à {AALONGUE_TELEPORT} unités.")
    units = [entity(g, uid) for uid in unit_ids]
    if any(u["owner"] != owner or u["kind"] != "unit" for u in units):
        raise ValueError("Choisis tes propres unités.")
    cells = teleport_cells(g, hero)
    if len(cells) < len(units):
        raise ValueError("Pas assez de cases libres autour d'Aalongue.")
    for unit, pos in zip(units, cells):
        unit["pos"] = list(pos)
    hero["spell_turn"] = g["turn"]
    log(g, f"Téléportation : {len(units)} unité(s) autour d'Aalongue.")


# ------------------------------------------------------------
# Bâtiments techniques : J5 (joueur du haut), P12 (joueur du bas)
# ------------------------------------------------------------

TECH_CELLS = {0: "J5", 1: "P12"}


def tech_cell(owner):
    return pos_from_coord(TECH_CELLS[owner])


def is_tech_building(g, owner, name):
    return name is not None and name == TECH_BUILDINGS.get(faction_id(g, owner))


_lw_tech_previous_build = build


def build(g, owner, source_id, name, pos, accelerated):
    if is_tech_building(g, owner, name) and tuple(require_position(pos)) != tech_cell(owner):
        raise ValueError(
            f"{name} : bâtiment technique, constructible seulement en {TECH_CELLS[owner]}."
        )
    return _lw_tech_previous_build(g, owner, source_id, name, pos, accelerated)


# ------------------------------------------------------------
# Interface : sélection, placements et clics sur le plateau
# ------------------------------------------------------------

_lw_vag_previous_planning_slots = planning_slots


def planning_slots(g, view):
    source = selected_entity(view)
    mode = st.session_state.ui_plan_mode
    name = st.session_state.ui_plan_name
    owner = g["active"]

    if (
        g["phase"] == "build"
        and not g["curtain"]
        and g["winner"] is None
        and source is not None
        and source["owner"] == owner
        and is_hero(source)
    ):
        if mode == "hero_move":
            return list(hero_destinations(view, source))
        if mode == "recruit":
            return recruitment_slots(view, source, 1) if hero_can_produce(view, source, name) else []
        return []

    slots = _lw_vag_previous_planning_slots(g, view)
    if mode == "build" and is_tech_building(view, owner, name):
        return [p for p in slots if p == tech_cell(owner)]
    return slots


_lw_vag_previous_board_event = board_event


def board_event(event, g, view):
    if (
        not isinstance(event, dict)
        or event.get("type") != "cell_click"
        or g["phase"] != "build"
        or g["winner"] is not None
        or g["curtain"]
        or event.get("event_id") == st.session_state.ui_last_event
        or not is_vagabond(g, g["active"])
    ):
        return _lw_vag_previous_board_event(event, g, view)

    try:
        pos = require_position(event.get("pos"))
    except ValueError:
        return _lw_vag_previous_board_event(event, g, view)

    owner = g["active"]
    clicked = at(view, pos)
    source = selected_entity(view)
    mode = st.session_state.ui_plan_mode

    # Déplacement du héros : le clic sur une case verte suffit.
    if mode == "hero_move" and is_hero(source) and clicked is None:
        st.session_state.ui_last_event = event["event_id"]
        if pos in hero_destinations(view, source):
            clear_placement()
            # Après le déplacement, le héros reste prêt à repartir.
            st.session_state["_resume_plan"] = {"id": source["id"], "mode": "hero_move", "name": source["name"]}
            perform(draft_action, move_hero, source["id"], pos)
        st.session_state.ui_message = "Cette case n'est pas accessible pour ce héros."
        bump_ui()
        st.rerun()

    # Ordre d'attaque : héros sélectionné puis clic sur un ennemi.
    if clicked is not None and clicked["owner"] != owner and is_hero(source) and source["owner"] == owner:
        st.session_state.ui_last_event = event["event_id"]
        perform(draft_action, set_hero_attack, source["id"], clicked["id"])

    # Sélection des esprits (fusion) pendant la production.
    if clicked is not None and clicked["owner"] == owner and clicked["kind"] == "unit":
        st.session_state.ui_last_event = event["event_id"]
        st.session_state.ui_selected_id = None if source is not None and source["id"] == clicked["id"] else clicked["id"]
        clear_placement()
        st.session_state.ui_message = f"{clicked['name']} sélectionné : fusion possible dans le menu."
        bump_ui()
        st.rerun()

    return _lw_vag_previous_board_event(event, g, view)


def render_vag_upgrades(view, owner, prefix):
    st.markdown("#### Améliorations")
    owned = view["players"][owner].get("upgrades", [])
    if owned:
        st.caption("Achetées : " + ", ".join(u for u in owned if UPGRADES[u]["owner"] == VAGABONDS))
    for name in available_upgrades(view, owner):
        data = UPGRADES[name]
        cols = st.columns([3, 1])
        with cols[0]:
            st.write(f"**{name}** · {data['cost']} or" + (f" · {data['mana']} mana" if data["mana"] else ""))
            st.caption(data["effect"])
        with cols[1]:
            if st.button("Acheter", key=f"{prefix}_vag_upgrade_{name}"):
                perform(draft_action, purchase_upgrade, name)


def render_hero_controls(view, hero, prefix):
    owner = hero["owner"]
    pf, move, reach, gold, mana = hero_stats(view, hero)
    st.markdown(f"#### 🧭 Héros : {hero['name']}")
    marker = hero.get("marker")
    st.caption(
        f"{'Défense' if not hero_can_attack(hero) else 'PF'} {pf} · MVT {move}"
        + (f" · portée {reach}" if reach else (" · corps à corps" if hero_can_attack(hero) else ""))
        + f" · récolte {gold} or ou {mana} mana × la case marquée"
        + (f" ({coord(marker)})" if marker else " (aucun marqueur)")
    )

    if not multitasking(view, owner):
        st.caption("Sans Multitâches : ce tour, le héros produit OU bouge/attaque.")

    # Déplacement (possible en plusieurs fois)
    left = hero_stats(view, hero)[1] - hero_spent(view, hero)
    if not hero_destinations(view, hero):
        st.caption("✓ Plus de déplacement possible ce tour.")
    elif st.session_state.ui_plan_mode == "hero_move":
        st.caption(f"{left} déplacement(s) restant(s).")
        st.info("Clique sur une case verte : le héros s'y rend aussitôt.")
        if st.button("✕ Annuler le déplacement", key=f"{prefix}_hero_move_cancel_{hero['id']}"):
            clear_placement()
            st.session_state.ui_selected_id = None
            bump_ui()
            st.rerun()
    elif hero_destinations(view, hero):
        if st.button("🚶 Déplacer le héros", key=f"{prefix}_hero_move_{hero['id']}"):
            start_placement("hero_move", hero["name"])
            st.rerun()

    # Attaque au dévoilement
    if hero_can_attack(hero):
        order = hero.get("attack_order") if hero_ordered(view, hero) else None
        if order:
            target = next((e for e in view["entities"] if e["id"] == order["target_id"]), None)
            st.success(
                f"⚔️ {hero['name']} a déjà attaqué ce tour"
                + (f" ({target['name']})." if target else " (cible détruite).")
            )
        else:
            targets = hero_attack_targets(view, hero)
            st.caption(
                f"⚔️ Attaque : clique sur un ennemi à portée ({len(targets)} possible(s)). "
                "Les dégâts sont immédiats, sans riposte pour le héros."
            )

    # Sorts d'Aalongue
    if hero["name"] == "Aalongue":
        render_aalongue_spells(view, hero, prefix)

    # Production
    capacity = hero_capacity(view, owner)
    used = hero_slots_used(view, hero)
    st.markdown(f"#### Produire ({used}/{capacity} unité(s) de production)")
    for name, slots in VAG_SLOTS.items():
        if UNIT_AGES.get(name, 1) > view["players"][owner]["age"]:
            continue
        data = UNITS[name]
        built = view["players"][owner]["units_built"].get(name, 0)
        with st.container(border=True):
            st.write(
                f"**{name}** · {data['cost']} or"
                + (f" · {data['mana']} mana" if data["mana"] else "")
                + f" · {slots} unité(s) de production"
            )
            st.caption(
                f"{data['pf']} PF · MVT {data['move']} · Portée {data['range']} · "
                f"Construites : {built}/{data['limit']}"
            )
            if st.button(
                f"Recruter : {name}",
                key=f"{prefix}_choose_recruit_hero_{hero['id']}_{name}",
                disabled=not hero_can_produce(view, hero, name),
            ):
                start_placement("recruit", name)
                st.rerun()

    render_vag_upgrades(view, owner, prefix)

    age = view["players"][owner]["age"]
    required = VAG_AGE_UPGRADES.get(age + 1)
    if required:
        st.caption(f"Passage à l'âge {age + 1} : amélioration « {required} » obligatoire.")


def render_fusion_controls(view, unit, prefix):
    owner = unit["owner"]
    recipes = [
        result for result, recipe in FUSIONS.items()
        if unit["name"] in recipe["parts"] and recipe["age"] <= view["players"][owner]["age"]
    ]
    st.markdown("#### 🌀 Fusion des esprits")
    if unit["wait"]:
        st.caption("Cet esprit vient d'arriver : fusion possible au tour suivant.")
        return
    if not recipes:
        st.caption("Aucune fusion disponible pour cet esprit à cet âge.")
        return

    result = st.selectbox(
        "Résultat",
        recipes,
        format_func=lambda r: (
            f"{r} = " + " + ".join(f"{n} {p}" for p, n in FUSIONS[r]["parts"].items())
            + f" · {FUSIONS[r]['gold']} or" + (f" + {FUSIONS[r]['mana']} mana" if FUSIONS[r]["mana"] else "")
        ),
        key=f"{prefix}_fusion_result_{unit['id']}",
    )
    recipe = FUSIONS[result]
    partners = {
        p["id"]: p for p in view["entities"]
        if p["owner"] == owner and p["kind"] == "unit" and p["id"] != unit["id"]
        and p["name"] in recipe["parts"] and not p["wait"]
        and distance(tuple(p["pos"]), tuple(unit["pos"])) <= FUSION_MAX_GAP
    }
    need = sum(recipe["parts"].values()) - 1
    chosen = st.multiselect(
        f"Esprits à fusionner avec celui-ci ({need}, à {FUSION_MAX_GAP} cases maximum)",
        options=list(partners),
        format_func=lambda eid: describe(partners[eid]),
        max_selections=need,
        key=f"{prefix}_fusion_parts_{unit['id']}_{result}",
    )
    parts = [unit] + [partners[i] for i in chosen]
    problem = fusion_problem(view, owner, result, parts)
    if problem:
        st.caption(problem)
        return
    cells = fusion_cells(view, parts)
    destination = st.selectbox(
        "Case de la fusion (entre les esprits)",
        cells,
        format_func=coord,
        key=f"{prefix}_fusion_cell_{unit['id']}_{result}",
    )
    if st.button(f"🌀 Fusionner en {result}", type="primary", key=f"{prefix}_fusion_go_{unit['id']}"):
        perform(draft_action, fuse_spirits, result, [p["id"] for p in parts], destination)


_lw_vag_previous_render_worker_controls = render_worker_controls


def render_worker_controls(view, worker, prefix):
    _lw_vag_previous_render_worker_controls(view, worker, prefix)
    if view["phase"] == "build" and is_vagabond(view, worker["owner"]) and worker["kind"] == "unit":
        render_fusion_controls(view, worker, prefix)


# Sorcier : panneau de sorts en manœuvre, lancé au clic sur la cible.

_lw_vag_previous_attack_map_preview = attack_map_preview


def attack_map_preview(g, attackers):
    if len(attackers) == 1 and attackers[0]["name"] == SORCERER:
        sorcerer = attackers[0]
        if not can_move(g, sorcerer):
            return set(), {}
        origin = tuple(sorcerer["pos"])
        zone = {p for p in CELLS if 1 <= distance(origin, p) <= UNITS[SORCERER]["range"]}
        targets = {
            tuple(p["pos"]): {"target_id": p["id"], "spell": True, "ranged": True,
                              "distance": distance(origin, tuple(p["pos"]))}
            for p in sorcerer_targets(g, sorcerer)
        }
        return zone, targets
    return _lw_vag_previous_attack_map_preview(g, attackers)


def render_sorcerer_controls(g, sorcerer, prefix):
    st.subheader("🔮 Sorts du Sorcier")
    if not can_move(g, sorcerer):
        st.info("Ce Sorcier a déjà agi ce tour.")
        return
    spell = st.radio("Sort", list(SORCERER_SPELLS), format_func=SORCERER_SPELLS.get, key=f"{prefix}_sorcerer_spell")
    candidates = {p["id"]: p for p in sorcerer_targets(g, sorcerer)}
    if not candidates:
        st.info("Aucune unité ennemie à 3 cases.")
        return
    st.caption("Clique sur la cible sur le plateau : le sort part aussitôt (la cible et ses 2 voisines).")
    clicked = st.session_state.get("ui_target_id")
    if clicked in candidates and auto_confirm("sorcerer", sorcerer["id"], spell, clicked):
        perform(game_action, cast_sorcerer_spell, sorcerer["id"], spell, clicked)


_lw_vag_previous_render_move_controls = render_move_controls


def render_move_controls(g):
    attackers = selected_attackers(g)
    if len(attackers) == 1 and attackers[0]["name"] == SORCERER:
        prefix = f"vag_{g['turn']}_{g['active']}_{st.session_state.ui_revision}"
        render_sorcerer_controls(g, attackers[0], prefix)
        render_previous_move_controls_without_target(g)
        return
    _lw_vag_previous_render_move_controls(g)


# ============================================================
# EXILÉS : ARAMIL LE SORCIER ÉLU ET LE TITAN ARAGNAK
# Amélioration au Marché : un Mage des montagnes peut devenir Aramil.
# Aramil garde les sorts du Mage et gagne 2 pouvoirs :
# - Incendie : détruit jusqu'à 2 bâtiments ennemis à sa portée ;
# - Appel du Titan Aragnak : une unité de 12 PF pendant 1 tour.
# ============================================================

TITAN = "Titan Aragnak"
ARAMIL_UPGRADE = "Aramil le sorcier élu"
ARAMIL_BURN_TARGETS = 2

UNITS[ARAMIL] = dict(UNITS[MOUNTAIN_MAGE], cost=0, mana=0)
UNITS[TITAN] = {"cost": 0, "mana": 0, "batch": 1, "pf": 12, "move": 3, "range": 0, "limit": 1}
UNIT_AGES[ARAMIL] = 2
UNIT_AGES[TITAN] = 2
UNIT_ENTITY_SOURCES[ARAMIL] = MOUNTAIN_MAGE
FACTIONS[EXILES].setdefault("extra_units", [])
if TITAN not in FACTIONS[EXILES]["extra_units"]:
    FACTIONS[EXILES]["extra_units"].append(TITAN)

UPGRADES[ARAMIL_UPGRADE] = {
    "owner": EXILES,
    "cost": 350,
    "mana": 2,
    "building": "Marché",
    "age": 2,
    "effect": (
        "Un Mage des montagnes peut devenir Aramil : il garde ses sorts, "
        "peut incendier 2 bâtiments ennemis à portée ou appeler le Titan Aragnak."
    ),
}
MUTATIONS[MOUNTAIN_MAGE] = (ARAMIL, ARAMIL_UPGRADE, 0)

AGE_REFERENCE["Exilés"][2].append(
    (ARAMIL_UPGRADE, "Amélioration · Marché · 350 or + 2 mana · transforme un Mage en Aramil")
)
AGE_REFERENCE["Exilés"][2].append(
    (TITAN, "Appelé par Aramil pour 1 tour · 12 PF · 3 MVT · corps à corps · montagne = 1 MVT")
)


def aramil_range(g, aramil):
    reach = UNITS[ARAMIL]["range"]
    if terrain(g, tuple(aramil["pos"])) == "mountain":
        reach += 1
    return reach


def aramil_burn_targets(g, aramil):
    return [
        piece for piece in g["entities"]
        if piece["owner"] != aramil["owner"]
        and piece["kind"] == "building"
        and distance(tuple(piece["pos"]), tuple(aramil["pos"])) <= aramil_range(g, aramil)
    ]


def titan_cells(g, aramil):
    return [
        pos for pos in neighbors(tuple(aramil["pos"]))
        if at(g, pos) is None and not blocked(g, pos)
    ]


def require_aramil_power(g, aramil_id):
    require_phase(g, "move")
    aramil = entity(g, aramil_id)
    if aramil["name"] != ARAMIL or aramil["owner"] != g["active"]:
        raise ValueError("Choisis ton Aramil.")
    if not mage_spell_ready(g, aramil):
        raise ValueError("Aramil a déjà lancé un sort récemment (un sort tous les deux tours).")
    return aramil


def end_aramil_power(g, aramil):
    aramil["acted"] = True
    aramil["next_spell_turn"] = g["turn"] + 2
    if g.get("moving_unit_id") == aramil["id"]:
        g.pop("moving_unit_id")


def aramil_burn(g, aramil_id, target_ids):
    aramil = require_aramil_power(g, aramil_id)
    if not 1 <= len(target_ids) <= ARAMIL_BURN_TARGETS or len(set(target_ids)) != len(target_ids):
        raise ValueError(f"Choisis 1 à {ARAMIL_BURN_TARGETS} bâtiments différents.")
    allowed = {p["id"] for p in aramil_burn_targets(g, aramil)}
    if any(t not in allowed for t in target_ids):
        raise ValueError("Bâtiment hors de portée d'Aramil, ou allié.")

    end_aramil_power(g, aramil)
    names = []
    for target_id in target_ids:
        target = entity(g, target_id)
        names.append(f"{target['name']} ({coord(target['pos'])})")
        destroy(g, target, aramil["owner"])
    log(g, "Incendie d'Aramil : " + ", ".join(names) + " réduit(s) en cendres.")
    g["_ui_message"] = "🔥 Incendie : " + ", ".join(names) + " détruit(s)."
    next_activation(g)


def aramil_summon_titan(g, aramil_id, pos):
    aramil = require_aramil_power(g, aramil_id)
    pos = require_position(pos)
    if any(e["owner"] == aramil["owner"] and e["name"] == TITAN for e in g["entities"]):
        raise ValueError("Le Titan Aragnak est déjà sur le plateau.")
    if pos not in titan_cells(g, aramil):
        raise ValueError("Choisis une case libre à côté d'Aramil.")

    end_aramil_power(g, aramil)
    titan = add_unit(g, aramil["owner"], TITAN, pos)
    # Le Titan agit dès ce tour, puis disparaît à la fin du tour.
    titan["summoned_turn"] = g["turn"]
    log(g, f"Aramil appelle le Titan Aragnak en {coord(pos)} pour 1 tour.")
    g["_ui_message"] = (
        f"🗿 Titan Aragnak appelé en {coord(pos)} : il peut agir ce tour, "
        "puis disparaîtra à la fin du tour."
    )
    next_activation(g)


_lw_aramil_previous_end_round = end_round


def end_round(g):
    # Le Titan Aragnak ne reste qu'un tour.
    for titan in [e for e in g["entities"] if e["name"] == TITAN and e.get("summoned_turn") is not None]:
        g["entities"].remove(titan)
        log(g, "Le Titan Aragnak retourne à la terre.")
    _lw_aramil_previous_end_round(g)


_lw_aramil_previous_paths = paths


def paths(g, unit, allow_attack=False):
    if unit.get("name") != TITAN:
        return _lw_aramil_previous_paths(g, unit, allow_attack)
    # Le Titan traverse les montagnes pour 1 déplacement au lieu de 2.
    flat = dict(g)
    flat["terrain"] = {
        cell: ("plain" if kind == "mountain" else kind)
        for cell, kind in g["terrain"].items()
    }
    return _lw_aramil_previous_paths(flat, unit, allow_attack)


_lw_aramil_previous_render_mage_controls = render_mage_controls


def render_mage_controls(g, mage):
    _lw_aramil_previous_render_mage_controls(g, mage)
    if mage["name"] != ARAMIL or not can_move(g, mage):
        return

    st.markdown("#### 🔥 Pouvoirs d'Aramil")
    if not mage_spell_ready(g, mage):
        st.caption("Pouvoirs disponibles quand le prochain sort est prêt.")
        return

    prefix = f"aramil_{g['turn']}_{mage['id']}_{st.session_state.ui_revision}"
    buildings = {p["id"]: p for p in aramil_burn_targets(g, mage)}
    if buildings:
        chosen = st.multiselect(
            f"Incendie : jusqu'à {ARAMIL_BURN_TARGETS} bâtiments ennemis à portée",
            options=list(buildings),
            format_func=lambda eid: describe(buildings[eid]),
            max_selections=ARAMIL_BURN_TARGETS,
            key=f"{prefix}_burn",
        )
        if chosen and st.button("🔥 Incendier", type="primary", key=f"{prefix}_burn_go"):
            perform(game_action, aramil_burn, mage["id"], list(chosen))
    else:
        st.caption("Incendie : aucun bâtiment ennemi à portée.")

    cells = titan_cells(g, mage)
    if any(e["owner"] == mage["owner"] and e["name"] == TITAN for e in g["entities"]):
        st.caption("Le Titan Aragnak est déjà sur le plateau.")
    elif cells:
        cell = st.selectbox("Case du Titan Aragnak", cells, format_func=coord, key=f"{prefix}_titan_cell")
        if st.button("🗿 Appeler le Titan Aragnak (1 tour)", key=f"{prefix}_titan_go"):
            perform(game_action, aramil_summon_titan, mage["id"], cell)
    else:
        st.caption("Titan : aucune case libre à côté d'Aramil.")


# ============================================================
# CATAPULTE DE L'ENFER : case visée et case de derrière 6 PF,
# cases de gauche et de droite 3 PF (alliés compris).
# ============================================================

HELL_MAIN_DAMAGE = 6.0
HELL_SIDE_DAMAGE = 3.0


def cell_behind(attacker_pos, target_pos):
    """Case voisine de la cible, dans le prolongement du tir."""
    gap = distance(attacker_pos, target_pos)
    ax, ay = flat_center(attacker_pos, 1, 0, 0)
    tx, ty = flat_center(target_pos, 1, 0, 0)
    px, py = tx + (tx - ax) / gap, ty + (ty - ay) / gap
    farther = [p for p in neighbors(target_pos) if distance(attacker_pos, p) == gap + 1]
    if not farther:
        return None
    return min(farther, key=lambda p: (
        (flat_center(p, 1, 0, 0)[0] - px) ** 2 + (flat_center(p, 1, 0, 0)[1] - py) ** 2, p
    ))


_lw_hell_previous_siege_values = siege_values


def siege_values(g, attacker, target):
    values = _lw_hell_previous_siege_values(g, attacker, target)
    if attacker["name"] == HELL_CATAPULT:
        damage = HELL_MAIN_DAMAGE + (2.0 if owns_upgrade(g, attacker["owner"], "Pierres enflammées") else 0.0)
        values = dict(values, damage=damage, remaining=max(0.0, float(target["pf"]) - damage))
    return values


_lw_hell_previous_siege_attack = siege_attack


def siege_attack(g, attacker, target):
    if attacker["name"] != HELL_CATAPULT:
        return _lw_hell_previous_siege_attack(g, attacker, target)

    values = siege_values(g, attacker, target)
    origin = tuple(attacker["pos"])
    target_pos = tuple(target["pos"])
    behind = cell_behind(origin, target_pos)
    flanks = siege_side_cells(origin, target_pos)

    report = {
        "turn": turn_label(g),
        "position": coord(target_pos),
        "power": values["damage"],
        "bonus": 0.0,
        "defense": float(target["pf"]),
        "occupier_id": None,
        "participants": [{
            "id": attacker["id"], "owner": attacker["owner"], "name": attacker["name"],
            "role": "Tir de siège", "before": float(attacker["pf"]),
            "damage": 0.0, "after": float(attacker["pf"]),
        }],
    }
    attacker["acted"] = True
    attacker["siege_ready_turn"] = g["turn"] + SIEGE_RELOAD_TURNS
    if g.get("moving_unit_id") == attacker["id"]:
        g.pop("moving_unit_id")

    log(g, f"{attacker['name']} #{attacker['id']} bombarde {coord(target_pos)}.")
    apply_damage(g, target, values["damage"], attacker, report, "Cible du tir de siège")
    if behind is not None:
        for victim in pieces_at(g, behind):
            apply_damage(g, victim, values["damage"], attacker, report, "Case derrière la cible")
    for pos in flanks:
        for victim in pieces_at(g, pos):
            apply_damage(g, victim, HELL_SIDE_DAMAGE, attacker, report, "Case voisine du tir de siège")

    g["_combat_report"] = report
    next_activation(g)


_lw_hell_previous_render_siege_controls = render_siege_controls


def render_siege_controls(g, unit, prefix):
    if unit["name"] != HELL_CATAPULT:
        return _lw_hell_previous_render_siege_controls(g, unit, prefix)
    low, high = SIEGE_RANGES[unit["name"]]
    ready = unit.get("siege_ready_turn", 0)
    st.caption(
        f"{unit['name']} : tir de {low} à {high} cases · "
        f"{HELL_MAIN_DAMAGE:g} PF sur la case visée et sur la case de derrière "
        f"(+2 avec Pierres enflammées), {HELL_SIDE_DAMAGE:g} PF à gauche et à droite, "
        "alliés compris."
        + (f" Rechargement : prochain tir au tour {ready}." if g["turn"] < ready else "")
    )


# Derniers nés : le bouton de construction affiche la base de l'âge actuel.

def dn_base_label(view, owner, name):
    if faction_id(view, owner) == DERNIERS_NES and name == faction_of(view, owner)["base"]:
        return dn_base_name(view, owner)
    return name


# ============================================================
# LIMITES DE BÂTIMENTS (symbole « château × N » des fiches)
# Bâtiments en jeu comptés ; les bases n'ont pas de limite (∞).
# ============================================================

def building_limit(g, owner, name):
    data = faction_of(g, owner)["buildings"].get(name)
    return None if data is None else data.get("limit")


def building_count(g, owner, name):
    return sum(p["owner"] == owner and p["name"] == name for p in g["entities"])


def building_limit_reached(g, owner, name):
    limit = building_limit(g, owner, name)
    return limit is not None and building_count(g, owner, name) >= limit


def building_limit_text(g, owner, name):
    limit = building_limit(g, owner, name)
    if limit is None:
        return "Construits : ∞"
    text = f"Construits : {building_count(g, owner, name)}/{limit}"
    return text + (" · limite atteinte" if building_limit_reached(g, owner, name) else "")


# ============================================================
# PLATEAU JAMAIS BLOQUÉ
# Le plateau se verrouille après un clic et attend une nouvelle
# révision. Tout clic qui ne change rien doit quand même répondre,
# sinon le plateau reste grisé et refuse les clics suivants.
# ============================================================

_lw_unlock_previous_process_queued_board_event = process_queued_board_event


def process_queued_board_event(g, view):
    event = st.session_state.get("ui_queued_board_event")
    revision = st.session_state.get("ui_revision")
    _lw_unlock_previous_process_queued_board_event(g, view)

    if event is None or st.session_state.get("ui_revision") != revision:
        return

    # Aucun traitement n'a répondu : on explique et on déverrouille.
    if not st.session_state.get("ui_message"):
        try:
            pos = require_position(event.get("pos"))
            clicked = at(view, pos)
        except (ValueError, AttributeError):
            clicked = None
        if (
            clicked is not None
            and g["phase"] == "move"
            and clicked["owner"] == g["active"]
            and clicked["kind"] != "unit"
        ):
            st.session_state.ui_message = (
                f"{clicked['name']} : on ne construit pas pendant les manœuvres. "
                "Sélectionne une unité pour la déplacer ou attaquer."
            )
        elif clicked is not None and clicked["owner"] == g["active"]:
            st.session_state.ui_message = (
                f"{clicked['name']} ne peut pas agir maintenant."
            )
    bump_ui()


# ============================================================
# CORRECTIONS DE RÈGLES
# ============================================================

# --- Tigre des forêts : piétinement contre l'âge I avec « Meute de tigres ».
TIGER = "Tigre des forêts"
TIGER_PACK = "Meute de tigres"

_lw_fix_previous_sync_unit_upgrades = sync_unit_upgrades


def sync_unit_upgrades(g, unit):
    _lw_fix_previous_sync_unit_upgrades(g, unit)
    if unit.get("name") == TIGER:
        if owns_upgrade(g, unit["owner"], TIGER_PACK):
            unit["trample_age"] = 1
        else:
            unit.pop("trample_age", None)


_lw_fix_previous_can_trample = can_trample


def can_trample(unit, target):
    max_age = unit.get("trample_age")
    if max_age is not None:
        return target["kind"] == "unit" and UNIT_AGES.get(target["name"], 1) <= max_age
    return _lw_fix_previous_can_trample(unit, target)


UPGRADES[TIGER_PACK]["effect"] = (
    UPGRADES[TIGER_PACK]["effect"].rstrip(".")
    + ". Les Tigres piétinent les unités d'âge I."
)


# --- Riposte des tirs : seule une unité qui tire elle-même riposte, si le
#     tireur est à sa portée (et pas s'il est invisible et non détecté).

def ranged_riposte(g, attacker, target):
    if hidden_from(g, attacker, target["owner"]):
        return 0.0
    reach = UNITS.get(target["name"], {}).get("range", 0) if target["kind"] == "unit" else 0
    if reach <= 0 or distance(tuple(attacker["pos"]), tuple(target["pos"])) > reach:
        return 0.0
    return min(float(attacker["pf"]), float(target["pf"]))


def ranged_riposte_text(g, attacker, target):
    if hidden_from(g, attacker, target["owner"]):
        return "👻 Tireur invisible et non détecté : aucune riposte."
    riposte = ranged_riposte(g, attacker, target)
    if riposte == 0:
        return "La cible ne tire pas jusqu'au tireur : aucune riposte."
    if riposte >= attacker["pf"]:
        return f"⚠️ Riposte : {riposte:g} PF, le tireur sera détruit."
    return f"Riposte : le tireur perd {riposte:g} PF et reste sur sa case."


# --- Une unité qui tire reste sur sa case : elle ne prend pas la place
#     de l'ennemi détruit, même au corps à corps.

def is_shooter(unit):
    return UNITS.get(unit.get("name"), {}).get("range", 0) > 0


_lw_fix_previous_attack = attack


def attack(g, attacker_ids, target_id, occupier_id=None, losses=None, *args, **kwargs):
    origins = {
        eid: list(entity(g, eid)["pos"])
        for eid in attacker_ids
        if any(e["id"] == eid for e in g["entities"])
    }
    target_pos = list(entity(g, target_id)["pos"])
    _lw_fix_previous_attack(g, attacker_ids, target_id, occupier_id, losses, *args, **kwargs)

    for eid, origin in origins.items():
        unit = next((e for e in g["entities"] if e["id"] == eid), None)
        if unit is not None and is_shooter(unit) and unit["pos"] == target_pos and at(g, tuple(origin)) is None:
            unit["pos"] = origin
            log(g, f"{unit['name']} #{eid} tire et reste sur sa case ({coord(origin)}).")


# --- Marais d'aspergeurs : plus de Rampants en recrutement direct
#     (ils viennent seulement de la mutation d'un Aspergeur).
FACTIONS[DEFERLANTS]["buildings"]["Marais d'aspergeurs"]["units"] = [
    u for u in FACTIONS[DEFERLANTS]["buildings"]["Marais d'aspergeurs"]["units"] if u != RAMPANT
]
FACTIONS[DEFERLANTS].setdefault("extra_units", [])
if RAMPANT not in FACTIONS[DEFERLANTS]["extra_units"]:
    FACTIONS[DEFERLANTS]["extra_units"].append(RAMPANT)
UPGRADES["Rampants"]["effect"] = "Débloque la mutation d'un Aspergeur en Rampant."


# --- Bâtiment technique détruit : les améliorations qu'il donnait sont perdues.

def remove_upgrades_of(g, owner, building):
    player = g["players"][owner]
    lost = [u for u in player.get("upgrades", []) if UPGRADES.get(u, {}).get("building") == building]
    if not lost:
        return []
    player["upgrades"] = [u for u in player["upgrades"] if u not in lost]

    for unit in g["entities"]:
        if unit["owner"] != owner or unit["kind"] != "unit":
            continue
        bonuses = unit.get("pf_bonuses") or []
        for upgrade in [u for u in bonuses if u in lost]:
            bonus = PF_UPGRADES.get(upgrade, (None, 0))[1]
            unit["max_pf"] -= bonus
            unit["pf"] = max(0.5, min(unit["pf"], unit["max_pf"]))
            bonuses.remove(upgrade)
        if any(u in ATTACK_UPGRADES for u in lost):
            unit.pop("attack_bonus", None)
        sync_unit_upgrades(g, unit)
    return lost


_lw_fix_previous_destroy = destroy


def destroy(g, victim, credited_owner, killer=None):
    _lw_fix_previous_destroy(g, victim, credited_owner, killer)
    owner = victim["owner"]
    tech = TECH_BUILDINGS.get(faction_id(g, owner))
    if victim["kind"] != "building" or victim["name"] != tech:
        return
    if any(e["owner"] == owner and e["name"] == tech for e in g["entities"]):
        return
    lost = remove_upgrades_of(g, owner, tech)
    if lost:
        log(g, f"{tech} détruit : améliorations perdues ({', '.join(lost)}).")


# --- 3e base détruite : fin de partie immédiate, même en mode « au temps ».

_lw_fix_previous_check_victory = check_victory


def check_victory(g):
    if g["winner"] is None:
        candidates = [o for o in (0, 1) if g["players"][o]["bases"] >= 3]
        if candidates:
            g["winner"] = candidates[0] if len(candidates) == 1 else -1
            return
    _lw_fix_previous_check_victory(g)


# ============================================================
# PRODUCTIONS : COLLISIONS RÉSOLUES AUTOMATIQUEMENT
# Les deux productions sont secrètes : deux pièces peuvent viser la même
# case (recrue, héros ou ouvrier déplacé, construction...). Le premier
# joueur garde sa case ; la pièce du second va sur la case libre la plus
# proche. La partie ne peut plus rester bloquée.
# ============================================================

def nearest_free_cell(g, taken, piece, origin):
    candidates = [
        pos for pos in CELLS
        if pos not in taken
        and not blocked(g, pos)
        and (piece["kind"] == "unit" or piece.get("hero") or key(pos) not in g["resources"])
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda pos: (distance(pos, origin), pos))


def resolve_production_collisions(bundle):
    g = bundle["game"]
    first_draft = bundle.get("committed")
    draft = bundle.get("draft")
    if g["phase"] != "build" or not g["ready"] or first_draft is None or draft is None:
        return []

    first_owner = g["ready"][0]
    second_owner = g["active"]
    placed = [e for e in first_draft["entities"] if e["owner"] == first_owner]
    moved = []

    for piece in [e for e in draft["entities"] if e["owner"] == second_owner]:
        if stacking_valid(g, placed + [piece]):
            placed.append(piece)
            continue
        origin = tuple(piece["pos"])
        taken = {tuple(e["pos"]) for e in placed}
        target = nearest_free_cell(g, taken, piece, origin)
        if target is None:
            placed.append(piece)
            continue
        piece["pos"] = list(target)
        placed.append(piece)
        moved.append(f"{piece['name']} {coord(origin)} → {coord(target)}")

    if moved:
        draft["log"].append(
            f"T{turn_label(g)} — Case déjà prise par le premier joueur : "
            + ", ".join(moved) + "."
        )
    return moved


_lw_collide_previous_commit_plan = commit_plan


def restore_strike_positions(bundle):
    """Avant le dévoilement, le héros revient sur sa case de frappe : sa cible
    existe encore chez l'adversaire. Il reprendra la case au dévoilement."""
    for plan in (bundle.get("committed"), bundle.get("draft")):
        if not plan:
            continue
        for hero in plan["entities"]:
            origin = hero.pop("strike_from", None)
            if origin is not None and is_hero(hero):
                hero["pos"] = origin


def commit_plan(bundle):
    g = bundle["game"]
    if g["phase"] == "build" and g["ready"]:
        restore_strike_positions(bundle)
    moved = resolve_production_collisions(bundle)
    _lw_collide_previous_commit_plan(bundle)
    if moved:
        g = bundle["game"]
        note = "Collision de productions : " + ", ".join(moved) + " (case libre la plus proche)."
        g["_ui_message"] = (g.get("_ui_message") + " " if g.get("_ui_message") else "") + note


# ============================================================
# HÉROS : SE DÉPLACER PUIS ATTAQUER EN PRODUCTION
# Comme une unité : le héros peut marcher jusqu'à l'ennemi (dans la
# limite de ses déplacements) puis frapper, sans riposte. Les cibles
# possibles sont surlignées en rouge sur le plateau.
# ============================================================

def hero_attack_plan(g, hero):
    """{id de la cible: case d'où le héros frappe}."""
    if not hero_can_attack(hero) or hero_ordered(g, hero):
        return {}
    if hero_produced(g, hero) and not multitasking(g, hero["owner"]):
        return {}
    _, _, reach, _, _ = hero_stats(g, hero)
    reach = max(1, reach)
    start = tuple(hero["pos"])
    costs, _ = hero_paths(g, hero)
    stands = {pos: c for pos, c in costs.items() if pos == start or at(g, pos) is None}

    plan = {}
    for piece in g["entities"]:
        if piece["owner"] == hero["owner"] or not visible_to_player(g, piece, hero["owner"]):
            continue
        if reach == 1 and is_flying(piece):
            continue
        spots = [p for p in stands if distance(p, tuple(piece["pos"])) <= reach]
        if spots:
            plan[piece["id"]] = min(spots, key=lambda p: (stands[p], p))
    return plan


def hero_attack_targets(g, hero):
    plan = hero_attack_plan(g, hero)
    return [p for p in g["entities"] if p["id"] in plan]


def set_hero_attack(g, owner, hero_id, target_id):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    if not hero_can_attack(hero):
        raise ValueError(f"{hero['name']} ne peut pas attaquer.")
    if hero_ordered(g, hero):
        raise ValueError(f"{hero['name']} a déjà attaqué ce tour.")
    if hero_produced(g, hero) and not multitasking(g, owner):
        raise ValueError("Ce héros a produit ce tour : il faut Multitâches pour aussi attaquer.")
    plan = hero_attack_plan(g, hero)
    if target_id not in plan:
        raise ValueError("Cible hors d'atteinte : trop loin pour ses déplacements, alliée ou invisible.")

    target = entity(g, target_id)
    stand = plan[target_id]

    # 1. Déplacement jusqu'à la case de frappe (marqueur de récolte compris).
    if stand != tuple(hero["pos"]):
        _, routes = hero_paths(g, hero)
        crossed = [p for p in routes[stand][1:] if key(p) in g["resources"]]
        if crossed:
            hero["marker"] = list(crossed[-1])
        log(g, f"{hero['name']} : {coord(hero['pos'])} → {coord(stand)}.")
        hero["pos"] = list(stand)
    hero["moved_turn"] = g["turn"]

    # 2. Frappe immédiate, sans riposte.
    damage = float(hero_stats(g, hero)[0])
    before = float(target["pf"])
    hero["attack_order"] = {"target_id": target_id, "turn": g["turn"], "damage": damage}
    target["pf"] = before - damage
    target_cell = list(target["pos"])
    if target["pf"] <= 0:
        g["entities"].remove(target)
        result = f"{target['name']} est détruit"
        # Corps à corps : le héros prend la case de sa victime (pas un tireur),
        # sauf si d'autres ouvriers ennemis tiennent encore la case.
        if (
            hero_stats(g, hero)[2] == 0
            and not blocked(g, tuple(target_cell))
            and not pieces_at(g, tuple(target_cell))
        ):
            hero["strike_from"] = list(hero["pos"])
            hero["pos"] = target_cell
            result += f", {hero['name']} prend sa case"
    else:
        result = f"{target['name']} tombe à {target['pf']:g} PF"
    log(g, f"{hero['name']} frappe {target['name']} : −{min(before, damage):g} PF, sans riposte.")
    g["_ui_message"] = f"{hero['name']} frappe : {result}. L'adversaire le découvrira au dévoilement."


_lw_heroatk_previous_render_board = render_board


def render_board(g, view, readonly=False):
    # En production, un héros sélectionné montre ses cibles en rouge.
    source = selected_entity(view)
    if (
        not readonly
        and g["phase"] == "build"
        and is_hero(source)
        and source["owner"] == g["active"]
        and st.session_state.ui_plan_mode is None
    ):
        st.session_state["_lw_hero_targets"] = {
            key(tuple(p["pos"])): {"target_id": p["id"]}
            for p in hero_attack_targets(view, source)
        }
    else:
        st.session_state.pop("_lw_hero_targets", None)
    return _lw_heroatk_previous_render_board(g, view, readonly)


# ============================================================
# SOLIDARITÉ : grisée tant qu'aucun héros n'est mort.
# ============================================================

def render_vag_upgrades(view, owner, prefix):
    st.markdown("#### Améliorations")
    owned = view["players"][owner].get("upgrades", [])
    if owned:
        st.caption("Achetées : " + ", ".join(u for u in owned if UPGRADES[u]["owner"] == VAGABONDS))
    lost = view["players"][owner].get("heroes_lost", 0)
    for name in available_upgrades(view, owner):
        data = UPGRADES[name]
        locked = name == "Solidarité" and not lost
        cols = st.columns([3, 1])
        with cols[0]:
            st.write(f"**{name}** · {data['cost']} or" + (f" · {data['mana']} mana" if data["mana"] else ""))
            st.caption(data["effect"] + (" — disponible après la mort d'un héros." if locked else ""))
        with cols[1]:
            if st.button("Acheter", key=f"{prefix}_vag_upgrade_{name}", disabled=locked):
                perform(draft_action, purchase_upgrade, name)


# ============================================================
# RIPOSTE DES BASES
# Une base riposte contre toute unité qui l'attaque à distance (volantes
# comprises), sauf une unité invisible non détectée et les armes de siège
# (Catapulte, Trébuchet, Catapulte de l'enfer).
# ============================================================

SIEGE_WEAPONS = {CATAPULT, TREBUCHET, HELL_CATAPULT}

_lw_base_previous_ranged_riposte = ranged_riposte


def ranged_riposte(g, attacker, target):
    if target["kind"] == "base":
        if attacker["name"] in SIEGE_WEAPONS or hidden_from(g, attacker, target["owner"]):
            return 0.0
        return min(float(attacker["pf"]), float(target["pf"]))
    return _lw_base_previous_ranged_riposte(g, attacker, target)


_lw_base_previous_ranged_riposte_text = ranged_riposte_text


def ranged_riposte_text(g, attacker, target):
    if target["kind"] == "base" and attacker["name"] in SIEGE_WEAPONS:
        return "Arme de siège : la base ne riposte pas."
    return _lw_base_previous_ranged_riposte_text(g, attacker, target)


# ============================================================
# DÉPLACEMENTS : CHEMIN CASE PAR CASE ET ANIMATION
# - Chaque déplacement mémorise son trajet (« last_move ») :
#   le plateau fait glisser la pièce le long du chemin, en accéléré.
# - Mode « tracé » : le joueur choisit chaque case du chemin,
#   puis reclique sur la dernière case pour partir.
# ============================================================

def record_move(g, unit_id, route):
    if len(route) >= 2:
        g["last_move"] = {
            "unit_id": unit_id,
            "route": [list(p) for p in route],
            "seq": uuid.uuid4().hex,
        }


_lw_wp_previous_paths = paths


def paths(g, unit, allow_attack=False):
    costs, routes = _lw_wp_previous_paths(g, unit, allow_attack)
    forced = g.get("_forced_route")
    if forced and forced["id"] == unit.get("id") and not allow_attack:
        costs = dict(costs)
        routes = dict(routes)
        destination = tuple(forced["route"][-1])
        costs[destination] = forced["cost"]
        routes[destination] = [tuple(p) for p in forced["route"]]
    return costs, routes


_lw_wp_previous_move_unit = move_unit


def move_unit(g, eid, destination):
    unit = entity(g, eid)
    start = tuple(unit["pos"])
    destination = require_position(destination)
    forced = g.get("_forced_route")
    if forced and forced["id"] == eid:
        route = [tuple(p) for p in forced["route"]]
    else:
        route = paths(g, unit)[1].get(destination, [start, destination])
    _lw_wp_previous_move_unit(g, eid, destination)
    record_move(g, eid, route)


def path_step_cost(g, unit, spent, a, b):
    """Coût pour aller de a à la case voisine b, selon les règles de l'unité."""
    if distance(a, b) != 1:
        return None
    probe = dict(unit, pos=list(a), movement_spent=spent, movement_spent_turn=g["turn"])
    cost = _lw_wp_previous_paths(g, probe)[0].get(b)
    return cost if cost is not None and cost <= 2 else None


def waypoint_next_steps(g, unit, path):
    """Cases où le chemin peut continuer : {case: coût total}."""
    start = tuple(unit["pos"])
    end = path[-1] if path else start
    spent = movement_spent(g, unit) + path_cost(g, unit, path)
    steps = {}
    for b in neighbors(end):
        if b == start or b in path:
            continue
        step = path_step_cost(g, unit, spent, end, b)
        if step is not None:
            steps[b] = spent - movement_spent(g, unit) + step
    return steps


def path_cost(g, unit, path):
    total, current = 0, tuple(unit["pos"])
    base = movement_spent(g, unit)
    for b in path:
        step = path_step_cost(g, unit, base + total, current, b)
        if step is None:
            return None
        total += step
        current = b
    return total


def move_unit_path(g, eid, path):
    require_phase(g, "move")
    unit = entity(g, eid)
    path = [require_position(p) for p in path]
    if not path:
        raise ValueError("Chemin vide.")
    cost = path_cost(g, unit, path)
    if cost is None:
        raise ValueError("Chemin impossible : cases voisines, sans ennemi ni bâtiment, dans la limite des déplacements.")
    if at(g, path[-1]) is not None:
        raise ValueError("Impossible de s'arrêter sur une case occupée.")
    g["_forced_route"] = {"id": eid, "route": [list(unit["pos"])] + [list(p) for p in path], "cost": cost}
    try:
        move_unit(g, eid, path[-1])
    finally:
        g.pop("_forced_route", None)


_lw_wp_previous_move_hero = move_hero


def move_hero(g, owner, hero_id, destination):
    hero = entity(g, hero_id)
    route = hero_paths(g, hero)[1].get(tuple(require_position(destination)), [])
    _lw_wp_previous_move_hero(g, owner, hero_id, destination)
    record_move(g, hero_id, route)


_lw_wp_previous_move_worker = move_worker


def move_worker(g, owner, unit_id, destination):
    worker = entity(g, unit_id)
    route = paths(g, worker)[1].get(tuple(require_position(destination)), [])
    _lw_wp_previous_move_worker(g, owner, unit_id, destination)
    record_move(g, unit_id, route)


# --- Interface du tracé ---------------------------------------------------

def waypoint_unit(g):
    if not st.session_state.get("ui_waypoint_mode") or g["phase"] != "move":
        return None
    attackers = selected_attackers(g)
    if len(attackers) != 1:
        return None
    unit = attackers[0]
    if st.session_state.get("ui_waypoints_unit") != unit["id"]:
        st.session_state.ui_waypoints_unit = unit["id"]
        st.session_state.ui_waypoints = []
    return unit


def current_waypoints():
    return [tuple(p) for p in st.session_state.get("ui_waypoints", [])]


_lw_wp_previous_board_event = board_event


def board_event(event, g, view):
    unit = waypoint_unit(g) if isinstance(event, dict) and event.get("type") == "cell_click" else None
    if unit is None or event.get("event_id") == st.session_state.ui_last_event or g["winner"] is not None or g["curtain"]:
        return _lw_wp_previous_board_event(event, g, view)
    try:
        pos = require_position(event.get("pos"))
    except ValueError:
        return _lw_wp_previous_board_event(event, g, view)

    path = current_waypoints()
    steps = waypoint_next_steps(g, unit, path)
    if pos not in steps and pos not in path:
        # Ni une étape possible ni une case du chemin : comportement habituel
        # (sélection d'une autre unité, attaque...).
        return _lw_wp_previous_board_event(event, g, view)

    st.session_state.ui_last_event = event["event_id"]
    if path and pos == path[-1]:
        # Reclic sur la dernière case : l'unité part.
        st.session_state.ui_waypoints = []
        perform(game_action, move_unit_path, unit["id"], path)
    if pos in path:
        # Clic sur une case du chemin : on revient à cette case.
        path = path[: path.index(pos) + 1]
    else:
        path = path + [pos]
    st.session_state.ui_waypoints = [list(p) for p in path]
    st.session_state.ui_message = (
        "Chemin : " + " → ".join(coord(p) for p in path)
        + ". Reclique sur la dernière case pour partir."
    )
    bump_ui()
    st.rerun()


_lw_wp_previous_render_board = render_board


def render_board(g, view, readonly=False):
    unit = waypoint_unit(g) if not readonly else None
    if unit is not None:
        path = current_waypoints()
        st.session_state["_lw_waypoint_view"] = {
            "path": path,
            "next": waypoint_next_steps(g, unit, path),
        }
    else:
        st.session_state.pop("_lw_waypoint_view", None)
    return _lw_wp_previous_render_board(g, view, readonly)


_lw_wp_previous_render_move_controls = render_move_controls


def render_move_controls(g):
    st.toggle(
        "🧭 Tracer le chemin case par case",
        key="ui_waypoint_mode",
        help="Clique chaque case du trajet, puis reclique sur la dernière case pour partir.",
    )
    unit = waypoint_unit(g)
    if unit is not None:
        path = current_waypoints()
        budget = remaining_actions(g, unit)
        used = path_cost(g, unit, path) or 0
        if path:
            st.caption(
                f"Chemin de {unit['name']} : " + " → ".join(coord(p) for p in path)
                + f" · {used}/{budget} déplacement(s)."
            )
            if st.button("Effacer le chemin", key=f"wp_clear_{unit['id']}_{st.session_state.ui_revision}"):
                st.session_state.ui_waypoints = []
                bump_ui()
                st.rerun()
        else:
            st.caption(f"Clique la 1re case du chemin de {unit['name']} ({budget} déplacement(s)).")
    _lw_wp_previous_render_move_controls(g)


# ============================================================
# GOBELIN : VOLER LA PROCHAINE RÉCOLTE
# - Arrêté à côté d'une base ennemie (ou d'ouvriers ennemis qui
#   récoltent pour elle), le Gobelin peut voler sa prochaine récolte :
#   à la fin du tour, cette base ne rapporte rien à son propriétaire,
#   l'or et le mana vont dans le butin du Gobelin.
# - Arrêté à côté d'une base alliée, il dépose son butin.
# - Un Gobelin détruit perd son butin.
# ============================================================

GOBLIN = "Gobelin"


def goblin_steal_targets(g, goblin):
    """Bases ennemies que le Gobelin peut piller depuis sa case."""
    owner = goblin["owner"]
    here = tuple(goblin["pos"])
    targets = {}
    for base in g["entities"]:
        if base["owner"] == owner or base["kind"] != "base":
            continue
        if distance(here, tuple(base["pos"])) == 1:
            targets[base["id"]] = base
            continue
        # Ouvriers ennemis voisins du Gobelin, sur une ressource de cette base.
        for worker in g["entities"]:
            if (
                worker["owner"] == base["owner"]
                and worker["name"] == WORKER
                and distance(here, tuple(worker["pos"])) <= 1
                and key(tuple(worker["pos"])) in g["resources"]
                and distance(tuple(worker["pos"]), tuple(base["pos"])) == 1
            ):
                targets[base["id"]] = base
                break
    return list(targets.values())


def goblin_home_bases(g, goblin):
    return [
        base for base in g["entities"]
        if base["owner"] == goblin["owner"]
        and base["kind"] == "base"
        and distance(tuple(goblin["pos"]), tuple(base["pos"])) == 1
    ]


def goblin_loot(goblin):
    loot = goblin.get("loot") or {}
    return int(loot.get("gold", 0)), int(loot.get("mana", 0))


def end_goblin_activation(g, goblin):
    goblin["acted"] = True
    if g.get("moving_unit_id") == goblin["id"]:
        g.pop("moving_unit_id")
    next_activation(g)


def goblin_steal(g, goblin_id, base_id):
    require_phase(g, "move")
    goblin = entity(g, goblin_id)
    if goblin["name"] != GOBLIN or goblin["owner"] != g["active"]:
        raise ValueError("Choisis un de tes Gobelins.")
    if not can_move(g, goblin):
        raise ValueError("Ce Gobelin ne peut plus agir ce tour.")
    base = entity(g, base_id)
    if base not in goblin_steal_targets(g, goblin):
        raise ValueError("Le Gobelin doit être à côté de la base ennemie ou de ses ouvriers.")
    base["stolen_by"] = goblin_id
    log(g, f"Gobelin #{goblin_id} prépare le vol de la prochaine récolte de {base['name']} en {coord(base['pos'])}.")
    g["_ui_message"] = (
        f"Vol préparé : à la fin du tour, la récolte de {base['name']} "
        f"({coord(base['pos'])}) ira au Gobelin."
    )
    end_goblin_activation(g, goblin)


def goblin_deposit(g, goblin_id):
    require_phase(g, "move")
    goblin = entity(g, goblin_id)
    if goblin["name"] != GOBLIN or goblin["owner"] != g["active"]:
        raise ValueError("Choisis un de tes Gobelins.")
    if not can_move(g, goblin):
        raise ValueError("Ce Gobelin ne peut plus agir ce tour.")
    if not goblin_home_bases(g, goblin):
        raise ValueError("Le Gobelin doit être à côté d'une de tes bases.")
    gold, mana = goblin_loot(goblin)
    if not gold and not mana:
        raise ValueError("Le Gobelin ne transporte aucun butin.")
    player = g["players"][goblin["owner"]]
    player["gold"] += gold
    player["mana"] += mana
    goblin.pop("loot", None)
    log(g, f"Gobelin #{goblin_id} dépose son butin : +{gold} or, +{mana} mana.")
    g["_ui_message"] = f"Butin déposé : +{gold} or, +{mana} mana."
    end_goblin_activation(g, goblin)


_lw_goblin_previous_collect = collect_adjacent_resources


def collect_adjacent_resources(g, base):
    thief_id = base.pop("stolen_by", None)
    if thief_id is None:
        return _lw_goblin_previous_collect(g, base)

    owner = g["players"][base["owner"]]
    before = (owner["gold"], owner["mana"])
    _lw_goblin_previous_collect(g, base)
    gold, mana = owner["gold"] - before[0], owner["mana"] - before[1]
    owner["gold"], owner["mana"] = before

    thief = next((e for e in g["entities"] if e["id"] == thief_id), None)
    if thief is None:
        log(g, f"{base['name']} en {coord(base['pos'])} : récolte perdue (le Gobelin a disparu).")
        return
    loot = thief.setdefault("loot", {"gold": 0, "mana": 0})
    loot["gold"] = loot.get("gold", 0) + gold
    loot["mana"] = loot.get("mana", 0) + mana
    log(g, f"Gobelin #{thief_id} vole la récolte de {base['name']} : {gold} or, {mana} mana.")


_lw_goblin_previous_describe = describe


def describe(e):
    text = _lw_goblin_previous_describe(e)
    gold, mana = goblin_loot(e) if e.get("name") == GOBLIN else (0, 0)
    if gold or mana:
        text += f" · butin {gold} or / {mana} mana"
    return text


def render_goblin_controls(g, goblin, prefix):
    st.markdown("#### 💰 Gobelin voleur")
    gold, mana = goblin_loot(goblin)
    if gold or mana:
        st.caption(f"Butin transporté : {gold} or · {mana} mana.")
    if not can_move(g, goblin):
        st.caption("Ce Gobelin a déjà agi ce tour.")
        return

    targets = goblin_steal_targets(g, goblin)
    for base in targets:
        already = base.get("stolen_by") is not None
        if st.button(
            f"🕵️ Voler la prochaine récolte de {base['name']} ({coord(base['pos'])})",
            key=f"{prefix}_goblin_steal_{goblin['id']}_{base['id']}",
            disabled=already,
            help="À la fin du tour, cette base ne rapporte rien à son propriétaire : la récolte va au Gobelin.",
        ):
            perform(game_action, goblin_steal, goblin["id"], base["id"])
    if not targets:
        st.caption("Pour voler : arrête-toi à côté d'une base ennemie ou de ses ouvriers.")

    if gold or mana:
        if goblin_home_bases(g, goblin):
            if st.button(
                f"📦 Déposer le butin ({gold} or · {mana} mana)",
                key=f"{prefix}_goblin_deposit_{goblin['id']}",
                type="primary",
            ):
                perform(game_action, goblin_deposit, goblin["id"])
        else:
            st.caption("Pour encaisser : arrête-toi à côté d'une de tes bases.")


_lw_goblin_previous_render_move_controls = render_move_controls


def render_move_controls(g):
    attackers = selected_attackers(g)
    if len(attackers) == 1 and attackers[0]["name"] == GOBLIN:
        render_goblin_controls(g, attackers[0], f"gob_{g['turn']}_{st.session_state.ui_revision}")
    _lw_goblin_previous_render_move_controls(g)


# ============================================================
# RAMPANT : planté dans le sol, il tire à distance mais jamais en l'air.
# ============================================================

_lw_rampant_previous_ranged_values = ranged_attack_values


def ranged_attack_values(g, attacker, target):
    if attacker.get("name") == RAMPANT and target.get("kind") == "unit" and is_flying(target):
        raise ValueError("Le Rampant, planté dans le sol, ne peut pas attaquer une unité volante.")
    return _lw_rampant_previous_ranged_values(g, attacker, target)


# ============================================================
# RAMPANT : TIR EN LIGNE
# Planté, il vise une cible en ligne droite (à sa portée) et frappe 3 cases
# qui se suivent à partir d'elle : la cible, puis les 2 cases derrière,
# 4 PF de dégâts sur chacune, ennemis seulement, jamais les unités volantes.
# ============================================================

RAMPANT_LINE_DAMAGE = 4.0
RAMPANT_LINE_LENGTH = 3


def rampant_line_cells(rampant, target_pos):
    """La cible et les 2 cases derrière elle ; None hors ligne droite."""
    origin, target_pos = tuple(rampant["pos"]), tuple(target_pos)
    direction = golem_direction(origin, target_pos)
    if direction is None:
        return None
    dq, dr = direction
    gap = distance(origin, target_pos)
    if (origin[0] + gap * dq, origin[1] + gap * dr) != target_pos:
        return None
    cells = [(target_pos[0] + k * dq, target_pos[1] + k * dr) for k in range(RAMPANT_LINE_LENGTH)]
    return [c for c in cells if c in CELL_SET]


_lw_rline_previous_ranged_values = ranged_attack_values


def ranged_attack_values(g, attacker, target):
    values = _lw_rline_previous_ranged_values(g, attacker, target)
    if attacker.get("name") == RAMPANT:
        cells = rampant_line_cells(attacker, target["pos"])
        if cells is None or tuple(target["pos"]) not in cells:
            raise ValueError("Le Rampant tire en ligne droite sur sa cible (portée 3).")
        values = dict(
            values,
            damage=RAMPANT_LINE_DAMAGE,
            remaining=max(0.0, float(target["pf"]) - RAMPANT_LINE_DAMAGE),
            line_cells=cells,
        )
    return values


_lw_rline_previous_ranged_attack = ranged_attack


def ranged_attack(g, attacker_id, target_id, *args, **kwargs):
    attacker = entity(g, attacker_id)
    if attacker["name"] != RAMPANT:
        return _lw_rline_previous_ranged_attack(g, attacker_id, target_id, *args, **kwargs)

    target = entity(g, target_id)
    values = ranged_attack_values(g, attacker, target)
    riposte = ranged_riposte(g, attacker, target)
    owner = attacker["owner"]

    report = {
        "turn": turn_label(g),
        "position": coord(target["pos"]),
        "power": RAMPANT_LINE_DAMAGE,
        "bonus": 0.0,
        "defense": float(target["pf"]),
        "occupier_id": None,
        "participants": [{
            "id": attacker["id"], "owner": owner, "name": attacker["name"],
            "role": "Tir en ligne", "before": float(attacker["pf"]),
            "damage": 0.0, "after": float(attacker["pf"]),
        }],
    }
    attacker["acted"] = True
    if g.get("moving_unit_id") == attacker["id"]:
        g.pop("moving_unit_id")

    cells = values["line_cells"]
    log(g, f"Rampant #{attacker['id']} tire en ligne : {', '.join(coord(c) for c in cells)}.")
    for cell in cells:
        for victim in list(pieces_at(g, cell)):
            if victim["owner"] == owner:
                continue
            if victim["kind"] == "unit" and is_flying(victim):
                continue
            if not visible_to_player(g, victim, owner):
                continue
            apply_damage(g, victim, RAMPANT_LINE_DAMAGE, attacker, report, "Touché par le tir en ligne")

    if riposte and attacker in g["entities"]:
        attacker["pf"] -= riposte
        report["participants"][0]["damage"] = riposte
        report["participants"][0]["after"] = max(0.0, attacker["pf"])
        log(g, f"Riposte : Rampant #{attacker['id']} perd {riposte:g} PF.")
        if attacker["pf"] <= 0:
            destroy(g, attacker, target["owner"])

    g["_combat_report"] = report
    next_activation(g)


# ============================================================
# DÉCIMANT : le bonus après une attraction laisse se rapprocher
# N'importe quelle unité peut se déplacer puis attaquer l'unité attirée.
# Le bonus ne se termine qu'avec une attaque sur elle (ou en renonçant).
# ============================================================

HUNT_MOVES = ("move_unit", "move_unit_path")
HUNT_ATTACKS = ("attack", "ranged_attack", "kamikaze_attack")


def decimant_hunters(g, owner, target):
    """Unités capables d'atteindre la cible ce tour (déplacement compris)."""
    hunters = []
    tpos = tuple(target["pos"])
    for unit in g["entities"]:
        if unit["owner"] != owner or unit["kind"] != "unit" or not can_move(g, unit):
            continue
        try:
            _, targets = attack_map_preview(g, [unit])
        except ValueError:
            targets = {}
        reach = UNITS.get(unit["name"], {}).get("range", 0)
        if tpos in targets:
            hunters.append(unit)
        elif reach > 0:
            # Tireur : peut-il se placer à portée avec ses déplacements ?
            # Il doit garder au moins 1 action pour tirer après s'être déplacé.
            budget = remaining_actions(g, unit) - 1
            spots = [p for p, c in move_preview(g, unit)[0].items() if c <= budget] + [tuple(unit["pos"])]
            if any(distance(p, tpos) <= reach + (1 if terrain(g, p) == "mountain" else 0) for p in spots):
                hunters.append(unit)
    return hunters


def game_action(bundle, fn, *args):
    g = bundle["game"]
    hunt = decimant_hunt(g)
    if hunt is None:
        g.pop("decimant_hunt", None)
        return _lw_hunt_previous_game_action(bundle, fn, *args)

    target_id = hunt["target_id"]
    name = getattr(fn, "__name__", "")
    is_attack = (
        (name in HUNT_ATTACKS and len(args) > 1 and args[1] == target_id)
        or (name == "cast_mage_spell" and len(args) > 2 and target_id in args[2])
    )
    if not (is_attack or name in HUNT_MOVES or name in ("pass_turn", "renounce_decimant_hunt")):
        target = entity(g, target_id)
        raise ValueError(
            f"Bonus du Décimant : rapproche une unité puis attaque {target['name']} "
            f"en {coord(target['pos'])}, ou renonce au bonus."
        )

    if name in HUNT_MOVES or name == "renounce_decimant_hunt":
        return _lw_hunt_previous_game_action(bundle, fn, *args)
    # Attaque (ou renoncement) : le bonus se termine avant l'action,
    # pour que le tour passe normalement ensuite.
    saved = g.pop("decimant_hunt", None)
    try:
        _lw_hunt_previous_game_action(bundle, fn, *args)
    except ValueError:
        g["decimant_hunt"] = saved
        raise


_lw_huntmove_previous_next_activation = next_activation


def next_activation(g, switch=True):
    # Pendant le bonus du Décimant, un déplacement garde la main au joueur.
    if decimant_hunt(g) is not None:
        g.pop("moving_unit_id", None)
        for unit in g["entities"]:
            if unit["owner"] == g["active"] and unit.get("movement_spent_turn") == g["turn"] and unit["acted"] and remaining_actions(g, unit) > 0:
                unit["acted"] = False
        return
    _lw_huntmove_previous_next_activation(g, switch)


# ============================================================
# NAIN DES MONTAGNES : LEADER
# Quand le Nain attaque, les 2 unités alliées à ses côtés attaquent
# aussitôt avec lui : le joueur garde la main pour les faire attaquer
# (attaque seulement), puis le tour continue normalement.
# ============================================================

def dwarf_rally(g):
    rally = g.get("dwarf_rally")
    if (
        not rally
        or rally["owner"] != g["active"]
        or rally["turn"] != g["turn"]
        or g["phase"] != "move"
    ):
        return None
    alive = [i for i in rally["ids"] if any(e["id"] == i for e in g["entities"])]
    rally["ids"] = alive
    return rally if alive else None


def grant_dwarf_attacks(g, dwarf_id, owner, excluded_ids):
    dwarf = next((e for e in g["entities"] if e["id"] == dwarf_id), None)
    if dwarf is None:
        return
    # Ses voisins sont ceux de sa case AVANT l'attaque (il a pu avancer).
    origin = tuple(g.get("_dwarf_origins", {}).get(dwarf_id, dwarf["pos"]))
    helpers = sorted(
        (
            e for e in g["entities"]
            if e["owner"] == owner
            and e["kind"] == "unit"
            and e["id"] not in excluded_ids
            and not e["wait"]
            and e["name"] not in NO_ATTACK_UNITS
            and distance(tuple(e["pos"]), origin) == 1
        ),
        key=lambda e: -e["pf"],
    )[:2]
    if not helpers:
        return
    for helper in helpers:
        helper["acted"] = False
        helper["extra_attack_turn"] = g["turn"]
        helper["movement_spent_turn"] = g["turn"]
        helper["movement_spent"] = 0
    g["dwarf_rally"] = {"owner": owner, "ids": [h["id"] for h in helpers], "turn": g["turn"]}
    names = ", ".join(f"{h['name']} #{h['id']}" for h in helpers)
    log(g, f"Le Nain mène l'assaut : {names} attaquent aussitôt avec lui.")
    g["_ui_message"] = (
        f"⚒️ Le Nain mène l'assaut : {names} peuvent attaquer maintenant, "
        "dans la foulée (attaque seulement)."
    )


_lw_rally_previous_apply_attack_effects = apply_attack_effects


def apply_attack_effects(g, effects):
    origins = {}
    for dwarf_id in effects.get("dwarves", []):
        if effects.get("occupier_id") == dwarf_id and effects.get("occupier_origin"):
            origins[dwarf_id] = effects["occupier_origin"]
    g["_dwarf_origins"] = origins
    try:
        keep = _lw_rally_previous_apply_attack_effects(g, effects)
    finally:
        g.pop("_dwarf_origins", None)
    return keep or dwarf_rally(g) is not None


_lw_rally_previous_next_activation = next_activation


def next_activation(g, switch=True):
    if dwarf_rally(g) is not None:
        return
    g.pop("dwarf_rally", None)
    _lw_rally_previous_next_activation(g, switch)


def end_dwarf_rally(g):
    if dwarf_rally(g) is None:
        raise ValueError("Aucun assaut du Nain en cours.")
    for i in g["dwarf_rally"]["ids"]:
        unit = next((e for e in g["entities"] if e["id"] == i), None)
        if unit is not None:
            unit["acted"] = True
    g.pop("dwarf_rally", None)
    log(g, "Fin de l'assaut du Nain.")
    next_activation(g)


_lw_rally_previous_game_action = game_action


def game_action(bundle, fn, *args):
    g = bundle["game"]
    rally = dwarf_rally(g)
    if rally is None:
        g.pop("dwarf_rally", None)
        return _lw_rally_previous_game_action(bundle, fn, *args)

    name = getattr(fn, "__name__", "")
    attackers = []
    if name == "attack" and args:
        attackers = list(args[0])
    elif name in ("ranged_attack", "kamikaze_attack") and args:
        attackers = [args[0]]
    if name not in ("end_dwarf_rally", "pass_turn") and not (
        attackers and set(attackers) <= set(rally["ids"])
    ):
        raise ValueError(
            "Assaut du Nain : attaque avec les unités à ses côtés, "
            "ou termine l'assaut."
        )
    # L'unité qui attaque quitte l'assaut avant le combat.
    rally["ids"] = [i for i in rally["ids"] if i not in attackers]
    _lw_rally_previous_game_action(bundle, fn, *args)


_lw_rally_previous_render_move_controls = render_move_controls


def render_move_controls(g):
    rally = dwarf_rally(g)
    if rally is not None:
        names = ", ".join(
            f"{e['name']} ({coord(e['pos'])})" for e in g["entities"] if e["id"] in rally["ids"]
        )
        st.warning(f"⚒️ Assaut du Nain : {names} peuvent attaquer maintenant.")
        if st.button("Terminer l'assaut du Nain", key=f"end_rally_{g['turn']}_{st.session_state.ui_revision}"):
            perform(game_action, end_dwarf_rally)
    _lw_rally_previous_render_move_controls(g)

AGE_REFERENCE["Exilés"][3] = [
    (n, ("Leader · quand il attaque, les 2 unités alliées à ses côtés attaquent aussitôt avec lui"
         if n == "Nain des montagnes" else d))
    for n, d in AGE_REFERENCE["Exilés"][3]
]


# ============================================================
# TRÉBUCHET (amélioration « Trébuchet » des Derniers nés)
# - Une Catapulte ou une Catapulte de l'enfer se transforme en Trébuchet
#   en 1 tour ; le Trébuchet est immobile. Il redevient sa catapulte
#   d'origine en 1 tour pour pouvoir se déplacer à nouveau.
# - Tir automatique : dès qu'une unité ennemie passe dans son rayon
#   (4 à 5 cases), il tire sur elle : 4 PF sur sa case, 2 PF à gauche
#   et à droite. Un tir automatique par Trébuchet et par tour.
# ============================================================

TREBUCHET_AUTO_DAMAGE = 4.0
TREBUCHET_AUTO_SIDE = 2.0
TRANSFORMABLE_SIEGE = (CATAPULT, HELL_CATAPULT)


def transform_siege(g, unit_id):
    require_phase(g, "move")
    unit = entity(g, unit_id)
    if unit["owner"] != g["active"] or unit["name"] not in (*TRANSFORMABLE_SIEGE, TREBUCHET):
        raise ValueError("Choisis une de tes catapultes ou un trébuchet.")
    if not owns_upgrade(g, unit["owner"], "Trébuchet"):
        raise ValueError("Achète d'abord l'amélioration « Trébuchet » à la Forge.")
    if not can_move(g, unit):
        raise ValueError("Cette unité ne peut plus agir ce tour.")

    if unit["name"] == TREBUCHET:
        new_name = unit.pop("siege_origin", CATAPULT)
    else:
        new_name = TREBUCHET
        unit["siege_origin"] = unit["name"]

    damage = unit["max_pf"] - unit["pf"]
    unit["name"] = new_name
    unit["max_pf"] = float(UNITS[new_name]["pf"])
    unit["pf"] = max(0.5, unit["max_pf"] - damage)
    unit["acted"] = True
    # La transformation prend un tour complet de manœuvres.
    unit["wait"] = 2
    if g.get("moving_unit_id") == unit["id"]:
        g.pop("moving_unit_id")

    log(g, f"Unité #{unit['id']} se transforme en {new_name} (1 tour).")
    next_activation(g)


def trebuchet_auto_fire(g, mover, route):
    """Tirs automatiques des Trébuchets ennemis sur une unité en mouvement."""
    if mover["kind"] != "unit":
        return
    for treb in [e for e in g["entities"] if e["name"] == TREBUCHET and e["owner"] != mover["owner"]]:
        if mover not in g["entities"]:
            return
        if treb["wait"] or treb.get("auto_fired_turn") == g["turn"]:
            continue
        if not visible_to_player(g, mover, treb["owner"]):
            continue
        low, high = SIEGE_RANGES[TREBUCHET]
        origin = tuple(treb["pos"])
        if not any(low <= distance(origin, tuple(p)) <= high for p in route[1:]):
            continue

        treb["auto_fired_turn"] = g["turn"]
        target_pos = tuple(mover["pos"])
        report = {
            "turn": turn_label(g), "position": coord(target_pos),
            "power": TREBUCHET_AUTO_DAMAGE, "bonus": 0.0, "defense": float(mover["pf"]),
            "occupier_id": None,
            "participants": [{
                "id": treb["id"], "owner": treb["owner"], "name": treb["name"],
                "role": "Tir automatique", "before": float(treb["pf"]),
                "damage": 0.0, "after": float(treb["pf"]),
            }],
        }
        log(g, f"Trébuchet #{treb['id']} tire automatiquement sur {mover['name']} en {coord(target_pos)}.")
        apply_damage(g, mover, TREBUCHET_AUTO_DAMAGE, treb, report, "Cible du tir automatique")
        for pos in siege_side_cells(origin, target_pos):
            for victim in list(pieces_at(g, pos)):
                apply_damage(g, victim, TREBUCHET_AUTO_SIDE, treb, report, "Case voisine du tir automatique")
        g["_combat_report"] = report
        g["_ui_message"] = (
            (g.get("_ui_message") + " " if g.get("_ui_message") else "")
            + f"💥 Tir automatique du Trébuchet sur {mover['name']} !"
        )


_lw_treb_previous_move_unit = move_unit


def move_unit(g, eid, destination):
    _lw_treb_previous_move_unit(g, eid, destination)
    mover = next((e for e in g["entities"] if e["id"] == eid), None)
    route = (g.get("last_move") or {}).get("route") or []
    if mover is None or not route:
        return
    was_active = g["active"]
    trebuchet_auto_fire(g, mover, route)
    if mover not in g["entities"] and g.get("moving_unit_id") == eid:
        # L'unité a été détruite en chemin : son activation se termine.
        g.pop("moving_unit_id")
        if g["active"] == was_active:
            next_activation(g)


_lw_treb_previous_render_siege_controls = render_siege_controls


def render_siege_controls(g, unit, prefix):
    _lw_treb_previous_render_siege_controls(g, unit, prefix)
    if unit["name"] == HELL_CATAPULT and owns_upgrade(g, unit["owner"], "Trébuchet") and can_move(g, unit):
        if st.button("🏗️ Devenir Trébuchet (1 tour, immobile, tir automatique)", key=f"{prefix}_transform_{unit['id']}"):
            perform(game_action, transform_siege, unit["id"])
    if unit["name"] == TREBUCHET:
        st.caption(
            f"Tir automatique : toute unité ennemie qui passe à 4-5 cases subit "
            f"{TREBUCHET_AUTO_DAMAGE:g} PF ({TREBUCHET_AUTO_SIDE:g} PF à gauche et à droite), "
            "une fois par tour."
        )


UPGRADES["Trébuchet"]["effect"] = (
    "Une Catapulte ou une Catapulte de l'enfer devient Trébuchet en 1 tour : immobile, "
    "il tire automatiquement (4 PF, 2 PF sur les côtés) sur toute unité ennemie qui "
    "passe à 4-5 cases. Redevient catapulte en 1 tour pour se déplacer."
)


# ============================================================
# JEU EN LIGNE À 2 JOUEURS
# - Un hôte crée une partie et envoie le lien ; l'invité la rejoint.
# - Salon : l'hôte règle la victoire et choisit sa faction, l'invité choisit
#   une autre faction ; chacun coche « Prêt » et la partie démarre.
# - Production en parallèle : chacun planifie en secret en même temps ;
#   quand les deux ont validé (ou après 3 min), tout est dévoilé.
# - Manœuvres inchangées : chacun son tour. 3 min par joueur et par phase.
# Les parties vivent dans la mémoire du serveur (partagée entre sessions).
# ============================================================

import random
import secrets
import threading

ONLINE_TURN_SECONDS = 180


@st.cache_resource
def online_registry():
    return {"rooms": {}, "lock": threading.Lock()}


def online_room(code):
    return online_registry()["rooms"].get(code)


def online_lock():
    return online_registry()["lock"]


def new_online_room():
    code = secrets.token_hex(3).upper()
    room = {
        "code": code,
        "created": time.time(),
        "tokens": {0: secrets.token_urlsafe(12), 1: None},
        "factions": {0: DEFERLANTS, 1: EXILES},
        "victory_mode": "time",
        "minutes": 60,
        "ready": {0: False, 1: False},
        "status": "lobby",
        "bundle": None,
        "version": 0,
        "drafts": {0: None, 1: None},
        "prod_ready": {0: False, 1: False},
        "prod_turn": None,
        "prod_started": None,
        "move_used": {0: 0.0, 1: 0.0},
        "move_clock": None,
    }
    with online_lock():
        online_registry()["rooms"][code] = room
    return room


def online_seat():
    return st.session_state.get("online_seat")


def online_active_room():
    code = st.session_state.get("online_code")
    return online_room(code) if code else None


def online_base_url():
    try:
        url = str(st.context.url or "")
    except Exception:
        url = ""
    return url.split("?")[0].rstrip("/") or "http://localhost:8501"


# ------------------------------------------------------------
# Synchronisation : actions locales -> partie partagée, minuteurs
# ------------------------------------------------------------

def online_merge_productions(room):
    shared = room["bundle"]
    g = copy.deepcopy(shared["game"])
    first, second = g["first"], 1 - g["first"]

    def draft_for(seat):
        draft = room["drafts"][seat]
        if draft is None:
            draft = copy.deepcopy(g)
        draft = copy.deepcopy(draft)
        draft["active"] = seat
        draft["curtain"] = False
        return draft

    g["active"] = first
    g["ready"] = []
    g["curtain"] = False
    bundle = {"game": g, "draft": draft_for(first), "committed": None}
    commit_plan(bundle)
    bundle["draft"] = draft_for(second)
    commit_plan(bundle)
    bundle["draft"] = None
    bundle["committed"] = None

    room["bundle"] = bundle
    room["drafts"] = {0: None, 1: None}
    room["prod_ready"] = {0: False, 1: False}
    room["move_used"] = {0: 0.0, 1: 0.0}
    room["move_clock"] = {"turn": bundle["game"]["turn"], "active": bundle["game"]["active"], "since": time.time()}
    room["version"] += 1


def online_sync(room, seat, publish=True):
    """À chaque exécution : publier l'action locale, appliquer les minuteurs."""
    now = time.time()
    with online_lock():
        handed = st.session_state.get("online_handed") if publish else None
        current = st.session_state.get("bundle")
        if handed is not None and current is not None and current is not handed:
            shared_g = room["bundle"]["game"]
            if st.session_state.get("online_handed_phase") == "build":
                if shared_g["phase"] == "build" and shared_g["turn"] == st.session_state.get("online_handed_turn"):
                    if current["game"].get("ready"):
                        room["drafts"][seat] = current.get("committed")
                        room["prod_ready"][seat] = True
                    else:
                        room["drafts"][seat] = current.get("draft")
                    room["version"] += 1
            elif room["version"] == st.session_state.get("online_handed_version"):
                room["bundle"] = current
                room["version"] += 1
        if publish:
            st.session_state.online_handed = None

        g = room["bundle"]["game"]
        if g["winner"] is not None:
            return

        if g["phase"] == "build":
            if room["prod_turn"] != g["turn"]:
                room["prod_turn"] = g["turn"]
                room["prod_started"] = now
                room["prod_ready"] = {0: False, 1: False}
            late = now - room["prod_started"] > ONLINE_TURN_SECONDS
            if all(room["prod_ready"].values()) or late:
                online_merge_productions(room)
            return

        # Manœuvres : 3 min cumulées par joueur.
        clock = room["move_clock"]
        if clock is None or clock["turn"] != g["turn"]:
            room["move_used"] = {0: 0.0, 1: 0.0}
            clock = room["move_clock"] = {"turn": g["turn"], "active": g["active"], "since": now}
        if clock["active"] != g["active"]:
            room["move_used"][clock["active"]] += now - clock["since"]
            clock["active"], clock["since"] = g["active"], now
        active = g["active"]
        spent = room["move_used"][active] + now - clock["since"]
        if spent > ONLINE_TURN_SECONDS and active not in g["passed"]:
            bundle = copy.deepcopy(room["bundle"])
            try:
                pass_turn(bundle["game"])
                log(bundle["game"], f"{faction_of(bundle['game'], active)['name']} : temps écoulé, manœuvres terminées.")
            except ValueError:
                return
            room["bundle"] = bundle
            room["version"] += 1


def online_time_left(room, seat):
    g = room["bundle"]["game"]
    now = time.time()
    if g["phase"] == "build":
        return max(0, ONLINE_TURN_SECONDS - (now - (room["prod_started"] or now)))
    clock = room["move_clock"] or {"active": g["active"], "since": now}
    spent = room["move_used"][seat] + (now - clock["since"] if clock["active"] == seat else 0)
    return max(0, ONLINE_TURN_SECONDS - spent)


@st.fragment(run_every=2)
def online_poll():
    room = online_active_room()
    seat = online_seat()
    if room is None or seat is None:
        return
    if room["status"] == "playing":
        # Minuteurs seulement : l'action locale est publiée par l'exécution complète.
        online_sync(room, seat, publish=False)
    if room["version"] != st.session_state.get("online_seen_version"):
        st.rerun(scope="app")
    if room["status"] == "playing" and room["bundle"]["game"]["winner"] is None:
        g = room["bundle"]["game"]
        left = int(online_time_left(room, seat))
        if g["phase"] == "build":
            who = "Production en parallèle"
        elif g["active"] == seat:
            who = "À toi de manœuvrer"
        else:
            who = "Manœuvres de l'adversaire"
        st.caption(f"🌐 {who} · ⏱️ {left // 60}:{left % 60:02d} restantes (3 min par joueur et par phase)")


# ------------------------------------------------------------
# Lecture seule quand ce n'est pas à ce joueur d'agir
# ------------------------------------------------------------

def online_readonly():
    room = online_active_room()
    seat = online_seat()
    if room is None or seat is None or room["status"] != "playing":
        return False
    g = room["bundle"]["game"]
    if g["winner"] is not None:
        return True
    if g["phase"] == "build":
        return room["prod_ready"][seat]
    return g["active"] != seat


_lw_online_previous_perform = perform


def perform(fn, *args):
    if online_readonly():
        st.session_state.ui_message = "Ce n'est pas encore à toi de jouer : attends l'adversaire."
        bump_ui()
        st.rerun()
    return _lw_online_previous_perform(fn, *args)


_lw_online_previous_process_queued_board_event = process_queued_board_event


def process_queued_board_event(g, view):
    if online_readonly() and st.session_state.get("ui_queued_board_event") is not None:
        st.session_state.pop("ui_queued_board_event", None)
        st.session_state.ui_message = "C'est au tour de l'adversaire."
        bump_ui()
        return
    return _lw_online_previous_process_queued_board_event(g, view)


_lw_online_previous_render_board = render_board


def render_board(g, view, readonly=False):
    return _lw_online_previous_render_board(g, view, readonly or online_readonly())


_lw_online_previous_render_move_controls = render_move_controls


def render_move_controls(g):
    if online_readonly():
        st.info("⏳ L'adversaire joue ses manœuvres. Le plateau se met à jour tout seul.")
        return
    _lw_online_previous_render_move_controls(g)


# ------------------------------------------------------------
# Salon d'attente
# ------------------------------------------------------------

def render_online_lobby(room, seat):
    st.markdown("<h1 style='text-align:center'>Partie en ligne</h1>", unsafe_allow_html=True)
    opponent = 1 - seat
    faction_ids = list(FACTIONS)

    if seat == 0:
        link = f"{online_base_url()}/?room={room['code']}"
        st.success("Envoie ce lien à ton ami pour qu'il rejoigne la partie :")
        st.code(link, language=None)
    else:
        st.info(f"Tu as rejoint la partie {room['code']}.")

    locked = room["ready"][seat]
    other_faction = room["factions"][opponent] if (seat == 0 and room["tokens"][1]) or seat == 1 else None
    choices = [f for f in faction_ids if f != other_faction]
    mine = room["factions"][seat] if room["factions"][seat] in choices else choices[0]
    faction = st.selectbox(
        "Ta faction",
        choices,
        index=choices.index(mine),
        format_func=lambda fid: FACTIONS[fid]["name"],
        disabled=locked,
        key=f"lobby_faction_{seat}",
    )
    if faction != room["factions"][seat] and not locked:
        with online_lock():
            room["factions"][seat] = faction
            room["version"] += 1

    if seat == 0:
        mode = st.radio(
            "Condition de victoire",
            list(VICTORY_MODES),
            index=list(VICTORY_MODES).index(room["victory_mode"]),
            format_func=VICTORY_MODES.get,
            disabled=locked,
            key="lobby_mode",
        )
        minutes = room["minutes"]
        if mode == "time":
            minutes = int(st.number_input("Durée en minutes", 5, 180, room["minutes"], 1, disabled=locked, key="lobby_minutes"))
        if (mode, minutes) != (room["victory_mode"], room["minutes"]) and not locked:
            with online_lock():
                room["victory_mode"], room["minutes"] = mode, minutes
                room["version"] += 1
    else:
        st.caption(
            f"Réglages de l'hôte : {VICTORY_MODES[room['victory_mode']]}"
            + (f" · {room['minutes']} min" if room["victory_mode"] == "time" else "")
        )

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown(f"**Toi** : {FACTIONS[room['factions'][seat]]['name']}")
        ready = st.checkbox("✅ Je suis prêt", value=room["ready"][seat], key=f"lobby_ready_{seat}")
        if ready != room["ready"][seat]:
            with online_lock():
                room["ready"][seat] = ready
                room["version"] += 1
            st.rerun()
    with right:
        if room["tokens"][opponent] is None:
            st.markdown("**Adversaire** : en attente de connexion…")
        else:
            st.markdown(
                f"**Adversaire** : {FACTIONS[room['factions'][opponent]]['name']} — "
                + ("✅ prêt" if room["ready"][opponent] else "⏳ pas encore prêt")
            )

    clash = room["factions"][0] == room["factions"][1]
    if clash:
        st.error("Les deux joueurs doivent choisir des factions différentes.")

    with online_lock():
        if (
            room["status"] == "lobby"
            and room["tokens"][1]
            and all(room["ready"].values())
            and not clash
        ):
            minutes = room["minutes"] if room["victory_mode"] == "time" else 0
            room["bundle"] = new_bundle(
                random.choice((0, 1)), 0, int(minutes), room["victory_mode"],
                (room["factions"][0], room["factions"][1]),
            )
            room["bundle"]["game"]["curtain"] = False
            room["status"] = "playing"
            room["version"] += 1
    if room["status"] == "playing":
        st.rerun()
    st.caption("La partie démarre dès que les deux joueurs ont coché « Je suis prêt ».")


# ------------------------------------------------------------
# Partie en cours
# ------------------------------------------------------------

def render_online_waiting(room, seat):
    st.markdown(CSS, unsafe_allow_html=True)
    render_logo_header(home=False)
    g = room["bundle"]["game"]
    st.subheader(f"Tour {turn_label(g)} — Production validée")
    st.info("⏳ Ta production est validée. En attente de l'adversaire (3 min maximum)…")
    draft = room["drafts"][seat] or g
    render_board(g, draft, readonly=True)


def online_game(room, seat):
    online_sync(room, seat)
    st.session_state.online_seen_version = room["version"]
    shared = room["bundle"]
    g = shared["game"]

    if g["phase"] == "build" and g["winner"] is None:
        if room["prod_ready"][seat]:
            online_poll()
            render_online_waiting(room, seat)
            return
        local_game = copy.deepcopy(g)
        local_game["active"] = seat
        local_game["ready"] = []
        local_game["curtain"] = False
        draft = copy.deepcopy(room["drafts"][seat]) if room["drafts"][seat] else None
        bundle = {"game": local_game, "draft": draft, "committed": None}
    else:
        bundle = shared

    st.session_state.bundle = bundle
    st.session_state.online_handed = bundle
    st.session_state.online_handed_phase = g["phase"]
    st.session_state.online_handed_turn = g["turn"]
    st.session_state.online_handed_version = room["version"]
    online_poll()
    _lw_online_previous_main()


def online_enter(code, token):
    room = online_room(code)
    if room is None:
        st.error("Partie introuvable : le lien est faux ou le serveur a redémarré.")
        if st.button("Retour au menu principal"):
            st.query_params.clear()
            st.rerun()
        return

    seat = next((s for s, t in room["tokens"].items() if t and t == token), None)
    if seat is None:
        with online_lock():
            if room["tokens"][1] is None:
                room["tokens"][1] = secrets.token_urlsafe(12)
                if room["factions"][1] == room["factions"][0]:
                    room["factions"][1] = next(f for f in FACTIONS if f != room["factions"][0])
                room["version"] += 1
                seat, token = 1, room["tokens"][1]
        if seat is None:
            st.error("Cette partie est déjà complète.")
            return
        st.query_params["p"] = token

    st.session_state.online_code = code
    st.session_state.online_seat = seat
    init_ui()

    if room["status"] == "lobby":
        st.session_state.online_seen_version = room["version"]
        online_poll()
        render_online_lobby(room, seat)
        return
    online_game(room, seat)


_lw_online_previous_main = main


def main():
    params = st.query_params
    code = params.get("room")
    if code:
        online_enter(str(code).upper(), params.get("p"))
        return
    st.session_state.pop("online_code", None)
    st.session_state.pop("online_seat", None)
    _lw_online_previous_main()


_lw_online_previous_render_home = render_home


def render_home():
    with st.container(border=True):
        st.markdown("### 🌐 Jouer en ligne à 2")
        st.caption("Crée une partie, envoie le lien à ton ami : chacun joue sur son ordinateur.")
        if st.button("Créer une partie en ligne", type="primary", key="online_create"):
            room = new_online_room()
            st.query_params["room"] = room["code"]
            st.query_params["p"] = room["tokens"][0]
            st.rerun()
    _lw_online_previous_render_home()


# ============================================================
# DIRIGEABLE : SORTS UTILISABLES DEPUIS LE PLATEAU
# - Choix du sort mémorisé (il ne revient plus à zéro à chaque clic).
# - Clic sur une cible alliée surlignée :
#   • +2 PF : l'unité centrale et ses 2 voisines (gauche/droite) : immédiat ;
#   • Doubler la récolte : la base est choisie, puis bouton de confirmation.
# - Doubler la récolte : base à portée qui récolte vraiment
#   (Derniers nés : au moins un ouvrier sur une ressource voisine).
# ============================================================

def base_can_harvest(g, base):
    owner = base["owner"]
    cells = [p for p in neighbors(tuple(base["pos"])) if key(p) in g["resources"]]
    if faction_id(g, owner) == DERNIERS_NES:
        return any(
            piece["owner"] == owner and piece["name"] == WORKER
            for p in cells for piece in pieces_at(g, p)
        )
    return bool(cells)


_lw_ship_previous_airship_targets = airship_targets


def airship_targets(g, airship, spell):
    targets = _lw_ship_previous_airship_targets(g, airship, spell)
    if spell == "harvest":
        targets = [b for b in targets if base_can_harvest(g, b) and not b.get("double_harvest")]
    return targets


def airship_spell_key(airship):
    return f"airship_spell_{airship['id']}"


def selected_airship(g):
    attackers = selected_attackers(g)
    if len(attackers) == 1 and attackers[0]["name"] == AIRSHIP and attackers[0]["owner"] == g["active"]:
        return attackers[0]
    return None


def current_airship_spell(airship):
    spell = st.session_state.get(airship_spell_key(airship), "boost")
    return spell if spell in AIRSHIP_SPELLS else "boost"


def render_airship_controls(g, airship, prefix):
    st.subheader("🎈 Dirigeable")
    cargo = airship.get("cargo", [])
    st.caption(
        f"À bord ({len(cargo)}/{AIRSHIP_CAPACITY}) : "
        + (", ".join(f"{u['name']} #{u['id']}" for u in cargo) or "personne")
        + f". Pas d'attaque. Détecte les invisibles à {AIRSHIP_RANGE} cases."
    )
    if not can_move(g, airship):
        st.info("Ce Dirigeable a déjà agi ce tour.")
        return

    candidates = {u["id"]: u for u in boarding_candidates(g, airship)}
    if candidates and len(cargo) < AIRSHIP_CAPACITY:
        unit_id = st.selectbox(
            "Unité voisine à embarquer",
            options=list(candidates),
            format_func=lambda eid: describe(candidates[eid]),
            key=f"airship_board_{airship['id']}",
        )
        if st.button("⬆️ Embarquer", key=f"{prefix}_board_ok_{airship['id']}"):
            perform(game_action, board_airship, airship["id"], unit_id)
    if cargo and st.button(
        "⬇️ Débarquer tout le monde (termine son activation)",
        key=f"{prefix}_unload_{airship['id']}",
    ):
        perform(game_action, unload_airship, airship["id"])

    st.markdown("##### Sorts")
    spell = st.radio(
        "Sort",
        options=list(AIRSHIP_SPELLS),
        format_func=AIRSHIP_SPELLS.get,
        key=airship_spell_key(airship),
    )
    targets = {e["id"]: e for e in airship_targets(g, airship, spell)}
    if not targets:
        st.caption(
            "Aucune unité alliée à portée."
            if spell == "boost"
            else "Aucune de tes bases à portée ne récolte (Derniers nés : il faut un ouvrier sur la ressource)."
        )
        return

    if spell == "boost":
        st.caption(
            f"Clique sur l'unité centrale surlignée (à {AIRSHIP_RANGE} cases maximum) : "
            "elle et ses voisines de gauche et de droite gagnent +2 PF pour ce tour."
        )
        return

    chosen = st.session_state.get("ui_airship_target")
    if chosen not in targets:
        st.caption("Clique sur la base surlignée dont tu veux doubler la prochaine récolte.")
        return
    base = targets[chosen]
    st.info(f"Base choisie : {base['name']} en {coord(base['pos'])}.")
    if st.button(
        "💰 Doubler la récolte de cette base au prochain tour",
        type="primary",
        key=f"{prefix}_harvest_ok_{airship['id']}_{chosen}",
    ):
        st.session_state.ui_airship_target = None
        perform(game_action, cast_airship_spell, airship["id"], "harvest", chosen)


_lw_ship_previous_board_event = board_event


def board_event(event, g, view):
    airship = selected_airship(g) if isinstance(event, dict) and g["phase"] == "move" else None
    if airship is None or event.get("event_id") == st.session_state.ui_last_event or g["curtain"]:
        return _lw_ship_previous_board_event(event, g, view)
    try:
        pos = require_position(event.get("pos"))
    except ValueError:
        return _lw_ship_previous_board_event(event, g, view)

    spell = current_airship_spell(airship)
    target = next((e for e in airship_targets(g, airship, spell) if tuple(e["pos"]) == pos), None)
    if target is None or target["id"] == airship["id"]:
        return _lw_ship_previous_board_event(event, g, view)

    st.session_state.ui_last_event = event["event_id"]
    if spell == "boost":
        perform(game_action, cast_airship_spell, airship["id"], "boost", target["id"])
    st.session_state.ui_airship_target = target["id"]
    st.session_state.ui_message = (
        f"{target['name']} choisie : confirme avec le bouton « Doubler la récolte »."
    )
    bump_ui()
    st.rerun()


_lw_ship_previous_render_board = render_board


def render_board(g, view, readonly=False):
    airship = selected_airship(g) if g["phase"] == "move" and not readonly else None
    if airship is not None and can_move(g, airship):
        spell = current_airship_spell(airship)
        st.session_state["_lw_spell_targets"] = {
            key(tuple(e["pos"])): {"target_id": e["id"], "spell": True}
            for e in airship_targets(g, airship, spell)
            if e["id"] != airship["id"]
        }
    else:
        st.session_state.pop("_lw_spell_targets", None)
    return _lw_ship_previous_render_board(g, view, readonly)


# ============================================================
# AALONGUE : SORTS (TÉLÉPORTATION, MOTIVATION)
# - Un sort tous les 2 tours ; Aalongue peut quand même se déplacer.
# - Téléportation : clique jusqu'à 4 de tes unités sur le plateau (en
#   jaune), puis « Téléporter » : elles arrivent autour d'Aalongue.
# ============================================================

AALONGUE_COOLDOWN = 2


def aalongue_spell_used(g, hero):
    """Vrai tant que le prochain sort n'est pas disponible."""
    return g["turn"] < hero.get("next_spell_turn", 1)


def aalongue_mark_spell(g, hero):
    hero["spell_turn"] = g["turn"]
    hero["next_spell_turn"] = g["turn"] + AALONGUE_COOLDOWN


def cast_motivation(g, owner, hero_id):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    if hero["name"] != "Aalongue":
        raise ValueError("Seul Aalongue lance ce sort.")
    if aalongue_spell_used(g, hero):
        raise ValueError(f"Prochain sort d'Aalongue au tour {hero['next_spell_turn']}.")
    aalongue_mark_spell(g, hero)
    g["players"][owner]["motivation_turn"] = g["turn"]
    log(g, "Motivation : +1 déplacement pour toutes les unités ce tour.")


def cast_teleport(g, owner, hero_id, unit_ids):
    require_phase(g, "build", owner)
    hero = require_own_hero(g, owner, hero_id)
    if hero["name"] != "Aalongue":
        raise ValueError("Seul Aalongue lance ce sort.")
    if aalongue_spell_used(g, hero):
        raise ValueError(f"Prochain sort d'Aalongue au tour {hero['next_spell_turn']}.")
    if not 1 <= len(unit_ids) <= AALONGUE_TELEPORT or len(set(unit_ids)) != len(unit_ids):
        raise ValueError(f"Choisis de 1 à {AALONGUE_TELEPORT} unités différentes.")
    units = [entity(g, uid) for uid in unit_ids]
    if any(u["owner"] != owner or u["kind"] != "unit" for u in units):
        raise ValueError("Choisis tes propres unités.")
    cells = teleport_cells(g, hero)
    if len(cells) < len(units):
        raise ValueError(f"Pas assez de cases libres autour d'Aalongue ({len(cells)}).")
    for unit, pos in zip(units, cells):
        origin = coord(unit["pos"])
        unit["pos"] = list(pos)
        log(g, f"Téléportation : {unit['name']} {origin} → {coord(pos)}.")
    aalongue_mark_spell(g, hero)
    g["_ui_message"] = f"🌀 Téléportation : {len(units)} unité(s) autour d'Aalongue."


def teleport_choice():
    return [int(i) for i in st.session_state.get("ui_teleport_ids", [])]


def selected_aalongue(view):
    source = selected_entity(view)
    if (
        source is not None
        and source["name"] == "Aalongue"
        and source["owner"] == view["active"]
        and view["phase"] == "build"
        and st.session_state.get("ui_teleport_mode")
    ):
        return source
    return None


_lw_tp_previous_board_event = board_event


def board_event(event, g, view):
    hero = selected_aalongue(view) if isinstance(event, dict) and event.get("type") == "cell_click" else None
    if hero is None or event.get("event_id") == st.session_state.ui_last_event or g["curtain"]:
        return _lw_tp_previous_board_event(event, g, view)
    try:
        pos = require_position(event.get("pos"))
    except ValueError:
        return _lw_tp_previous_board_event(event, g, view)
    unit = next(
        (e for e in pieces_at(view, pos) if e["owner"] == hero["owner"] and e["kind"] == "unit"),
        None,
    )
    if unit is None:
        return _lw_tp_previous_board_event(event, g, view)

    st.session_state.ui_last_event = event["event_id"]
    chosen = teleport_choice()
    if unit["id"] in chosen:
        chosen.remove(unit["id"])
    elif len(chosen) < AALONGUE_TELEPORT:
        chosen.append(unit["id"])
    else:
        st.session_state.ui_message = f"Maximum {AALONGUE_TELEPORT} unités pour la téléportation."
    st.session_state.ui_teleport_ids = chosen
    bump_ui()
    st.rerun()


_lw_tp_previous_render_board = render_board


def render_board(g, view, readonly=False):
    hero = selected_aalongue(view) if not readonly else None
    if hero is not None:
        ids = set(teleport_choice())
        st.session_state.ui_plan_positions = [
            list(e["pos"]) for e in view["entities"] if e["id"] in ids
        ]
    return _lw_tp_previous_render_board(g, view, readonly)


def render_aalongue_spells(view, hero, prefix):
    st.markdown("##### ✨ Sorts d'Aalongue (un sort tous les 2 tours)")
    if aalongue_spell_used(view, hero):
        st.caption(f"Prochain sort disponible au tour {hero['next_spell_turn']}. Aalongue peut quand même se déplacer.")
        st.session_state["_tp_reset"] = True
        return
    if st.button("💨 Motivation : +1 déplacement à toutes tes unités ce tour", key=f"{prefix}_motivation_{hero['id']}"):
        perform(draft_action, cast_motivation, hero["id"])

    if st.session_state.pop("_tp_reset", False):
        st.session_state.ui_teleport_mode = False
    mode = st.toggle(
        f"🌀 Téléportation : choisir jusqu'à {AALONGUE_TELEPORT} unités sur le plateau",
        key="ui_teleport_mode",
    )
    if not mode:
        if st.session_state.get("ui_teleport_ids"):
            st.session_state.ui_teleport_ids = []
            if st.session_state.ui_plan_mode is None:
                st.session_state.ui_plan_positions = []
        return
    chosen = [e for e in view["entities"] if e["id"] in teleport_choice()]
    free = len(teleport_cells(view, hero))
    st.caption(
        f"Clique tes unités sur le plateau (elles passent en jaune) : {len(chosen)}/{AALONGUE_TELEPORT}. "
        f"Cases libres autour d'Aalongue : {free}."
    )
    if chosen:
        st.write(", ".join(f"{e['name']} ({coord(e['pos'])})" for e in chosen))
        if st.button(
            f"🌀 Téléporter {len(chosen)} unité(s) autour d'Aalongue",
            type="primary",
            disabled=free < len(chosen),
            key=f"{prefix}_teleport_go_{hero['id']}",
        ):
            ids = [e["id"] for e in chosen]
            st.session_state.ui_teleport_ids = []
            st.session_state.ui_plan_positions = []
            st.session_state["_tp_reset"] = True
            perform(draft_action, cast_teleport, hero["id"], ids)


# ============================================================
# DÉPLACEMENTS EN PLUSIEURS FOIS (héros, ouvriers)
# Après un déplacement, la pièce reste sélectionnée, en mode déplacement,
# tant qu'il lui reste des déplacements.
# ============================================================

_lw_resume_previous_main = main


def main():
    resume = st.session_state.pop("_resume_plan", None)
    if resume:
        init_ui()
        st.session_state.ui_selected_id = resume["id"]
        st.session_state.ui_plan_mode = resume["mode"]
        st.session_state.ui_plan_name = resume["name"]
        st.session_state.ui_plan_positions = []
    _lw_resume_previous_main()


# ============================================================
# VAGABONDS : UNE CASE DE RESSOURCE NE RAPPORTE QU'UNE FOIS
# Deux marqueurs (ou deux héros) sur la même case d'or ou de mana ne
# cumulent pas : seule la première récolte compte pour ce tour.
# ============================================================

_lw_marker_previous_hero_collect = hero_collect


def hero_collect(g, hero):
    marker = hero.get("marker")
    taken = g.get("_harvested_markers")
    if marker and taken is not None:
        cell = (hero["owner"], key(tuple(marker)))
        if cell in taken:
            log(g, f"{hero['name']} : la case {coord(marker)} a déjà été récoltée ce tour (marqueurs non cumulables).")
            return
        taken.add(cell)
    _lw_marker_previous_hero_collect(g, hero)


_lw_marker_previous_harvest = harvest


def harvest(g):
    g["_harvested_markers"] = set()
    try:
        _lw_marker_previous_harvest(g)
    finally:
        g.pop("_harvested_markers", None)


def shared_marker_heroes(g, hero):
    marker = hero.get("marker")
    if not marker:
        return []
    return [
        h for h in g["entities"]
        if h is not hero and h["owner"] == hero["owner"] and is_hero(h) and h.get("marker") == marker
    ]


_lw_marker_previous_move_hero = move_hero


def move_hero(g, owner, hero_id, destination):
    _lw_marker_previous_move_hero(g, owner, hero_id, destination)
    hero = entity(g, hero_id)
    others = shared_marker_heroes(g, hero)
    if others:
        g["_ui_message"] = (
            f"⚠️ {hero['name']} pose son marqueur en {coord(hero['marker'])}, déjà utilisé par "
            + ", ".join(h["name"] for h in others)
            + " : cette case ne rapportera qu'une seule fois."
        )


# ============================================================
# CONSTRUCTION ACCÉLÉRÉE : boutons « Construire » et « ⚡ Accélérée »
# côte à côte dans chaque fiche de bâtiment (+50 % du prix,
# disponible immédiatement). Les bases ne s'accélèrent pas.
# ============================================================

def build_button_type(name, fast):
    chosen = (
        st.session_state.ui_plan_mode == "build"
        and st.session_state.ui_plan_name == name
        and bool(st.session_state.ui_plan_accelerated) == fast
    )
    return "primary" if chosen else "secondary"


def start_build(name, fast):
    start_placement("build", name)
    st.session_state.ui_plan_accelerated = bool(fast)
    st.session_state.ui_message = (
        f"⚡ {name} en construction accélérée : clique sur une case verte."
        if fast else f"{name} : clique sur une case verte."
    )
    st.rerun()


# ============================================================
# ARMES DE SIÈGE : CASES TOUCHÉES (gauche, droite, derrière)
# Vu depuis la catapulte, « gauche » et « droite » sont les deux voisines
# de la cible situées de part et d'autre du tir, du côté de la case de
# derrière : avec la cible et la case de derrière, elles forment un bloc
# de 4 cases. Les cases touchées s'affichent en rouge avant le tir.
# ============================================================

def siege_side_cells(origin, target_pos):
    origin, target_pos = tuple(origin), tuple(target_pos)
    ox, oy = flat_center(origin, 1, 0, 0)
    tx, ty = flat_center(target_pos, 1, 0, 0)
    ux, uy = tx - ox, ty - oy
    norm = math.hypot(ux, uy) or 1.0
    ux, uy = ux / norm, uy / norm
    left, right = [], []
    for n in neighbors(target_pos):
        nx, ny = flat_center(n, 1, 0, 0)
        vx, vy = nx - tx, ny - ty
        vnorm = math.hypot(vx, vy) or 1.0
        angle = math.degrees(math.acos(max(-1.0, min(1.0, (ux * vx + uy * vy) / vnorm))))
        cross = ux * vy - uy * vx
        # Voisines à environ 60° de l'axe du tir (côté arrière).
        (left if cross < 0 else right).append((abs(angle - 60), n))
    picks = [min(side)[1] for side in (left, right) if side]
    return [p for p in picks if p in CELL_SET]


def cell_behind(origin, target_pos):
    """Voisine de la cible dans le prolongement exact du tir."""
    origin, target_pos = tuple(origin), tuple(target_pos)
    ox, oy = flat_center(origin, 1, 0, 0)
    tx, ty = flat_center(target_pos, 1, 0, 0)
    ux, uy = tx - ox, ty - oy
    best = None
    for n in neighbors(target_pos):
        nx, ny = flat_center(n, 1, 0, 0)
        vx, vy = nx - tx, ny - ty
        score = (ux * vx + uy * vy) / ((math.hypot(ux, uy) or 1) * (math.hypot(vx, vy) or 1))
        if best is None or score > best[0]:
            best = (score, n)
    return best[1] if best and best[1] in CELL_SET else None


def siege_impact_cells(attacker, target_pos):
    """{case: dégâts} d'un tir de siège sur cette case."""
    origin = tuple(attacker["pos"])
    target_pos = tuple(target_pos)
    if attacker["name"] == HELL_CATAPULT:
        cells = {target_pos: HELL_MAIN_DAMAGE}
        behind = cell_behind(origin, target_pos)
        if behind is not None:
            cells[behind] = HELL_MAIN_DAMAGE
        for p in siege_side_cells(origin, target_pos):
            cells[p] = HELL_SIDE_DAMAGE
        return cells
    cells = {target_pos: SIEGE_DAMAGE}
    for p in siege_side_cells(origin, target_pos):
        cells[p] = SIEGE_SIDE_DAMAGE
    return cells


_lw_impact_previous_render_board = render_board


def render_board(g, view, readonly=False):
    if g["phase"] == "move" and not readonly:
        attackers = selected_attackers(g)
        target = current_target(g) if attackers else None
        if len(attackers) == 1 and attackers[0]["name"] in SIEGE_RANGES and target is not None:
            # Aperçu : toutes les cases que le tir va toucher, en rouge.
            st.session_state["_lw_siege_targets"] = {
                key(p): {"target_id": target["id"]}
                for p in siege_impact_cells(attackers[0], target["pos"])
            }
            return _lw_impact_previous_render_board(g, view, readonly)
    st.session_state.pop("_lw_siege_targets", None)
    return _lw_impact_previous_render_board(g, view, readonly)

# ============================================================
# VENGEANCE : un tueur réduit à 0 PF est détruit à son tour
# (l'amélioration retire 0,5 PF au tueur : il ne peut pas rester à 0 PF).
# ============================================================

def purge_dead_pieces(g):
    for piece in [e for e in g["entities"] if float(e.get("pf", 1)) <= 0]:
        if piece in g["entities"]:
            destroy(g, piece, 1 - piece["owner"])


_lw_venge_previous_game_action = game_action


def game_action(bundle, fn, *args):
    result = _lw_venge_previous_game_action(bundle, fn, *args)
    purge_dead_pieces(bundle["game"])
    return result


_lw_venge_previous_draft_action = draft_action


def draft_action(bundle, fn, *args):
    result = _lw_venge_previous_draft_action(bundle, fn, *args)
    if bundle.get("draft") is not None:
        purge_dead_pieces(bundle["draft"])
    return result


# ============================================================
# BONUS D'ATTAQUE (Marteau foudroyant) : il absorbe aussi les pertes
# Le Guerrier attaque avec 2,5 PF : contre 2 PF, il gagne et survit
# avec 0,5 PF (auparavant l'attaque était impossible à valider).
# ============================================================

_lw_bonus_previous_combat_values = combat_values


def combat_values(attackers, target):
    values = _lw_bonus_previous_combat_values(attackers, target)
    bonus = sum(float(a.get("attack_bonus", 0.0)) for a in attackers)
    if bonus and values.get("winnable") and values.get("losses", 0) > 0:
        values = dict(values, losses=max(0.0, float(values["losses"]) - bonus))
    return values

# ============================================================
# PIÉTINEMENT : seulement contre des unités
# Attaquer une base ou un bâtiment arrête toujours l'attaquant,
# même s'il a le piétinement (Chevalier, Molosse, Roi, Barbare…).
# ============================================================

_lw_trample_previous_can_trample = can_trample


def can_trample(unit, target):
    if target is None or target.get("kind") != "unit":
        return False
    return _lw_trample_previous_can_trample(unit, target)

# ============================================================
# OUVRIERS ET HÉROS : DÉPLACEMENT DIRECT
# Un clic sur un ouvrier (Derniers nés) ou un héros (Vagabonds) affiche
# aussitôt ses cases de déplacement en vert : plus besoin du bouton
# « Déplacer ». Le menu de construction / production reste disponible.
# ============================================================

def auto_piece_move_mode():
    bundle = st.session_state.get("bundle")
    if not isinstance(bundle, dict) or not isinstance(bundle.get("game"), dict):
        return
    g = bundle["game"]
    if g["phase"] != "build" or g["winner"] is not None or g.get("curtain"):
        return
    if st.session_state.get("ui_plan_mode") is not None:
        return
    selected = st.session_state.get("ui_selected_id")
    if selected is None:
        return
    ensure_draft(bundle)
    view = bundle["draft"] or g
    piece = next((e for e in view["entities"] if e["id"] == selected), None)
    if piece is None or piece["owner"] != g["active"]:
        return
    if piece["name"] == WORKER and not piece["wait"] and worker_destinations(view, piece):
        mode, name = "worker_move", WORKER
    elif is_hero(piece) and hero_destinations(view, piece):
        mode, name = "hero_move", piece["name"]
    else:
        return
    st.session_state.ui_plan_mode = mode
    st.session_state.ui_plan_name = name
    st.session_state.ui_plan_positions = []


_lw_automove_previous_main = main


def main():
    init_ui()
    auto_piece_move_mode()
    _lw_automove_previous_main()

# ============================================================
# ABANDON DE LA PARTIE
# À tout moment, le joueur peut abandonner : l'autre joueur gagne.
# - Partie locale : abandon du joueur qui a la main.
# - Contre l'IA : abandon du joueur humain.
# - En ligne : abandon du joueur de ce navigateur (même hors de son tour).
# ============================================================

def forfeit_game(bundle, loser):
    g = bundle["game"]
    if g["winner"] is not None:
        raise ValueError("La partie est déjà terminée.")
    g["winner"] = 1 - loser
    log(g, f"{faction_of(g, loser)['name']} abandonne la partie : victoire des {faction_of(g, 1 - loser)['name']}.")
    g["_ui_message"] = f"🏳️ Les {faction_of(g, loser)['name']} ont abandonné la partie."


def forfeit_loser(bundle):
    """Siège du joueur qui abandonne depuis cet écran."""
    if st.session_state.get("online_code") and online_seat() in (0, 1):
        return online_seat()
    config = ai_config(bundle)
    if config is not None:
        return 1 - config["seat"]
    return bundle["game"]["active"]


def forfeit_online(loser):
    room = online_active_room()
    if room is None:
        return
    with online_lock():
        shared = copy.deepcopy(room["bundle"])
        try:
            forfeit_game(shared, loser)
        except ValueError:
            return
        shared["game"].pop("_ui_message", None)
        room["bundle"] = shared
        room["version"] += 1
    st.session_state.online_handed = None
    st.session_state.ui_message = "🏳️ Tu as abandonné la partie."
    bump_ui(clear_selection=True)
    st.rerun()


def render_forfeit(bundle):
    g = bundle["game"]
    if g["winner"] is not None:
        return
    loser = forfeit_loser(bundle)
    name = faction_of(g, loser)["name"]
    with st.expander("🏳️ Abandonner la partie"):
        st.caption(f"Les {name} abandonnent : les {faction_of(g, 1 - loser)['name']} gagnent aussitôt.")
        sure = st.checkbox("Je confirme vouloir abandonner", key="forfeit_confirm")
        if st.button(f"🏳️ Abandonner ({name})", type="primary", disabled=not sure, key="forfeit_go"):
            if st.session_state.get("online_code"):
                forfeit_online(loser)
            else:
                perform(forfeit_game, loser)


_lw_forfeit_previous_render_sidebar = render_sidebar


def render_sidebar(bundle):
    _lw_forfeit_previous_render_sidebar(bundle)
    with st.sidebar:
        render_forfeit(bundle)

# --- Écran de fin après un abandon : image dédiée.
ABANDON_IMAGE = Path(__file__).parent / "assets" / "abandon.jpg"


def abandon_image_data():
    return file_base64(ABANDON_IMAGE)


def game_forfeiter(g):
    """Siège du joueur qui a abandonné, sinon None."""
    if g.get("winner") not in (0, 1):
        return None
    loser = 1 - g["winner"]
    marker = f"{faction_of(g, loser)['name']} abandonne la partie"
    return loser if any(marker in line for line in g.get("log", [])[-5:]) else None


_lw_abandon_previous_render_victory_screen = render_victory_screen


def render_victory_screen(g):
    loser = game_forfeiter(g)
    image = abandon_image_data() if loser is not None else None
    if image is None:
        return _lw_abandon_previous_render_victory_screen(g)
    title = (
        f"Les {faction_of(g, loser)['name']} abandonnent : "
        f"victoire des {faction_of(g, g['winner'])['name']} !"
    )
    st.markdown(
        f"""
        <div style="position: relative; width: min(100%, 620px); margin: 0 auto;
                    aspect-ratio: 1 / 1;
                    border-radius: 14px; overflow: hidden; border: 2px solid #b8913f;
                    background: url('data:image/jpeg;base64,{image}') center / cover no-repeat;
                    box-shadow: 0 8px 28px #00000066;">
          <div style="position: absolute; inset: 0;
                      background: linear-gradient(180deg, #00000099 0%, #00000022 45%, #00000000 70%);"></div>
          <div style="position: absolute; top: 6%; left: 0; right: 0;
                      text-align: center; padding: 0 4%;
                      color: #ffffff; font-weight: 900;
                      font-size: clamp(18px, 2.8vw, 34px); line-height: 1.15;
                      text-shadow: 0 3px 12px #000000, 0 0 4px #000000;">
            🏳️ {escape(title)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# IA : ADVERSAIRE CONTRÔLÉ PAR L'ORDINATEUR — TROIS NIVEAUX
# Un seul moteur, des réglages différents par niveau (AI_PARAMS).
# Chaque action est d'abord essayée sur une copie de la partie : l'IA
# respecte toutes les règles du jeu. Elle ne voit que ce qu'un joueur
# voit (pas d'unité invisible non détectée, pas la production secrète
# de l'adversaire). Aucun choix n'est tiré au hasard.
#
# Débutant      : dépense au moins 75 % de son or et de son mana.
#                 Attaque ce qu'il bat, avance vers la base ennemie la
#                 plus proche, ne surveille pas les menaces.
# Intermédiaire : dépense au moins 90 %. Voit venir la riposte adverse,
#                 évite les cases menacées au prochain tour, défend ses
#                 bases, attaque en groupe.
# Expert        : dépense 100 % de ses ressources, sauf ce qu'il garde
#                 pour passer à l'âge II ou III. Anticipe l'adversaire sur
#                 2 tours (riposte, réponse, nouvelle riposte), agressif :
#                 vise les bases (3 bases détruites = victoire).
# ============================================================

AI_LEVELS = {
    "debutant": "🟢 Débutant",
    "intermediaire": "🟠 Intermédiaire",
    "expert": "🔴 Expert",
    "sanguinaire": "💀 Destructeur sanguinaire",
}

AI_LEVEL_TEXT = {
    "debutant": "Débutant : joue simplement mais jamais au hasard, dépense au moins 75 % de ses ressources.",
    "intermediaire": "Intermédiaire : dépense au moins 90 %, voit venir tes attaques, se défend et attaque bien.",
    "expert": "Expert : dépense tout (sauf pour changer d'âge), anticipe sur 2 tours et attaque sans relâche.",
    "sanguinaire": "Destructeur sanguinaire : joue comme l'Expert mais ne pense qu'à détruire. "
                   "Il fonce sur tes bases, accepte de sacrifier ses unités et frappe à chaque occasion.",
}

AI_PARAMS = {
    "debutant": {
        # Jeu simple mais jamais au hasard : unités les moins chères, pas
        # d'améliorations (sauf celles indispensables aux Vagabonds), marche
        # vers l'ennemi le plus proche, prend la première attaque gagnante.
        "spend": 0.75, "save_for_age": False, "age_from": {2: 7, 3: 11},
        "building_goal": 1, "fast_build_at": None, "eco_colonies": False,
        "upgrade_min": 99999, "decisive_upgrades": False, "unit_rule": "cheap",
        "advance": 10.0, "danger": 0.0, "threat_turns": 0, "defend": 0.0,
        "groups": False, "replies": 0, "top": 0, "base_bonus": 1500.0,
        "front": False, "chase": True, "first_attack": True, "tier_buildings": False,
    },
    "intermediaire": {
        "spend": 0.90, "save_for_age": True, "age_from": {2: 4, 3: 7},
        "building_goal": 2, "fast_build_at": None, "eco_colonies": True,
        "upgrade_min": 300, "decisive_upgrades": True, "unit_rule": "balanced",
        "advance": 12.0, "danger": 0.3, "threat_turns": 1, "defend": 1.0,
        "groups": True, "replies": 1, "top": 5, "base_bonus": 2500.0,
        "front": True,
    },
    "expert": {
        "spend": 1.0, "save_for_age": True, "age_from": {2: 3, 3: 6},
        "building_goal": "limit", "fast_build_at": 1500, "eco_colonies": True,
        "upgrade_min": 150, "decisive_upgrades": True, "unit_rule": "tier",
        "advance": 26.0, "danger": 0.15, "threat_turns": 2, "defend": 0.6,
        "groups": True, "replies": 3, "top": 4, "base_bonus": 3500.0,
        "front": True,
    },
    # Comme l'Expert (anticipation sur 2 tours, économie complète), mais très
    # très agressif : il vise les bases ennemies, craint peu les menaces et
    # accepte les échanges, même défavorables : il attaque sans cesse.
    "sanguinaire": {
        "spend": 1.0, "save_for_age": True, "age_from": {2: 3, 3: 6},
        "building_goal": "limit", "fast_build_at": 800, "eco_colonies": True,
        "upgrade_min": 150, "decisive_upgrades": True, "unit_rule": "tier",
        "advance": 33.0, "danger": 0.1, "threat_turns": 2, "defend": 0.5,
        "groups": True, "replies": 3, "top": 4, "base_bonus": 8000.0,
        "front": True,
        # Agressivité (réglée sur des parties contre l'Expert : près de deux
        # fois plus d'attaques) : ses pertes comptent pour 60 %, il craint
        # moins les ripostes à venir et chaque attaque reçoit une prime.
        "own_value": 0.6, "anticipate_weight": 0.35, "attack_drive": 300.0,
    },
}

AI_MAX_STEPS = 1500  # garde-fou : l'IA joue tout son tour d'un coup
AI_TRIES = 12
AI_REPLY_LIMIT = 8
AI_ATTACK_LIMIT = 30  # attaques simulées au plus par activation (les plus prometteuses)
AI_ANTICIPATE_WEIGHT = 0.8
AI_GUARD_VALUE = 70.0
AI_ERRORS = (ValueError, KeyError, TypeError, IndexError, AttributeError, ZeroDivisionError)

# Unités dont l'IA n'exploite pas les pouvoirs : produites en dernier recours.
AI_WEAK_UNITS = {"Gobelin", "Mage des montagnes", "Décimant", "Dirigeable", "Kamikaze", "Aramil"}


def ai_params(level):
    return AI_PARAMS.get(level, AI_PARAMS["intermediaire"])


# ------------------------------------------------------------
# Copies rapides et essais d'actions
# ------------------------------------------------------------

def ai_copy(value):
    kind = type(value)
    if kind is dict:
        return {k: ai_copy(v) for k, v in value.items()}
    if kind is list:
        return [ai_copy(v) for v in value]
    if kind is tuple:
        return tuple(ai_copy(v) for v in value)
    if kind is set:
        return set(value)
    return value


# La carte ne change jamais pendant la partie : les copies la partagent.
AI_SHARED_FIELDS = ("terrain", "resources")


def ai_clone(g):
    """Copie de travail de la partie (journal vidé, recollé ensuite)."""
    return {
        k: [] if k == "log" else v if k in AI_SHARED_FIELDS else ai_copy(v)
        for k, v in g.items()
    }


def ai_restore_log(original, clone):
    clone["log"] = list(original.get("log", [])) + clone.get("log", [])
    return clone


def ai_simulate(g, fn, *args):
    """Manœuvre essayée sur une copie ; None si les règles la refusent."""
    bundle = {"game": ai_clone(g), "draft": None, "committed": None}
    try:
        game_action(bundle, fn, *args)
    except AI_ERRORS:
        return None
    return bundle["game"]


def ai_try(g, fn, me, *args):
    """Action de production essayée sur une copie du brouillon."""
    clone = ai_clone(g)
    try:
        fn(clone, me, *args)
    except AI_ERRORS:
        return None
    return ai_restore_log(g, clone)


def ai_gold(g, me):
    return g["players"][me]["gold"]


def ai_mana(g, me):
    return g["players"][me]["mana"]


# ------------------------------------------------------------
# Évaluation d'une position
# ------------------------------------------------------------

def ai_unit_value(e):
    data = UNITS.get(e["name"], {})
    if e["name"] == WORKER:
        return 140.0
    base = data.get("cost", 100) / max(1, data.get("batch", 1)) + 140 * data.get("mana", 0)
    base = max(base, 140.0 * float(data.get("pf", 1)))
    top = float(e.get("max_pf") or data.get("pf") or 1)
    return base * (0.35 + 0.65 * min(1.0, float(e["pf"]) / top))


def ai_piece_value(g, e):
    if e["kind"] == "unit":
        return ai_unit_value(e)
    pf = float(e["pf"])
    top = float(e.get("max_pf") or 0) or max(pf, 1.0)
    if is_hero(e):
        return 1800.0 + 1200.0 * min(1.0, pf / top)
    if e["kind"] == "base":
        return 2200.0 + 1800.0 * min(1.0, pf / top) + (0 if e["wait"] else 300)
    data = faction_of(g, e["owner"])["buildings"].get(e["name"], {})
    return float(data.get("cost", 200)) * (0.5 + 0.5 * min(1.0, pf / top)) + 100


def ai_material(g, me, P):
    if g.get("winner") is not None:
        if g["winner"] == me:
            return 1e7
        return 0.0 if g["winner"] == -1 else -1e7
    score = 0.0
    own_value = P.get("own_value", 1.0)
    for e in g["entities"]:
        if e["owner"] == me:
            score += ai_piece_value(g, e) * own_value
        elif visible_to_player(g, e, me):
            score -= ai_piece_value(g, e)
    for owner in (0, 1):
        sign = 1 if owner == me else -1
        player = g["players"][owner]
        score += sign * (0.5 * player.get("gold", 0) + 120 * player.get("mana", 0))
    # Détruire 3 bases gagne la partie : chaque base détruite compte beaucoup.
    score += P["base_bonus"] * (
        g["players"][me].get("bases", 0) - g["players"][1 - me].get("bases", 0)
    )
    return score


def ai_enemy_pieces(g, me):
    return [e for e in g["entities"] if e["owner"] != me and visible_to_player(g, e, me)]


# ------------------------------------------------------------
# Cartes de distances (vrais chemins : montagne = 2, mer infranchissable)
# ------------------------------------------------------------

_AI_DIST_CACHE = {}
_AI_TERRAIN_FP = {}


def ai_terrain_fp(g):
    terrain = g["terrain"]
    entry = _AI_TERRAIN_FP.get(id(terrain))
    if entry is None or entry[0] is not terrain:
        if len(_AI_TERRAIN_FP) > 50:
            _AI_TERRAIN_FP.clear()
        entry = (terrain, hash(tuple(sorted(terrain.items()))))
        _AI_TERRAIN_FP[id(terrain)] = entry
    return entry[1]


def ai_distance_map(g, starts):
    """Distance de marche minimale depuis des cases de départ {case: coût initial}."""
    cache_key = (ai_terrain_fp(g), frozenset(starts.items()))
    cached = _AI_DIST_CACHE.get(cache_key)
    if cached is not None:
        return cached
    dist = dict(starts)
    queue = [(cost, pos) for pos, cost in starts.items()]
    heapq.heapify(queue)
    while queue:
        cost, pos = heapq.heappop(queue)
        if cost != dist.get(pos):
            continue
        for nxt in neighbors(pos):
            kind = terrain(g, nxt)
            if kind == "sea":
                continue
            new = cost + (2 if kind == "mountain" else 1)
            if new < dist.get(nxt, math.inf):
                dist[nxt] = new
                heapq.heappush(queue, (new, nxt))
    if len(_AI_DIST_CACHE) > 400:
        _AI_DIST_CACHE.clear()
    _AI_DIST_CACHE[cache_key] = dist
    return dist


# ------------------------------------------------------------
# Positionnement : avancer, défendre, éviter les menaces
# ------------------------------------------------------------

def ai_context(g, me, P):
    enemies = ai_enemy_pieces(g, me)
    fighters = [e for e in enemies if e["kind"] == "unit" and e["name"] not in NO_ATTACK_UNITS]
    if P.get("chase"):
        # Débutant : il marche vers l'ennemi le plus proche, quel qu'il soit.
        starts = {tuple(e["pos"]): 0 for e in enemies}
    else:
        starts = {tuple(e["pos"]): 0 for e in enemies if e["kind"] == "base"}
    for e in enemies:
        # Les bâtiments comptent, mais les bases passent avant.
        if e["kind"] == "building":
            starts.setdefault(tuple(e["pos"]), 3)
    if not starts:
        starts = {tuple(e["pos"]): 0 for e in fighters}
    goal = ai_distance_map(g, starts) if starts else {}
    my_bases = {tuple(e["pos"]): 0 for e in g["entities"] if e["owner"] == me and e["kind"] == "base"}
    home = ai_distance_map(g, my_bases) if my_bases and P["defend"] else {}
    mine = sum(
        ai_unit_value(e) for e in g["entities"]
        if e["owner"] == me and e["kind"] == "unit" and e["name"] != WORKER
    )
    theirs = sum(ai_unit_value(e) for e in fighters)
    horizon = max(1, P["threat_turns"])
    approaching = []
    if home:
        for e in fighters:
            d = home.get(tuple(e["pos"]), 99)
            if d <= horizon * UNITS.get(e["name"], {}).get("move", 3) + 2:
                approaching.append((tuple(e["pos"]), d))
    return {
        "P": P,
        "goal": goal,
        "goal_cells": list(starts),
        "goal_far": max(goal.values(), default=0) + 5,
        "home": home,
        "approaching": approaching,
        "defensive": bool(P["defend"]) and mine < 0.9 * theirs,
        "threats": [
            (tuple(e["pos"]), UNITS.get(e["name"], {}).get("move", 0),
             max(1, UNITS.get(e["name"], {}).get("range", 0)), float(e["pf"]))
            for e in fighters
        ],
    }


def ai_place_score(ctx, unit, pos):
    P = ctx["P"]
    score = 0.0
    # Avancer vers les bases ennemies (vrais chemins ; les volants vont droit).
    if ctx["goal_cells"]:
        if is_flying(unit):
            dist = min(distance(pos, q) for q in ctx["goal_cells"])
        else:
            dist = ctx["goal"].get(pos, ctx["goal_far"])
        score += P["advance"] * (0.3 if ctx["defensive"] else 1.0) * max(0, ctx["goal_far"] - dist)
    # Défendre : tenir les passages entre l'ennemi et ses bases.
    home = ctx["home"]
    if home:
        here = home.get(pos, 99)
        if ctx["defensive"] and here > 4:
            score -= 12 * (here - 4)
        for where, their_home in ctx["approaching"]:
            if here <= 4 and here + distance(pos, where) <= their_home + 1:
                guard = 1.0 if here >= 1 else 0.5
                score += AI_GUARD_VALUE * P["defend"] * guard * (1.5 if ctx["defensive"] else 1.0)
                break
    # Menaces : ennemis capables de frapper cette case (1 ou 2 tours).
    if P["danger"] and ctx["threats"]:
        mine = float(unit["pf"])
        now = later = 0.0
        for where, move, reach, pf in ctx["threats"]:
            gap = distance(pos, where)
            if gap <= move + reach:
                now = max(now, pf)
            elif P["threat_turns"] >= 2 and gap <= 2 * move + reach:
                later = max(later, pf)
        value = ai_unit_value(unit)
        if now >= mine:
            score -= P["danger"] * value
        elif now:
            score -= P["danger"] * 0.25 * value
        if later >= mine:
            score -= P["danger"] * 0.4 * value
    return score


def ai_positional(g, me, P, ctx=None):
    ctx = ctx or ai_context(g, me, P)
    return sum(
        ai_place_score(ctx, unit, tuple(unit["pos"]))
        for unit in g["entities"]
        if unit["owner"] == me and unit["kind"] == "unit" and unit["name"] != WORKER
    )


def ai_evaluate(g, me, P):
    return ai_material(g, me, P) + ai_positional(g, me, P)


# ------------------------------------------------------------
# Manœuvres
# ------------------------------------------------------------

def ai_active_units(g, me):
    units = [
        e for e in g["entities"]
        if e["owner"] == me and e["kind"] == "unit" and e["name"] != WORKER and can_move(g, e)
    ]
    moving = g.get("moving_unit_id")
    if moving is not None:
        units = [u for u in units if u["id"] == moving] or units
    return units


def ai_melee_args(g, ids, target_id):
    attackers, target, _ = prepare_attack(g, ids, target_id)
    values = combat_values(attackers, target)
    melee = [a for a in attackers if UNITS.get(a["name"], {}).get("range", 0) <= 0]
    occupier = max(melee or attackers, key=lambda a: a["pf"])["id"]
    if not values.get("winnable"):
        return occupier, None
    return occupier, default_losses(attackers, values.get("losses", 0.0), occupier)


AI_FOCUS_RADIUS = 8


def ai_attack_candidates(g, side, groups, near=None):
    """Attaques possibles : (fonction, arguments, cible). « near » : seulement
    les unités proches de ces cases (anticipation locale, plus rapide)."""
    candidates = []
    reach = {}
    units = ai_active_units(g, side)
    if near:
        units = [
            u for u in units
            if min(distance(tuple(u["pos"]), p) for p in near) <= AI_FOCUS_RADIUS
        ]
    for unit in units:
        try:
            _, targets = attack_map_preview(g, [unit])
        except AI_ERRORS:
            continue
        for pos, data in targets.items():
            tid = data.get("target_id") if isinstance(data, dict) else None
            target = at(g, pos) if tid is None else next((e for e in g["entities"] if e["id"] == tid), None)
            if target is None or target["owner"] == side:
                continue
            if unit["name"] == SORCERER:
                for spell in SORCERER_SPELLS:
                    candidates.append((cast_sorcerer_spell, (unit["id"], spell, target["id"]), target))
                continue
            if unit["name"] in MAGES or unit["name"] == "Décimant":
                continue
            if UNITS.get(unit["name"], {}).get("range", 0) > 0:
                candidates.append((ranged_attack, (unit["id"], target["id"]), target))
            reach.setdefault(target["id"], (target, []))[1].append(unit)
            candidates.append(("melee", ([unit["id"]], target["id"]), target))
    if groups:
        for target, group in reach.values():
            fighters = sorted(
                (u for u in group if UNITS.get(u["name"], {}).get("range", 0) <= 0),
                key=lambda u: (-u["pf"], u["id"]),
            )
            for size in (2, 3):
                if len(fighters) >= size:
                    candidates.append(("melee", ([u["id"] for u in fighters[:size]], target["id"]), target))
    return candidates


def ai_resolve(g, candidate):
    fn, args, _ = candidate
    if fn == "melee":
        ids, tid = args
        try:
            occupier, losses = ai_melee_args(g, ids, tid)
        except AI_ERRORS:
            return None, None
        return attack, (ids, tid, occupier, losses)
    return fn, args


def ai_special_candidates(g):
    special = []
    if decimant_hunt(g) is not None:
        special.append((renounce_decimant_hunt, (), None))
    if dwarf_rally(g) is not None:
        special.append((end_dwarf_rally, (), None))
    return special


def ai_move_candidates(g, me, ctx):
    """Déplacements notés directement (sans simulation) : (gain, unité, case)."""
    scored = []
    for unit in ai_active_units(g, me):
        try:
            destinations, _ = move_preview(g, unit)
        except AI_ERRORS:
            continue
        here = ai_place_score(ctx, unit, tuple(unit["pos"]))
        for pos in sorted(destinations):
            scored.append((ai_place_score(ctx, unit, pos) - here, unit["id"], pos))
    return scored


def ai_best_attack(g, side, me, P, near=None):
    """Meilleure attaque immédiate de « side » ; gain vu par « side »."""
    if g.get("winner") is not None or g.get("phase") != "move" or g.get("active") != side:
        return 0.0, None
    base = ai_material(g, me, P)
    candidates = ai_attack_candidates(g, side, groups=False, near=near)
    # Les cibles de grande valeur d'abord (bases, grosses unités).
    candidates.sort(key=lambda c: -(ai_piece_value(g, c[2]) if c[2] is not None else 0))
    best, best_state = 0.0, None
    for candidate in candidates[:AI_REPLY_LIMIT]:
        fn, args = ai_resolve(g, candidate)
        if fn is None:
            continue
        after = ai_simulate(g, fn, *args)
        if after is None:
            continue
        delta = ai_material(after, me, P) - base
        gain = delta if side == me else -delta
        if gain > best:
            best, best_state = gain, after
    return best, best_state


def ai_exchange(state, me, P, plies, near=None):
    """Attaques alternées (meilleure de chaque camp) : bilan vu par « me »."""
    total = 0.0
    for _ in range(plies):
        if state.get("winner") is not None or state.get("phase") != "move":
            break
        side = state["active"]
        gain, after = ai_best_attack(state, side, me, P, near)
        if after is None:
            other = 1 - side
            if other in state.get("passed", []):
                break
            state = dict(state, active=other)
            state.pop("moving_unit_id", None)
            continue
        total += gain if side == me else -gain
        state = after
    return total


# Budget de réflexion par tour de l'IA : au-delà, elle joue sans anticiper
# (la page ne doit jamais rester figée).
AI_TURN_BUDGET = 6.0
_AI_DEADLINE = [0.0]


def ai_anticipate(g, me, options, P):
    """Corrige les meilleurs coups par les ripostes adverses à venir."""
    plies, top = P["replies"], P["top"]
    if not plies or not top or (1 - me) in g.get("passed", []):
        return options
    if _AI_DEADLINE[0] and time.time() > _AI_DEADLINE[0]:
        return options
    now = ai_clone(g)
    now["active"] = 1 - me
    now.pop("moving_unit_id", None)
    before = {e["id"]: (tuple(e["pos"]), float(e["pf"])) for e in g["entities"]}
    checked = []
    for gain, after, move in options[:top]:
        if after is None:
            after = ai_simulate(g, move_unit, *move)
            if after is None:
                continue
        # Zone du coup : cases des pièces déplacées, blessées ou détruites.
        near = set()
        after_ids = set()
        for e in after["entities"]:
            after_ids.add(e["id"])
            old = before.get(e["id"])
            if old is None or old != (tuple(e["pos"]), float(e["pf"])):
                near.add(tuple(e["pos"]))
                if old is not None:
                    near.add(old[0])
        near.update(pos for eid, (pos, _) in before.items() if eid not in after_ids)
        if not near:
            checked.append((gain, after, move))
            continue
        baseline = ai_exchange(now, me, P, plies, near)
        future = ai_exchange(after, me, P, plies, near)
        weight = P.get("anticipate_weight", AI_ANTICIPATE_WEIGHT)
        checked.append((gain + weight * (future - baseline), after, move))
    checked.sort(key=lambda item: -item[0])
    return checked + options[top:]


def ai_move_step(bundle, me, level):
    """Une activation de l'IA pendant les manœuvres."""
    g = bundle["game"]
    P = ai_params(level)
    ctx = ai_context(g, me, P)
    material = ai_material(g, me, P)
    placed = {
        u["id"]: (tuple(u["pos"]), float(u["pf"]), ai_place_score(ctx, u, tuple(u["pos"])))
        for u in g["entities"]
        if u["owner"] == me and u["kind"] == "unit" and u["name"] != WORKER
    }

    def gain_of(after):
        """Bilan matériel + position des seules unités qui ont changé."""
        gain = ai_material(after, me, P) - material
        seen = set()
        for u in after["entities"]:
            if u["owner"] != me or u["kind"] != "unit" or u["name"] == WORKER:
                continue
            seen.add(u["id"])
            old = placed.get(u["id"])
            if old is None:
                gain += ai_place_score(ctx, u, tuple(u["pos"]))
            elif tuple(u["pos"]) != old[0] or float(u["pf"]) != old[1]:
                gain += ai_place_score(ctx, u, tuple(u["pos"])) - old[2]
        for uid, (_, _, value) in placed.items():
            if uid not in seen:
                gain -= value
        return gain

    attacks = ai_attack_candidates(g, me, P["groups"])
    # Les cibles les plus précieuses d'abord (bases, grosses unités), attaques
    # groupées comprises ; au-delà de la limite, on ne simule pas.
    attacks.sort(key=lambda c: (
        -(ai_piece_value(g, c[2]) if c[2] is not None else 0),
        len(c[1][0]) if c[0] == "melee" else 1,
    ))
    options = []  # (gain, état simulé ou None, déplacement)
    for candidate in attacks[:AI_ATTACK_LIMIT] + ai_special_candidates(g):
        fn, args = ai_resolve(g, candidate)
        if fn is None:
            continue
        after = ai_simulate(g, fn, *args)
        if after is None:
            continue
        # Prime à l'attaque (niveau agressif) : frapper plutôt que se replacer.
        gain = gain_of(after) + P.get("attack_drive", 0.0)
        if P.get("first_attack") and gain > 0:
            # Débutant : il prend la première attaque gagnante, sans comparer.
            bundle["game"] = ai_restore_log(g, after)
            return True
        options.append((gain, after, None))
    for gain, unit_id, pos in ai_move_candidates(g, me, ctx):
        options.append((gain, None, (unit_id, pos)))

    options.sort(key=lambda item: -item[0])
    options = ai_anticipate(g, me, options, P)
    for gain, after, move in options[:AI_TRIES]:
        if gain <= 0:
            break
        if after is None:
            after = ai_simulate(g, move_unit, *move)
            if after is None:
                continue
        bundle["game"] = ai_restore_log(g, after)
        return True

    # Rien d'utile : terminer l'activation de l'unité en cours, sinon passer.
    moving = g.get("moving_unit_id")
    for fn, args in (((finish_unit_activation, (moving,)),) if moving is not None else ()) + ((pass_turn, ()),):
        after = ai_simulate(g, fn, *args)
        if after is not None:
            bundle["game"] = ai_restore_log(g, after)
            return True
    return False


# ------------------------------------------------------------
# Production : choix des unités, bâtiments, améliorations
# ------------------------------------------------------------

AI_UPGRADE_UNITS = {
    "2 pattes en plus": ("Déferlant",),
    "Dents acérées": ("Déferlant",),
    "Dents acérées volants": ("Volant",),
    "Instinct elfique": ("Elfe",),
    "Développement musculaire": ("Mammouth dompté",),
    "Meute de tigres": ("Tigre des forêts",),
    "Marteau foudroyant": ("Guerrier",),
    "Esquive": ("Éclaireur",),
    "Flèches enflammées": ("Archer",),
    "Pierres enflammées": ("Catapulte", "Catapulte de l'enfer"),
    "Invisibilité griffons": ("Griffon",),
    "Mutation imminente": ("Agile",),
    "Endurance": ("Barbare",),
}
# Mécaniques que l'IA n'exploite pas.
AI_MINOR_UPGRADES = {"Mutation kamikaze", "Rampants", "Trébuchet", "Aramil le sorcier élu", "Solidarité"}
# Production des héros vagabonds : indispensables.
AI_PRIORITY_UPGRADES = ["Étroite communication I", "Multitâches", "Étroite communication II"]
AI_DECISIVE = 2000


def ai_enemy_home(g, me):
    pieces = [tuple(e["pos"]) for e in g["entities"] if e["owner"] != me and e["kind"] == "base"]
    if not pieces:
        pieces = [tuple(e["pos"]) for e in g["entities"] if e["owner"] != me] or [CELLS[len(CELLS) // 2]]
    return min(pieces, key=lambda p: (sum(distance(p, q) for q in pieces), p))


def ai_free_cells_near(g, origin, low, high):
    return [
        p for p in CELLS
        if low <= distance(origin, p) <= high
        and at(g, p) is None
        and not blocked(g, p)
        and key(p) not in g["resources"]
    ]


AI_VAGABOND_UPGRADES = {
    "Étroite communication I": 2600,
    "Mutation imminente": 2300,
    "Endurance": 2250,
    "Solidarité": 2100,
}


def ai_upgrade_value(g, me, name):
    """Intérêt d'une amélioration selon la partie en cours."""
    if is_vagabond(g, me) and (name in AI_VAGABOND_UPGRADES or name in VAG_AGE_UPGRADES.values()):
        # Les améliorations font toute la force des Vagabonds : toutes, au plus tôt.
        if name == "Étroite communication I" and owns_upgrade(g, me, "Étroite communication II"):
            return 0
        if VAG_AGE_UPGRADES.get(g["players"][me]["age"] + 1) == name:
            return 3000
        return AI_VAGABOND_UPGRADES.get(name, 2400)
    if name in VAG_AGE_UPGRADES.values():
        # Obligatoire pour l'âge suivant : décisive ; sinon très utile.
        age = g["players"][me]["age"]
        return 3000 if VAG_AGE_UPGRADES.get(age + 1) == name else 1200
    if name == "Étroite communication I":
        # Inutile une fois la version II achetée.
        return 0 if owns_upgrade(g, me, "Étroite communication II") else 1500
    if name in AI_MINOR_UPGRADES:
        return 60
    mine = [e for e in g["entities"] if e["owner"] == me and e["kind"] == "unit"]
    enemies = [e for e in ai_enemy_pieces(g, me) if e["kind"] == "unit"]
    concerned = AI_UPGRADE_UNITS.get(name, ())
    owned = sum(e["name"] in concerned for e in mine)
    producible = any(
        n in concerned
        for data in faction_of(g, me)["buildings"].values()
        for n in data.get("units", [])
    )
    value = 150 + 130 * owned + (120 if producible else 0)
    if name == "Meute de tigres":
        # Contre une marée d'unités d'âge I (ex. 10 Déferlants) : les Tigres piétinent.
        weak = sum(UNIT_AGES.get(e["name"], 1) == 1 for e in enemies)
        swarm = sum(e["name"] == "Déferlant" for e in enemies)
        value += 70 * weak + (2500 if swarm >= 10 or weak >= 12 else 0)
    elif name == "Vengeance":
        value += 25 * len(enemies)
    elif name in PF_UPGRADES or name in ATTACK_UPGRADES:
        value += 80 * owned
    return value


def ai_boosted_units(g, me):
    return {
        unit for name, units in AI_UPGRADE_UNITS.items()
        if owns_upgrade(g, me, name) for unit in units
    }


def ai_unit_score(g, me, name, P, want_mana, boosted):
    data = UNITS[name]
    strength = data["pf"] * (1.3 if data["range"] else 1.0) + 0.1 * data["move"]
    if name in AI_WEAK_UNITS or name in NO_ATTACK_UNITS:
        strength *= 0.35
    price = data["cost"] / max(1, data["batch"]) + 150 * data["mana"]
    efficiency = strength / max(price, 50) * 1000
    rule = P["unit_rule"]
    if rule == "cheap":
        score = 10000 / max(price, 50)
    elif rule == "value":
        score = efficiency
    elif rule == "balanced":
        score = efficiency + 6 * strength
    else:
        # Expert : unités de son âge d'abord, les plus fortes en tête.
        tier = min(UNIT_AGES.get(name, 1), g["players"][me]["age"])
        score = 100 * tier + 10 * strength
    if name in boosted:
        score *= 1.3
    if want_mana and data["mana"] and name not in AI_WEAK_UNITS and name not in NO_ATTACK_UNITS:
        # Mana en trop : les unités de combat qui en consomment passent devant.
        score = score * 1.6 + 400 * data["mana"]
    return score


def ai_recruit_options(g, me, producer):
    faction = faction_of(g, me)
    if is_hero(producer):
        return [n for n in VAG_SLOTS if hero_can_produce(g, producer, n)]
    if producer["kind"] == "base":
        return []
    return [
        n for n in faction["buildings"].get(producer["name"], {}).get("units", [])
        if n in UNITS and n != WORKER
    ]


def ai_recruit_positions(g, me, producer, count):
    enemy = ai_enemy_home(g, me)
    g["_recruit_batch"] = count
    try:
        cells = list(recruitment_slots(g, producer))
    except TypeError:
        cells = list(recruitment_slots(g, producer, count))
    finally:
        g.pop("_recruit_batch", None)
    cells.sort(key=lambda p: (distance(p, enemy), p))
    return cells


def ai_producers(g, me):
    producers = [
        e for e in g["entities"]
        if e["owner"] == me and (e["kind"] == "building" or is_hero(e)) and not e["wait"]
    ]
    producers.sort(key=lambda e: (-BUILDING_AGES.get((faction_id(g, me), e["name"]), 1), e["id"]))
    return producers


def ai_within(g, me, floors):
    return ai_gold(g, me) >= floors[0] and ai_mana(g, me) >= floors[1]


def ai_step_recruit(g, me, P, floors, want_mana):
    """Chaque producteur prêt recrute sa meilleure unité abordable."""
    boosted = ai_boosted_units(g, me)
    for producer in ai_producers(g, me):
        current = next((e for e in g["entities"] if e["id"] == producer["id"]), None)
        if current is None or (current.get("used") and not is_hero(current)):
            continue
        names = sorted(
            ai_recruit_options(g, me, current),
            key=lambda n: (-ai_unit_score(g, me, n, P, want_mana, boosted), n),
        )
        for name in names:
            data = UNITS[name]
            if data["cost"] > ai_gold(g, me) - floors[0] or data["mana"] > ai_mana(g, me) - floors[1]:
                continue
            batch = 1 if is_hero(current) else recruitment_batch(g, me, name)
            cells = ai_recruit_positions(g, me, current, batch)
            if len(cells) < batch:
                continue
            new = ai_try(g, recruit, me, current["id"], name, cells[:batch])
            if new is not None and ai_within(new, me, floors):
                g = new
                break
    return g


def ai_wanted_buildings(g, me, P, goal=None, want_mana=False):
    faction = faction_of(g, me)
    age = g["players"][me]["age"]
    wanted = []
    for name in (
        AGE_PREREQUISITES.get((faction_id(g, me), age + 1)),
        TECH_BUILDINGS.get(faction_id(g, me)),
    ):
        if name and building_is_available(g, me, name) and not any(
            e["owner"] == me and e["name"] == name for e in g["entities"]
        ):
            wanted.append(name)
    def buildable(data):
        """Unités que ce bâtiment peut produire maintenant."""
        return [
            n for n in data["units"]
            if n in UNITS and n != WORKER
            and UNIT_AGES.get(n, 1) <= age
            and UNIT_MAX_AGES.get(n, 9) >= age
            and unit_requirement_met(g, me, n)
        ]

    def grade(item):
        """(âge des unités produites, force, mana consommé) du bâtiment."""
        names = buildable(item[1])
        if not names:
            return (0, 0.0, 0)
        return (
            max(UNIT_AGES.get(n, 1) for n in names),
            max(UNITS[n]["pf"] * (1.3 if UNITS[n]["range"] else 1.0) for n in names),
            max(UNITS[n]["mana"] for n in names if n not in AI_WEAK_UNITS) if any(
                n not in AI_WEAK_UNITS for n in names
            ) else 0,
        )

    available = [
        (name, data) for name, data in faction["buildings"].items()
        if data.get("units") and building_is_available(g, me, name)
    ]
    if P.get("tier_buildings", True):
        producers = sorted(available, key=lambda item: (
            # Mana en trop : d'abord les bâtiments dont les unités en consomment.
            -(grade(item)[2] if want_mana else 0),
            -grade(item)[0],          # unités de l'âge le plus élevé
            -grade(item)[1],          # puis les plus fortes
            item[0],
        ))
    else:
        # Débutant : le moins cher d'abord, sans réfléchir à l'âge.
        producers = sorted(available, key=lambda item: (item[1]["cost"], item[0]))
    goal = goal or P["building_goal"]
    for name, data in producers:
        count = sum(e["owner"] == me and e["name"] == name for e in g["entities"])
        target = data["limit"] if goal == "limit" else min(data["limit"], goal)
        tier = grade((name, data))[0]
        if tier and tier < age and P.get("tier_buildings", True):
            # Bâtiment dépassé (ses unités sont d'un âge inférieur) : peu d'exemplaires.
            target = min(target, 2)
        if count < target:
            wanted.append(name)
    return list(dict.fromkeys(wanted))


def ai_build_sources(g, me):
    if faction_id(g, me) == DERNIERS_NES:
        workers = [
            e for e in g["entities"]
            if e["owner"] == me and e["name"] == WORKER and not e["wait"] and not e["used"]
        ]
        # Les ouvriers en trop construisent ; ceux qui récoltent, en dernier.
        spare = {w["id"] for w in ai_dn_spare_workers(g, me)}
        workers.sort(key=lambda w: (w["id"] not in spare, w["id"]))
        return workers
    return [
        e for e in g["entities"]
        if e["owner"] == me and e["kind"] == "base" and not is_hero(e) and not e["wait"]
        # Les Habitations des Exilés peuvent construire plusieurs fois par tour.
        and (not e["used"] or faction_id(g, me) == EXILES)
    ]


def ai_build_positions(g, me, source, name, P):
    if name == TECH_BUILDINGS.get(faction_id(g, me)) and me in TECH_CELLS:
        return [tech_cell(me)]
    enemy = ai_enemy_home(g, me)
    if source["name"] == WORKER:
        cells = worker_build_slots(g, source, name)
    else:
        cells = ai_free_cells_near(g, tuple(source["pos"]), 1, 4)
    origin = tuple(source["pos"])
    if P["front"]:
        # Vers le front (unités plus vite au combat), mais hors de portée immédiate.
        reach = [
            (tuple(e["pos"]), UNITS.get(e["name"], {}).get("move", 0) + max(1, UNITS.get(e["name"], {}).get("range", 0)))
            for e in ai_enemy_pieces(g, me) if e["kind"] == "unit"
        ]
        cells.sort(key=lambda p: (any(distance(p, w) <= r for w, r in reach), distance(p, enemy), distance(p, origin), p))
    else:
        # Débutant : à l'abri, derrière ses bases.
        cells.sort(key=lambda p: (-distance(p, enemy), distance(p, origin), p))
    return cells[:6]


AI_BUILDS_PER_TURN = 2   # chantiers par tour (hors colonies)
AI_KEEP_FOR_UNITS = 400  # or gardé pour recruter après un chantier


def ai_try_build(g, me, name, P, floors, accelerated=False, keep=0):
    # Caisse pleine : un chantier de plus (l'or doit servir à quelque chose).
    limit = AI_BUILDS_PER_TURN + (1 if ai_gold(g, me) - floors[0] >= 1500 else 0)
    if g.get("_ai_builds", 0) >= limit:
        return None
    for source in ai_build_sources(g, me):
        for pos in ai_build_positions(g, me, source, name, P):
            new = ai_try(g, build, me, source["id"], name, pos, accelerated)
            if new is None or not ai_within(new, me, floors):
                continue
            if keep and ai_gold(new, me) < floors[0] + keep:
                continue  # il doit rester de quoi produire des unités
            new["_ai_builds"] = new.get("_ai_builds", 0) + 1
            return new
    return None


def ai_step_buildings(g, me, P, floors, want_mana, accelerated=False):
    rich = P["fast_build_at"] is not None and ai_gold(g, me) - floors[0] >= P["fast_build_at"]
    for name in ai_wanted_buildings(g, me, P, goal="limit" if accelerated else None, want_mana=want_mana):
        new = None
        if accelerated or rich:
            new = ai_try_build(g, me, name, P, floors, accelerated=True, keep=AI_KEEP_FOR_UNITS)
        if new is None and not accelerated:
            new = ai_try_build(g, me, name, P, floors, keep=AI_KEEP_FOR_UNITS)
        if new is not None:
            g = new
    return g


def ai_step_key_buildings(g, me, P, floors, want_mana):
    """Un chantier clé par tour, avant le recrutement : un bâtiment qui produit
    les unités de l'âge atteint (ou qui consomme le mana qui s'accumule).
    Sinon l'or part en unités et ces bâtiments ne sortent jamais de terre."""
    if ai_level_name(P) == "debutant" or g.get("_ai_key_builds", 0) >= 1:
        return g
    faction = faction_of(g, me)
    age = g["players"][me]["age"]
    spare = ai_mana(g, me) - floors[1]

    def units_now(name):
        return [
            n for n in faction["buildings"].get(name, {}).get("units", ())
            if n in UNITS and n != WORKER and UNIT_AGES.get(n, 1) <= age
            and UNIT_MAX_AGES.get(n, 9) >= age and unit_requirement_met(g, me, n)
        ]

    # Mana que ses bâtiments peuvent déjà consommer en un tour.
    capacity = 0
    for producer in ai_producers(g, me):
        costs = [
            UNITS[n]["mana"] for n in ai_recruit_options(g, me, producer)
            if UNITS[n]["mana"] and n not in AI_WEAK_UNITS
        ]
        if costs:
            capacity += max(costs)
    mana_short = want_mana and spare >= 2 and capacity < spare

    for name in ai_wanted_buildings(g, me, P, goal="limit", want_mana=mana_short):
        names = units_now(name)
        if not names:
            continue
        tier = max(UNIT_AGES.get(n, 1) for n in names)
        uses_mana = any(UNITS[n]["mana"] and n not in AI_WEAK_UNITS for n in names)
        # Bâtiment du meilleur âge, ou capable d'écouler le mana en trop.
        if tier < age and not (mana_short and uses_mana):
            continue
        new = ai_try_build(g, me, name, P, floors, accelerated=True, keep=800)
        if new is None:
            new = ai_try_build(g, me, name, P, floors, keep=AI_KEEP_FOR_UNITS)
        if new is not None:
            new["_ai_key_builds"] = new.get("_ai_key_builds", 0) + 1
            return new
    return g


def ai_step_fast_buildings(g, me, P, floors, want_mana):
    """Or encore en trop : bâtiments accélérés (prêts tout de suite pour recruter)."""
    return ai_step_buildings(g, me, P, floors, want_mana, accelerated=True)


def ai_buy_upgrades(g, me, P, floors, minimum):
    names = sorted(available_upgrades(g, me), key=lambda n: (-ai_upgrade_value(g, me, n), n))
    for name in names:
        value = ai_upgrade_value(g, me, name)
        if value < minimum:
            break
        # Les améliorations décisives passent avant l'or gardé pour l'âge.
        limits = (0, 0) if value >= AI_DECISIVE else floors
        new = ai_try(g, purchase_upgrade, me, name)
        if new is not None and ai_within(new, me, limits):
            g = new
    return g


def ai_step_upgrades(g, me, P, floors, want_mana):
    return ai_buy_upgrades(g, me, P, floors, P["upgrade_min"])


def ai_has_mana_base(g, me):
    return any(
        g["resources"].get(key(q), ("", 0))[0] == "mana"
        for e in g["entities"] if e["owner"] == me and e["kind"] == "base" and not is_hero(e)
        for q in neighbors(tuple(e["pos"]))
    )


def ai_colony_value(g, p):
    # Le mana compte triple : il débloque l'âge III et les meilleures unités.
    return sum(
        (3 if g["resources"][key(q)][0] == "mana" else 1) * g["resources"][key(q)][1]
        for q in neighbors(p)
        if key(q) in g["resources"] and at(g, q) is None
    )


def ai_colony_positions(g, me, source):
    enemy = ai_enemy_home(g, me)
    bases = [tuple(e["pos"]) for e in g["entities"] if e["owner"] == me and e["kind"] == "base"]
    if source["name"] == WORKER:
        cells = worker_build_slots(g, source, faction_of(g, me)["base"])
    else:
        # Jusqu'à 8 cases de la base : les ressources éloignées comptent aussi.
        cells = ai_free_cells_near(g, tuple(source["pos"]), 2, 8)
    cells = [
        p for p in cells
        if ai_colony_value(g, p) >= AI_COLONY_MIN_VALUE
        and min((distance(p, b) for b in bases), default=9) >= 2
        and all(distance(p, q) > 3 for q in (tuple(e["pos"]) for e in ai_enemy_pieces(g, me) if e["kind"] == "base"))
    ]
    cells.sort(key=lambda p: (-ai_colony_value(g, p), -distance(p, enemy), p))
    return cells[:6]


def ai_near_mana(g, p):
    return any(g["resources"].get(key(q), ("", 0))[0] == "mana" for q in neighbors(p))


def ai_try_colony(g, me, floors, mana_only=False):
    if is_vagabond(g, me):
        return g
    bases = [e for e in g["entities"] if e["owner"] == me and e["kind"] == "base"]
    if len(bases) >= 7:
        return g
    name = faction_of(g, me)["base"]
    options = [
        (source, pos)
        for source in ai_build_sources(g, me)
        for pos in ai_colony_positions(g, me, source)
        if not mana_only or ai_near_mana(g, pos)
    ]
    options.sort(key=lambda item: (-ai_colony_value(g, item[1]), item[1]))
    for source, pos in options:
        new = ai_try(g, build, me, source["id"], name, pos, False)
        if new is not None and ai_within(new, me, floors):
            return new
    return g


def ai_dn_colony(g, me, floors):
    """Derniers nés : un ouvrier bâtisseur fonde une colonie sur une case riche."""
    bases = [tuple(e["pos"]) for e in g["entities"] if e["owner"] == me and e["kind"] == "base"]
    if len(bases) >= 7:
        return g
    enemy = [tuple(e["pos"]) for e in ai_enemy_pieces(g, me) if e["kind"] == "base"]
    sites = sorted(
        (
            p for p in CELLS
            if at(g, p) is None and not blocked(g, p) and key(p) not in g["resources"]
            and ai_colony_value(g, p) >= 2
            and min((distance(p, q) for q in bases), default=9) >= 2
            and all(distance(p, q) > 4 for q in enemy)
        ),
        key=lambda p: (-ai_colony_value(g, p), p),
    )[:12]
    busy = {w["id"] for w in g["entities"] if w["owner"] == me and w["name"] == WORKER} - {
        w["id"] for w in ai_dn_spare_workers(g, me)
    }
    g, worker = ai_worker_to_site(g, me, sites, reserved=busy)
    if worker is None:
        return g
    for pos in sorted(
        (p for p in sites if distance(p, tuple(worker["pos"])) == 1),
        key=lambda p: (-ai_colony_value(g, p), p),
    ):
        new = ai_try(g, build, me, worker["id"], faction_of(g, me)["base"], pos, False)
        if new is not None and ai_within(new, me, floors):
            return new
    return g


AI_COLONY_MIN_VALUE = 2


def ai_colonies_allowed(g, me, P):
    """Colonies fondées par tour : 2 en début de partie, 1 ensuite."""
    if ai_level_name(P) == "debutant":
        return 1
    return 2 if g["turn"] <= 6 else 1


def ai_step_colony(g, me, P, floors, want_mana):
    if not P["eco_colonies"]:
        # Débutant : il ne s'étend pas pour l'économie, juste de quoi
        # atteindre le mana (nécessaire à l'âge III).
        bases = sum(e["owner"] == me and e["kind"] == "base" for e in g["entities"])
        if ai_has_mana_base(g, me) or bases >= 5:
            return g
    built = g.get("_ai_colonies", 0)
    if built >= ai_colonies_allowed(g, me, P):
        return g
    if faction_id(g, me) == DERNIERS_NES:
        new = ai_dn_colony(g, me, floors)
    else:
        new = ai_try_colony(g, me, floors)
    if new is not g:
        new["_ai_colonies"] = built + 1
    return new


def ai_step_workers(g, me, P, floors, want_mana):
    """Derniers nés : de nouveaux ouvriers pour récolter et construire."""
    if faction_id(g, me) != DERNIERS_NES:
        return g
    bases = [e for e in g["entities"] if e["owner"] == me and e["kind"] == "base" and not e["wait"]]
    wanted = sum(ai_dn_slots(g, me).values()) + 2
    workers = worker_count(g, me)
    for base in bases:
        if workers >= wanted:
            break
        current = entity(g, base["id"])
        batch = worker_batch(g, current)
        if not batch or current["used"]:
            continue
        cells = sorted(worker_slots(g, current), key=lambda p: (key(p) not in g["resources"], p))
        if len(cells) < batch:
            continue
        new = ai_try(g, recruit, me, current["id"], WORKER, cells[:batch])
        if new is not None and ai_within(new, me, floors):
            g = new
            workers += batch
    return g


def ai_step_fusions(g, me, P, floors, want_mana):
    """Vagabonds : fusions d'esprits (unités plus fortes, consomment du mana)."""
    if not is_vagabond(g, me):
        return g
    for result, data in sorted(FUSIONS.items(), key=lambda item: (-item[1]["age"], item[0])):
        if data["age"] > g["players"][me]["age"]:
            continue
        pool = {}
        for e in g["entities"]:
            if e["owner"] == me and e["kind"] == "unit" and e["name"] in data["parts"] and not e["wait"]:
                pool.setdefault(e["name"], []).append(e)
        if any(len(pool.get(n, [])) < k for n, k in data["parts"].items()):
            continue
        ids = [u["id"] for n, k in data["parts"].items() for u in pool[n][:k]]
        first = entity(g, ids[0])
        for pos in [tuple(first["pos"])] + list(neighbors(tuple(first["pos"]))):
            new = ai_try(g, fuse_spirits, me, result, ids, pos)
            if new is not None and ai_within(new, me, floors):
                g = new
                break
    return g


# ------------------------------------------------------------
# Production : préparatifs (ouvriers, héros, chantiers clés, âge)
# ------------------------------------------------------------

def ai_dn_slots(g, me):
    """Derniers nés : {case: ouvriers utiles}. Chaque base récolte avec autant
    d'ouvriers que son niveau (Colonie 1, Ville 2, Forteresse 3), empilés sur
    sa meilleure case d'or et sa meilleure case de mana."""
    slots = {}
    for base in g["entities"]:
        if base["owner"] != me or base["kind"] != "base" or base["wait"]:
            continue
        level = BASE_LEVEL_DATA.get(base["name"], {"level": 1})["level"]
        for kind in ("gold", "mana"):
            cells = [
                p for p in neighbors(tuple(base["pos"]))
                if g["resources"].get(key(p), ("", 0))[0] == kind
                and not blocked(g, p)
                and all(e["owner"] == me and e["name"] == WORKER for e in pieces_at(g, p))
            ]
            if cells:
                best = max(cells, key=lambda p: (g["resources"][key(p)][1], p))
                slots[best] = max(slots.get(best, 0), min(level, WORKER_STACK))
    return slots


def ai_dn_present(g, me, pos):
    return sum(1 for e in pieces_at(g, pos) if e["owner"] == me and e["name"] == WORKER)


def ai_dn_spare_workers(g, me, slots=None):
    """Ouvriers libres qui ne remplissent pas un poste de récolte."""
    slots = ai_dn_slots(g, me) if slots is None else slots
    spare = []
    for worker in g["entities"]:
        if worker["owner"] != me or worker["name"] != WORKER or worker["wait"]:
            continue
        pos = tuple(worker["pos"])
        if ai_dn_present(g, me, pos) > slots.get(pos, 0):
            spare.append(worker)
    return spare


def ai_move_workers(g, me):
    """Derniers nés : les ouvriers en trop remplissent les postes de récolte."""
    if faction_id(g, me) != DERNIERS_NES:
        return g
    slots = ai_dn_slots(g, me)
    deficits = sorted(
        (pos for pos, need in slots.items() if ai_dn_present(g, me, pos) < need),
        key=lambda pos: (g["resources"][key(pos)][0] != "gold", -g["resources"][key(pos)][1], pos),
    )
    for pos in deficits:
        while ai_dn_present(g, me, pos) < slots[pos]:
            movers = [
                w for w in ai_dn_spare_workers(g, me, slots)
                if not w["used"] and pos in worker_destinations(g, w)
            ]
            if not movers:
                break
            worker = min(movers, key=lambda w: (distance(tuple(w["pos"]), pos), w["id"]))
            new = ai_try(g, move_worker, me, worker["id"], pos)
            if new is None:
                break
            g = new
    return g


def ai_marker_value(g, me, hero, cell, need_mana):
    """Récolte d'un héros dont le marqueur est sur cette case (en équivalent or)."""
    resource = g["resources"].get(key(tuple(cell))) if cell else None
    if resource is None:
        return 0.0
    kind, mult = resource
    _, _, _, gold, mana = hero_stats(g, hero)
    if kind == "gold":
        return float(gold * mult)
    return float(mana * mult * (300 if need_mana else 130))


def ai_hero_danger(g, me, pos):
    """PF ennemis capables d'atteindre cette case à la prochaine manœuvre."""
    return sum(
        float(e["pf"]) for e in ai_enemy_pieces(g, me)
        if e["kind"] == "unit" and e["name"] not in NO_ATTACK_UNITS
        and distance(pos, tuple(e["pos"])) <= UNITS.get(e["name"], {}).get("move", 0)
        + max(1, UNITS.get(e["name"], {}).get("range", 0))
    )


def ai_hero_safe(g, me, hero, pos):
    """Un héros détruit compte comme une base perdue : éviter les cases menacées."""
    return ai_hero_danger(g, me, pos) < float(hero["pf"])


def ai_move_heroes(g, me, careful=False):
    """Vagabonds : chaque héros vise la case d'or ou de mana la plus rentable
    (×2, ×3 en priorité) ; trop loin, il s'en approche tour après tour.

    careful (Intermédiaire, Expert) : le marqueur garde la DERNIÈRE case de
    ressource traversée, et c'est elle qui est récoltée. Le héros n'a donc pas
    besoin de rester dessus : menacé, il traverse la ressource (ou la garde
    comme marqueur) et s'arrête à l'abri, sans rien perdre de sa récolte."""
    if not is_vagabond(g, me):
        return g
    # Mana rare (âges, unités fortes) ou or qui s'entasse : le mana vaut plus.
    need_mana = g["players"][me]["age"] < 3 or ai_mana(g, me) < 6 or ai_gold(g, me) > 1500
    heroes = sorted(
        (e for e in g["entities"] if e["owner"] == me and is_hero(e)),
        key=lambda h: (-hero_stats(g, h)[3], h["id"]),
    )
    taken = {}
    for h in heroes:
        if h.get("marker"):
            taken.setdefault(key(tuple(h["marker"])), h["id"])
    cells = [tuple(int(x) for x in k.split(",")) for k in g["resources"]]
    enemy_bases = [
        tuple(e["pos"]) for e in ai_enemy_pieces(g, me) if e["kind"] == "base"
    ]
    claimed = set()

    for hero in heroes:
        current = entity(g, hero["id"])
        options = hero_destinations(g, current)
        if not options:
            continue
        mine_key = key(tuple(current["marker"])) if current.get("marker") else None
        if mine_key and taken.get(mine_key) not in (None, current["id"]):
            mine_key = None  # marqueur partagé : il ne rapporte rien
        others = {k for k, hid in taken.items() if hid != current["id"]}

        def value_of(cell):
            if cell is None or key(tuple(cell)) in others:
                return 0.0
            return ai_marker_value(g, me, current, cell, need_mana)

        here_value = value_of(current.get("marker")) if mine_key else 0.0
        _, routes = hero_paths(g, current)

        def after_move(p):
            crossed = [q for q in routes.get(p, [])[1:] if key(q) in g["resources"]]
            return crossed[-1] if crossed else current.get("marker")

        safe = [p for p in sorted(options) if ai_hero_safe(g, me, current, p)]
        here = tuple(current["pos"])
        if careful:
            danger = {p: ai_hero_danger(g, me, p) for p in list(options) + [here]}

            def exposed(p):
                # Case de ressource menacée : à éviter même si le héros y survit.
                return danger[p] > 0 and key(p) in g["resources"]

            rank = lambda p: (value_of(after_move(p)), not exposed(p), -danger[p], -distance(p, here))
        else:
            rank = lambda p: (value_of(after_move(p)), -distance(p, here))
        best = max(safe, key=rank, default=None)
        target = None
        if careful and best is not None and (
            not ai_hero_safe(g, me, current, here)
            or (exposed(here) and value_of(after_move(best)) >= here_value)
        ):
            # En danger de mort : il fuit (un héros perdu vaut une base).
            # Seulement exposé sur sa ressource : il se met à l'abri en gardant
            # au moins la même récolte.
            target = best
        elif best is not None and value_of(after_move(best)) > 1.15 * here_value:
            target = best
        else:
            # Une case bien plus riche, à 2 tours de marche au plus, loin des
            # bases ennemies et pas déjà visée par un autre héros : s'en approcher
            # sans perdre la valeur du marqueur actuel.
            reach = 2 * hero_stats(g, current)[1] + 1
            here = tuple(current["pos"])
            richer = [
                c for c in cells
                if value_of(c) >= 1.5 * max(here_value, 1.0)
                and key(c) not in claimed
                and distance(here, c) <= reach
                and all(distance(c, b) > 3 for b in enemy_bases)
            ]
            if richer and safe:
                goal = min(richer, key=lambda c: (-value_of(c), distance(here, c), c))
                step = min(
                    (p for p in safe if value_of(after_move(p)) >= here_value),
                    key=lambda p: (distance(p, goal), p),
                    default=None,
                )
                if step is not None and distance(step, goal) < distance(here, goal):
                    target = step
                    claimed.add(key(goal))
        if target is None:
            continue
        new = ai_try(g, move_hero, me, current["id"], target)
        if new is None:
            continue
        g = new
        moved = entity(g, hero["id"])
        for k, hid in list(taken.items()):
            if hid == hero["id"]:
                del taken[k]
        if moved.get("marker"):
            taken.setdefault(key(tuple(moved["marker"])), hero["id"])
    return g


def ai_worker_to_site(g, me, sites, reserved=()):
    """Envoie un ouvrier libre à côté d'une des cases « sites » ; renvoie (état, ouvrier prêt)."""
    sites = [p for p in sites if at(g, p) is None]
    if not sites:
        return g, None
    workers = [
        e for e in g["entities"]
        if e["owner"] == me and e["name"] == WORKER and not e["wait"] and not e["used"]
        and e["id"] not in reserved
    ]
    for worker in workers:
        if any(distance(tuple(worker["pos"]), p) == 1 for p in sites):
            return g, worker
    workers.sort(key=lambda w: (
        key(tuple(w["pos"])) in g["resources"],
        min(distance(tuple(w["pos"]), p) for p in sites),
        w["id"],
    ))
    for worker in workers[:2]:
        options = list(worker_destinations(g, worker))
        if not options:
            continue
        best = min(options, key=lambda p: (min(abs(distance(p, q) - 1) for q in sites), p))
        new = ai_try(g, move_worker, me, worker["id"], best)
        if new is not None:
            moved = entity(new, worker["id"])
            ready = any(distance(tuple(moved["pos"]), p) == 1 for p in sites)
            return new, (moved if ready else None)
    return g, None


def ai_mana_sites(g, me):
    bases = [tuple(e["pos"]) for e in g["entities"] if e["owner"] == me and e["kind"] == "base"]
    return [
        p for k, v in g["resources"].items() if v[0] == "mana"
        for p in neighbors(tuple(int(x) for x in k.split(",")))
        if valid_position(p) and at(g, p) is None and not blocked(g, p)
        and key(p) not in g["resources"]
        and min((distance(p, b) for b in bases), default=9) >= 2
    ]


def ai_key_constructions(g, me, P, floors=(0, 0)):
    """Avant les dépenses : colonie au bord du mana, prérequis d'âge, bâtiment technique."""
    faction = faction_of(g, me)
    dn = faction_id(g, me) == DERNIERS_NES
    used = set()
    if not is_vagabond(g, me) and not ai_has_mana_base(g, me):
        if dn:
            sites = ai_mana_sites(g, me)
            g, worker = ai_worker_to_site(g, me, sites)
            if worker is not None:
                used.add(worker["id"])
                for pos in sorted(
                    (p for p in sites if distance(p, tuple(worker["pos"])) == 1),
                    key=lambda p: (-ai_colony_value(g, p), p),
                ):
                    new = ai_try(g, build, me, worker["id"], faction["base"], pos, False)
                    if new is not None and ai_within(new, me, floors):
                        g = new
                        break
        elif g["turn"] >= 2:
            g = ai_try_colony(g, me, floors, mana_only=True)
    age = g["players"][me]["age"]
    for name in (
        AGE_PREREQUISITES.get((faction_id(g, me), age + 1)),
        TECH_BUILDINGS.get(faction_id(g, me)),
    ):
        if not name or not building_is_available(g, me, name) or any(
            e["owner"] == me and e["name"] == name for e in g["entities"]
        ):
            continue
        if dn and name == TECH_BUILDINGS.get(DERNIERS_NES) and me in TECH_CELLS:
            cell = tech_cell(me)
            g, worker = ai_worker_to_site(g, me, [cell], reserved=used)
            if worker is not None:
                new = ai_try(g, build, me, worker["id"], name, cell, False)
                if new is not None and ai_within(new, me, floors):
                    g = new
                    used.add(worker["id"])
            continue
        new = ai_try_build(g, me, name, P, floors)
        if new is not None:
            g = new
    return g


def ai_next_age_cost(g, me):
    age = g["players"][me]["age"]
    if age >= 3:
        return None
    gold, mana = AGE_COSTS[age + 1]["gold"], AGE_COSTS[age + 1]["mana"]
    if is_vagabond(g, me):
        needed = VAG_AGE_UPGRADES.get(age + 1)
        if needed and not owns_upgrade(g, me, needed):
            gold += UPGRADES[needed]["cost"]
            mana += UPGRADES[needed]["mana"]
    return gold, mana


AI_VAGABOND_AGE_II = {"debutant": 3, "intermediaire": 2, "expert": 2, "sanguinaire": 2}


def ai_level_name(P):
    return next((lvl for lvl, params in AI_PARAMS.items() if params is P), "intermediaire")


def ai_age_from(g, me, P):
    """Tour à partir duquel l'âge suivant est visé."""
    age = g["players"][me]["age"]
    turn = P["age_from"].get(age + 1, 99)
    if is_vagabond(g, me) and age == 1:
        # Les Vagabonds grandissent vite : âge II au plus tard au tour 3.
        turn = min(turn, AI_VAGABOND_AGE_II[ai_level_name(P)])
    return turn


def ai_age_due(g, me, P):
    """L'âge suivant est visé (tour atteint, prérequis construits)."""
    age = g["players"][me]["age"]
    if age >= 3 or g["turn"] < ai_age_from(g, me, P):
        return False
    needed = AGE_PREREQUISITES.get((faction_id(g, me), age + 1))
    return not needed or building_is_completed(g, me, needed)


def ai_try_age(g, me):
    """Passe à l'âge suivant ; l'amélioration obligatoire des Vagabonds est
    achetée dès que possible, même si l'âge ne se paie qu'au tour suivant."""
    age = g["players"][me]["age"]
    if is_vagabond(g, me):
        needed = VAG_AGE_UPGRADES.get(age + 1)
        if needed and not owns_upgrade(g, me, needed):
            new = ai_try(g, purchase_upgrade, me, needed)
            if new is None:
                return g
            g = new
    return ai_try(g, advance_age, me, age + 1) or g


def ai_expected_income(g, me):
    """Or et mana que la prochaine récolte rapportera."""
    clone = ai_clone(g)
    before = (ai_gold(clone, me), ai_mana(clone, me))
    try:
        harvest(clone)
    except AI_ERRORS:
        return 0, 0
    return ai_gold(clone, me) - before[0], ai_mana(clone, me) - before[1]


def ai_age_floors(g, me, P):
    """Ressources gardées pour l'âge suivant : seulement ce que la récolte ne couvrira pas."""
    vagabond_rush = is_vagabond(g, me) and g["players"][me]["age"] == 1
    if not (P["save_for_age"] or vagabond_rush) or not ai_age_due(g, me, P):
        return 0, 0
    gold_cost, mana_cost = ai_next_age_cost(g, me)
    income_gold, income_mana = ai_expected_income(g, me)
    if ai_mana(g, me) + income_mana < mana_cost:
        # Le mana manque encore : on le garde, mais l'or est dépensé.
        return 0, min(ai_mana(g, me), mana_cost)
    return (
        max(0, min(ai_gold(g, me), gold_cost - income_gold)),
        max(0, min(ai_mana(g, me), mana_cost - income_mana)),
    )


def ai_under_threat(g, me, P):
    """Danger immédiat : armée bien plus faible et ennemis à un tour de ses bases."""
    if not P["defend"]:
        return False
    age = g["players"][me]["age"]
    if age < 3 and g["turn"] >= ai_age_from(g, me, P) + 3:
        return False  # l'âge suivant ne peut plus attendre
    bases = {tuple(e["pos"]): 0 for e in g["entities"] if e["owner"] == me and e["kind"] == "base"}
    if not bases:
        return False
    home = ai_distance_map(g, bases)
    fighters = [
        e for e in ai_enemy_pieces(g, me)
        if e["kind"] == "unit" and e["name"] not in NO_ATTACK_UNITS
    ]
    close = [
        e for e in fighters
        if home.get(tuple(e["pos"]), 99) <= UNITS.get(e["name"], {}).get("move", 3) + 2
    ]
    if not close:
        return False
    mine = sum(
        ai_unit_value(e) for e in g["entities"]
        if e["owner"] == me and e["kind"] == "unit" and e["name"] != WORKER
    )
    return mine < 0.6 * sum(ai_unit_value(e) for e in fighters)


def ai_production(draft, me, level):
    """Production complète de l'IA dans son brouillon privé."""
    P = ai_params(level)
    g = draft
    g["_ai_colonies"] = 0
    g["_ai_key_builds"] = 0
    g["_ai_builds"] = 0
    start_gold, start_mana = ai_gold(g, me), ai_mana(g, me)

    g = ai_move_workers(g, me)
    g = ai_move_heroes(g, me, careful=ai_level_name(P) != "debutant")
    urgent = False
    if P["decisive_upgrades"] or is_vagabond(g, me):
        # Améliorations décisives : contre-mesures (ex. Meute de tigres face à
        # 10 Déferlants) et, pour les Vagabonds, toutes leurs améliorations.
        owned = set(g["players"][me].get("upgrades", []))
        g = ai_buy_upgrades(g, me, P, (0, 0), AI_DECISIVE)
        bought = set(g["players"][me].get("upgrades", [])) - owned
        urgent = any(
            n not in AI_VAGABOND_UPGRADES and n not in VAG_AGE_UPGRADES.values() for n in bought
        )
    # Armée nettement plus faible et ennemis qui approchent : les unités
    # passent avant le changement d'âge (Intermédiaire et Expert).
    threatened = ai_under_threat(g, me, P)
    if ai_age_due(g, me, P) and not threatened:
        g = ai_try_age(g, me)
    floors = (0, 0) if threatened else ai_age_floors(g, me, P)
    if urgent or threatened:
        # Contre-mesure achetée ou danger : les unités avant les chantiers.
        g = ai_step_recruit(g, me, P, floors, ai_mana(g, me) > 0)
    if faction_id(g, me) == DERNIERS_NES:
        # Les ouvriers font tout le revenu : les postes de récolte d'abord.
        g = ai_step_workers(g, me, P, floors, False)
        g = ai_move_workers(g, me)
    g = ai_key_constructions(g, me, P, floors)
    goal_gold = max(floors[0], (1 - P["spend"]) * start_gold)
    goal_mana = max(floors[1], (1 - P["spend"]) * start_mana)
    steps = (
        # Une colonie sur l'or ou le mana (elle paie la suite), de quoi dépenser
        # le mana, puis toute la production militaire.
        # Un chantier clé et une colonie (ils paient la suite), puis toute
        # la production militaire avec le reste.
        ai_step_key_buildings, ai_step_colony, ai_step_recruit, ai_step_workers,
        ai_step_buildings, ai_step_upgrades, ai_step_fusions, ai_step_fast_buildings,
    )
    for _ in range(8):
        progress = False
        for step in steps:
            gold_over = ai_gold(g, me) > goal_gold
            mana_over = ai_mana(g, me) > goal_mana
            if not (gold_over or mana_over):
                return g
            new = step(g, me, P, floors, mana_over)
            if new is not g:
                g, progress = new, True
        if not progress:
            break
    g.pop("_ai_colonies", None)
    g.pop("_ai_key_builds", None)
    g.pop("_ai_builds", None)
    return g


def ai_build_phase(bundle, me, level):
    g = bundle["game"]
    ensure_draft(bundle)
    draft = bundle["draft"]
    draft["remaining"] = g["remaining"]
    draft["tick"] = g["tick"]
    draft["active"] = g["active"]
    try:
        bundle["draft"] = ai_production(draft, me, level)
    except Exception:
        bundle["draft"] = draft
    try:
        commit_plan(bundle)
    except ValueError:
        # Plan impossible à fusionner : l'IA valide une production vide.
        bundle["draft"] = None
        ensure_draft(bundle)
        commit_plan(bundle)


# ------------------------------------------------------------
# Pilotage d'un tour complet
# ------------------------------------------------------------

def ai_config(bundle):
    config = bundle.get("ai") if isinstance(bundle, dict) else None
    if not isinstance(config, dict) or config.get("seat") not in (0, 1):
        return None
    return config


def ai_take_turn(bundle):
    """Fait jouer l'IA jusqu'à ce que ce soit au joueur humain."""
    config = ai_config(bundle)
    if config is None:
        return False
    me, level = config["seat"], config.get("level", "intermediaire")
    played = False
    _AI_DEADLINE[0] = time.time() + AI_TURN_BUDGET
    for _ in range(AI_MAX_STEPS):
        g = bundle["game"]
        if g["winner"] is not None or g["active"] != me:
            break
        g["curtain"] = False
        signature = (g["turn"], g["phase"], g["active"], len(g["log"]), g.get("moving_unit_id"))
        if g["phase"] == "build":
            if me in g.get("ready", []):
                break
            ai_build_phase(bundle, me, level)
        elif g["phase"] == "move":
            if not ai_move_step(bundle, me, level):
                break
        else:
            break
        played = True
        check_victory(bundle["game"])
        after = bundle["game"]
        if (after["turn"], after["phase"], after["active"], len(after["log"]), after.get("moving_unit_id")) == signature:
            break  # plus rien ne bouge : on rend la main
    return played


def ai_force_pass(bundle):
    """Secours : l'IA termine proprement sa phase."""
    g = bundle["game"]
    if g["phase"] == "move":
        game_action(bundle, pass_turn)
    elif g["phase"] == "build":
        bundle["draft"] = None
        ensure_draft(bundle)
        commit_plan(bundle)


# ------------------------------------------------------------
# Interface : partie contre l'IA
# ------------------------------------------------------------

def ai_label(bundle):
    config = ai_config(bundle)
    if config is None:
        return ""
    g = bundle["game"]
    return f"{AI_LEVELS.get(config.get('level'), 'IA')} · {faction_of(g, config['seat'])['name']}"


def ai_autoplay():
    """Avant l'affichage : si c'est à l'IA, elle joue jusqu'au tour du joueur."""
    bundle = st.session_state.get("bundle")
    config = ai_config(bundle)
    if config is None or not isinstance(bundle.get("game"), dict):
        return
    g = bundle["game"]
    tick(g)
    if g["winner"] is not None or g["active"] != config["seat"]:
        return

    candidate = copy.deepcopy(bundle)
    start = len(candidate["game"]["log"])
    problem = None
    try:
        ai_take_turn(candidate)
    except Exception as exc:  # l'IA ne doit jamais bloquer la partie
        problem = exc
        candidate = copy.deepcopy(bundle)
        try:
            ai_force_pass(candidate)
        except Exception:
            return

    game = candidate["game"]
    report = game.pop("_combat_report", None)
    game.pop("_ui_message", None)
    game["curtain"] = False
    if report is not None:
        st.session_state.ui_combat_report = report

    name = faction_of(game, config["seat"])["name"]
    lines = [line for line in game["log"][start:] if "passe pour le reste" not in line]
    st.session_state.ai_last_actions = lines[-40:]
    if problem is not None:
        st.session_state.ui_message = f"🤖 L'IA a rencontré un problème ({problem}) : elle passe."
    elif lines:
        shown = [line.split(" — ", 1)[-1] for line in lines[-6:]]
        st.session_state.ui_message = (
            f"🤖 {name} (IA) a joué :\n\n" + "\n".join(f"- {line}" for line in shown)
        )
    st.session_state.bundle = candidate
    bump_ui(clear_selection=True)


_lw_ai_previous_main = main


def main():
    if not st.query_params.get("room"):
        init_ui()
        ai_autoplay()
    _lw_ai_previous_main()


_lw_ai_previous_render_sidebar = render_sidebar


def render_sidebar(bundle):
    if ai_config(bundle) is not None:
        with st.sidebar:
            st.markdown(f"**🤖 Adversaire : IA** — {ai_label(bundle)}")
            lines = st.session_state.get("ai_last_actions") or []
            if lines:
                with st.expander("Derniers coups de l'IA"):
                    st.markdown("\n".join(f"- {line}" for line in lines[-15:]))
    _lw_ai_previous_render_sidebar(bundle)


_lw_ai_previous_render_home = render_home


def render_home():
    with st.container(border=True):
        st.markdown("### 🤖 Jouer contre l'IA")
        st.caption("L'ordinateur joue l'autre faction, en respectant toutes les règles.")
        faction_ids = list(FACTIONS)
        mine_col, ai_col = st.columns(2)
        with mine_col:
            mine = st.selectbox(
                "Ta faction", faction_ids, index=faction_ids.index(EXILES),
                format_func=lambda fid: FACTIONS[fid]["name"], key="ai_home_mine",
            )
        with ai_col:
            theirs = st.selectbox(
                "Faction de l'IA", faction_ids, index=faction_ids.index(DEFERLANTS),
                format_func=lambda fid: FACTIONS[fid]["name"], key="ai_home_theirs",
            )
        level = st.radio(
            "Niveau de l'IA", list(AI_LEVELS), index=1, horizontal=True,
            format_func=AI_LEVELS.get, key="ai_home_level",
        )
        st.caption(AI_LEVEL_TEXT[level])
        first_col, mode_col = st.columns(2)
        with first_col:
            human_first = st.radio(
                "Qui commence ?", [True, False], horizontal=True,
                format_func=lambda v: "Moi" if v else "L'IA", key="ai_home_first",
            )
        with mode_col:
            mode = st.radio(
                "Victoire", list(VICTORY_MODES), index=list(VICTORY_MODES).index("bases"),
                format_func=lambda m: VICTORY_MODES[m].split(" — ")[0], key="ai_home_mode",
            )
        minutes = 0
        if mode == "time":
            minutes = st.number_input("Durée en minutes", 5, 180, 60, 1, key="ai_home_minutes")
        same = mine == theirs
        if same:
            st.error("Choisis deux factions différentes.")
        if st.button("⚔️ Lancer la partie contre l'IA", type="primary", disabled=same, key="ai_home_start"):
            # L'IA joue en haut du plateau (siège 0), toi en bas (siège 1).
            bundle = new_bundle(1 if human_first else 0, 0, int(minutes), mode, (theirs, mine))
            bundle["ai"] = {"seat": 0, "level": level}
            reset_session(bundle)
            st.rerun()
    _lw_ai_previous_render_home()

# ============================================================
# UNITÉS VOLANTES : HORS D'ATTEINTE DU CORPS À CORPS
# Une unité de corps à corps qui ne vole pas (Enragé, Tigre, Guerrier…)
# ne peut pas attaquer une unité volante : seuls les tireurs et les
# autres unités volantes le peuvent. Les dégâts de zone d'une attaque au
# corps à corps (Enragé, 2e case du Molosse…) ne la touchent pas non plus.
# ============================================================

def melee_cannot_reach(attacker, target):
    return (
        target.get("kind") == "unit"
        and is_flying(target)
        and UNITS.get(attacker.get("name"), {}).get("range", 0) <= 0
        and not is_flying(attacker)
    )


_lw_fly_previous_prepare_attack = prepare_attack


def prepare_attack(g, attacker_ids, target_id):
    target = entity(g, target_id)
    for eid in attacker_ids:
        attacker = entity(g, eid)
        if melee_cannot_reach(attacker, target):
            raise ValueError(
                f"{attacker['name']} attaque au corps à corps : "
                f"il ne peut pas atteindre {target['name']}, une unité volante."
            )
    return _lw_fly_previous_prepare_attack(g, attacker_ids, target_id)


_lw_fly_previous_attack_map_preview = attack_map_preview


def attack_map_preview(g, attackers):
    zone, targets = _lw_fly_previous_attack_map_preview(g, attackers)
    walkers = [a for a in attackers if UNITS.get(a["name"], {}).get("range", 0) <= 0 and not is_flying(a)]
    if walkers and targets:
        # Pas de case rouge sur une unité volante pour le corps à corps.
        targets = {
            pos: data for pos, data in targets.items()
            if not any(
                melee_cannot_reach(walkers[0], piece) for piece in pieces_at(g, pos)
            )
        }
    return zone, targets


_lw_fly_previous_apply_attack_effects = apply_attack_effects


def apply_attack_effects(g, effects):
    if effects and effects.get("splash"):
        kept = []
        for hit in effects["splash"]:
            name = (hit.get("source") or {}).get("name")
            melee = name in UNITS and UNITS[name].get("range", 0) <= 0 and name not in FLYING_UNITS
            if melee and any(
                victim["kind"] == "unit" and is_flying(victim)
                for victim in pieces_at(g, hit["pos"])
            ):
                continue
            kept.append(hit)
        effects = dict(effects, splash=kept)
    return _lw_fly_previous_apply_attack_effects(g, effects)


# ============================================================
# GOBELIN : VOL DE RESSOURCES
# - Le Gobelin vole en s'arrêtant sur une case d'or ou de mana récoltée
#   par une base ennemie (case voisine de la base, ou marqueur d'un héros
#   vagabond) : il prend aussitôt, dans le trésor ennemi, ce que cette
#   case rapporte à l'ennemi à chaque récolte.
# - Il rapporte son butin en revenant à une de ses bases (case voisine,
#   ou en traversant la base) : l'or ou le mana va dans le trésor.
# - Un seul butin à la fois ; un Gobelin détruit perd son butin.
# - Une pastille 💰 (or) ou 🔮 (mana) sur le pion montre son butin.
# ============================================================

def goblin_cell_yield(g, thief_owner, pos):
    """(ressource, quantité) que cette case rapporte à l'ennemi, sinon None."""
    resource = g["resources"].get(key(tuple(pos)))
    if resource is None:
        return None
    kind, mult = resource
    enemy = 1 - thief_owner
    age = g["players"][enemy]["age"]
    best = 0
    for base in g["entities"]:
        if base["owner"] != enemy or base["kind"] != "base" or base.get("wait"):
            continue
        if is_hero(base):
            marker = base.get("marker")
            if marker and tuple(marker) == tuple(pos):
                _, _, _, gold, mana = hero_stats(g, base)
                best = max(best, (gold if kind == "gold" else mana) * mult)
        elif distance(tuple(base["pos"]), tuple(pos)) == 1:
            gold_income, mana_income = harvest_income(g, enemy)
            income = gold_income if kind == "gold" else mana_income
            best = max(best, income * mult)
    return (kind, int(best)) if best else None


def goblin_try_deposit(g, goblin, route):
    gold, mana = goblin_loot(goblin)
    if not gold and not mana:
        return
    owner = goblin["owner"]
    crossed = {tuple(p) for p in route}
    here = tuple(goblin["pos"])
    home = [
        base for base in g["entities"]
        if base["owner"] == owner and base["kind"] == "base"
        and (tuple(base["pos"]) in crossed or distance(here, tuple(base["pos"])) <= 1)
    ]
    if not home:
        return
    player = g["players"][owner]
    player["gold"] += gold
    player["mana"] += mana
    goblin.pop("loot", None)
    text = " et ".join(part for part in (f"{gold} or" if gold else "", f"{mana} mana" if mana else "") if part)
    log(g, f"Gobelin #{goblin['id']} rapporte son butin à {home[0]['name']} : +{text}.")
    g["_ui_message"] = f"💰 Le Gobelin rapporte son butin : +{text}."


def goblin_try_steal(g, goblin):
    if any(goblin_loot(goblin)):
        return
    found = goblin_cell_yield(g, goblin["owner"], tuple(goblin["pos"]))
    if found is None:
        return
    kind, amount = found
    victim = 1 - goblin["owner"]
    taken = min(amount, int(g["players"][victim][kind]))
    label = "or" if kind == "gold" else "mana"
    if taken <= 0:
        log(g, f"Gobelin #{goblin['id']} : le trésor ennemi est vide, rien à voler ({label}).")
        return
    g["players"][victim][kind] -= taken
    goblin["loot"] = {"gold": taken if kind == "gold" else 0, "mana": taken if kind == "mana" else 0}
    log(
        g,
        f"Gobelin #{goblin['id']} vole {taken} {label} aux {faction_of(g, victim)['name']} "
        f"en {coord(goblin['pos'])}.",
    )
    g["_ui_message"] = (
        f"🕵️ Le Gobelin vole {taken} {label} ! Ramène-le à une de tes bases pour l'encaisser."
    )


_lw_goblin2_previous_move_unit = move_unit


def move_unit(g, eid, destination):
    _lw_goblin2_previous_move_unit(g, eid, destination)
    goblin = next((e for e in g["entities"] if e["id"] == eid), None)
    if goblin is None or goblin["name"] != GOBLIN:
        return
    route = (g.get("last_move") or {}).get("route") or []
    goblin_try_deposit(g, goblin, route)
    goblin_try_steal(g, goblin)


def render_goblin_controls(g, goblin, prefix):
    st.markdown("#### 💰 Gobelin voleur")
    gold, mana = goblin_loot(goblin)
    if gold or mana:
        st.success(
            f"Butin transporté : {gold} or · {mana} mana. "
            "Ramène le Gobelin à côté d'une de tes bases (ou traverse-la) pour l'encaisser."
        )
    else:
        st.caption(
            "Pour voler : arrête le Gobelin sur une case d'or ou de mana récoltée "
            "par une base ennemie (ou marquée par un héros ennemi). Il prend aussitôt "
            "ce que cette case rapporte à l'ennemi."
        )

# ============================================================
# CONTRE L'IA : ANNULER SON DERNIER COUP
# Avant chaque action du joueur (production ou manœuvre), la partie est
# mémorisée. Le bouton « Annuler mon dernier coup » la remet dans l'état
# d'avant cette action, réponse de l'IA comprise. Uniquement contre l'IA
# (jamais en ligne ni à deux sur le même ordinateur).
# ============================================================

AI_UNDO_LIMIT = 30


def ai_undo_stack():
    return st.session_state.setdefault("ai_undo_stack", [])


_lw_undo_previous_perform = perform


def perform(fn, *args):
    bundle = st.session_state.get("bundle")
    snapshot = None
    if (
        ai_config(bundle) is not None
        and not st.query_params.get("room")
        and bundle["game"]["winner"] is None
    ):
        snapshot = copy.deepcopy(bundle)
    try:
        return _lw_undo_previous_perform(fn, *args)
    finally:
        # Seulement si l'action a réellement changé la partie.
        if snapshot is not None and st.session_state.get("bundle") is not bundle:
            stack = ai_undo_stack()
            stack.append(snapshot)
            del stack[:-AI_UNDO_LIMIT]


def ai_undo_last_move():
    stack = ai_undo_stack()
    if not stack:
        return
    st.session_state.bundle = stack.pop()
    st.session_state.ai_last_actions = []
    st.session_state.ui_combat_report = None
    st.session_state.ui_message = "↩️ Coup annulé : la partie revient juste avant ta dernière action."
    bump_ui(clear_selection=True)


_lw_undo_previous_render_sidebar = render_sidebar


def render_sidebar(bundle):
    if ai_config(bundle) is not None and not st.query_params.get("room"):
        stack = ai_undo_stack()
        with st.sidebar:
            if st.button(
                "↩️ Annuler mon dernier coup",
                disabled=not stack,
                width="stretch",
                key="ai_undo_button",
                help="Revient juste avant ta dernière action (la réponse de l'IA est annulée aussi).",
            ):
                ai_undo_last_move()
                st.rerun()
            if stack:
                st.caption(f"{len(stack)} coup(s) peuvent être annulés.")
    _lw_undo_previous_render_sidebar(bundle)

# ============================================================
# CONTRE L'IA : CE QUE L'IA A FAIT CE TOUR, EN SURBRILLANCE
# Au début de chaque tour, la position des pièces de l'IA est notée.
# Sur le plateau :
# - orange (flèche en pointillés depuis le départ) : pièces déplacées ;
# - vert « NOUVEAU » : unités apparues ce tour (recrutées, fusionnées) ;
# - doré « NOUVEAU » : bâtiments, bases ou héros apparus ce tour.
# ============================================================

def ai_update_turn_marks(bundle):
    """Nouveau tour : on repart de zéro, mais seulement après la première
    action du joueur (il voit d'abord tout ce que l'IA a fait)."""
    config = ai_config(bundle)
    if config is None or not isinstance(bundle.get("game"), dict):
        return
    g = bundle["game"]
    marks = st.session_state.get("ai_turn_marks")
    new_turn = bool(marks) and marks.get("turn") != g["turn"] and st.session_state.get("ai_marks_seen", True)
    if not marks or new_turn or marks.get("seat") != config["seat"]:
        st.session_state.ai_turn_marks = {
            "turn": g["turn"],
            "seat": config["seat"],
            "start": {
                str(e["id"]): list(e["pos"]) for e in g["entities"] if e["owner"] == config["seat"]
            },
        }


def ai_turn_marks_view(bundle):
    config = ai_config(bundle)
    marks = st.session_state.get("ai_turn_marks")
    if config is None or not marks:
        return None
    g = bundle["game"]
    start = marks["start"]
    # Pièces apparues ce tour (recrutées, construites, fusionnées).
    new = [
        e["id"] for e in g["entities"]
        if e["owner"] == config["seat"] and str(e["id"]) not in start
    ]
    # Un seul déplacement en relief : le dernier joué sur le plateau.
    moved = {}
    last = g.get("last_move") or {}
    route = last.get("route") or []
    unit = next((e for e in g["entities"] if e["id"] == last.get("unit_id")), None)
    if unit is not None and len(route) >= 2 and list(unit["pos"]) != list(route[0]):
        moved[str(unit["id"])] = list(route[0])
    return {"moved": moved, "new": new} if moved or new else None


_lw_marks_previous_perform = perform


def perform(fn, *args):
    # Le joueur agit : il a vu ce que l'IA a fait.
    st.session_state.ai_marks_seen = True
    return _lw_marks_previous_perform(fn, *args)


_lw_marks_previous_ai_autoplay = ai_autoplay


def ai_autoplay():
    before = st.session_state.get("bundle")
    _lw_marks_previous_ai_autoplay()
    if st.session_state.get("bundle") is not before:
        # L'IA vient de jouer : le joueur ne l'a pas encore vu.
        st.session_state.ai_marks_seen = False


_lw_marks_previous_main = main


def main():
    if not st.query_params.get("room"):
        ai_update_turn_marks(st.session_state.get("bundle"))
    _lw_marks_previous_main()


_lw_marks_previous_render_board = render_board


def render_board(g, view, readonly=False):
    bundle = st.session_state.get("bundle")
    if ai_config(bundle) is not None and not st.query_params.get("room"):
        # L'IA a pu changer de tour pendant qu'elle jouait : on recale.
        ai_update_turn_marks(bundle)
    # Les ronds « NOUVEAU » viennent du journal de bord : ils marquent ce que
    # l'adversaire vient de produire, jusqu'à la première manœuvre du joueur
    # (et non plus pendant tout le tour).
    st.session_state["_lw_ai_marks"] = None
    return _lw_marks_previous_render_board(g, view, readonly)

# ============================================================
# PROFILS DE JOUEURS ET STATISTIQUES
# - Chaque joueur choisit un pseudo (accueil, ou salon en ligne).
# - À la fin d'une partie en ligne ou contre l'IA, le résultat est ajouté
#   à son profil (fichier profils.json à côté du jeu).
# - Page « Profils » : statistiques contre l'IA et contre des joueurs.
# - Export / import du profil (Streamlit Cloud efface les fichiers au
#   redémarrage de l'application).
# ============================================================

PROFILES_FILE = Path(__file__).parent / "profils.json"


_lw_profile_previous_new_bundle = new_bundle


def new_bundle(*args, **kwargs):
    bundle = _lw_profile_previous_new_bundle(*args, **kwargs)
    bundle["game_id"] = uuid.uuid4().hex  # identifiant de partie (statistiques)
    return bundle
PROFILE_RESULTS = ("victoire", "défaite", "nul")


@st.cache_resource
def profiles_lock():
    return threading.Lock()


def profiles_load():
    try:
        data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def profiles_save(data):
    tmp = PROFILES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(PROFILES_FILE)


def profile_add_games(name, games):
    with profiles_lock():
        data = profiles_load()
        profile = data.setdefault(name, {"parties": []})
        known = {(p.get("id"), p.get("joueur")) for p in profile["parties"]}
        for game in games:
            if (game.get("id"), game.get("joueur")) not in known:
                profile["parties"].append(game)
        profiles_save(data)


def current_player_name():
    return (st.session_state.get("player_name") or "").strip()


def game_result_entry(bundle, seat, mode, opponent):
    g = bundle["game"]
    winner = g["winner"]
    result = "nul" if winner == -1 else ("victoire" if winner == seat else "défaite")
    loser = game_forfeiter(g)
    return {
        "id": bundle.get("game_id") or f"{g.get('tick', 0)}-{len(g['log'])}",
        "joueur": seat,
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "mode": mode,
        "adversaire": opponent,
        "faction": FACTIONS[faction_id(g, seat)]["name"],
        "faction_adverse": FACTIONS[faction_id(g, 1 - seat)]["name"],
        "resultat": result,
        "abandon": loser is not None,
        "abandon_par_moi": loser == seat,
        "tours": g["turn"],
        "bases_detruites": g["players"][seat].get("bases", 0),
        "bases_perdues": g["players"][1 - seat].get("bases", 0),
        "victoire": g.get("victory_mode"),
    }


def record_finished_game(bundle):
    """Une seule fois par partie et par joueur : ajoute le résultat au profil."""
    if not isinstance(bundle, dict) or bundle["game"].get("winner") is None:
        return
    done = bundle.setdefault("stats_recorded", [])
    config = ai_config(bundle)
    room = online_active_room() if st.session_state.get("online_code") else None
    if room is not None:
        seat = online_seat()
        names = room.get("names") or {}
        name = (names.get(seat) or "").strip()
        opponent = (names.get(1 - seat) or "").strip() or "Adversaire en ligne"
        mode = "humain"
    elif config is not None:
        seat = 1 - config["seat"]
        name = (bundle.get("names") or {}).get(str(seat), "") or current_player_name()
        opponent = f"IA {AI_LEVELS.get(config.get('level'), '').split(' ', 1)[-1]}"
        mode = "ia"
    else:
        return  # partie à deux sur le même ordinateur : non comptée
    if seat not in (0, 1) or not name or seat in done:
        return
    done.append(seat)
    entry = game_result_entry(bundle, seat, mode, opponent)
    if mode == "ia":
        entry["niveau"] = opponent
    profile_add_games(name, [entry])


_lw_profile_previous_render_victory_screen = render_victory_screen


def render_victory_screen(g):
    _lw_profile_previous_render_victory_screen(g)
    bundle = st.session_state.get("bundle")
    if isinstance(bundle, dict) and isinstance(bundle.get("game"), dict) and bundle["game"].get("winner") is not None:
        before = list(bundle.get("stats_recorded", []))
        record_finished_game(bundle)
        if bundle.get("stats_recorded", []) != before and current_player_name():
            st.caption(f"📊 Résultat enregistré dans le profil de {current_player_name()}.")


# ------------------------------------------------------------
# Statistiques
# ------------------------------------------------------------

def profile_rate(won, played):
    return f"{100 * won / played:.0f} %" if played else "—"


def profile_rows(games, field):
    rows = {}
    for game in games:
        row = rows.setdefault(game.get(field) or "?", {"parties": 0, "victoires": 0, "défaites": 0, "nuls": 0})
        row["parties"] += 1
        row[{"victoire": "victoires", "défaite": "défaites"}.get(game["resultat"], "nuls")] += 1
    return [
        {field.replace("_", " ").capitalize(): label, **row, "% victoires": profile_rate(row["victoires"], row["parties"])}
        for label, row in sorted(rows.items(), key=lambda item: -item[1]["parties"])
    ]


def profile_streaks(games):
    best = current = 0
    for game in games:
        if game["resultat"] == "victoire":
            current += 1
            best = max(best, current)
        else:
            current = 0
    return current, best


def render_profile_games(games, versus_ai):
    if not games:
        st.info("Aucune partie terminée pour l'instant.")
        return
    won = sum(g["resultat"] == "victoire" for g in games)
    lost = sum(g["resultat"] == "défaite" for g in games)
    played = len(games)
    cols = st.columns(4)
    cols[0].metric("Parties jouées", played)
    cols[1].metric("Gagnées", won)
    cols[2].metric("Perdues", lost)
    cols[3].metric("Ratio de victoires", profile_rate(won, played))
    current, best = profile_streaks(games)
    wins = [g for g in games if g["resultat"] == "victoire"]
    cols = st.columns(4)
    cols[0].metric("Série en cours", f"{current} victoire(s)")
    cols[1].metric("Meilleure série", f"{best} victoire(s)")
    cols[2].metric("Durée moyenne", f"{sum(g['tours'] for g in games) / played:.1f} tours")
    cols[3].metric("Victoire la plus rapide", f"tour {min(g['tours'] for g in wins)}" if wins else "—")
    cols = st.columns(4)
    cols[0].metric("Bases détruites", sum(g.get("bases_detruites", 0) for g in games))
    cols[1].metric("Bases perdues", sum(g.get("bases_perdues", 0) for g in games))
    cols[2].metric("Abandons (toi)", sum(g.get("abandon_par_moi", False) for g in games))
    cols[3].metric("Abandons (adversaire)", sum(g.get("abandon", False) and not g.get("abandon_par_moi") for g in games))

    favorite = max(profile_rows(games, "faction"), key=lambda r: r["parties"])
    ranked = [r for r in profile_rows(games, "faction") if r["parties"] >= 3]
    st.caption(
        f"⭐ Faction la plus jouée : **{favorite['Faction']}**"
        + (f" · 🏆 meilleure faction (3 parties ou plus) : **{max(ranked, key=lambda r: r['victoires'] / r['parties'])['Faction']}**" if ranked else "")
    )

    st.markdown("**Par faction jouée**")
    st.dataframe(profile_rows(games, "faction"), hide_index=True, width="stretch")
    st.markdown("**Contre chaque faction adverse**")
    st.dataframe(profile_rows(games, "faction_adverse"), hide_index=True, width="stretch")

    factions = [FACTIONS[f]["name"] for f in FACTIONS]
    matrix = []
    for mine in factions:
        row = {"Ta faction ↓ / adverse →": mine}
        for theirs in factions:
            row[theirs] = sum(
                1 for g in games
                if g["faction"] == mine and g["faction_adverse"] == theirs and g["resultat"] == "défaite"
            )
        matrix.append(row)
    st.markdown("**Défaites : ta faction contre chaque faction adverse**")
    st.dataframe(matrix, hide_index=True, width="stretch")

    if versus_ai:
        st.markdown("**Par niveau de l'IA**")
        st.dataframe(profile_rows(games, "niveau"), hide_index=True, width="stretch")
    else:
        st.markdown("**Par adversaire**")
        st.dataframe(profile_rows(games, "adversaire"), hide_index=True, width="stretch")

    st.markdown("**Dernières parties**")
    st.dataframe(
        [
            {
                "Date": g["date"], "Ta faction": g["faction"], "Adversaire": g["adversaire"],
                "Faction adverse": g["faction_adverse"],
                "Résultat": {"victoire": "🏆 victoire", "défaite": "💀 défaite"}.get(g["resultat"], "🤝 nul")
                + (" (abandon)" if g.get("abandon") else ""),
                "Tours": g["tours"],
            }
            for g in reversed(games[-15:])
        ],
        hide_index=True,
        width="stretch",
    )


def render_profiles_page():
    data = profiles_load()
    names = sorted(data)
    me = current_player_name()
    if me and me not in names:
        names.insert(0, me)
    if not names:
        st.info("Aucun profil pour l'instant : choisis un pseudo, puis termine une partie contre l'IA ou en ligne.")
    else:
        name = st.selectbox(
            "Profil", names, index=names.index(me) if me in names else 0, key="profile_view_name",
        )
        games = (data.get(name) or {}).get("parties", [])
        ai_tab, human_tab = st.tabs(["🤖 Contre l'IA", "🧑‍🤝‍🧑 Contre des joueurs"])
        with ai_tab:
            render_profile_games([g for g in games if g.get("mode") == "ia"], True)
        with human_tab:
            render_profile_games([g for g in games if g.get("mode") == "humain"], False)
        st.download_button(
            "📥 Télécharger ce profil",
            data=json.dumps({name: data.get(name, {"parties": []})}, ensure_ascii=False, indent=1),
            file_name=f"profil_{name}.json",
            mime="application/json",
            key="profile_download",
        )
    uploaded = st.file_uploader("📤 Importer un profil (fichier téléchargé auparavant)", type=["json"], key="profile_upload")
    if uploaded is not None and st.button("Importer", key="profile_import"):
        try:
            imported = json.loads(uploaded.getvalue().decode("utf-8"))
            for name, profile in imported.items():
                games = [g for g in profile.get("parties", []) if isinstance(g, dict) and g.get("resultat") in PROFILE_RESULTS]
                profile_add_games(str(name)[:24], games)
            st.success("Profil importé.")
        except (ValueError, AttributeError, UnicodeError):
            st.error("Fichier de profil invalide.")


# ------------------------------------------------------------
# Accueil, salon en ligne, partie contre l'IA : le pseudo
# ------------------------------------------------------------

_lw_profile_previous_render_home = render_home


def render_home():
    with st.container(border=True):
        cols = st.columns([2, 1])
        with cols[0]:
            name = st.text_input(
                "👤 Ton pseudo (pour tes statistiques)",
                value=st.session_state.get("player_name", ""),
                max_chars=24,
                key="home_player_name",
            )
            st.session_state.player_name = name.strip()
        with cols[1]:
            st.write("")
            show = st.toggle("📊 Profils et statistiques", key="home_show_profiles")
        if show:
            render_profiles_page()
    _lw_profile_previous_render_home()


_lw_profile_previous_render_online_lobby = render_online_lobby


def render_online_lobby(room, seat):
    names = room.setdefault("names", {0: "", 1: ""})
    name = st.text_input(
        "👤 Ton pseudo (pour tes statistiques)",
        value=names.get(seat) or st.session_state.get("player_name", ""),
        max_chars=24,
        key=f"lobby_name_{seat}",
    ).strip()
    if name != (names.get(seat) or ""):
        with online_lock():
            names[seat] = name
            room["version"] += 1
    if name:
        st.session_state.player_name = name
    _lw_profile_previous_render_online_lobby(room, seat)


# Nouvelle partie : le pseudo est gardé (et inscrit dans la partie contre l'IA).
_lw_profile_previous_reset_session = reset_session


def reset_session(bundle=None):
    name = current_player_name()
    _lw_profile_previous_reset_session(bundle)
    if name:
        st.session_state.player_name = name
        config = ai_config(bundle) if isinstance(bundle, dict) else None
        if config is not None:
            bundle.setdefault("names", {})[str(1 - config["seat"])] = name


# L'annulation d'un coup ne peut pas effacer un résultat déjà enregistré.
_lw_profile_previous_ai_undo_last_move = ai_undo_last_move


def ai_undo_last_move():
    recorded = list((st.session_state.get("bundle") or {}).get("stats_recorded", []))
    _lw_profile_previous_ai_undo_last_move()
    if recorded and isinstance(st.session_state.get("bundle"), dict):
        st.session_state.bundle["stats_recorded"] = recorded


# ============================================================
# CATAPULTES : AUCUNE RIPOSTE
# Une Catapulte ou une Catapulte de l'enfer ne riposte jamais, ni à une
# attaque au corps à corps, ni à un tir. (Seul le Trébuchet a un tir
# automatique sur les unités qui traversent sa zone.)
# ============================================================

NO_RIPOSTE_UNITS = {CATAPULT, HELL_CATAPULT}


def never_ripostes(target):
    return target.get("kind") == "unit" and target.get("name") in NO_RIPOSTE_UNITS


_lw_noriposte_previous_combat_values = combat_values


def combat_values(attackers, target):
    values = _lw_noriposte_previous_combat_values(attackers, target)
    if not never_ripostes(target):
        return values
    # Même traitement qu'une attaque invisible : aucune perte pour les
    # attaquants, la cible perd les PF de l'attaque si elle survit.
    values = dict(values, hidden=True, no_riposte=target["name"], losses=0.0)
    if not values["winnable"]:
        values["defender_damage"] = values["power"]
        values["defender_remaining"] = values["defense"] - values["power"]
    return values


_lw_noriposte_previous_ranged_riposte = ranged_riposte


def ranged_riposte(g, attacker, target):
    if never_ripostes(target):
        return 0.0
    return _lw_noriposte_previous_ranged_riposte(g, attacker, target)


_lw_noriposte_previous_ranged_riposte_text = ranged_riposte_text


def ranged_riposte_text(g, attacker, target):
    if never_ripostes(target):
        return f"{target['name']} ne riposte pas."
    return _lw_noriposte_previous_ranged_riposte_text(g, attacker, target)


# ============================================================
# JOURNAL DE BORD ET EFFETS DE COMBAT SUR LE PLATEAU
# - Chaque action (manœuvre, attaque, sort, production dévoilée) ajoute
#   UNE ligne au journal de bord de la partie (g["journal"]), avec ce
#   qu'il faut au plateau pour la montrer : tirs, cases touchées, PF
#   perdus, pièces apparues.
# - Le journal est affiché juste au-dessus du plateau ; les actions faites
#   depuis ta dernière manœuvre sont numérotées, et les mêmes numéros
#   apparaissent sur le plateau (PF perdus en rouge sur les cases touchées).
# - Le plateau anime chaque nouvelle action une fois : flèche, rocher,
#   boule de feu, nuage de poussière, sort…
# ============================================================

JOURNAL_KEEP = 150
JOURNAL_SHOWN = 14
FX_RECENT_MAX = 25

# Le journal est remplacé (jamais modifié en place) : les copies de travail
# de l'IA peuvent donc le partager sans le recopier.
AI_SHARED_FIELDS = tuple(AI_SHARED_FIELDS) + ("journal",)

FX_SHOT_KINDS = {
    CATAPULT: "rock", TREBUCHET: "rock", HELL_CATAPULT: "fireball",
    "Golem de pierre": "rock", "Dragon": "fire",
    "Aspergeur": "acid", "Rampant": "acid",
    "Voyant": "arcane", "Errant": "arcane", "Super Errant": "arcane", "Parfait": "arcane",
}
FX_SPELL_KINDS = {
    ("cast_mage_spell", "slow"): "ice", ("cast_mage_spell", "damage"): "arcane",
    ("cast_sorcerer_spell", "freeze"): "ice", ("cast_sorcerer_spell", "stalactites"): "ice",
    ("cast_decimant_spell", "block"): "dark", ("cast_decimant_spell", "attract"): "dark",
    ("cast_airship_spell", "boost"): "buff", ("cast_airship_spell", "harvest"): "buff",
}
FX_SPELL_LABELS = {
    ("cast_mage_spell", "slow"): "🐌 Ralentissement",
    ("cast_mage_spell", "damage"): "💥 Sort de dégâts",
    **{("cast_sorcerer_spell", k): v for k, v in SORCERER_SPELLS.items()},
    **{("cast_decimant_spell", k): v for k, v in DECIMANT_SPELLS.items()},
    **{("cast_airship_spell", k): v for k, v in AIRSHIP_SPELLS.items()},
}
FX_ICONS = {
    "melee": "⚔️", "arrow": "🏹", "rock": "🪨", "fireball": "☄️", "fire": "🔥",
    "acid": "🧪", "arcane": "✨", "ice": "❄️", "dark": "🌑", "buff": "💪",
    "summon": "🌀", "mutation": "🧬", "explosion": "💥", "loot": "💰",
    "move": "🚶", "build": "🏗️", "recruit": "🪖", "upgrade": "🔬", "age": "⏫",
    "pass": "⏭️", "impact": "💢", "info": "•",
}
# Couleur des factions (identique aux pions du plateau).
FX_FACTION_COLORS = {0: "#23945a", 1: "#2d6cc4", 2: "#c62828", 3: "#78716c"}


def fx_state(g):
    """Photo des pièces avant une action : position, PF, gel, tir auto."""
    return {
        e["id"]: {
            "name": e["name"], "owner": e["owner"], "kind": e["kind"],
            "pos": [int(v) for v in e["pos"]], "pf": float(e["pf"]),
            "frozen": e.get("frozen_until_turn"), "auto": e.get("auto_fired_turn"),
        }
        for e in g["entities"]
    }


def fx_push(g, entry):
    seq = int(g.get("fx_seq", 0)) + 1
    g["fx_seq"] = seq
    entry["seq"] = seq
    g["journal"] = (list(g.get("journal") or []) + [entry])[-JOURNAL_KEEP:]


def fx_hits(before, g, actor_owner):
    """PF perdus (ou gagnés), pièces détruites ou gelées par l'action."""
    after = {e["id"]: e for e in g["entities"]}
    destroyed = set(g.get("_fx_destroyed") or [])
    hits = []
    for eid, old in before.items():
        new = after.get(eid)
        if new is None:
            # Une pièce ennemie qui disparaît est détruite ; une pièce alliée
            # peut aussi embarquer ou fusionner : seulement si destroy() l'a dit.
            if old["pf"] > 0 and (eid in destroyed or old["owner"] != actor_owner):
                hits.append({
                    "id": eid, "name": old["name"], "owner": old["owner"], "pos": old["pos"],
                    "damage": old["pf"], "destroyed": True, "kind": old["kind"],
                    "faction": faction_id(g, old["owner"]),
                })
            continue
        pf = float(new["pf"])
        pos = [int(v) for v in new["pos"]]
        if pf < old["pf"] - 1e-9:
            hits.append({
                "id": eid, "name": old["name"], "owner": old["owner"], "pos": pos,
                "damage": old["pf"] - pf, "left": pf, "destroyed": False,
            })
        elif pf > old["pf"] + 1e-9:
            hits.append({
                "id": eid, "name": old["name"], "owner": old["owner"], "pos": pos,
                "heal": pf - old["pf"], "left": pf,
            })
        if new.get("frozen_until_turn") != old["frozen"] and new.get("frozen_until_turn"):
            hits.append({"id": eid, "name": old["name"], "owner": old["owner"], "pos": pos, "status": "❄ GELÉ"})
    return hits


def fx_num(value):
    return f"{float(value):g}".replace(".", ",")


def fx_hit_text(hit):
    if hit.get("status"):
        return f"{hit['name']} {hit['status'].split(' ', 1)[-1].lower()}"
    if hit.get("heal"):
        return f"{hit['name']} +{fx_num(hit['heal'])} PF"
    if hit.get("destroyed"):
        return f"{hit['name']} détruit (−{fx_num(hit['damage'])} PF)"
    return f"{hit['name']} −{fx_num(hit['damage'])} PF (reste {fx_num(hit['left'])})"


def fx_result_text(hits, owner):
    enemy = [h for h in hits if h["owner"] != owner]
    own = [h for h in hits if h["owner"] == owner]
    parts = []
    if enemy:
        parts.append(", ".join(fx_hit_text(h) for h in enemy))
    losses = [h for h in own if h.get("damage")]
    gains = [h for h in own if not h.get("damage")]
    if gains:
        parts.append(", ".join(fx_hit_text(h) for h in gains))
    if losses:
        parts.append("pertes : " + ", ".join(fx_hit_text(h) for h in losses))
    return " · ".join(parts)


def fx_strip_log(line):
    return line.split(" — ", 1)[-1]


def fx_label(piece):
    return f"{piece['name']} ({coord(piece['pos'])})"


def fx_action_ids(name, args):
    """(acteurs, cibles) d'une action, d'après ses arguments."""
    def ids(value):
        if isinstance(value, (list, tuple)):
            return [v for v in value if isinstance(v, int)]
        return [value] if isinstance(value, int) else []

    if not args:
        return [], []
    if name == "attack":
        return ids(args[0]), ids(args[1]) if len(args) > 1 else []
    if name in ("ranged_attack", "kamikaze_attack", "goblin_steal"):
        return ids(args[0]), ids(args[1]) if len(args) > 1 else []
    if name == "cast_mage_spell":
        return ids(args[0]), ids(args[2]) if len(args) > 2 else []
    if name in ("cast_decimant_spell", "cast_airship_spell", "cast_sorcerer_spell"):
        return ids(args[0]), ids(args[2]) if len(args) > 2 else []
    if name == "aramil_burn":
        return ids(args[0]), ids(args[1]) if len(args) > 1 else []
    if name == "board_airship":
        return ids(args[1]) if len(args) > 1 else [], ids(args[0])
    return ids(args[0]), []


def fx_describe(g, before, owner, label, turn, name, args, new_log):
    """Une ligne de journal (et ses effets) pour une manœuvre."""
    hits = fx_hits(before, g, owner)
    actor_ids, target_ids = fx_action_ids(name, args)
    actors = [before[i] for i in actor_ids if i in before]
    targets = [before[i] for i in target_ids if i in before]
    entry = {
        "turn": label, "round": turn, "owner": owner, "phase": "move",
        "kind": "info", "text": "", "shots": [], "moves": [], "hits": hits,
        "spawns": [], "auras": [],
    }
    result = fx_result_text(hits, owner)
    spell = args[1] if len(args) > 1 and isinstance(args[1], str) else None

    if name == "attack" and actors and targets:
        entry["kind"] = "melee"
        routes = g.get("_fx_routes") or {}
        entry["shots"] = [
            {
                "from": a["pos"], "to": targets[0]["pos"], "kind": "melee",
                "route": routes.get(a_id) or [a["pos"], targets[0]["pos"]],
                "actor": {"id": a_id, "name": a["name"], "faction": faction_id(g, a["owner"])},
            }
            for a_id, a in zip([i for i in actor_ids if i in before], actors)
        ]
        # Un attaquant tué tombe sur sa case de frappe, pas à son départ.
        strike_cells = {
            s["actor"]["id"]: s["route"][-2] for s in entry["shots"] if len(s["route"]) >= 2
        }
        for hit in hits:
            if hit.get("destroyed") and hit["id"] in strike_cells:
                hit["pos"] = strike_cells[hit["id"]]
                hit["attacker"] = True
        who = ", ".join(fx_label(a) for a in actors)
        verb = "attaquent" if len(actors) > 1 else "attaque"
        entry["text"] = f"{who} {verb} {targets[0]['name']} en {coord(targets[0]['pos'])}"
    elif name == "ranged_attack" and actors and targets:
        kind = FX_SHOT_KINDS.get(actors[0]["name"], "arrow")
        entry["kind"] = kind
        entry["shots"] = [{"from": actors[0]["pos"], "to": targets[0]["pos"], "kind": kind}]
        verb = "bombarde" if kind in ("rock", "fireball") else "tire sur"
        entry["text"] = f"{fx_label(actors[0])} {verb} {targets[0]['name']} en {coord(targets[0]['pos'])}"
    elif name == "kamikaze_attack" and actors and targets:
        entry["kind"] = "explosion"
        entry["shots"] = [{"from": actors[0]["pos"], "to": targets[0]["pos"], "kind": "explosion"}]
        entry["auras"] = [{"pos": targets[0]["pos"], "kind": "explosion"}]
        entry["text"] = f"{fx_label(actors[0])} explose sur {targets[0]['name']} en {coord(targets[0]['pos'])}"
    elif (name, spell) in FX_SPELL_KINDS and actors:
        kind = FX_SPELL_KINDS[(name, spell)]
        entry["kind"] = kind
        spell_label = FX_SPELL_LABELS.get((name, spell), spell)
        entry["shots"] = [{"from": actors[0]["pos"], "to": t["pos"], "kind": kind} for t in targets]
        entry["auras"] = [{"pos": t["pos"], "kind": kind} for t in targets] or [{"pos": actors[0]["pos"], "kind": kind}]
        if name == "cast_sorcerer_spell":
            # Sort de zone : toutes les pièces touchées montrent l'effet.
            entry["auras"] += [{"pos": h["pos"], "kind": kind} for h in hits]
        entry["text"] = f"{fx_label(actors[0])} lance « {spell_label} »" + (
            f" sur {', '.join(fx_label(t) for t in targets)}" if targets else ""
        )
    elif name == "aramil_burn" and actors:
        entry["kind"] = "fire"
        entry["shots"] = [{"from": actors[0]["pos"], "to": t["pos"], "kind": "fire"} for t in targets]
        entry["auras"] = [{"pos": t["pos"], "kind": "fire"} for t in targets]
        entry["text"] = f"{fx_label(actors[0])} brûle " + ", ".join(fx_label(t) for t in targets)
    elif name == "aramil_summon_titan" and actors:
        entry["kind"] = "summon"
        titan = [e for e in g["entities"] if e["id"] not in before and e["owner"] == owner]
        entry["spawns"] = [[int(v) for v in e["pos"]] for e in titan]
        entry["auras"] = [{"pos": p, "kind": "summon"} for p in entry["spawns"]]
        entry["text"] = f"{fx_label(actors[0])} invoque " + (
            ", ".join(fx_label(e) for e in titan) if titan else "le Titan"
        )
    elif name == "battle_mutation" and actors:
        entry["kind"] = "mutation"
        mutant = next((e for e in g["entities"] if e["id"] == actors[0].get("id", actor_ids[0])), None)
        pos = [int(v) for v in (mutant or actors[0])["pos"]]
        entry["auras"] = [{"pos": pos, "kind": "mutation"}]
        entry["text"] = f"{fx_label(actors[0])} mute en combat" + (
            f" en {mutant['name']}" if mutant is not None and mutant["name"] != actors[0]["name"] else ""
        )
    elif name == "goblin_steal" and actors:
        entry["kind"] = "loot"
        entry["auras"] = [{"pos": actors[0]["pos"], "kind": "loot"}]
        entry["text"] = f"{fx_label(actors[0])} vole des ressources"
    elif name in ("move_unit", "move_unit_path") and actors:
        entry["kind"] = "move"
        mover = next((e for e in g["entities"] if e["id"] == actor_ids[0]), None)
        last = g.get("last_move") or {}
        route = last.get("route") or []
        start = actors[0]["pos"]
        end = [int(v) for v in (mover["pos"] if mover is not None else (route[-1] if route else start))]
        entry["moves"] = [{
            "from": start, "to": end,
            "route": [[int(v) for v in p] for p in route] if route and list(route[-1]) == end else [start, end],
            "actor": {"id": actor_ids[0], "name": actors[0]["name"], "faction": faction_id(g, owner)},
        }]
        entry["unit_id"] = actor_ids[0]
        entry["path"] = [start, end]
        entry["text"] = f"{actors[0]['name']} : {coord(start)} → {coord(end)}"
        # Tir automatique d'un Trébuchet ennemi pendant le trajet.
        shooters = [
            e for e in g["entities"]
            if e["name"] == TREBUCHET and e["owner"] != owner
            and e["id"] in before and e.get("auto_fired_turn") != before[e["id"]]["auto"]
        ]
        if shooters and hits:
            target_pos = hits[0]["pos"]
            entry["shots"] = [{"from": [int(v) for v in t["pos"]], "to": target_pos, "kind": "rock"} for t in shooters]
            entry["text"] += " · 🪨 tir automatique du Trébuchet"
    elif name == "pass_turn":
        entry["kind"] = "pass"
        entry["text"] = "passe la main"
    else:
        lines = [fx_strip_log(line) for line in new_log]
        if actors:
            entry["auras"] = []
        entry["text"] = lines[0] if lines else name.replace("_", " ")

    if result:
        entry["text"] += " → " + result
    entry["icon"] = FX_ICONS.get(entry["kind"], "•")
    return entry


# --- Trajets des attaquants (corps à corps), notés quand l'attaque les calcule.
_lw_fx_previous_prepare_attack = prepare_attack


def prepare_attack(g, attacker_ids, target_id):
    result = _lw_fx_previous_prepare_attack(g, attacker_ids, target_id)
    routes = result[2] if isinstance(result, tuple) and len(result) > 2 else None
    if isinstance(routes, dict):
        g["_fx_routes"] = {
            eid: [[int(v) for v in p] for p in route] for eid, route in routes.items() if route
        }
    return result


# --- Destructions : notées pour le journal (une pièce alliée qui disparaît
#     peut aussi avoir embarqué ou fusionné).
_lw_fx_previous_destroy = destroy


def destroy(g, victim, credited_owner, killer=None):
    g["_fx_destroyed"] = list(g.get("_fx_destroyed") or []) + [victim["id"]]
    return _lw_fx_previous_destroy(g, victim, credited_owner, killer)


_lw_fx_previous_game_action = game_action


def game_action(bundle, fn, *args):
    g = bundle["game"]
    before = fx_state(g)
    owner, label, turn = g["active"], turn_label(g), g["turn"]
    log_start = len(g["log"])
    g.pop("_fx_destroyed", None)
    g.pop("_fx_routes", None)
    result = _lw_fx_previous_game_action(bundle, fn, *args)
    g = bundle["game"]
    try:
        entry = fx_describe(
            g, before, owner, label, turn, getattr(fn, "__name__", ""), args, g["log"][log_start:]
        )
    except Exception:  # le journal ne doit jamais bloquer une action
        entry = None
    g.pop("_fx_destroyed", None)
    g.pop("_fx_routes", None)
    if entry is None or not entry["text"] or getattr(fn, "__name__", "") in FX_SILENT_ACTIONS:
        return result
    journal = list(g.get("journal") or [])
    last = journal[-1] if journal else None
    if (
        entry["kind"] == "move" and not entry["hits"] and not entry["shots"]
        and last is not None and last.get("kind") == "move" and not last.get("hits")
        and last.get("unit_id") == entry.get("unit_id") and last.get("owner") == owner
        and last.get("turn") == label and last.get("path")
    ):
        # Même unité, même activation : une seule ligne pour tout le trajet.
        path = list(last["path"]) + [entry["path"][-1]]
        merged = dict(last)
        merged["path"] = path
        old_route = (last.get("moves") or [{}])[0].get("route") or path[:-1]
        new_route = entry["moves"][0].get("route") or entry["path"]
        merged["moves"] = [dict(entry["moves"][0], **{"from": path[0], "to": path[-1], "route": list(old_route) + list(new_route[1:])})]
        merged["text"] = f"{entry['text'].split(' : ')[0]} : " + " → ".join(coord(p) for p in path)
        g["journal"] = journal[:-1]
        fx_push(g, merged)
        return result
    fx_push(g, entry)
    return result


# Actions sans effet visible : pas de ligne dans le journal.
FX_SILENT_ACTIONS = {"finish_unit_activation"}


def fx_production_entries(g, before, players_before, hero_orders, label, turn):
    """Lignes du journal au dévoilement des productions."""
    entries = []
    after = {e["id"]: e for e in g["entities"]}
    for owner in (g["first"], 1 - g["first"]):
        def entry(kind, text, **extra):
            data = {
                "turn": label, "round": turn, "owner": owner, "phase": "build",
                "kind": kind, "icon": FX_ICONS.get(kind, "•"), "text": text,
                "shots": [], "moves": [], "hits": [], "spawns": [], "auras": [],
            }
            data.update(extra)
            entries.append(data)

        new = [e for e in g["entities"] if e["owner"] == owner and e["id"] not in before]
        gone = [old for eid, old in before.items() if old["owner"] == owner and eid not in after]
        # Mutations : une pièce remplacée par une autre sur la même case.
        for piece in list(new):
            old = next((o for o in gone if o["pos"] == [int(v) for v in piece["pos"]] and o["kind"] == piece["kind"]), None)
            if old is not None and old["name"] != piece["name"]:
                gone.remove(old)
                new.remove(piece)
                pos = [int(v) for v in piece["pos"]]
                entry("mutation", f"{old['name']} mute en {piece['name']} ({coord(pos)})",
                      spawns=[pos], auras=[{"pos": pos, "kind": "mutation"}])
        # Recrues regroupées par type ; bâtiments et bases un par un.
        groups = {}
        for piece in new:
            groups.setdefault((piece["kind"], piece["name"]), []).append([int(v) for v in piece["pos"]])
        for (kind, name), cells in groups.items():
            where = ", ".join(coord(p) for p in cells)
            if kind == "unit":
                count = f"{len(cells)} × " if len(cells) > 1 else ""
                entry("recruit", f"Recrute {count}{name} ({where})", spawns=cells)
            else:
                entry("build", f"Construit {name} ({where})", spawns=cells)
        # Déplacements de production (ouvriers, héros).
        for eid, old in before.items():
            piece = after.get(eid)
            if piece is None or old["owner"] != owner:
                continue
            pos = [int(v) for v in piece["pos"]]
            if pos != old["pos"]:
                entry("move", f"{old['name']} : {coord(old['pos'])} → {coord(pos)}",
                      moves=[{"from": old["pos"], "to": pos}])
        # Améliorations et âge.
        old_upgrades, old_age = players_before[owner]
        player = g["players"][owner]
        for name in player.get("upgrades", []):
            if name not in old_upgrades:
                entry("upgrade", f"Achète l'amélioration « {name} »")
        if player.get("age", 1) > old_age:
            entry("age", f"Passe à l'âge {player['age']}")

    # Attaques des héros pendant la production (et autres dégâts).
    hits = [h for h in fx_hits(before, g, -1) if h.get("damage")]
    for hit in hits:
        order = hero_orders.get(hit["id"])
        if order is not None:
            hero_name, hero_pos, owner = order
            kind = "melee" if distance(tuple(hero_pos), tuple(hit["pos"])) <= 1 else "arrow"
            entries.append({
                "turn": label, "round": turn, "owner": owner, "phase": "build",
                "kind": kind, "icon": FX_ICONS[kind],
                "text": f"{hero_name} ({coord(hero_pos)}) frappe {hit['name']} en {coord(hit['pos'])} → {fx_hit_text(hit)}",
                "shots": [{"from": hero_pos, "to": hit["pos"], "kind": kind}],
                "moves": [], "hits": [hit], "spawns": [], "auras": [],
            })
        else:
            entries.append({
                "turn": label, "round": turn, "owner": 1 - hit["owner"], "phase": "build",
                "kind": "impact", "icon": FX_ICONS["impact"], "text": fx_hit_text(hit),
                "shots": [], "moves": [], "hits": [hit], "spawns": [], "auras": [],
            })
    return entries


_lw_fx_previous_commit_plan = commit_plan


def commit_plan(bundle):
    g = bundle["game"]
    revealing = g["phase"] == "build" and bool(g.get("ready"))
    if not revealing:
        return _lw_fx_previous_commit_plan(bundle)

    before = fx_state(g)
    players_before = [
        (list(p.get("upgrades", [])), int(p.get("age", 1))) for p in g["players"]
    ]
    hero_orders = {}
    for draft in (bundle.get("committed"), bundle.get("draft")):
        for e in (draft or {}).get("entities", []):
            order = e.get("attack_order")
            if order and order.get("turn") == g["turn"]:
                hero_orders[order.get("target_id")] = (e["name"], [int(v) for v in e["pos"]], e["owner"])
    label, turn = turn_label(g), g["turn"]
    _lw_fx_previous_commit_plan(bundle)
    g = bundle["game"]
    g.pop("_fx_destroyed", None)
    if g["phase"] != "move":
        return
    try:
        entries = fx_production_entries(g, before, players_before, hero_orders, label, turn)
    except Exception:
        entries = []
    for entry in entries:
        fx_push(g, entry)


# --- Qui regarde le plateau : le joueur de cet écran.

def fx_viewer(bundle, g):
    if st.query_params.get("room"):
        seat = online_seat()
        return seat if seat in (0, 1) else g["active"]
    config = ai_config(bundle)
    if config is not None:
        return 1 - config["seat"]
    return g["active"]


def fx_recent(g, viewer):
    """Actions depuis la dernière manœuvre du joueur (elle comprise)."""
    journal = list(g.get("journal") or [])
    last_own = max(
        (i for i, e in enumerate(journal) if e.get("owner") == viewer and e.get("phase") == "move"),
        default=None,
    )
    if last_own is None:
        recent = journal[-FX_RECENT_MAX:]
    else:
        recent = journal[last_own:]
    # Rien de plus vieux que le tour précédent.
    recent = [e for e in recent if int(e.get("round", 0)) >= g["turn"] - 1]
    return recent[-FX_RECENT_MAX:]


def fx_owner_name(bundle, g, owner):
    faction = faction_of(g, owner)["name"]
    config = ai_config(bundle)
    if config is not None and owner == config["seat"]:
        return f"🤖 {faction}"
    names = (bundle or {}).get("names") or {}
    pseudo = names.get(str(owner)) or names.get(owner)
    room = online_active_room() if st.session_state.get("online_code") else None
    if room is not None:
        pseudo = (room.get("names") or {}).get(owner) or (room.get("names") or {}).get(str(owner)) or pseudo
    return f"{pseudo} · {faction}" if pseudo else faction


def fx_board_payload(bundle, g, viewer, recent):
    events = []
    for number, e in enumerate(recent, 1):
        events.append({
            "seq": e["seq"], "n": number, "kind": e.get("kind", "info"),
            "owner": e.get("owner"), "mine": e.get("owner") == viewer,
            "faction": faction_id(g, e["owner"]) if e.get("owner") in (0, 1) else None,
            "shots": e.get("shots", []), "moves": e.get("moves", []),
            "hits": e.get("hits", []), "spawns": e.get("spawns", []),
            "auras": e.get("auras", []), "text": e.get("text", ""),
        })
    game_id = (bundle or {}).get("game_id") or (bundle or {}).get("code") or ""
    return {
        "events": events, "viewer": viewer, "game": str(game_id),
        "deaths": fx_deaths(g),
        "harvest": fx_harvest(g),
    }


def fx_harvest(g):
    """Récolte de chaque base (ou héros), montrée pendant la production qui
    la suit : or en jaune, mana en orange au-dessus de la base."""
    h = g.get("last_harvest")
    if not h or h.get("turn") != g["turn"] or g["phase"] != "build" or not h.get("items"):
        return None
    return {"id": f"{h['turn']}:{h.get('seq', 0)}", "items": h["items"]}


def fx_phase_index(round_number, phase):
    return 2 * int(round_number) + (1 if phase == "move" else 0)


def fx_deaths(g):
    """Case(s) où une pièce est morte lors du DERNIER combat seulement
    (une seule case rouge avec sa croix), effacée au tour suivant."""
    now = fx_phase_index(g["turn"], g["phase"])
    for e in reversed(g.get("journal") or []):
        if now - fx_phase_index(e.get("round", 0), e.get("phase")) > 2:
            break
        # La cible abattue d'abord ; l'attaquant tué en riposte sinon.
        dead = sorted(
            (hit for hit in e.get("hits") or [] if hit.get("destroyed")),
            key=lambda hit: bool(hit.get("attacker")),
        )
        if dead:
            return [{"pos": dead[0]["pos"], "seq": e["seq"]}]
    return []


def fx_color_pf(text, css):
    """Met en couleur les « −N PF », « +N PF » et « détruit » d'un texte."""
    tokens = {
        t for t in text.replace("(", " ").replace(")", " ").split()
        if t.startswith("−") or (t.startswith("+") and t[1:2].isdigit())
    }
    for token in sorted(tokens, key=len, reverse=True):
        # PF regagnés (sorts de soutien) : toujours en vert.
        token_css = "lw-j-gain" if token.startswith("+") else css
        text = text.replace(token, f'<b class="{token_css}">{token}</b>')
    return text.replace("détruit", f'<b class="{css}">détruit</b>')


def render_journal(bundle, g, viewer, recent):
    journal = list(g.get("journal") or [])
    numbers = {e["seq"]: n for n, e in enumerate(recent, 1)}
    shown = journal[-JOURNAL_SHOWN:]

    def line_html(e, highlight=True):
        owner = e.get("owner")
        color = FX_FACTION_COLORS.get(faction_id(g, owner) if owner in (0, 1) else None, "#6b7280")
        number = numbers.get(e["seq"]) if highlight else None
        fresh = number is not None and owner != viewer
        badge = (
            f'<span class="lw-j-num" style="background:{color}">{number}</span>'
            if number is not None else '<span class="lw-j-num lw-j-old"></span>'
        )
        # En rouge : ce que l'attaquant inflige ; en orange : ce que le défenseur
        # lui inflige en riposte (après « pertes : »).
        dealt, _, taken = e.get("text", "").partition(" · pertes : ")
        text = fx_color_pf(escape(dealt), "lw-j-loss")
        if taken:
            text += " · pertes : " + fx_color_pf(escape(taken), "lw-j-riposte")
        return (
            f'<div class="lw-j-line{" lw-j-fresh" if fresh else ""}" style="border-left-color:{color}">'
            f'{badge}<span class="lw-j-turn">T{escape(str(e.get("turn", "")))}</span>'
            f'<span class="lw-j-who" style="color:{color}">{escape(fx_owner_name(bundle, g, owner))}</span>'
            f'<span class="lw-j-icon">{e.get("icon", "•")}</span>'
            f'<span class="lw-j-text">{text}</span>'
            + ('<span class="lw-j-new">NOUVEAU</span>' if fresh else "")
            + "</div>"
        )

    style = """
    <style>
    .lw-journal { border: 1px solid #d6d3d1; border-radius: 10px; padding: 8px 10px; margin: 4px 0 10px;
                  background: #fffdf7; max-height: 290px; overflow-y: auto; }
    .lw-journal h4 { margin: 0 0 6px; font-size: 15px; color: #1c1917; }
    .lw-j-line { display: flex; align-items: baseline; gap: 7px; padding: 3px 6px; margin: 2px 0;
                 border-left: 4px solid #6b7280; border-radius: 4px; font-size: 13.5px; line-height: 1.35;
                 color: #1c1917; background: #ffffff; }
    .lw-j-fresh { background: #fff7ed; box-shadow: inset 0 0 0 1px #fdba74; }
    .lw-j-num { flex: 0 0 auto; min-width: 20px; height: 20px; border-radius: 10px; color: #fff; font-weight: 800;
                font-size: 12px; text-align: center; line-height: 20px; align-self: center; }
    .lw-j-old { background: transparent; }
    .lw-j-turn { flex: 0 0 auto; color: #78716c; font-size: 12px; font-variant-numeric: tabular-nums; }
    .lw-j-who { flex: 0 0 auto; font-weight: 800; font-size: 12.5px; }
    .lw-j-icon { flex: 0 0 auto; }
    .lw-j-text { flex: 1 1 auto; }
    .lw-j-loss { color: #dc2626; }
    .lw-j-gain { color: #15803d; }
    .lw-j-riposte { color: #ea580c; }
    .lw-j-new { flex: 0 0 auto; background: #ea580c; color: #fff; font-size: 10px; font-weight: 800;
                padding: 1px 6px; border-radius: 8px; align-self: center; }
    .lw-j-empty { color: #78716c; font-size: 13px; }
    @media (prefers-color-scheme: dark) {
      .lw-journal { background: #1c1917; border-color: #44403c; }
      .lw-journal h4 { color: #f5f5f4; }
      .lw-j-line { background: #292524; color: #f5f5f4; }
      .lw-j-fresh { background: #431407; box-shadow: inset 0 0 0 1px #9a3412; }
      .lw-j-loss { color: #f87171; }
      .lw-j-gain { color: #4ade80; }
      .lw-j-riposte { color: #fb923c; }
    }
    </style>
    """
    if shown:
        body = "".join(line_html(e) for e in reversed(shown))
    else:
        body = '<div class="lw-j-empty">Aucune action pour l\'instant.</div>'
    st.markdown(
        style
        + '<div class="lw-journal"><h4>📜 Journal de bord — une ligne par action '
        + '<span style="font-weight:400;font-size:12px;color:#78716c">(les numéros renvoient au plateau)</span></h4>'
        + body + "</div>",
        unsafe_allow_html=True,
    )
    if len(journal) > len(shown):
        with st.expander(f"📜 Tout le journal de bord ({len(journal)} actions)"):
            st.markdown(
                style + '<div class="lw-journal" style="max-height:none">'
                + "".join(line_html(e, highlight=False) for e in reversed(journal)) + "</div>",
                unsafe_allow_html=True,
            )


_lw_fx_previous_render_board = render_board


def render_board(g, view, readonly=False):
    bundle = st.session_state.get("bundle")
    room = online_active_room() if st.query_params.get("room") else None
    if room is not None:
        bundle = room.get("bundle") or bundle
    viewer = fx_viewer(bundle, g)
    recent = fx_recent(g, viewer)
    with st.expander("📜 Journal de la partie (détaillé)"):
        for line in reversed(g.get("log", [])):
            st.text(line)
    render_journal(bundle, g, viewer, recent)
    render_phase_badge(g)
    payload = fx_board_payload(bundle, g, viewer, recent)
    st.session_state["_lw_fx"] = payload if recent or payload["deaths"] or payload["harvest"] else None
    return _lw_fx_previous_render_board(g, view, readonly)


# --- Contre l'IA : le message résume, le détail est dans le journal.
_lw_fx_previous_ai_autoplay = ai_autoplay


def ai_autoplay():
    before = st.session_state.get("bundle")
    seq = int(((before or {}).get("game") or {}).get("fx_seq", 0)) if isinstance(before, dict) else 0
    _lw_fx_previous_ai_autoplay()
    bundle = st.session_state.get("bundle")
    config = ai_config(bundle)
    if bundle is before or config is None:
        return
    message = st.session_state.get("ui_message") or ""
    if "problème" in message:
        return
    g = bundle["game"]
    done = [e for e in g.get("journal") or [] if e.get("seq", 0) > seq and e.get("owner") == config["seat"]]
    if done:
        st.session_state.ui_message = (
            f"🤖 {faction_of(g, config['seat'])['name']} (IA) a joué {len(done)} action(s) : "
            "détail ligne par ligne dans le journal de bord, au-dessus du plateau."
        )


# ============================================================
# PILE D'OUVRIERS : UN SEUL DÉFENSEUR
# Au corps à corps, les 1 à 3 ouvriers d'une case se défendent ensemble :
# défense = somme de leurs PF. Si l'attaque l'emporte, tous les ouvriers
# meurent d'un coup, l'attaquant perd cette somme et prend la case.
# Sinon, les dégâts tuent les ouvriers un par un (la cible d'abord).
# (Les tirs, eux, visent toujours un seul ouvrier.)
# ============================================================

def worker_stack_mates(g, target):
    """Les autres ouvriers de la pile de la cible (liste vide si seul)."""
    if g is None or target.get("name") != WORKER or not any(e is target for e in g["entities"]):
        return []
    pieces = pieces_at(g, tuple(target["pos"]))
    if len(pieces) < 2 or not is_worker_stack(g, pieces):
        return []
    return [p for p in pieces if p is not target]


_lw_stack_previous_combat_values = combat_values


def combat_values(attackers, target):
    mates = worker_stack_mates(_LW_COMBAT_GAME, target)
    if mates:
        total = float(target["pf"]) + sum(float(m["pf"]) for m in mates)
        target = dict(target, pf=total)
    return _lw_stack_previous_combat_values(attackers, target)


_lw_stack_previous_attack = attack


def attack(g, attacker_ids, target_id, occupier_id=None, losses=None, *args, **kwargs):
    target = entity(g, target_id)
    mates = worker_stack_mates(g, target)
    if not mates:
        return _lw_stack_previous_attack(g, attacker_ids, target_id, occupier_id, losses, *args, **kwargs)

    owner = g["active"]
    workers = [target] + mates
    original = {w["id"]: float(w["pf"]) for w in workers}
    total = sum(original.values())
    # Le combat se joue contre un seul défenseur qui porte toute la pile.
    g["entities"] = [e for e in g["entities"] if all(e is not m for m in mates)]
    target["pf"] = total
    try:
        _lw_stack_previous_attack(g, attacker_ids, target_id, occupier_id, losses, *args, **kwargs)
    except Exception:
        target["pf"] = original[target["id"]]
        g["entities"].extend(mates)
        raise

    survived = any(e is target for e in g["entities"])
    damage = total - (float(target["pf"]) if survived else 0.0)
    if not survived:
        # Victoire : toute la pile tombe d'un coup.
        for mate in mates:
            g["entities"].append(mate)
            destroy(g, mate, owner)
        log(g, f"Les {len(workers)} ouvriers de la case sont détruits d'un coup.")
        return

    # Défaite ou attaque invisible : dégâts répartis ouvrier par ouvrier.
    remaining = damage
    target["pf"] = original[target["id"]]
    g["entities"].extend(mates)
    for worker in workers:
        hit = min(float(worker["pf"]), remaining)
        worker["pf"] = float(worker["pf"]) - hit
        remaining -= hit
    for worker in workers:
        if worker["pf"] <= 0 and any(e is worker for e in g["entities"]):
            destroy(g, worker, owner)


# ============================================================
# ATTAQUE GROUPÉE AU CORPS À CORPS : CHACUN AU CONTACT
# Les attaquants qui ne prennent pas la case s'arrêtent chacun sur une
# case libre voisine de la cible (atteignable avec leur mouvement), au
# lieu de rester à leur case de départ. Les tireurs restent sur place.
# ============================================================

_lw_group_previous_attack = attack


def attack(g, attacker_ids, target_id, occupier_id=None, losses=None, *args, **kwargs):
    target_pos = tuple(entity(g, target_id)["pos"])
    plans = {}
    for eid in attacker_ids:
        unit = next((e for e in g["entities"] if e["id"] == eid), None)
        if unit is None or eid == occupier_id or is_shooter(unit):
            continue
        origin = tuple(unit["pos"])
        if distance(origin, target_pos) <= 1:
            continue  # déjà au contact
        try:
            costs, routes = paths(g, unit)
        except AI_ERRORS:
            continue
        options = {
            tuple(p): (c, [tuple(s) for s in routes.get(p, [origin, p])])
            for p, c in costs.items()
            if distance(tuple(p), target_pos) == 1
        }
        if options:
            plans[eid] = (origin, options)

    _lw_group_previous_attack(g, attacker_ids, target_id, occupier_id, losses, *args, **kwargs)
    if not plans:
        return

    fx_routes = dict(g.get("_fx_routes") or {})
    taken = set()
    for eid in attacker_ids:
        if eid not in plans:
            continue
        unit = next((e for e in g["entities"] if e["id"] == eid), None)
        origin, options = plans[eid]
        if unit is None or tuple(unit["pos"]) != origin:
            continue  # mort au combat, ou déjà déplacé (piétinement…)
        preferred = tuple(fx_routes.get(eid, [None, None])[-2] or ()) if fx_routes.get(eid) else None
        free = [
            p for p in options
            if p not in taken and at(g, p) is None and not blocked(g, p)
        ]
        if not free:
            continue
        spot = preferred if preferred in free else min(free, key=lambda p: (options[p][0], p))
        taken.add(spot)
        unit["pos"] = list(spot)
        fx_routes[eid] = [list(p) for p in options[spot][1]] + [list(target_pos)]
        log(g, f"{unit['name']} #{eid} s'arrête au contact, en {coord(spot)}.")
    g["_fx_routes"] = fx_routes


# ============================================================
# FIN DE PARTIE : BANDEROLE ET IMAGE SUR LE PLATEAU
# Le plateau final reste affiché, avec une banderole qui dit pourquoi la
# partie est gagnée et, juste en dessous, UNE image : celle de la faction
# gagnante, ou celle de l'abandon. Elle reste jusqu'au retour à l'accueil.
# ============================================================

def victory_banner_text(g):
    winner = g["winner"]
    faction = faction_of(g, winner)["name"]
    loser = game_forfeiter(g)
    if loser is not None:
        return f"Les {faction_of(g, loser)['name']} abandonnent : les {faction} remportent la victoire !"
    if g.get("victory_mode") == "bases":
        count = int(g["players"][winner].get("bases", 0))
        return f"Les {faction} ont détruit {count} bases ennemies : ils remportent la victoire !"
    points = g["players"][winner].get("pv", 0)
    return f"Fin du temps : les {faction} remportent la victoire avec {float(points):g} PV !"


def victory_image_uri(g):
    """L'image de fin : abandon, sinon celle de la faction gagnante."""
    if game_forfeiter(g) is not None:
        image = abandon_image_data()
    else:
        image = faction_victory_image_data(faction_of(g, g["winner"])["name"]) or victory_image_data()
    return f"data:image/jpeg;base64,{image}" if image else None


def render_victory_screen(g):
    st.session_state["_lw_victory_banner"] = {
        "text": victory_banner_text(g),
        "faction": faction_id(g, g["winner"]),
        "image": victory_image_uri(g),
    }
    try:
        render_board(g, g, readonly=True)
    finally:
        st.session_state.pop("_lw_victory_banner", None)
    # Résultat ajouté au profil du joueur (une seule fois par partie).
    bundle = st.session_state.get("bundle")
    if isinstance(bundle, dict) and isinstance(bundle.get("game"), dict) and bundle["game"].get("winner") is not None:
        before = list(bundle.get("stats_recorded", []))
        record_finished_game(bundle)
        if bundle.get("stats_recorded", []) != before and current_player_name():
            st.caption(f"📊 Résultat enregistré dans le profil de {current_player_name()}.")


# ============================================================
# RAMPANT : JAMAIS DE CORPS À CORPS
# Il n'attaque que par son tir en ligne, une fois planté.
# ============================================================

_lw_ramp_previous_prepare_attack = prepare_attack


def prepare_attack(g, attacker_ids, target_id):
    for eid in attacker_ids:
        if entity(g, eid)["name"] == RAMPANT:
            raise ValueError(
                "Le Rampant n'attaque pas au corps à corps : planté, il tire en ligne."
            )
    return _lw_ramp_previous_prepare_attack(g, attacker_ids, target_id)


# ============================================================
# UNITÉS DE CORPS À CORPS : PAS DE RIPOSTE CONTRE UN TIREUR
# Une unité sans tir (Ravageur, Silencieux, Déferlant…) ne riposte pas
# quand un tireur l'attaque, même au contact : seules les attaques au
# corps à corps d'unités de mêlée entraînent sa riposte.
# ============================================================

def melee_only(piece):
    return piece.get("kind") == "unit" and UNITS.get(piece.get("name"), {}).get("range", 0) <= 0


_lw_shooter_previous_combat_values = combat_values


def combat_values(attackers, target):
    values = _lw_shooter_previous_combat_values(attackers, target)
    if not (attackers and melee_only(target) and all(is_shooter(a) for a in attackers)):
        return values
    # Même traitement que les catapultes : aucune perte pour les tireurs.
    values = dict(values, hidden=True, no_riposte=target["name"], losses=0.0)
    if not values["winnable"]:
        values["defender_damage"] = values["power"]
        values["defender_remaining"] = values["defense"] - values["power"]
    return values

# ============================================================
# LIMITES D'UNITÉS : +30 % POUR TOUTES LES FACTIONS
# Arrondi à l'entier le plus proche (les unités uniques restent à 1) ;
# pour les unités recrutées par lots, au multiple du lot le plus proche
# (le dernier lot reste toujours recrutable).
# ============================================================

UNIT_LIMIT_BONUS = 1.30


def raised_limit(limit, batch=1):
    batch = max(1, int(batch))
    return max(int(limit), batch * math.floor(limit * UNIT_LIMIT_BONUS / batch + 0.5))


for _name, _data in UNITS.items():
    if _name == WORKER:
        continue
    _data["limit"] = raised_limit(_data["limit"], _data.get("batch", 1))
WORKER_LIMIT = raised_limit(WORKER_LIMIT)
UNITS[WORKER]["limit"] = WORKER_LIMIT


# ============================================================
# RÉCOLTE : BARÈME PAR FACTION ET PAR ÂGE
# Chaque base récolte, par tour, l'or OU le mana des cases voisines
# (× le multiplicateur de la meilleure case de ce type).
# Derniers nés : il faut au moins un ouvrier sur la case pour récolter.
# Vagabonds : chaque héros récolte la case de son marqueur.
# ============================================================

HARVEST_BY_AGE = {
    #              âge : (or, mana) par base et par tour
    DEFERLANTS: {1: (100, 1), 2: (150, 1), 3: (200, 2)},
    EXILES: {1: (125, 1), 2: (150, 1), 3: (200, 2)},
    DERNIERS_NES: {1: (125, 1), 2: (200, 1), 3: (250, 2)},
}
for _fid, _table in HARVEST_BY_AGE.items():
    FACTIONS[_fid]["income"] = _table[1][0]


def harvest_income(g, owner):
    """(or, mana) que rapporte une base de ce joueur, à son âge actuel."""
    age = int(g["players"][owner].get("age", 1))
    table = HARVEST_BY_AGE.get(faction_id(g, owner))
    if table is None:
        return {1: (faction_of(g, owner)["income"], 1), 2: (200, 2), 3: (300, 3)}[age]
    return table[age]


# Derniers nés : la récolte dépend du nombre d'ouvriers sur les cases de
# ressource voisines de la base (plafonné par le niveau de la base : 1
# ouvrier pour la Colonie, 2 pour la Ville, 3 pour la Forteresse).
DN_GOLD_BY_WORKERS = {1: 125, 2: 200, 3: 250}
DN_MANA_BY_WORKERS = {1: 1, 2: 1, 3: 2}
HARVEST_BY_AGE[DERNIERS_NES] = {
    n: (DN_GOLD_BY_WORKERS[n], DN_MANA_BY_WORKERS[n]) for n in (1, 2, 3)
}


# Héros Vagabonds : (or, mana) récoltés par tour sur la case du marqueur.
HERO_HARVEST = {
    "De Marbourg": {1: (200, 1), 2: (250, 1), 3: (500, 2)},
    "Sayn": {1: (125, 1), 2: (150, 1), 3: (175, 2)},
    "Wulfoad": {1: (125, 1), 2: (150, 1), 3: (175, 2)},
    "Campbell": {2: (250, 1), 3: (350, 2)},
    "Aalongue": {3: (400, 2)},
}
for _hero, _ages in HERO_HARVEST.items():
    for _age, (_gold, _mana) in _ages.items():
        if _age in HERO_STATS[_hero]:
            _pf, _move, _reach, _, _ = HERO_STATS[_hero][_age]
            HERO_STATS[_hero][_age] = (_pf, _move, _reach, _gold, _mana)


# --- Ce que chaque base (ou héros) récolte : affiché sur le plateau.
_lw_harvestfx_previous_collect = collect_adjacent_resources


def collect_adjacent_resources(g, base):
    player = g["players"][base["owner"]]
    before = (player["gold"], player["mana"])
    result = _lw_harvestfx_previous_collect(g, base)
    gold, mana = player["gold"] - before[0], player["mana"] - before[1]
    items = g.get("_harvest_items")
    if items is not None and (gold or mana):
        items.append({
            "pos": [int(v) for v in base["pos"]], "owner": base["owner"],
            "gold": gold, "mana": mana,
        })
    return result


_lw_harvestfx_previous_harvest = harvest


def harvest(g):
    g["_harvest_items"] = []
    try:
        _lw_harvestfx_previous_harvest(g)
    finally:
        items = g.pop("_harvest_items", [])
    g["last_harvest"] = {"turn": g["turn"], "seq": int(g.get("fx_seq", 0)), "items": items}


# --- Textes de référence (âges) alignés sur le barème de récolte.
import re as _re


def _harvest_text(gold, mana):
    return f"récolte {gold} or ou {mana} mana par tour"


_BASE_NAMES = {"Incubateur", "Habitations", "Colonie", "Ville", "Forteresse"}
for _fname, _fid in (("Déferlants", DEFERLANTS), ("Exilés", EXILES), ("Derniers nés", DERNIERS_NES)):
    for _age, _entries in AGE_REFERENCE.get(_fname, {}).items():
        for _i, (_name, _text) in enumerate(_entries):
            if _name not in _BASE_NAMES:
                continue
            _gold, _mana = HARVEST_BY_AGE[_fid][_age]
            _text = _re.sub(r" · (collecte|récolte)[^·]*", "", _text)
            _note = (
                f" (avec {_age} ouvrier{'s' if _age > 1 else ''} sur la case)"
                if _fid == DERNIERS_NES else ""
            )
            _entries[_i] = (_name, f"{_text} · {_harvest_text(_gold, _mana)}{_note}")
            break
for _age, _entries in AGE_REFERENCE.get("Vagabonds", {}).items():
    for _i, (_name, _text) in enumerate(_entries):
        _harvest = HERO_HARVEST.get(_name, {}).get(_age)
        if _harvest:
            _text = _re.sub(r"(récolte )?\d+ or ou \d+ mana", _harvest_text(*_harvest), _text)
            _entries[_i] = (_name, _text)


# ============================================================
# EXILÉS : CONSTRUIRE DE L'AUTRE CÔTÉ DE LA LIGNE NOIRE
# Une construction (bâtiment ou base) du côté adverse de la ligne en
# pointillés coûte 3 fois son prix en or et 3 mana. (Le recrutement
# d'unités garde son surcoût de +50 %.)
# ============================================================

EXILE_FAR_BUILD_GOLD = 3
EXILE_FAR_BUILD_MANA = 3

_lw_exilefar_previous_placement_cost = placement_cost


def placement_cost(view, owner, mode, name, positions, accelerated=False):
    if (
        mode == "build" and positions
        and faction_id(view, owner) == EXILES
        and enemy_side_of_line(owner, tuple(positions[0]))
    ):
        gold, mana = _lw_exilefar_previous_placement_cost(view, owner, mode, name, [], accelerated)
        return gold * EXILE_FAR_BUILD_GOLD, mana + EXILE_FAR_BUILD_MANA
    return _lw_exilefar_previous_placement_cost(view, owner, mode, name, positions, accelerated)


# ============================================================
# LIMITE PAR ÂGE (fiche des Déferlants : 26, « AGE II 16 », « AGE III 10 »)
# La limite compte toutes les unités recrutées depuis le début de la partie
# et devient celle de l'âge atteint : au-delà, plus de recrutement.
# ============================================================

UNIT_LIMITS_BY_AGE = {
    "Déferlant": {1: raised_limit(20, 2), 2: raised_limit(12, 2), 3: raised_limit(8, 2)},
}


def unit_limit(g, owner, name):
    """Limite de l'unité pour ce joueur, à son âge actuel."""
    by_age = UNIT_LIMITS_BY_AGE.get(name)
    if by_age:
        return by_age[int(g["players"][owner].get("age", 1))]
    return UNITS[name]["limit"]


_lw_agelimit_previous_recruit = recruit


def recruit(g, owner, producer_id, name, positions, *args, **kwargs):
    if name in UNIT_LIMITS_BY_AGE:
        built = g["players"][owner]["units_built"].get(name, 0)
        batch = recruitment_batch(g, owner, name)
        limit = unit_limit(g, owner, name)
        if built + batch > limit:
            raise ValueError(
                f"Limite de {name}s atteinte pour l'âge {g['players'][owner]['age']} : "
                f"{limit} au total ({built} déjà recrutés)."
            )
    return _lw_agelimit_previous_recruit(g, owner, producer_id, name, positions, *args, **kwargs)


# ============================================================
# EXILÉS : COÛT DE LA CONSTRUCTION SUR CHAQUE CASE DE PLACEMENT
# Pendant le placement d'un bâtiment ou d'une base, chaque case verte
# affiche ce qu'elle coûterait : prix normal, ou ×3 + 3 mana (en
# surbrillance) de l'autre côté de la ligne noire.
# ============================================================

def exile_build_costs(g, view, readonly):
    if readonly or g["phase"] != "build" or st.session_state.get("ui_plan_mode") != "build":
        return None
    owner = g["active"]
    name = st.session_state.get("ui_plan_name")
    if not name or faction_id(view, owner) != EXILES:
        return None
    accelerated = bool(st.session_state.get("ui_plan_accelerated"))
    costs = {}
    for pos in planning_slots(g, view):
        try:
            gold, mana = placement_cost(view, owner, "build", name, [pos], accelerated)
        except (ValueError, KeyError):
            continue
        costs[key(pos)] = {"gold": gold, "mana": mana, "far": enemy_side_of_line(owner, tuple(pos))}
    return costs or None


_lw_cellcost_previous_render_board = render_board


def render_board(g, view, readonly=False):
    st.session_state["_lw_cell_costs"] = exile_build_costs(g, view, readonly)
    try:
        return _lw_cellcost_previous_render_board(g, view, readonly)
    finally:
        st.session_state.pop("_lw_cell_costs", None)


# ============================================================
# ARMES DE SIÈGE : JAMAIS DE RIPOSTE CONTRE ELLES
# Catapulte, Trébuchet, Catapulte de l'enfer et Golem de pierre tirent
# sans subir de dégâts en retour (ni des unités, ni des bases).
# ============================================================

SIEGE_WEAPONS = set(SIEGE_WEAPONS) | {STONE_GOLEM}

_lw_siegeshot_previous_ranged_riposte = ranged_riposte


def ranged_riposte(g, attacker, target):
    if attacker.get("name") in SIEGE_WEAPONS:
        return 0.0
    return _lw_siegeshot_previous_ranged_riposte(g, attacker, target)


_lw_siegeshot_previous_ranged_riposte_text = ranged_riposte_text


def ranged_riposte_text(g, attacker, target):
    if attacker.get("name") in SIEGE_WEAPONS:
        return "Arme de siège : aucune riposte."
    return _lw_siegeshot_previous_ranged_riposte_text(g, attacker, target)


# ============================================================
# TIRS AU SOL : PAS D'UNITÉS VOLANTES
# Catapulte, Trébuchet, Catapulte de l'enfer, Golem de pierre et Rampant
# ne peuvent pas viser une unité volante, et leurs dégâts de zone ne
# touchent pas les unités volantes (tir automatique du Trébuchet compris).
# ============================================================

GROUND_ONLY_SHOOTERS = {CATAPULT, TREBUCHET, HELL_CATAPULT, STONE_GOLEM, RAMPANT}


def flying_enemy(piece, owner):
    return piece.get("kind") == "unit" and piece.get("owner") != owner and is_flying(piece)


_lw_ground_previous_ranged_values = ranged_attack_values


def ranged_attack_values(g, attacker, target):
    if attacker.get("name") in GROUND_ONLY_SHOOTERS and flying_enemy(target, attacker["owner"]):
        raise ValueError(f"{attacker['name']} : impossible de viser une unité volante.")
    return _lw_ground_previous_ranged_values(g, attacker, target)


_lw_ground_previous_ranged_attack = ranged_attack


def ranged_attack(g, attacker_id, target_id, *args, **kwargs):
    attacker = entity(g, attacker_id)
    if attacker["name"] not in GROUND_ONLY_SHOOTERS:
        return _lw_ground_previous_ranged_attack(g, attacker_id, target_id, *args, **kwargs)
    target = entity(g, target_id)
    if flying_enemy(target, attacker["owner"]):
        raise ValueError(f"{attacker['name']} : impossible de viser une unité volante.")
    # Les unités volantes ennemies sont mises de côté pendant le tir : les
    # dégâts de zone (cases voisines, ligne du Golem) ne les atteignent pas.
    flyers = [e for e in g["entities"] if flying_enemy(e, attacker["owner"])]
    g["entities"] = [e for e in g["entities"] if all(e is not f for f in flyers)]
    try:
        return _lw_ground_previous_ranged_attack(g, attacker_id, target_id, *args, **kwargs)
    finally:
        g["entities"].extend(flyers)


_lw_ground_previous_trebuchet_auto_fire = trebuchet_auto_fire


def trebuchet_auto_fire(g, mover, route):
    if is_flying(mover):
        return  # le Trébuchet ne tire pas sur une unité volante
    # Ses éclats sur les cases voisines épargnent aussi les unités volantes.
    flyers = [
        e for e in g["entities"]
        if e is not mover and e.get("kind") == "unit" and e["owner"] == mover["owner"] and is_flying(e)
    ]
    g["entities"] = [e for e in g["entities"] if all(e is not f for f in flyers)]
    try:
        return _lw_ground_previous_trebuchet_auto_fire(g, mover, route)
    finally:
        g["entities"].extend(flyers)


# ============================================================
# MENU DE GAUCHE RÉORGANISÉ
# 1. Informations générales (partie, objectif, fiches, sauvegarde)
# 2. Actions du joueur (annuler, terminer la phase, commandes)
# 3. Pièce sélectionnée : PF, déplacement, portée, capacités
# ============================================================

# Capacités particulières de chaque unité (affichées dans la fiche).
UNIT_BONUS = {
    # Déferlants
    "Déferlant": ["Unité de base des Déferlants, recrutée par 2 à la Mare.",
                  "Peut muter en Kamikaze (amélioration Mutation kamikaze)."],
    "Kamikaze": ["💥 Explose sur sa cible : 2 PF sur la cible, 1 PF à gauche et à droite.",
                 "Il disparaît en explosant."],
    "Aspergeur": ["Tir à distance.", "Peut muter en Rampant (amélioration Rampants)."],
    "Rampant": ["Se plante dans le sol (fin d'activation) : invisible, sauf détecteur à portée.",
                "Planté, il tire en ligne : 4 PF sur la cible et les 2 cases derrière elle.",
                "N'attaque jamais au corps à corps ; ne vise pas les unités volantes."],
    "Enragé": ["Frappe la cible et ses 2 voisines (3 PF chacune), alliés compris !"],
    "Costaud": ["N'attaque que les bâtiments et les bases."],
    "Molosse": ["Frappe aussi une 2e case au contact de la cible.",
                "Les unités d'âge I ne lui infligent que la moitié des dégâts."],
    "Volant": ["Unité volante : hors d'atteinte du corps à corps.",
               "Piétinement contre les unités d'âge I."],
    "Décimant": ["N'attaque pas : il lance des sorts.",
                 *[f"{v}" for v in DECIMANT_SPELLS.values()]],
    # Exilés
    "Tigre des forêts": ["Rapide au corps à corps.",
                         "Meute de tigres : recrutés par 2, ils piétinent l'âge I."],
    "Elfe": ["Tir à distance.",
             "Instinct elfique : touche aussi la case derrière la cible."],
    "Réveil des morts": ["Recrutés par 4."],
    "Gobelin": ["Vole la récolte d'une case ennemie, puis la dépose près d'une de tes bases."],
    "Mage des montagnes": ["2 sorts, un tous les 2 tours :",
                           "🐌 Ralentissement : −50 % de déplacement à 3 unités ennemies.",
                           "💥 Sort de dégâts : −2 PF à 2 unités ennemies."],
    "Aramil": ["Garde les 2 sorts du Mage.",
               "🔥 Incendie 2 bâtiments ennemis à portée.",
               "🌀 Appelle le Titan Aragnak pour 1 tour."],
    "Dragon": ["Unité volante, tir à distance (souffle de feu)."],
    "Titan Aragnak": ["Appelé par Aramil pour 1 tour.", "Traverse les montagnes (1 MVT)."],
    "Mammouth dompté": ["Frappe 3 cases : 10 PF sur la cible, 5 PF sur 2 voisines.",
                        "Développement musculaire : +3 PF."],
    "Nain des montagnes": ["Leader : quand il attaque, les 2 alliés à ses côtés attaquent avec lui."],
    "Golem de pierre": ["Arme de siège : tir en ligne à 3 ou 4 cases, touche 3 cases l'une derrière l'autre.",
                        "Vise uniquement des unités, jamais les unités volantes.",
                        "Ne subit jamais de riposte."],
    "Daeron et Finwe": ["Unité volante et invisible, sauf détecteur à portée.",
                        "Rend invisibles les unités alliées à 1 case."],
    "Daeron": ["Unité volante et invisible, sauf détecteur à portée."],
    "Finwe": ["Unité volante et invisible, sauf détecteur à portée."],
    # Derniers nés
    "Ouvrier": ["Se déplace pendant la production ; construit bâtiments et bases.",
                "Récolte : 1 à 3 ouvriers par case, selon le niveau de la base (Colonie 1, Ville 2, Forteresse 3)."],
    "Guerrier": ["Frappe 2 cases ennemies.", "Marteau foudroyant : +0,5 PF en attaque."],
    "Éclaireur": ["Très rapide.", "Sabote une base ennemie : elle ne récolte pas.",
                  "N'attaque pas les bases.", "Esquive : traverse les unités ennemies sans dégâts."],
    "Chevalier": ["Piétinement contre les unités d'âge I."],
    "Archer": ["Tir à 1 à 3 cases.", "Flèches enflammées : touche 2 cases voisines."],
    "Catapulte": ["Arme de siège : tir à 3-4 cases, 4 PF sur la cible et 2 PF à gauche et à droite.",
                  "1 tir tous les 2 tours ; ne vise pas les unités volantes.",
                  "Ne riposte jamais et ne subit jamais de riposte.",
                  "Peut devenir Trébuchet (amélioration Trébuchet)."],
    "Trébuchet": ["Immobile ; tir à 4-5 cases.",
                  "Tir automatique sur toute unité ennemie (non volante) qui passe à 4-5 cases : 4 PF, 2 PF sur les côtés.",
                  "Redevient Catapulte en 1 tour pour se déplacer.",
                  "Ne subit jamais de riposte."],
    "Catapulte de l'enfer": ["Arme de siège : tir à 3-5 cases, 6 PF sur la cible et la case de derrière.",
                             "Ne vise pas les unités volantes.",
                             "Ne riposte jamais et ne subit jamais de riposte."],
    "Dirigeable": ["Volant ; transporte jusqu'à 3 unités.", "N'attaque pas ; détecte les unités invisibles.",
                   *[f"{v}" for v in AIRSHIP_SPELLS.values()]],
    "Griffon": ["Volant ; tir à 3 cases, touche 2 cases.",
                "Invisibilité griffons : invisible, sauf détecteur à portée."],
    "Roi Théobald": ["Invisible, sauf détecteur à portée.", "Piétinement contre les âges I et II."],
    # Vagabonds
    "Errant": ["Esprit ; 5 Errants fusionnent en Super Errant (7 PF)."],
    "Ravageur": ["Esprit ; 4 Ravageurs fusionnent en Super Ravageur (10 PF)."],
    "Super Errant": ["Fusion de 5 Errants ; une seule par partie."],
    "Super Ravageur": ["Fusion de 4 Ravageurs ; une seule par partie."],
    "Sorcier": ["N'attaque pas : il lance des sorts.", *[f"{v}" for v in SORCERER_SPELLS.values()]],
    "Agile": ["Mutation imminente : les Agiles volent."],
    "Barbare": ["Piétinement contre l'âge I.", "Endurance : +1 PF et +1 déplacement."],
    "Voyant": ["Détecteur : révèle les unités invisibles à portée."],
    "Silencieux": ["Invisible, sauf détecteur à portée."],
    "Destruction": ["Fusion de 2 Barbares."],
    "Parfait": ["Unité volante ; la plus puissante des Vagabonds."],
}
HERO_BONUS = {
    "De Marbourg": ["N'attaque pas : 2 PF de défense seulement."],
    "Aalongue": ["Détecteur ; ne combat pas.",
                 "Téléporte 4 unités sur les cases voisines.",
                 "Motivation : +1 déplacement à toutes les unités pendant 1 tour."],
}


def piece_range_text(name):
    if name in SIEGE_RANGES:
        low, high = SIEGE_RANGES[name]
        return f"Tir à distance : {low} à {high} cases"
    if name == STONE_GOLEM:
        return "Tir à distance : 3 à 4 cases (en ligne)"
    reach = UNITS.get(name, {}).get("range", 0)
    if name in MAGES or name == DECIMANT:
        return f"Sorts à {reach} cases (pas de tir normal)"
    if name in NO_ATTACK_UNITS:
        return "N'attaque pas" + (f" (sorts à {reach} cases)" if reach else "")
    return f"Tir à distance : {reach} case{'s' if reach > 1 else ''}" if reach > 0 else "Corps à corps"


def render_selected_card(g, view):
    st.markdown("### 📋 Pièce sélectionnée")
    piece = selected_entity(view)
    if piece is None:
        st.caption("Clique sur une unité ou un bâtiment du plateau pour voir ses caractéristiques.")
        return
    owner_name = faction_of(view, piece["owner"])["name"]
    st.markdown(f"**{piece['name']}** — {owner_name} · {coord(piece['pos'])}")
    lines = []
    max_pf = piece.get("max_pf")
    pf_text = f"{float(piece['pf']):g}" + (f" / {float(max_pf):g}" if max_pf and float(max_pf) != float(piece["pf"]) else "")
    if piece.get("attack_bonus"):
        pf_text += f" (+{float(piece['attack_bonus']):g} en attaque)"
    lines.append(f"❤️ **PF** : {pf_text}")
    if is_hero(piece):
        pf, move, reach, gold, mana = hero_stats(view, piece)
        lines.append(f"🦶 **Déplacement** : {move} cases")
        lines.append("🎯 **Portée** : " + (f"tir à {reach} cases" if reach else "corps à corps"))
        lines.append(f"💰 **Récolte** : {gold} or ou {mana} mana par tour (case du marqueur)")
        bonus = ["Héros : compte comme une base ; produit des unités.",
                 "Récolte la dernière case d'or ou de mana traversée (son marqueur).",
                 "Attaque pendant la production, sans riposte."] + HERO_BONUS.get(piece["name"], [])
    elif piece["kind"] == "unit":
        data = UNITS.get(piece["name"], {})
        move_text = f"{data.get('move', 0)} cases"
        if g["phase"] == "move" and piece["owner"] == g["active"]:
            try:
                move_text += f" (reste {remaining_actions(g, piece)} ce tour)"
            except Exception:
                pass
        lines.append(f"🦶 **Déplacement** : {move_text}")
        lines.append(f"🎯 **Portée** : {piece_range_text(piece['name'])}")
        traits = []
        if is_flying(piece):
            traits.append("volant")
        if piece["name"] in INVISIBLE_UNITS or (piece["name"] == RAMPANT and piece.get("planted")):
            traits.append("invisible")
        if traits:
            lines.append("✨ **Type** : " + ", ".join(traits))
        bonus = UNIT_BONUS.get(piece["name"], [])
    else:
        kind = "Base" if piece["kind"] == "base" else "Bâtiment"
        lines.append(f"🏠 **Type** : {kind}")
        units = faction_of(view, piece["owner"])["buildings"].get(piece["name"], {}).get("units", [])
        if units:
            lines.append("🪖 **Produit** : " + ", ".join(units))
        if piece.get("wait"):
            lines.append(f"⏳ **Disponible dans** : {piece['wait']} fin(s) de tour")
        bonus = []
    st.markdown("  \n".join(lines))
    if bonus:
        st.markdown("**Capacités**")
        st.markdown("\n".join(f"- {line}" for line in bonus))


def age_advance_possible(view, owner, target_age):
    """Le passage d'âge réussirait-il ? (essai sur une copie)"""
    try:
        advance_age(copy.deepcopy(view), owner, target_age)
        return True
    except Exception:
        return False


def can_pay(view, owner, gold, mana=0):
    player = view["players"][owner]
    return player["gold"] >= gold and player["mana"] >= mana


SIDEBAR_CSS = """
<style>
/* Rubriques du menu de gauche */
section[data-testid="stSidebar"] .st-key-lw_side_info,
section[data-testid="stSidebar"] .st-key-lw_side_actions,
section[data-testid="stSidebar"] .st-key-lw_side_unit {
    background: #fffdf7;
}
section[data-testid="stSidebar"] h3 { margin-top: 0 !important; }

/* Actions possibles en vert, impossibles en rouge (toutes les factions). */
section[data-testid="stSidebar"] [class*="_choose_recruit_"] button,
section[data-testid="stSidebar"] [class*="_choose_build_"] button,
section[data-testid="stSidebar"] [class*="_choose_fast_"] button,
section[data-testid="stSidebar"] [class*="_workers_"] button,
section[data-testid="stSidebar"] [class*="_worker_build_"] button,
section[data-testid="stSidebar"] [class*="_worker_fast_"] button,
section[data-testid="stSidebar"] [class*="_upgrade_"] button,
section[data-testid="stSidebar"] [class*="_mutate_"] button,
section[data-testid="stSidebar"] [class*="_kamikaze_"] button,
section[data-testid="stSidebar"] [class*="_fusion_go_"] button,
section[data-testid="stSidebar"] [class*="_advance_age_ok_"] button {
    background: #15803d !important;
    border-color: #166534 !important;
    color: #ffffff !important;
}
section[data-testid="stSidebar"] [class*="_choose_"] button:hover,
section[data-testid="stSidebar"] [class*="_upgrade_"] button:hover,
section[data-testid="stSidebar"] [class*="_advance_age_ok_"] button:hover {
    filter: brightness(1.12);
}
section[data-testid="stSidebar"] [class*="_choose_recruit_"] button:disabled,
section[data-testid="stSidebar"] [class*="_choose_build_"] button:disabled,
section[data-testid="stSidebar"] [class*="_choose_fast_"] button:disabled,
section[data-testid="stSidebar"] [class*="_workers_"] button:disabled,
section[data-testid="stSidebar"] [class*="_worker_build_"] button:disabled,
section[data-testid="stSidebar"] [class*="_worker_fast_"] button:disabled,
section[data-testid="stSidebar"] [class*="_upgrade_"] button:disabled,
section[data-testid="stSidebar"] [class*="_mutate_"] button:disabled,
section[data-testid="stSidebar"] [class*="_kamikaze_"] button:disabled,
section[data-testid="stSidebar"] [class*="_fusion_go_"] button:disabled,
section[data-testid="stSidebar"] [class*="_advance_age_ko_"] button {
    background: #b91c1c !important;
    border-color: #7f1d1d !important;
    color: #ffffff !important;
    opacity: 0.9 !important;
}
/* Choix en cours : liseré jaune. */
section[data-testid="stSidebar"] [class*="_choose_"] button[data-testid="stBaseButton-primary"] {
    box-shadow: 0 0 0 3px #facc15 !important;
}
section[data-testid="stSidebar"] [class*="_choose_"] button p,
section[data-testid="stSidebar"] [class*="_upgrade_"] button p,
section[data-testid="stSidebar"] [class*="_advance_age_"] button p { color: inherit !important; }

/* Terminer la phase : toujours rouge, toujours au même endroit. */
.st-key-lw_end_phase button {
    background: #dc2626 !important;
    border-color: #991b1b !important;
    color: #ffffff !important;
    font-weight: 800 !important;
}
.st-key-lw_end_phase button:disabled { background: #fca5a5 !important; border-color: #f87171 !important; }
.st-key-lw_end_phase button p { color: inherit !important; }
</style>
"""


def render_sidebar(bundle):
    g = bundle["game"]
    view = bundle["draft"] if g["phase"] == "build" and bundle.get("draft") is not None else g
    online = bool(st.query_params.get("room"))
    with st.sidebar:
        st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)

        # 1. Informations générales
        with st.container(border=True, key="lw_side_info"):
            st.markdown("### ℹ️ Informations générales")
            if ai_config(bundle) is not None:
                st.markdown(f"🤖 **Adversaire** : IA — {ai_label(bundle)}")
            phase = "🛠️ Production" if g["phase"] == "build" else "⚔️ Manœuvres"
            st.markdown(f"**Tour {g['turn']}** · {phase}")
            if g["winner"] is None:
                st.caption(f"Joueur actif : {faction_of(g, g['active'])['name']}")
            if g.get("victory_mode") == "bases":
                st.markdown("🏰 **Victoire** : 3 bases ennemies détruites")
                st.caption(" · ".join(
                    f"{faction_of(g, owner)['name']} : {g['players'][owner]['bases']}/3" for owner in (0, 1)
                ))
            else:
                st.markdown("⏱️ **Victoire** : meilleur score en PV à la fin du temps")
                seconds = max(0, math.ceil(g["remaining"]))
                st.caption(f"Temps restant : {seconds // 60:02d}:{seconds % 60:02d}")
                st.button("Actualiser le chronomètre", key="refresh_clock")
            with st.expander("📖 Fiches des factions", expanded=False):
                render_faction_sheet_menu("sidebar")
            with st.expander("💾 Sauvegarde et retour à l'accueil", expanded=False):
                st.download_button(
                    "Sauvegarder",
                    data=json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False),
                    file_name="the_four_realms.json",
                    mime="application/json",
                    key="download_save",
                )
                st.caption("La sauvegarde contient aussi les planifications privées.")
                confirm = st.checkbox("Confirmer le retour à l'accueil", key="confirm_home")
                if st.button("Retour à l'accueil", disabled=not confirm, key="go_home"):
                    reset_session()
                    st.rerun()
            render_forfeit(bundle)

        # 2. Actions du joueur
        with st.container(border=True, key="lw_side_actions"):
            st.markdown("### 🎮 Actions du joueur")
            if ai_config(bundle) is not None and not online:
                stack = ai_undo_stack()
                if st.button(
                    "↩️ Annuler mon dernier coup",
                    disabled=not stack,
                    width="stretch",
                    key="ai_undo_button",
                    help="Revient juste avant ta dernière action (la réponse de l'IA est annulée aussi).",
                ):
                    ai_undo_last_move()
                    st.rerun()
            # Terminer la phase : même place, en rouge, en production comme en manœuvres.
            with st.container(key="lw_end_phase"):
                if g["phase"] == "build":
                    if st.button(
                        "✅ Terminer ma phase de production",
                        disabled=g["winner"] is not None,
                        width="stretch",
                        key="sidebar_finish_production",
                    ):
                        perform(commit_plan)
                else:
                    if st.button(
                        "🏁 Terminer mes manœuvres",
                        disabled=g["winner"] is not None or g["curtain"] or g["active"] in g["passed"],
                        width="stretch",
                        key="sidebar_finish_maneuvers_always",
                    ):
                        perform(game_action, pass_turn)
            if g["winner"] is None:
                if g["phase"] == "build":
                    render_build_controls(g, view, local=True, on_board=False)
                elif g["phase"] == "move":
                    render_movement_validation(g)
                    render_move_controls(g)

        # 3. Pièce sélectionnée
        with st.container(border=True, key="lw_side_unit"):
            render_selected_card(g, view)


# --- Journal de la partie : en haut du journal de bord (plus en bas de page).

def render_log(view):
    return None


# --- Rappel de la phase en haut à gauche du plateau, qui reste visible quand
#     on fait défiler la page (ne capte aucun clic).

PHASE_BADGE_CSS = """
<style>
/* Streamlit enveloppe le conteneur dans une boîte : c'est elle, enfant
   direct du bloc du plateau, qui reste collée en haut pendant le défilement. */
div:has(> .st-key-lw_phase_badge) {
    position: sticky !important;
    top: 3.8rem;
    z-index: 1000;
    height: 0 !important;
    min-height: 0 !important;
    overflow: visible !important;
    pointer-events: none;
}
.st-key-lw_phase_badge {
    height: 0 !important;
    min-height: 0 !important;
    overflow: visible !important;
    pointer-events: none;
    gap: 0 !important;
}
.st-key-lw_phase_badge > div { height: 0 !important; overflow: visible !important; }
.lw-phase-badge {
    display: inline-block;
    margin: 8px 0 0 10px;
    padding: 4px 14px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.62);
    color: #ffffff;
    font-weight: 800;
    font-size: 14px;
    letter-spacing: 0.2px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
    pointer-events: none;
    white-space: nowrap;
}
</style>
"""


def render_phase_badge(g):
    if g.get("winner") is not None:
        return
    label = "🛠️ Phase de production" if g["phase"] == "build" else "⚔️ Phase de manœuvres"
    with st.container(key="lw_phase_badge"):
        st.markdown(
            PHASE_BADGE_CSS + f'<div class="lw-phase-badge">Tour {g["turn"]} · {label}</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# PSEUDO OBLIGATOIRE
# Sans pseudo, impossible de lancer, charger ou rejoindre une partie.
# ============================================================

START_BUTTON_KEYS = {"home_start", "home_load", "ai_home_start", "online_create"}
_lw_pseudo_original_button = st.button
_lw_pseudo_original_checkbox = st.checkbox


def _lw_pseudo_button(*args, **kwargs):
    if kwargs.get("key") in START_BUTTON_KEYS and not current_player_name():
        kwargs["disabled"] = True
        kwargs["help"] = "Indique d'abord ton pseudo, en haut de la page."
    return _lw_pseudo_original_button(*args, **kwargs)


def _lw_pseudo_checkbox(*args, **kwargs):
    if str(kwargs.get("key", "")).startswith("lobby_ready_") and not current_player_name():
        kwargs["disabled"] = True
        kwargs["value"] = False
        kwargs["help"] = "Indique d'abord ton pseudo."
    return _lw_pseudo_original_checkbox(*args, **kwargs)


_lw_pseudo_previous_render_home = render_home


def render_home():
    st.button = _lw_pseudo_button
    try:
        if not (st.session_state.get("home_player_name") or st.session_state.get("player_name") or "").strip():
            st.warning("👤 Indique ton pseudo ci-dessous pour pouvoir lancer une partie.")
        _lw_pseudo_previous_render_home()
    finally:
        st.button = _lw_pseudo_original_button


_lw_pseudo_previous_render_online_lobby = render_online_lobby


def render_online_lobby(room, seat):
    st.checkbox = _lw_pseudo_checkbox
    try:
        _lw_pseudo_previous_render_online_lobby(room, seat)
        if not current_player_name():
            st.warning("👤 Indique ton pseudo pour pouvoir te déclarer prêt.")
    finally:
        st.checkbox = _lw_pseudo_original_checkbox


if __name__ == "__main__":
    main()
