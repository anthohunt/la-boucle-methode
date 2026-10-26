#!/usr/bin/env python3
"""etat-passe.py — etapes des DEUX NIVEAUX (entrainement autonome puis examen). Ecrit <DASH_DIR>/etat-passe.json : ou en est la passe de la boucle, etape par etape.
Lit le dernier run Workflow du moteur (journal + transcript de chaque agent). A lancer chaque minute (cron, minuteur systemd ou boucle shell).
Lecture seule ; ne touche ni au moteur ni au juge. ."""
import glob, json, os, re, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reglages
BASES = reglages.TRANSCRIPTS   # transcriptions de sessions Claude Code (DASH_TRANSCRIPTS)
M = reglages.MOTEUR
OUT = reglages.DIR + "etat-passe.json"
CFG = reglages.CFG
UN = CFG["unite"][1]   # « demandes », « messages »... (mot du pluriel)
T_ENT, T_EXA, T_VER = (CFG["tailles"].get(k) for k in ("entrainement", "examen", "verification"))
MAXT = 6000

# etapes affichees, dans l'ordre ; chaque label du moteur est range par la premiere regle qui lui correspond
# ARCHITECTURE A DEUX NIVEAUX. Chaque etape porte son niveau (0 = demarrage, 1 = entrainement autonome,
# 2 = examen). Chaque label du moteur est range par la premiere regle qui lui correspond.
ETAPES = [
    ("depart", 0, "Démarrage", "Relire l'état et la fiche", r"^(lit etat|etat fiche)"),
    ("etape0", 0, "Mesure du départ", "Départ noté : entraînement + examen", r"^(etape 0|lance etape 0|attend etape 0)"),
    ("n1_meilleure", 1, "Racine du niveau 1", "Meilleur essai d'entraînement : fixe le palier", r"^(lance|attend) (meilleure version|racine)"),
    ("audit", 1, "Lecture des fautes", "Fautes classées par cause", r"^audit (\d|verdict)"),
    ("audit_critique", 1, "Vérification lecture", "Recompte et preuves relues", r"^verification-audit"),
    ("audit_correction", 1, "Lecture corrigée", "Lecture finale, transmise à la stratégie", r"^audit correction"),
    ("donnees", 1, "Jeu d'entraînement", "Si l'entraînement trompe sur une catégorie", r"^donnees :"),
    # Stratégie + Critique + Stratégie corrigée = UNE étape à l'écran (le moteur garde ses 3 étapes)
    ("plan", 1, "Plan de départ", "Stratégie en équipe, critiquée puis corrigée", r"^(reflexion (\d|verdict|correction)|critique (\d|verdict))"),
    ("essais", 1, "3 premières branches", "Chaque idée devient un essai", r"^geste "),
    ("controle", 1, "Contrôle", "Écarte un essai cassé", r"^controle"),
    ("entrainement", 1, "Entraînement de l'arbre", ("%s %s, fautes visibles ; baisse = élagué" % (T_ENT or "", UN)).strip(), r"^(lance|attend) entrainement"),
    ("developpement", 1, "Développement", "Un enfant par branche qui monte", r"^developpe noeud"),
    ("decision_n1", 1, "Palier franchi ?", "Palier franchi : examen ; sinon nouvelle stratégie", r"^$^"),
    ("examen", 2, "Examen", ("%s %s scellés, +%s pts requis" % (T_EXA or "", UN, f"{reglages.PROGRES:g}")).strip(), r"^(lance|attend) examen"),
    ("recorrection", 2, "Recorrection", "Mêmes cas, autres postes", r"^(lance|attend) recorrection|^audit [a-z]+\d"),
    ("verification", 2, "Vérification", "Lot jamais utilisé pour choisir", r"^(lance|attend) lot de verification"),
    ("decision_n2", 2, "Nouvelle meilleure ?", "+5 à l'examen et à la recorrection", r"^$^"),
    ("methode", 2, "Réflexion niveau 2", "Après 2 échecs : propositions, pause", r"^"),
    ("memoire", 0, "Mémoire", "État et journal sauvés", r"^(sauve|journal|signale|note|hypoth|memoire)"),
]


def _chantier():
    """premier fichier chantier-*.json du dossier d'etat de la boucle (prefixe des essais, serie_debut...)."""
    for p in sorted(glob.glob(M + "chantier-*.json")):
        try:
            c = json.load(open(p, encoding="utf-8"))
            if isinstance(c, dict):
                return c
        except Exception:
            pass
    return {}


def ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def texte(c):
    if isinstance(c, str):
        return c
    return "\n".join(b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text")


def agent_info(d, aid):
    f = os.path.join(d, "agent-%s.jsonl" % aid)
    info = {"debut": None, "fin": None, "demande": "", "modele": None}
    try:
        meta = json.load(open(os.path.join(d, "agent-%s.meta.json" % aid)))
        info["modele"] = meta.get("model")
    except Exception:
        pass
    try:
        users = []
        for l in open(f):
            o = json.loads(l)
            t = ts(o.get("timestamp", ""))
            if t:
                info["debut"] = info["debut"] or t
                info["fin"] = t
            if o.get("type") == "user" and len(users) < 2:
                x = texte(o.get("message", {}).get("content"))
                if x:
                    users.append(x)
        dem = users[-1] if users else ""
        dem = re.sub(r"^\[Workflow harness[^\n]*\n", "", dem)
        info["demande"] = "\n".join(l[2:] if l.startswith("  ") else l for l in dem.splitlines())[:MAXT]
    except Exception:
        pass
    return info


def rendu(r):
    if r is None:
        return ""
    if isinstance(r, dict) and len(r) == 1:
        v = next(iter(r.values()))
        if isinstance(v, str):
            return v[:MAXT]
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            return "\n\n".join(v)[:MAXT]
    return json.dumps(r, ensure_ascii=False, indent=1)[:MAXT]


def main():
    runs = sorted([r for B in BASES for r in glob.glob(B + "/*/subagents/workflows/wf_*")], key=lambda p: os.stat(p).st_mtime)
    # une nouvelle SERIE ne montre pas les runs d'une serie archivee (champ serie_debut du chantier)
    try:
        deb = _chantier().get("serie_debut")
        if deb:
            t0 = datetime.fromisoformat(deb).timestamp()
            runs = [r for r in runs if os.stat(r).st_mtime >= t0]
    except Exception:
        pass
    if not runs:
        doc = {"genere": time.time(), "run": None, "fin_run": "pas encore lancee", "tour": None, "etapes": [], "en_mesure": [], "mesures": {}, "champion": {}}
        try:
            sys_ = __import__("sys"); sys_.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import journal as J; doc["histoire"] = J.histoire()
        except Exception as ex:
            doc["histoire"] = {"erreur": str(ex)[:200], "passes": []}
        json.dump(doc, open(OUT + ".tmp", "w"), ensure_ascii=False); os.replace(OUT + ".tmp", OUT)
        return
    d = runs[-1]
    run = os.path.basename(d)
    lignes, fini = [], None
    lab = {}
    for l in open(os.path.join(d, "journal.jsonl")):
        try:
            o = json.loads(l)
        except Exception:
            continue
        t = o.get("type")
        if t == "started":
            lab[o["key"]] = len(lignes)
            lignes.append({"label": o.get("label", "?"), "phase": o.get("phase"), "agent": o.get("agentId"), "resultat": None, "fini": False})
        elif t == "result" and o.get("key") in lab:
            x = lignes[lab[o["key"]]]
            x["resultat"], x["fini"] = o.get("result"), True
        elif t in ("completed", "failed", "cancelled", "error"):
            fini = t
    # fin du run : le fichier d'etat du workflow (projects/<session>/workflows/<run>.json) porte son statut
    wfs = sorted([w for B in BASES for w in glob.glob(B + "/*/workflows/%s*.json" % run.split("-")[0])], key=os.path.getmtime)
    # un statut TERMINAL du workflow (arrete a la main, fini, en echec) vaut tout de suite
    try:
        _st = json.load(open(wfs[-1])).get("status") if wfs else None
        if _st in ("killed", "completed", "failed", "cancelled"): fini = _st
    except Exception:
        pass
    if wfs and time.time() - max(os.stat(f).st_mtime for f in glob.glob(d + "/*")) > 900:   # le plus recent seulement, et seulement si plus rien ne bouge
        try:
            st = json.load(open(wfs[-1])).get("status")
            if st and st not in ("running", "pending"):
                fini = st
        except Exception:
            pass
    # un run couvre plusieurs passes -> chaque ligne recoit SA passe ; les etapes affichees = la passe en cours
    cour = None
    for x in lignes:
        m = re.search(r" t(\d+)", x["label"]) or re.search(r"^geste [a-z]+?(\d+)m\d", x["label"]) or re.search(r"^audit [a-z]+?(\d+)m\d", x["label"])
        if m: cour = int(m.group(1))
        x["tour"] = cour
    T = max([x["tour"] for x in lignes if x["tour"]] or [None]) if any(x["tour"] for x in lignes) else None
    lignes_tous = lignes
    lignes = [x for x in lignes if x["tour"] == T] if T else lignes
    def construire(lignes):
      etapes = {k: {"id": k, "niveau": nv, "titre": ti, "desc": de, "agents": []} for k, nv, ti, de, _ in ETAPES}
      autres = {"id": "autres", "niveau": 0, "titre": "Autres", "desc": "Étapes non classées", "agents": []}
      for x in lignes:
          lb = re.sub(r" t\d+( \(essai \d\))?$", "", x["label"])
          cible = autres
          for k, _, _, _, rx in ETAPES:
              if re.search(rx, x["label"]) or re.search(rx, lb):
                  cible = etapes[k]
                  break
          info = agent_info(d, x["agent"]) if x["agent"] else {}
          fait = x["resultat"].get("fait") if isinstance(x["resultat"], dict) else None
          cible["agents"].append({
              "label": x["label"], "fini": x["fini"], "refus": fait is False,
              "debut": info.get("debut"), "fin": info.get("fin") if x["fini"] else None,
              "modele": info.get("modele"), "demande": info.get("demande", ""), "rendu": rendu(x["resultat"]),
          })
      sortie = []
      ordre = list(etapes.values())
      dernier = max([i for i, e in enumerate(ordre) if e["agents"] and e["id"] != "memoire"] or [-1])   # la memoire tourne tout au long
      for i, e in enumerate(ordre):
          if not e["agents"] and i < dernier:
              e["saute"] = True
      for e in list(etapes.values()) + [autres]:
          a = e["agents"]
          if not a:
              e["etat"] = "saute" if e.get("saute") else "avenir"
          elif any(not x["fini"] for x in a) and not any(o["agents"] and o["id"] != "memoire" and any(y["fini"] and (y["debut"] or 0) > max(z["debut"] or 0 for z in a) for y in o["agents"]) for o in (ordre[ordre.index(e) + 1:] if e in ordre else [])):
              e["etat"] = "encours"   # des agents orphelins (run arrete puis repris) ne gardent pas l'etape "en cours" si une etape suivante a deja fini
          else:
              e["etat"] = "fait"
          e["refus"] = sum(1 for x in a if x["refus"])
          deb = [x["debut"] for x in a if x["debut"]]
          fin = [x["fin"] for x in a if x["fin"]]
          e["debut"], e["fin"] = (min(deb) if deb else None), (max(fin) if fin and e["etat"] == "fait" else None)
          if e["id"] == "mesure" and len(a) > 3:   # l'attente des mesures = des dizaines de petits sondages : on garde le dernier
              e["sondages"] = len(a)
              e["agents"] = a[-1:]
          if e is autres and not a:
              continue
          sortie.append(e)
      return sortie
    sortie = construire(lignes)
    etat = {}
    try:
        etat = json.load(open(M + "journal-wf-etat.json"))
    except Exception:
        pass
    mesures = {}
    try:
        mesures = json.load(open(reglages.DIR + "mesures-live.json"))
    except Exception:
        pass
    ch = etat.get("champion") or {}
    tours = [int(m) for x in lignes for m in re.findall(r" t(\d+)", x["label"])]
    for mm in (mesures.get("mesures") or []):
        try:
            g = json.load(open(M + "gestes/%s.json" % mm["tag"]))
            mm["titre"], mm["description"] = g.get("titre"), g.get("description")
        except Exception:
            pass
    try: LIB = json.load(open(reglages.DIR + "libelles.json"))
    except Exception: LIB = {}
    try: PREF = _chantier().get("prefixe") or ""
    except Exception: PREF = ""
    # ---------------- ARCHITECTURE A DEUX NIVEAUX ----------------
    # Le journal (fichiers PERSISTANTS du moteur, journal.py) donne le cycle en cours ; l'etat du moteur donne la phase du niveau 1.
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import journal as J
        H = J.histoire()
    except Exception as ex:
        H = {"erreur": str(ex)[:200], "passes": []}
    HP = {p["tour"]: p for p in H.get("passes") or []}
    hp = HP.get(T) or {}
    n1 = etat.get("n1") if isinstance(etat.get("n1"), dict) and etat["n1"].get("tour") == T else {}
    ph = n1.get("phase") or ""
    try: RS = json.load(open(reglages.DIR + "resumes-journal.json"))
    except Exception: RS = {}
    def f1(x): return ("%.1f" % x).replace(".", ",") if isinstance(x, (int, float)) else "?"
    ess = hp.get("arbre") or []
    ex = hp.get("examen") or {}
    palier = hp.get("palier") or n1.get("palier")
    # texte « ce qui en est sorti » (etape faite) et « ce qui se passe » (etape en cours)
    RES = {}
    a = hp.get("audit") or {}
    if a.get("fait"):
        RES["audit_correction"] = a.get("texte") or "faite"
        ec = [e for e in a.get("ecarts") or [] if e.get("corriger")]
        if ec: RES["audit_correction"] += " · jeu trompeur : " + ", ".join(e["cat"] for e in ec)
    d = hp.get("donnees") or {}
    if d: RES["donnees"] = (d.get("texte") or "jeu corrigé") if d.get("ok") else "refusée"
    # durée CUMULÉE du plan de départ = somme des 3 sous-étapes du moteur (stratégie, critique, correction)
    for e in sortie:
        if e["id"] == "plan" and (hp.get("plan") or {}).get("duree"): e["duree"] = hp["plan"]["duree"]
    prem = [e for e in ess if e.get("profondeur") == 1]
    if prem: RES["essais"] = " · ".join(e.get("court") or e["changement"] for e in prem)
    if prem and any(e.get("decision") == "ecarte" for e in prem): RES["controle"] = "écartés : " + ", ".join(str(e["id"]) for e in prem if e.get("decision") == "ecarte")
    notees = [e for e in ess if e.get("note") is not None]
    if notees:
        b = max(notees, key=lambda e: e["note"])
        RES["entrainement"] = "%d notés · %d élagués · meilleur %s %%" % (len(notees), sum(1 for e in ess if e.get("decision") == "elaguer"), f1(b["note"]))
    if ess and any(e.get("decision") in ("developper", "impasse") for e in ess):
        RES["developpement"] = "%d développés · %d impasses" % (sum(1 for e in ess if e.get("decision") == "developper"), sum(1 for e in ess if e.get("decision") == "impasse"))
    ch_ent = (etat.get("champion") or {}).get("entrainement") or {}
    rac = n1.get("racineN1") if isinstance(n1.get("racineN1"), dict) else None   # racine du niveau 1 = meilleur essai d'entrainement
    if rac and rac.get("moy") is not None:
        RES["n1_meilleure"] = "racine %s %% · seuil %s %%" % (f1(rac["moy"]), f1(palier or (rac["moy"] + 20)))
    elif ch_ent.get("moy") is not None: RES["n1_meilleure"] = "%s %% · seuil %s %%" % (f1(ch_ent["moy"]), f1(palier))
    if ex.get("note") is not None:
        RES["examen"] = "%s %% · %s pts" % (f1(ex["note"]), (("+" if ex["delta"] >= 0 else "") + f1(ex["delta"])) if isinstance(ex.get("delta"), (int, float)) else "?")
        rc = ex.get("recorrection") or {}
        if rc: RES["recorrection"] = ("%s pts" % (("+" if rc["delta"] >= 0 else "") + f1(rc["delta"]))) if isinstance(rc.get("delta"), (int, float)) else "en panne"
        vf = ex.get("verification") or {}
        if vf.get("note") is not None: RES["verification"] = "%s %%%s" % (f1(vf["note"]), " · avant %s %%" % f1(vf["ancienne"]) if vf.get("ancienne") is not None else "")
        RES["decision_n2"] = hp.get("decision") or ""
    cands = [e for e in ess if e.get("decision") == "examen"]
    if hp.get("verdict") == "sans_palier": RES["decision_n1"] = "non · nouvelle stratégie"
    elif cands: RES["decision_n1"] = "oui · branche %s à l'examen" % (ex.get("num") or cands[0]["id"])
    if hp.get("niveau2", {}).get("fait"): RES["methode"] = "propositions envoyées · pause"
    ENC = {"entrainement": "tour %s" % (n1.get("tourEntrainement") or 1), "developpement": "tour %s" % (n1.get("tourEntrainement") or 1)}
    # etapes sans agent (decisions du CODE) : etat deduit de la phase du niveau 1 et du journal
    for e in sortie:
        if e["id"] == "decision_n1":
            if hp.get("verdict") in ("sans_palier", "progres", "echec_examen") or ph in ("examen",) or ex: e["etat"] = "fait"
            elif ph == "decision": e["etat"] = "encours"
        if e["id"] == "decision_n2":
            if ex.get("verdict") or hp.get("verdict") in ("progres", "echec_examen"): e["etat"] = "fait"
    # etapes CONDITIONNELLES : toujours visibles ; barrees (avec leur raison) quand elles ne servent pas dans ce cycle
    COND = {"etape0": "si premier démarrage", "n1_meilleure": "si jeu d'entraînement changé", "donnees": "si jeu trompeur",
            "examen": "si palier franchi", "recorrection": "si examen ≥ +5", "verification": "si nouvelle meilleure", "decision_n2": "si examen passé",
            "methode": "si 2 échecs à l'examen"}
    fini_cycle = hp.get("verdict") in ("sans_palier", "progres", "echec_examen")
    rang = {e["id"]: i for i, e in enumerate(sortie)}
    for e in sortie:
        if e["id"] in COND and e["etat"] in ("avenir", "saute"):
            inutile = e["etat"] == "saute" or (fini_cycle and not (e["id"] == "methode" and False))
            if e["id"] in ("examen", "decision_n2") and hp.get("verdict") == "sans_palier": inutile = True
            if e["id"] in ("recorrection", "verification") and (hp.get("verdict") in ("sans_palier", "echec_examen")): inutile = True
            e["conditionnelle"] = True
            e["resume"] = COND[e["id"]]
            e["etat"] = "inutile" if inutile else "avenir"
    for e in sortie:
        if e.get("conditionnelle"): continue
        if e["etat"] == "fait" and RES.get(e["id"]): e["resume"] = RES[e["id"]]
        elif e["etat"] == "encours": e["resume"] = ENC.get(e["id"], "")
        else: e.setdefault("resume", "")
        if e["etat"] == "avenir" and e["id"] == "decision_n1" and RES.get("decision_n1"): e["etat"] = "fait"; e["resume"] = RES["decision_n1"]
    for e in sortie:
        e["n_agents"] = len(e.get("agents") or [])
        e.pop("agents", None)   # la fenetre d'une etape = texte simple, jamais la liste technique des agents
    # mesures en cours, regroupees (toutes les parts d'une meme mesure) : « 311 / 423 demandes »
    grp = {}
    GR = {str(x.get("id")): x.get("graine") for x in (mesures.get("mesures") or []) if "~" not in str(x.get("id", ""))}
    PHASE_DE = {"complet": "examen", "entrainement": "entrainement", "verification": "verification"}
    for x in (mesures.get("mesures") or []):
        b = str(x.get("id", "")).split("~")[0]
        x["graine"] = x.get("graine") or GR.get(b)
        # deux mesures du MEME nom sur un poste partagent gestes/<nom>.progres ; on ne garde que le compteur de SA phase
        pr = x.get("progres") or {}
        if pr and x["graine"] in PHASE_DE and pr.get("phase") != PHASE_DE[x["graine"]]:
            x["progres"] = None
        grp.setdefault(b, []).append(x)
    JEU = {"entrainement": "entraînement", "verification": "vérification", "complet": "examen"}
    def _n(f):
        try: return sum(1 for l in open(f, encoding="utf-8") if l.strip())
        except Exception: return 0
    try: courant = open(M + "donnees/COURANT.txt").read().strip()
    except Exception: courant = ""
    TAILLE = {"complet": T_EXA, "verification": T_VER, "entrainement": T_ENT or ((_n(M + "ref/exemples-entrainement-lot01.jsonl") + _n(M + "donnees/" + courant)) or None)}
    # UNE barre par mesure en cours, nommee en francais (« Branche 2 : consigne corrigee... »), et sous chaque barre
    # les 4 POSTES : combien de cas chacun a notes pour CETTE mesure, et s'il a un paquet en cours (file dynamique du juge :
    # progres_juge.par_poste / en_cours, postes_etat).
    POSTES = mesures.get("postes") or []
    PE = mesures.get("postes_etat") or {}
    def vivant(x):
        if x.get("etat") in ("fini", "echec"): return False
        try: return time.time() - datetime.fromisoformat(str(x.get("demande") or x.get("depuis"))).replace(tzinfo=timezone.utc).timestamp() < 12 * 3600
        except Exception: return True
    def nom_mesure(t, gr, titre):
        m = re.match(r"^" + re.escape(PREF) + r"r(\d+)n(\d+)(c?)(p\d+)?$", t)
        m2 = re.match(r"^" + re.escape(PREF) + r"r(\d+)m(\d+)v(\d+)(c?)(p\d)?$", t)
        idee = (" : " + titre) if titre else ""
        if re.search(r"dep([a-z]|-e[xn])?$", t): return "Version de départ (%s)" % JEU.get(gr, gr), None
        if m:
            n = int(m.group(2))
            if m.group(3): return "Recorrection de la branche %d%s" % (n, idee), int(m.group(1))
            r0 = int(m.group(1))
            # une branche d'une passe PRECEDENTE mesuree a l'entrainement = remesure sur le jeu courant pour choisir la racine
            if gr == "entrainement" and T and r0 < T: return "Remesure sur le nouveau jeu : branche %d de la passe %d%s" % (n, r0, idee), T
            return {"complet": "Examen de la branche %d%s", "verification": "Vérification de la branche %d%s"}.get(gr, "Branche %d%s") % (n, idee), r0
        if m2: return "%s de l'essai %d (version %d)" % ("Recorrection" if m2.group(4) else {"entrainement": "Entraînement", "verification": "Vérification"}.get(gr, "Examen"), int(m2.group(2)) + 1, int(m2.group(3))), int(m2.group(1))
        if t == (etat.get("champion") or {}).get("tag"): return "Meilleure version (%s)" % JEU.get(gr, gr), None
        return "Mesure (%s)" % JEU.get(gr, gr), None
    vivantes = []
    for b, parts in grp.items():
        tete = next((x for x in parts if "~p" not in str(x.get("id", ""))), parts[0])
        pparts = [x for x in parts if "~p" in str(x.get("id", ""))]
        if not vivant(tete) or not (tete.get("etat") in ("en file", "mesure", "attend le poste") or any(x.get("etat") in ("mesure", "attend le poste") for x in pparts)):
            continue
        vivantes.append((b, tete, pparts))
    occupe = {}   # poste -> nom de la mesure qui y a un paquet en cours
    for b, tete, pparts in vivantes:
        for h in ((tete.get("progres_juge") or {}).get("en_cours") or {}):   # en_cours = {poste: numero du paquet en cours}
            occupe.setdefault(h, b)
        for x in pparts:
            if x.get("etat") == "mesure" and x.get("machine"): occupe.setdefault(x["machine"], b)
    # ARRET SEQUENTIEL du juge = evenements sequentiel_ordre / sequentiel_lecture dans le journal du juge
    # (fichier JSON par ligne, DASH_JOURNAL_JUGE ; facultatif). On garde, par mesure, la derniere lecture :
    # estimation courante (note_vue), fourchette (note [bas, haut]), ecart au parent (delta_vu), cas lus (n).
    SEQ = {}
    try:
        with open(reglages.JOURNAL_JUGE, encoding="utf-8") as _fj:
            out = "".join(l for l in _fj.readlines()[-5000:] if "sequentiel_" in l)
    except Exception:
        out = ""
    try:
        for l in out.splitlines():
            try: o = json.loads(l)
            except Exception: continue
            q = SEQ.setdefault(str(o.get("id")), {})
            if o.get("evt") == "sequentiel_ordre": q["ordre"] = True
            elif o.get("evt") == "sequentiel_lecture":
                q["lecture"] = {"n": o.get("n"), "est": o.get("note_vue"), "bas": (o.get("note") or [None, None])[0], "haut": (o.get("note") or [None, None])[1],
                                "ecart": o.get("delta_vu"), "decision": o.get("decision")}
    except Exception:
        pass
    en_mesure = []
    for b, tete, pparts in vivantes:
        t = tete.get("tag") or ""; gr = tete.get("graine") or GR.get(b) or "complet"
        titre = tete.get("titre")
        for tt in (t, re.sub(r"p\d+$", "", t)):   # branche relancee (suffixe p1) -> titre de l'original
            try:
                titre = titre or json.load(open(M + "gestes/%s.json" % tt)).get("titre")
            except Exception:
                pass
        nom, passe = nom_mesure(t, gr, titre)
        mn = re.match(r"^" + re.escape(PREF) + r"r(\d+)n(\d+)(c?)(p\d+)?$", t)
        pj = tete.get("progres_juge") or {}
        tot = pj.get("total") or TAILLE.get(gr) or sum(((x.get("progres") or {}).get("total") or 0) for x in pparts)
        if isinstance(pj.get("fait"), int):
            fait = pj["fait"]
        else:
            k = max(1, len(pparts))
            fait = sum(((x.get("progres") or {}).get("total") or round((tot or 0) / k)) if x.get("etat") == "fini" else ((x.get("progres") or {}).get("fait") or 0) for x in pparts)
        fait = min(fait, tot) if tot else fait
        postes = []
        for h in POSTES:
            # cas notes par ce poste pour CETTE mesure, paquet en
            # cours COMPRIS = compteur du poste (gestes/<nom>.progres, cumule sur ses paquets) ; a defaut, ses paquets finis (par_poste)
            poste_fait = sum(((x.get("progres") or {}).get("fait") or 0) for x in pparts if x.get("machine") == h)
            notes = max(poste_fait, (pj.get("par_poste") or {}).get(h) or 0)
            ec = pj.get("en_cours") or {}
            enc = h in ec or (not pj and any(x.get("machine") == h and x.get("etat") == "mesure" for x in pparts))
            if enc:
                txt = ("paquet %d/%d en cours" % (ec[h] + 1, pj["paquets"])) if h in ec and isinstance(ec[h], int) and pj.get("paquets") else "paquet en cours"
            elif occupe.get(h) and occupe[h] != b:
                autre = next((nom_mesure(tt.get("tag") or "", tt.get("graine") or "complet", None)[0] for bb, tt, _ in vivantes if bb == occupe[h]), "une autre mesure")
                txt = "occupé : " + autre
            else:
                txt = "libre" if (PE.get(h) or {}).get("libre", True) else "occupé hors de la boucle"
            postes.append({"poste": h.upper(), "notes": notes or 0, "etat": txt, "actif": bool(enc)})
        if postes:   # la barre = la somme exacte des postes (jamais deux chiffres differents a l'ecran)
            fait = sum(p["notes"] for p in postes)
            fait = min(fait, tot) if tot else fait
        attente = not fait and not any(p["actif"] for p in postes)
        en_mesure.append({"nom": nom, "graine": gr, "fait": fait, "total": tot or None, "pct": round(100 * fait / tot) if tot else 0, "passe": passe,
                          "postes": postes, "attente": attente, "paquets": [pj.get("paquets_faits"), pj.get("paquets")] if pj.get("paquets") else None,
                          # de quoi relier la mesure a son noeud de l'arbre (bloc « En test maintenant » de tpl.html)
                          "branche": int(mn.group(2)) if mn and not mn.group(3) else None, "tour_branche": int(mn.group(1)) if mn else None, "titre": titre,
                          "sequentiel": bool((SEQ.get(b) or {}).get("ordre")), "lecture": (SEQ.get(b) or {}).get("lecture")})
    en_mesure.sort(key=lambda q: q["nom"])
    POUR = {"etape0": ("complet", "entrainement"), "n1_meilleure": ("entrainement",), "entrainement": ("entrainement",), "examen": ("complet",), "recorrection": ("complet",), "verification": ("verification",)}
    for e in sortie:
        if e["id"] in POUR and e["etat"] == "encours":
            q = [x for x in en_mesure if x["graine"] in POUR[e["id"]]]
            if q: e["progres"] = q
    # run arrete -> plus aucune etape « en cours » cote moteur ; PILOTAGE MANUEL (pilotage.json, ecrit par le manager) :
    # {"annonce": "...", "etapes": {"id": "fait|encours|avenir|inutile"}} applique par-dessus (ex. examen lance a la main).
    if fini:
        for e in sortie:
            if e["etat"] == "encours": e["etat"] = "fait"
    annonce = None
    try:
        pil = json.load(open(reglages.DIR + "pilotage.json"))
        if pil.get("run") in (None, run):
            annonce = pil.get("annonce")
            for e in sortie:
                if e["id"] in (pil.get("etapes") or {}): e["etat"] = pil["etapes"][e["id"]]
    except Exception:
        pass
    for e in sortie:   # une mesure du juge en cours (lancee par le moteur OU a la main) donne sa progression a son etape
        if e["id"] in POUR and e["etat"] == "encours" and not e.get("progres"):
            q = [x for x in en_mesure if x["graine"] in POUR[e["id"]]]
            if q: e["progres"] = q
    doc = {"genere": time.time(), "run": run, "fin_run": fini, "annonce": annonce, "tour": T if T else etat.get("tour"), "histoire": H, "en_mesure": en_mesure, "palier": palier,
           "champion": {"tag": ch.get("tag"), "mesures": ch.get("mesures")}, "etapes": sortie, "mesures": mesures}
    tmp = OUT + ".tmp"
    from noms_postes import renommer
    open(tmp, "w").write(renommer(json.dumps(doc, ensure_ascii=False)))
    os.replace(tmp, OUT)

if __name__ == "__main__":
    main()
