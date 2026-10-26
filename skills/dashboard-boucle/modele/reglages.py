"""reglages.py - les reglages du tableau de bord, lus une seule fois.

Rien n'est ecrit en dur : tout vient de variables d'environnement, puis du fichier
`dashboard.config.json` (voir `dashboard.config.example.json`).

  DASH_MOTEUR      dossier d'etat de la boucle (journal-arbre.jsonl, gestes/, strategies.jsonl...)   defaut ./etat-boucle/
  DASH_DIR         dossier du tableau (resultats-moteur.jsonl, mesures-live.json, sorties)           defaut ./tableau/
  DASH_CONFIG      fichier de configuration                                                          defaut $DASH_DIR/dashboard.config.json
  DASH_TRANSCRIPTS dossiers (separes par ':') des transcriptions de sessions Claude Code            defaut ~/.claude/projects (facultatif)
  DASH_JOURNAL_JUGE journal du juge (JSON par ligne) pour les lectures de l'arret sequentiel         defaut aucun (facultatif)
"""
import json
import os


def _slash(p):
    return p if p.endswith("/") else p + "/"


MOTEUR = _slash(os.path.expanduser(os.environ.get("DASH_MOTEUR", "./etat-boucle/")))
DIR = _slash(os.path.expanduser(os.environ.get("DASH_DIR", "./tableau/")))
CONFIG_FILE = os.path.expanduser(os.environ.get("DASH_CONFIG", DIR + "dashboard.config.json"))
def _projets(racines):
    """chaque racine donnee + ses sous-dossiers directs (un dossier par projet Claude Code)."""
    sortie = []
    for r in racines:
        r = os.path.expanduser(r)
        if os.path.isdir(r):
            sortie.append(r)
            sortie += [os.path.join(r, d) for d in sorted(os.listdir(r)) if os.path.isdir(os.path.join(r, d))]
    return sortie


TRANSCRIPTS = _projets([p for p in os.environ.get("DASH_TRANSCRIPTS", "~/.claude/projects").split(":") if p])
JOURNAL_JUGE = os.environ.get("DASH_JOURNAL_JUGE") or None

DEFAUTS = {
    "titre": "Ma boucle",
    "surtitre": "Boucle d'amélioration automatique",
    "intro": "",
    "unite": ["cas", "cas"],
    "unite_vitesse": "cas",
    "categories": {"a": {"nom": "Catégorie A", "court": "A"}},
    "tailles": {"entrainement": None, "examen": None, "verification": None},
    "progres_min": 5.0,
    "lien": None,
}


def config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            c = json.load(f)
    except Exception:
        c = {}
    sortie = dict(DEFAUTS)
    sortie.update(c)
    sortie["tailles"] = dict(DEFAUTS["tailles"], **(c.get("tailles") or {}))
    return sortie


CFG = config()
CATS = list(CFG["categories"].keys())
PROGRES = float(CFG["progres_min"])
