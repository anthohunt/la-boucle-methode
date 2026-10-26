import json, pathlib, sys
# Generateur du tableau de bord de la boucle.
# Toute l'histoire (depart, passes, essais, champion, cible) vient de journal.py, qui ne lit que les fichiers
# PERSISTANTS du moteur. tpl.html est autonome (tout le CSS dedans) ; ce script y injecte DATA -> index.html.
# etat-passe.py (cron chaque minute) ecrit la meme histoire dans etat-passe.json, relue par la page toutes les 30 s.
D = pathlib.Path(__file__).parent
sys.path.insert(0, str(D))
import reglages, journal


def _obj_vitesse():
    """objectif de vitesse (secondes par cas) lu dans le fichier de chantier, s'il en declare un."""
    import glob
    for p in sorted(glob.glob(reglages.MOTEUR + "chantier-*.json")):
        try:
            o = (json.loads(pathlib.Path(p).read_text(encoding="utf-8")).get("objectif") or {}).get("temps_par_cas_s")
        except Exception:
            o = None
        if o:
            return o
    return {}
H = journal.histoire()
data = {"histoire": H, "cats": journal.CATS, "progres_min": journal.PROGRES,
        "obj_vitesse": _obj_vitesse(), "config": reglages.CFG}
# (journal fusionne dans la passe) : titres et roles des etapes, SEULE source = ETAPES d'etat-passe.py, pour que la page
# range aussi les passes precedentes etape par etape des le premier affichage.
import importlib.util
_sp = importlib.util.spec_from_file_location("etat_passe", D / "etat-passe.py"); _ep = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_ep)
data["etapes"] = [{"id": k, "niveau": nv, "titre": ti, "desc": de} for k, nv, ti, de, _ in _ep.ETAPES]
tpl = (D / "tpl.html").read_text(encoding="utf-8")
pathlib.Path(reglages.DIR).mkdir(parents=True, exist_ok=True)
(pathlib.Path(reglages.DIR) / "index.html").write_text(tpl.replace("/*DATA*/", "var DATA=" + __import__("noms_postes").renommer(json.dumps(data, ensure_ascii=False)) + ";"), encoding="utf-8")
print("passes:", len(H.get("passes") or []), "champion:", (H.get("champion") or {}).get("titre"))
