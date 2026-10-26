"""noms_postes.py - renomme a l'ecran les machines de mesure (codes internes -> noms lisibles).

Table dans `dashboard.config.json`, cle "noms_postes" : {"code": "nom affiche"}. Sans table, rien n'est renomme.
Seules les VALEURS JSON sont renommees (un nom entre guillemets suivi de , ] ou }), jamais une cle.
"""
import json
import re

import reglages

NOMS = reglages.CFG.get("noms_postes") or {}


def renommer(s):
    if not NOMS:
        return s
    return re.sub(r'(?<=")(' + "|".join(re.escape(k) for k in NOMS) + r')(?="\s*[,\]}])', lambda m: NOMS[m.group(1)], s)
