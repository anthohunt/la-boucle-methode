#!/usr/bin/env python3
"""journal.py — HISTOIRE PERSISTANTE de la boucle.

Construit, a partir des SEULS fichiers persistants du moteur (jamais des transcriptions d'un run) :
  - le depart (version de depart, sa note, ses notes par categorie) ;
  - chaque passe : strategie en 2 phrases simples, audit s'il y en a eu, etapes conditionnelles sautees
    (avec leur raison), chaque essai (titre, idee, note, ecart au champion, verdict, confirmation),
    la decision (nouveau champion ou non), le meilleur essai et le champion apres la passe ;
  - le champion actuel et la cible.
Lu par generer.py (graphiques, toutes les 5 min) et etat-passe.py (journal, chaque minute).
Lecture seule : ne touche ni au moteur ni au juge.

Sources : strategies.jsonl, audits-erreurs.jsonl, journal-wf-etat.json, propositions(-systeme).jsonl,
gestes/<tag>.json (titre, description, journal {probleme, idee, attendu}, parent), chantier-*.json (prefixe,
objectif) et <DASH_DIR>/resultats-moteur.jsonl (toutes les mesures).
Textes : resumes-journal.json (a la main, prioritaire) > champ « en_clair » ecrit par le moteur > phrases
entieres extraites automatiquement, sans code interne (jamais coupees au milieu).
"""
import glob, json, os, re, statistics

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reglages
M = reglages.MOTEUR   # dossier d'etat de la boucle
D = reglages.DIR      # dossier du tableau
CATS = reglages.CATS
PROGRES = reglages.PROGRES   # regle de la methode : progres = au moins +5 points sur le champion (apparie)
TAILLE_EXAMEN = reglages.CFG["tailles"].get("examen") or 100


def _jl(p):
    o = []
    try:
        for l in open(p, encoding="utf-8"):
            l = l.strip()
            if not l:
                continue
            try:
                o.append(json.loads(l))
            except Exception:
                pass
    except Exception:
        pass
    return o


def _js(p, defaut=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return defaut


# --- francais : accents oublies par le moteur (textes ASCII) -------------------------------------------------
ACC = [(r"\bdepart\b", "départ"), (r"\betapes?\b", lambda m: "étape" + ("s" if m.group(0).endswith("s") else "")),
       (r"\bdeja teste\b", "déjà testé"), (r"\bdeja\b", "déjà"), (r"\bmodele(s?)\b", r"modèle\1"), (r"\bpiege(s?)\b", r"piège\1"),
       (r"\bpiegeux\b", "piégeux"), (r"\becrit\b", "écrit"), (r"\bpassees\b", "passées"), (r"\bregle(s?)\b", r"règle\1"),
       (r"\bexpediteur(s?)\b", r"expéditeur\1"), (r"\bcree\b", "crée"), (r"\babimes\b", "abîmés"), (r"\bmeme\b", "même"),
       (r"\breponse\b", "réponse"), (r"\b([Aa])pres\b", lambda m: m.group(1) + "près"), (r"\brecopiees\b", "recopiées"),
       (r"\bannee\b", "année"), (r"\boublies\b", "oubliés"), (r"\btrouves\b", "trouvés"), (r"\ba trouve\b", "a trouvé"),
       (r"\brefuses d'office\b", "refusés d'office"), (r"\bevenement(s?)\b", r"événement\1"), (r"\bsysteme\b", "système"),
       (r"\bcategorie(s?)\b", r"catégorie\1"), (r"\bdecide\b", "décide"), (r"\bpremiere\b", "première"),
       (r"\bdifferent(e?s?)\b", r"différent\1"), (r"\bequipe\b", "équipe"), (r"\bspecialiser\b", "spécialiser"), (r"\bresultat(s?)\b", r"résultat\1"),
       (r" a (ignorer|partir|tort|plusieurs|la liste)\b", r" à \1"), (r"\bqu'a\b", "qu'à"), (r"\bcote\b", "côté"), (r"\brepechage\b", "repêchage"), (r"\brepeche\b", "repêche"), (r"\btri allege\b", "tri allégé"), (r"\bon allege\b", "on allège"),
       (r"\bbien dates\b", "bien datés"),
       (r"\bcorrigee\b", "corrigée"), (r"\binventees\b", "inventées"), (r"\bremplacees\b", "remplacées"), (r"\bretirees\b", "retirées"),
       (r"\bjetees\b", "jetées"), (r"\bfusionnes\b", "fusionnés"), (r"\boubliees\b", "oubliées"), (r"\bmontres\b", "montrés"),
       (r"\bdecider\b", "décider"), (r"\bpassee\b", "passée"), (r"\bcoupe\b", "coupé"), (r"\bempechant\b", "empêchant"),
       (r"\bdeclencher\b", "déclencher"), (r"\btot\b", "tôt"), (r"\bschema\b", "schéma"), (r"\bverifi", "vérifi")]


def acc(t):
    """accents seuls, sans majuscule (famille d'idees affichee en fin de ligne)."""
    t = str(t or "").strip()
    for a, b in ACC:
        t = re.sub(a, b, t)
    return t


def fr(t):
    t = str(t or "").strip()
    for a, b in ACC:
        t = re.sub(a, b, t)
    return t[:1].upper() + t[1:] if t else t


# --- phrases entieres, sans code interne ----------------------------------------------------------------------
CODE = re.compile(r"\b[a-z]{1,3}dep-e[xn]\b|\b[a-z]{2,4}r\d+m\d\w*|\b[a-z]{2,4}r\d+n\d+\w*|(^|\s)_\w+|=\w+|\b[a-z]\d{2}-\d{3}\b|\blot-\d+|\b\w+-(fr|en)-\d+|\w\d?:\d\w|\b[a-z]{1,3}dep[a-z]?\b|\b\w+_\w+\b|\b\w+\.(py|jsonl?|txt|sh|md)\b|\bE\d\b|\bM\d\b|"
                  r"\bR0\b|\bA/A\b|\bp ?<|\b1B\b|\bDECIDE\b|\bnoter\(|\bpr[ée]-vol|\bapparié|\bgeste|\btamisage|\bbanc\b|\bscell")


def phrases(t, n=2, maxc=320):
    """au plus n phrases ENTIERES du texte, sans code interne ; jamais coupees ; '' si rien de propre."""
    out, tot = [], 0
    for bloc in re.split(r"\n\s*\n|\n(?=\s*[-•\d(])", str(t or "")):
        b = " ".join(bloc.split())
        if not b or re.match(r"^[-•\d(]", b) or b.isupper():
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý«])", b):
            s = s.strip()
            if not s or not re.search(r"[.!?]$", s) or s.endswith(":") or CODE.search(s) or len(s) > 240 or len(s) < 25 \
                    or len(re.findall(r"\b[A-ZÀ-Ý]{4,}\b", s)) >= 2 or re.match(r"(?i)strat[ée]gie d[ée]finitive", s):
                if re.match(r"(?i)strat[ée]gie d[ée]finitive", s):
                    continue   # simple en-tete, on passe a la phrase suivante
                return " ".join(out)   # on ne prend que les phrases de TETE : une phrase sortie de son contexte trompe

            if tot + len(s) > maxc:
                return " ".join(out)
            out.append(fr(s)); tot += len(s)
            if len(out) >= n:
                return " ".join(out)
    return " ".join(out)


def main_histoire():
    conf = next((c for c in (_js(p) for p in sorted(glob.glob(M + "chantier-*.json"))) if isinstance(c, dict) and c.get("prefixe")), {}) or {}
    P = conf.get("prefixe") or ""
    OBJ = (conf.get("objectif") or {}).get("qualite_pct_par_categorie") or {}
    cible = None
    if OBJ:
        cible = {"minimum": round(statistics.mean(v["minimum"] for v in OBJ.values()), 1),
                 "ideal": round(statistics.mean(v["ideal"] for v in OBJ.values()), 1), "par_cat": OBJ}
    RES = _js(D + "resumes-journal.json", {}) or {}
    LIB = _js(D + "libelles.json", {}) or {}
    etat = _js(M + "journal-wf-etat.json", {}) or {}

    def geste(tag):
        g = _js(M + "gestes/%s.json" % tag, {}) or {}
        L = LIB.get(tag) if isinstance(LIB.get(tag), dict) else {}
        # une branche RELANCEE (suffixe p1, p2… apres une panne) n'a pas son propre gestes/<tag>.json : titre de l'original
        if not g and not L and re.search(r"p\d+$", str(tag or "")):
            return geste(re.sub(r"p\d+$", "", str(tag)))
        j = {}
        for src in (g.get("journal"), (L or {}).get("journal")):
            if isinstance(src, dict):
                j.update(src)
            elif isinstance(src, str) and src.strip():
                j["idee"] = phrases(src, 1, 240)
        return {"titre": fr((L or {}).get("titre") or g.get("titre") or ""), "description": fr((L or {}).get("description") or g.get("description") or ""),
                "probleme": fr(j.get("probleme") or ""), "idee": fr(j.get("idee") or ""), "attendu": fr(j.get("attendu") or ""),
                "parent": g.get("parent")}

    rx_essai = re.compile(r"^" + re.escape(P) + r"r(\d+)m(\d)$")
    rx_conf = re.compile(r"^" + re.escape(P) + r"r(\d+)m(\d)c$")
    rx_dep = re.compile(r"^" + re.escape(P) + r"dep([a-z]|-e[xn])?$")
    mes = [m for m in _jl(D + "resultats-moteur.jsonl") if str(m.get("tag", "")).startswith(P)] if P else []
    ok = lambda m: m.get("ok") and m.get("sealed_moy") is not None

    def vec(m):
        s = m.get("sealed") or {}
        return {c: s.get(c) for c in CATS if s.get(c) is not None}

    def perf(m):
        return {"note": m.get("sealed_moy"), "cats": vec(m), "vitesse": (m.get("vitesse") or {}).get("moy"),
                "tokens": (m.get("tokens") or {}).get("moy"), "n": m.get("n"), "ts": m.get("ts")}

    # --- depart : la derniere mesure reussie de la version de depart
    dm = [m for m in mes if rx_dep.match(str(m.get("tag"))) and ok(m) and m.get("jeu") in (None, "examen")]   # le depart affiche = sa note d'EXAMEN
    depart = dict(perf(dm[-1]), tag=dm[-1]["tag"]) if dm else None
    if depart:
        depart["texte"] = RES.get("depart") or "Version de départ : la consigne simple, un seul appel au petit modèle, sans aide autour."

    # --- essais et confirmations (derniere mesure reussie de chaque tag ; echecs gardes si jamais mesure)
    dern, echecs = {}, {}
    for m in mes:
        t = str(m.get("tag"))
        if ok(m):
            dern[t] = m
        elif not m.get("ok"):
            echecs[t] = m
    live = (_js(D + "mesures-live.json", {}) or {}).get("mesures") or []

    def en_mesure(tag):
        """compteur de cas d'une mesure en cours (toutes ses parts), ou None."""
        parts = [x for x in live if x.get("tag") == tag]
        run = [x for x in parts if x.get("etat") in ("mesure", "attend le poste")]
        if not run:
            return None
        base = str(run[0].get("id", "")).split("~")[0]
        parts = [x for x in parts if str(x.get("id", "")).split("~")[0] == base]
        if any("~p" in str(x.get("id", "")) for x in parts):
            parts = [x for x in parts if "~p" in str(x.get("id", ""))]
        tot = next((x["progres"]["total"] for x in parts if (x.get("progres") or {}).get("total")), None)
        k = len(parts)
        taille = tot or (TAILLE_EXAMEN // max(1, k))
        fait = sum(taille if x.get("etat") == "fini" else ((x.get("progres") or {}).get("fait") or 0) for x in parts)
        return {"fait": fait, "total": taille * k, "pct": round(100 * fait / max(1, taille * k))}

    tours = set()
    for t in list(dern) + list(echecs):
        mm = rx_essai.match(t) or rx_conf.match(t)
        if mm:
            tours.add(int(mm.group(1)))
    for f in glob.glob(M + "gestes/%sr*m[0-9].json" % P) + glob.glob(M + "gestes/%sr*m[0-9].py" % P):
        mm = re.search(r"r(\d+)m\d\.", os.path.basename(f))
        if mm:
            tours.add(int(mm.group(1)))
    # cycles de l'ARCHITECTURE A DEUX NIVEAUX (essais <prefixe>rNnK, journal-arbre.jsonl, etat n1) -> traites a part (cycles_deux_niveaux)
    NOUVEAUX = set()
    for o in _jl(M + "journal-arbre.jsonl"):
        try: NOUVEAUX.add(int(o.get("tour")))
        except Exception: pass
    for f in glob.glob(M + "gestes/%sr*n*.json" % P):
        mm = re.match(re.escape(P) + r"r(\d+)n\d+$", os.path.basename(f)[:-5])
        if mm: NOUVEAUX.add(int(mm.group(1)))
    if isinstance(etat.get("n1"), dict) and etat["n1"].get("tour"): NOUVEAUX.add(int(etat["n1"]["tour"]))
    for o in _jl(M + "strategies.jsonl"):
        if o.get("niveau") == 1:
            try: NOUVEAUX.add(int(o.get("tour")))
            except Exception: pass
    STRAT = {}
    for o in _jl(M + "strategies.jsonl"):
        try:
            STRAT[int(o.get("tour"))] = o
        except Exception:
            pass
    tours |= set(STRAT)
    tours -= NOUVEAUX
    AUD = {}
    for o in _jl(M + "audits-erreurs.jsonl"):
        try:
            AUD[int(o.get("tour"))] = o.get("audit") or {}
        except Exception:
            pass
    PROP = {}
    for f in ("propositions-systeme.jsonl", "propositions.jsonl"):
        for o in _jl(M + f):
            if o.get("revue"):   # propositions deja tranchees avec l'operateur (revue de niveau 2) : plus affichees comme en attente
                continue
            x = o.get("en_clair") or o.get("resume") or o.get("proposition") or o.get("texte") or ""
            x = phrases(x, 2) if isinstance(x, str) else ""
            if x:
                PROP.setdefault(o.get("tour"), []).append(x)
            for pr in o.get("propositions") or []:   # reflexion de niveau 2 : une ligne par changement propose
                y = fr(pr.get("changement") or "") if isinstance(pr, dict) else ""
                if y:
                    PROP.setdefault(o.get("tour"), []).append(y)

    champ_etat = (etat.get("champion") or {}).get("tag")
    note_champ_etat = None
    v = (etat.get("champion") or {}).get("vec") or {}
    if v and all(isinstance(v.get(c), (int, float)) for c in CATS):
        note_champ_etat = round(statistics.mean(v[c] for c in CATS), 1)

    def perf_champ(tag):
        if not tag:
            return {}
        if rx_dep.match(tag) and depart:
            return {"vitesse": depart.get("vitesse"), "tokens": depart.get("tokens")}
        m = dern.get(tag + "c") or dern.get(tag)
        return {"vitesse": (m.get("vitesse") or {}).get("moy"), "tokens": (m.get("tokens") or {}).get("moy")} if m else {}

    def note_retenue(tag):
        """note d'un champion : sa confirmation si elle existe, sinon sa mesure."""
        if not tag:
            return None, None
        c = dern.get(tag + "c")
        m = c or dern.get(tag)
        if rx_dep.match(tag) and depart:
            return depart["note"], depart["cats"]
        if tag == champ_etat and note_champ_etat is not None and not c:
            return note_champ_etat, v
        return (m.get("sealed_moy"), vec(m)) if m else (None, None)

    tour_max = max(tours) if tours else 0
    passes = []
    champ = depart["tag"] if depart else None
    champ_note = depart["note"] if depart else None
    champ_cats = depart["cats"] if depart else {}
    sans_prog = 0
    for r in sorted(tours):
        tags = sorted({t for t in list(dern) + list(echecs) if rx_essai.match(t) and int(rx_essai.match(t).group(1)) == r} |
                      {os.path.basename(f)[:-5] for f in glob.glob(M + "gestes/%sr%dm[0-9].json" % (P, r))})
        essais = []
        for t in tags:
            g = geste(t)
            m = dern.get(t)
            c = dern.get(t + "c")
            e = {"num": int(t[-1]) + 1, "titre": g["titre"] or "essai sans titre", "idee": g["idee"] or g["description"],
                 "probleme": g["probleme"], "attendu": g["attendu"], "description": g["description"]}
            if m:
                e.update(perf(m))
                vp = m.get("vs_parent") or {}
                e["ecart"] = vp.get("delta_moy") if isinstance(vp.get("delta_moy"), (int, float)) else (
                    round(m["sealed_moy"] - champ_note, 1) if champ_note is not None and m.get("sealed_moy") is not None else None)
                e["apparie"] = isinstance(vp.get("delta_moy"), (int, float))
                e["gagnes"], e["perdus"] = vp.get("gagnes"), vp.get("perdus")
                e["verdict"] = "progres" if (e["ecart"] or 0) >= PROGRES else "recul" if (e["ecart"] or 0) <= -PROGRES else "stagnation"
            elif t in echecs:
                err = str(echecs[t].get("err") or "")
                e["verdict"] = "echec"
                e["raison"] = "le poste de mesure était occupé" if re.search(r"pris depuis|occup", err) else \
                    "alerte d'intégrité du juge, mesure refaite plus tard" if "INTEGRITE" in err else "la mesure a échoué"
            elif r < max(tours):
                e["verdict"] = "echec"
                e["raison"] = "écarté avant la mesure"
            else:
                e["verdict"] = "attente"
            if c:
                vpc = c.get("vs_parent") or {}
                e["confirme"] = {"note": c.get("sealed_moy"), "ecart": vpc.get("delta_moy"),
                                 "tient": isinstance(vpc.get("delta_moy"), (int, float)) and vpc["delta_moy"] >= PROGRES}
            else:
                lm = en_mesure(t + "c")
                if lm:
                    e["confirmation_en_cours"] = lm
            lm = en_mesure(t)
            if lm and not m:
                e["mesure_en_cours"] = lm
            essais.append(e)
        # parent des essais de la passe suivante = champion apres cette passe
        suiv = [geste(os.path.basename(f)[:-5]).get("parent") for f in glob.glob(M + "gestes/%sr%dm[0-9].json" % (P, r + 1))]
        suiv = [x for x in suiv if x]
        mesures = [e for e in essais if e.get("note") is not None]
        meilleur = max(mesures, key=lambda e: e["note"]) if mesures else None
        attente = any(e["verdict"] == "attente" or e.get("confirmation_en_cours") or e.get("mesure_en_cours") for e in essais)
        confirme = [e for e in essais if (e.get("confirme") or {}).get("tient")]
        nouveau = None
        cand = suiv[0] if suiv else (champ_etat if champ_etat and rx_essai.match(champ_etat) and int(rx_essai.match(champ_etat).group(1)) == r else None)
        if cand and cand != champ and rx_essai.match(cand) and int(rx_essai.match(cand).group(1)) == r:
            nouveau = cand
        elif confirme and not suiv and r != tour_max:
            nouveau = P + "r%dm%d" % (r, max(confirme, key=lambda e: e["confirme"]["note"])["num"] - 1)
        if nouveau:
            verdict = "progres"
        elif r == tour_max and (attente or not mesures) and not suiv:
            verdict = "encours"
        elif mesures and all(e["verdict"] == "recul" for e in mesures):
            verdict = "recul"
        elif mesures:
            verdict = "stagnation"
        else:
            verdict = "encours" if r == tour_max else "stagnation"
        champ_avant, note_avant = champ, champ_note
        if nouveau:
            champ = nouveau
            champ_note, champ_cats = note_retenue(nouveau)
        # --- etapes conditionnelles, avec leur raison
        S = STRAT.get(r) or {}
        a = AUD.get(r)
        prec = passes[-1]["verdict"] if passes else None
        if a:
            txt = RES.get("audit-t%d" % r) or a.get("en_clair") or ""
            causes = []
            for cz in (a.get("causes") or [])[:4]:
                x = fr(cz.get("en_clair") or "") or phrases(cz.get("cause"), 1, 240)
                causes.append({"texte": x, "cas": cz.get("nb_cas"), "cats": [c for c in (cz.get("categories") or []) if c in CATS],
                               "code": cz.get("corrigeable_par_code")})
            audit = {"fait": True, "texte": fr(txt) if txt else "", "causes": causes}
            if not audit["texte"] and not causes:
                audit["texte"] = "L'audit a été fait, mais son résumé est trop technique pour être affiché ici."
        else:
            raison = ("première passe : c'est la fiche de départ qui a servi de diagnostic" if r == min(tours) else
                      "la passe %d avait progressé, pas besoin de chercher pourquoi ça bloque" % (r - 1) if prec == "progres" else
                      "pas d'audit enregistré pour cette passe")
            audit = {"fait": False, "raison": raison}
        if S.get("niveau2"):
            n2 = {"fait": True, "texte": RES.get("niveau2-t%d" % r) or phrases(S.get("methode") if isinstance(S.get("methode"), str) else json.dumps(S.get("methode") or "", ensure_ascii=False), 2)
                  or "La boucle a revu sa propre méthode ; ses propositions attendent ton avis."}
        else:
            n2 = {"fait": False, "raison": "elle ne se déclenche qu'après 2 passes d'affilée sans progrès (%s)" % (
                "aucune avant celle-ci" if sans_prog == 0 else "une seule avant celle-ci" if sans_prog == 1 else "%d avant celle-ci" % sans_prog)}
        strat = RES.get("strategie-t%d" % r) or fr(S.get("en_clair") or "") or phrases(S.get("hypothese"), 2) or phrases(S.get("strategie"), 2)
        if not strat and essais:
            strat = "Cette passe essaie %s : %s." % ("une idée" if len(essais) == 1 else "%d idées" % len(essais), ", ".join("« %s »" % e["titre"] for e in essais))
        # --- decision en clair
        if verdict == "progres":
            nc = next((e for e in essais if P + "r%dm%d" % (r, e["num"] - 1) == champ), None)
            dec = "Nouveau champion : « %s », %s %% (%s points sur l'ancien champion)." % (
                nc["titre"] if nc else "?", _f(champ_note), _sg(champ_note - note_avant) if champ_note is not None and note_avant is not None else "?")
            autres = [e for e in essais if e is not nc and e["verdict"] == "progres" and champ_note is not None]
            for e in autres:
                n = (e.get("confirme") or {}).get("note") or e.get("note")
                if n is not None and n > champ_note:
                    dec += " « %s » fait à peine mieux (%s point%s) : trop peu pour compter, il faut 5 points." % (
                        e["titre"], _sg(n - champ_note), "s" if abs(n - champ_note) >= 2 else "")
        elif verdict == "encours":
            dec = "Pas encore décidé : " + ("des essais sont encore en mesure." if any(e.get("mesure_en_cours") for e in essais) else
                                             "la confirmation est en cours sur d'autres postes." if any(e.get("confirmation_en_cours") for e in essais) else
                                             "les essais ne sont pas encore tous mesurés.")
        else:
            dec = "Pas de nouveau champion : aucun essai ne gagne 5 points. « %s » reste champion." % (_titre_champ(champ, geste, rx_dep))
        passes.append({"tour": r, "verdict": verdict, "strategie": strat, "alerte": RES.get("alerte-t%d" % r) or "",
                       "audit": audit, "niveau2": n2, "essais": essais, "decision": dec, "propositions": PROP.get(r, []),
                       "meilleur": {k: meilleur.get(k) for k in ("num", "titre", "note", "cats", "vitesse", "tokens")} if meilleur else None,
                       "champion_avant": {"tag": champ_avant, "note": note_avant},
                       "champion": dict(perf_champ(champ), titre=_titre_champ(champ, geste, rx_dep), note=champ_note, cats=champ_cats)})
        sans_prog = 0 if verdict == "progres" else sans_prog + (1 if verdict in ("stagnation", "recul") else 0)
    # --- cycles a deux niveaux (entrainement puis examen) ---
    cyc = cycles_deux_niveaux(P, NOUVEAUX, etat, geste, dern, live, AUD, STRAT, PROP, RES, champ, champ_note, champ_cats, perf_champ, rx_dep)
    if cyc["passes"]:
        passes += cyc["passes"]
        champ, champ_note, champ_cats = cyc["champ"], cyc["champ_note"], cyc["champ_cats"]
        tour_max = max(tour_max, max(p["tour"] for p in cyc["passes"]))
    ch_titre = _titre_champ(champ, geste, rx_dep)
    ce = ((etat.get("champion") or {}).get("entrainement") or {})
    try:
        graphe_n1 = entrainement_graphe(passes)
    except Exception as ex:   # le graphique ne doit jamais casser l'histoire
        graphe_n1 = {"points": [], "racines": [], "exclues": [], "erreur": str(ex)[:200]}
    return {"entrainement_graphe": graphe_n1, "paliers": etat.get("paliers"), "cycle": cyc.get("courant"), "entrainement_meilleure": ce.get("moy"), "jeu_entrainement": ce.get("jeu"),
            "verification_meilleure": ((etat.get("champion") or {}).get("verification") or {}).get("moy"), "echecs_examen": etat.get("echecsExamen"), "prefixe": P, "cible": cible, "depart": depart, "passes": passes, "tour": tour_max,
            "champion": {"titre": ch_titre, "note": champ_note, "cats": champ_cats, "depart": bool(champ and rx_dep.match(champ)),
                         "gain": round(champ_note - depart["note"], 1) if depart and champ_note is not None else None}}


# SOBRIETE : libelles courts, resultat d'abord, aucune phrase qui explique, aucun chiffre en double.
DECISION = {"racine": "meilleure version", "a entrainer": "à entraîner", "garder": "monte", "developper": "développé", "elaguer": "élagué",
            "examen": "au palier", "impasse": "impasse", "ecarte": "écarté", "panne": "panne"}


def cycles_deux_niveaux(P, NOUVEAUX, etat, geste, dern, live, AUD, STRAT, PROP, RES, champ, champ_note, champ_cats, perf_champ, rx_dep):
    """(architecture a deux niveaux + recherche en arbre) : un cycle = NIVEAU 1 (lecture des fautes, strategie, ARBRE d'essais
    notes sur le jeu d'entrainement : on elague ce qui baisse, on developpe ce qui monte) puis, si une branche franchit le
    palier, NIVEAU 2 (examen, recorrection, verification). L'arbre vient du JOURNAL UNIQUE du niveau 1 (journal-arbre.jsonl,
    une ligne par noeud). Les notes d'ENTRAINEMENT et d'EXAMEN ne sont jamais melangees : les graphiques ne montrent que l'examen."""
    out = {"passes": [], "champ": champ, "champ_note": champ_note, "champ_cats": champ_cats, "courant": None}
    LIB = _js(D + "libelles.json", {}) or {}
    JA = {}
    for o in _jl(M + "journal-arbre.jsonl"):
        try: JA.setdefault(int(o["tour"]), []).append(o)
        except Exception: pass
    NOUVEAUX = set(NOUVEAUX) | set(JA)
    if not NOUVEAUX:
        return out
    n1 = etat.get("n1") if isinstance(etat.get("n1"), dict) else None
    EXA = {}
    for x in etat.get("examens") or []:
        try: EXA[int(x["tour"])] = x
        except Exception: pass
    echecs = 0

    def en_mes(tag, graine):
        parts = [x for x in live if x.get("tag") == tag and (x.get("graine") in (graine, None))]
        run = [x for x in parts if x.get("etat") in ("mesure", "attend le poste")]
        if not run:
            return None
        base = str(run[0].get("id", "")).split("~")[0]
        parts = [x for x in parts if str(x.get("id", "")).split("~")[0] == base and "~p" in str(x.get("id", ""))] or run
        tot = sum(((x.get("progres") or {}).get("total") or 0) for x in parts)
        fait = sum(((x.get("progres") or {}).get("total") or 0) if x.get("etat") == "fini" else ((x.get("progres") or {}).get("fait") or 0) for x in parts)
        return {"fait": fait, "total": tot or None, "pct": round(100 * fait / tot) if tot else 0}

    for r in sorted(NOUVEAUX):
        lignes = sorted(JA.get(r, []), key=lambda o: o.get("noeud") or 0)
        racine = next((o for o in lignes if o.get("noeud") == 0), {})
        encours = bool(n1 and n1.get("tour") == r)
        S = STRAT.get(r) or {}
        champ_avant, note_avant = champ, champ_note
        # --- l'ARBRE (racine = meilleure version ; un noeud par essai entraine)
        noeuds = []
        for o in lignes:
            if o.get("noeud") == 0:
                continue
            g = geste(o.get("tag")) if o.get("tag") else {}
            x = {"id": o.get("noeud"), "parent": o.get("parent") or 0, "famille": acc(o.get("famille") or g.get("famille")) or None, "decision": o.get("decision"), "decision_txt": DECISION.get(o.get("decision"), o.get("decision") or ""),
                 "note": o.get("moyenne"), "cats": o.get("notes"), "changement": fr(o.get("changement") or "") or g.get("titre") or "essai",
                 "court": fr(((LIB.get(o.get("tag")) or {}) if isinstance(LIB.get(o.get("tag")), dict) else {}).get("court") or g.get("titre") or ""),
                 "titre": g.get("titre") or "", "raison": fr(o.get("raison") or ""), "quand": o.get("quand_mesure") or o.get("quand"), "conditions": o.get("conditions"),
                 "vitesse": o.get("vitesse"), "examen": o.get("examen"), "probleme": g.get("probleme"), "idee": g.get("idee"), "attendu": g.get("attendu"),
                 # (arret sequentiel) : noeud ARRETE TOT par le juge -> pas de note complete (note = None), un encadrement
                 "arret_tot": o.get("arret_tot") if isinstance(o.get("arret_tot"), dict) else None, "ecart_parent": o.get("ecart_parent")}
            if x["note"] is None and encours and x["decision"] == "a entrainer":
                x["en_mesure"] = en_mes(o.get("tag"), "entrainement")
            noeuds.append(x)
        # profondeur
        par = {n["id"]: n for n in noeuds}
        for n in noeuds:
            d, y = 1, n
            while y["parent"] and y["parent"] in par and d < 30:
                d += 1; y = par[y["parent"]]
            n["profondeur"] = d
        # --- examen (niveau 2)
        x = EXA.get(r)
        examen = None
        cand = (n1 or {}).get("candidat") if encours else None
        if x:
            nd = par.get(x.get("essai")) or {}
            if nd: nd["decision_txt"] = "examen"
            examen = {"num": x.get("essai"), "titre": nd.get("court") or nd.get("changement") or geste(x.get("tag")).get("titre") or "essai", "note": x.get("examen"), "cats": x.get("examen_vec"),
                      "delta": x.get("delta"), "gagnes": x.get("gagnes"), "perdus": x.get("perdus"), "entrainement": x.get("note_entrainement"),
                      "recorrection": x.get("recorrection"), "verification": x.get("verification"), "verdict": x.get("verdict"),
                      "vitesse": x.get("vitesse"), "conditions": x.get("conditions"), "tokens": (dern.get(str(x.get("tag"))) or {}).get("tokens", {}).get("moy") if isinstance((dern.get(str(x.get("tag"))) or {}).get("tokens"), dict) else None}
        elif cand:
            nd = par.get(cand.get("num")) or {}
            if nd: nd["decision_txt"] = "à l'examen"
            examen = {"num": cand.get("num"), "titre": nd.get("changement") or "essai", "note": None, "entrainement": cand.get("entrainement"),
                      "en_mesure": en_mes(cand.get("tag"), "complet") or en_mes(str(cand.get("tag")) + "c", "complet")}
        palier = racine.get("palier") or ((n1 or {}).get("palier") if encours else None)
        issue = racine.get("issue") or ""
        if examen and examen.get("verdict") == "nouvelle meilleure version":
            verdict = "progres"
            champ, champ_note, champ_cats = x.get("tag"), examen["note"], examen.get("cats") or {}
            rc = examen.get("recorrection") or {}; vf = examen.get("verification") or {}
            dec = "Nouvelle meilleure : branche %s" % examen.get("num")
            echecs = 0
        elif examen and examen.get("verdict") == "echec examen":
            verdict = "echec_examen"; echecs += 1
            rc = examen.get("recorrection") or {}
            dec = "Échec examen %d/2 · il faut +5" % echecs
        elif issue.startswith("aucune branche"):
            verdict = "sans_palier"
            dec = "Aucune branche au palier · nouvelle stratégie"
        else:
            verdict = "encours"
            ph = (n1 or {}).get("phase") if encours else ""
            dec = {"lecture": "Lecture des fautes", "donnees": "Correction du jeu d'entraînement", "strategie": "Stratégie et premières branches",
                   "entrainement": "Arbre · tour %s" % ((n1 or {}).get("tourEntrainement") or 1), "decision": "Palier ?",
                   "examen": "Examen de la branche %s" % (((n1 or {}).get("candidat") or {}).get("num") or "?")}.get(ph, "En cours")
        a = AUD.get(r)
        audit = {"fait": False, "raison": "pas encore faite"}
        if a:
            causes = [{"texte": fr(cz.get("en_clair") or "") or phrases(cz.get("cause"), 1, 240), "cas": cz.get("nb_cas"), "cats": [k for k in (cz.get("categories") or []) if k in CATS]} for cz in (a.get("causes") or [])[:4]]
            ecarts = [{"cat": ec.get("categorie"), "texte": fr(ec.get("constat") or ""), "corriger": ec.get("corriger_donnees")} for ec in (a.get("ecarts_entrainement_examen") or [])]
            if isinstance(RES.get("causes-t%d" % r), list):
                causes = [{"texte": x.get("texte"), "cas": x.get("cas"), "cats": []} for x in RES["causes-t%d" % r]]
            audit = {"fait": True, "texte": fr(RES.get("audit-t%d" % r) or a.get("en_clair") or ""), "causes": causes, "ecarts": ecarts}
        corr = _js(M + "donnees/correction-t%d.json" % r)
        donnees = {"ok": corr.get("ok"), "texte": fr(RES.get("donnees-t%d" % r) or corr.get("resume") or ""), "fichier": corr.get("fichier"), "n": corr.get("n"), "cats": corr.get("categories")} if corr else None
        n2 = {"fait": True, "texte": " ".join(PROP.get(r))} if PROP.get(r) else \
             {"fait": False, "raison": "échecs %d/2" % echecs}
        if n2["fait"]:
            echecs = 0
        strat = RES.get("strategie-t%d" % r) or fr(S.get("en_clair") or "") or phrases(S.get("hypothese"), 2) or phrases(S.get("strategie"), 2)
        meilleur = {"num": examen.get("num"), "titre": examen["titre"], "note": examen["note"], "cats": examen.get("cats"), "vitesse": examen.get("vitesse"), "tokens": examen.get("tokens")} \
            if examen and examen.get("note") is not None else None
        p = {"tour": r, "deux_niveaux": True, "verdict": verdict, "palier": palier, "strategie": strat, "alerte": RES.get("alerte-t%d" % r) or "",
             "audit": audit, "donnees": donnees, "niveau2": n2, "racine": {"note": racine.get("moyenne"), "cats": racine.get("notes")}, "arbre": noeuds,
             "essais": noeuds, "examen": examen, "decision": dec, "propositions": PROP.get(r, []),
             "tour_entrainement": (n1 or {}).get("tourEntrainement") if encours else None, "phase": (n1 or {}).get("phase") if encours else None, "meilleur": meilleur,
             "champion_avant": {"tag": champ_avant, "note": note_avant},
             "champion": dict(perf_champ(champ), titre=_titre_champ(champ, geste, rx_dep), note=champ_note, cats=champ_cats)}
        # « Plan de départ » = stratégie + critique + correction fusionnées à l'écran (plan_depart.py)
        try:
            import plan_depart
            p["plan"] = plan_depart.plan(r, S.get("strategie"))
        except Exception:
            p["plan"] = None
        out["passes"].append(p)
        if encours:
            out["courant"] = {"tour": r, "phase": (n1 or {}).get("phase"), "palier": palier, "tour_entrainement": (n1 or {}).get("tourEntrainement")}
    out.update(champ=champ, champ_note=champ_note, champ_cats=champ_cats)
    return out


def _f(x):
    return ("%.1f" % x).replace(".", ",") if isinstance(x, (int, float)) else "—"


def _sg(x):
    return ("+" if x >= 0 else "−") + _f(abs(x))


def _titre_champ(tag, geste, rx_dep):
    if not tag:
        return "—"
    if rx_dep.match(tag):
        return "version de départ"
    return geste(tag)["titre"] or "champion"


# GRAPHIQUE DE TOUTES LES TENTATIVES NOTEES A L'ENTRAINEMENT (niveau 1). Un point par essai qui a une note
# COMPLETE (jamais une estimation d'arret tot), a l'heure de sa mesure ; escalier = note d'entrainement de la meilleure version
# (racine de chaque passe) ; seuil = palier de la passe en cours. Les notes sur des jeux d'entrainement differents ne sont pas
# comparables : chaque point porte son jeu (champ `jeu` du noeud, sinon celui de la racine) et la page coupe l'axe a chaque
# changement de jeu. Archives (journal-arbre.*.jsonl, archive-*/journal-arbre.jsonl) : montrees en grise si elles ont ete
# mesurees sur un seul jeu IDENTIQUE au fichier actuel (mesure posterieure a sa derniere ecriture), sinon EXCLUES et comptees.
# Rien n'est invente : aucune note, aucune heure qui ne soit dans un journal.
CLASSE = {"developper": "garde", "garder": "garde", "elaguer": "elague", "impasse": "impasse", "examen": "examen"}


def _utc(t):
    """'2026-09-28 08:16' ou '2026-09-28T09:18' (UTC, sans fuseau) -> secondes epoch ; None si illisible."""
    import datetime as _dt
    if not t:
        return None
    try:
        return _dt.datetime.strptime(str(t)[:16].replace("T", " "), "%Y-%m-%d %H:%M").replace(tzinfo=_dt.timezone.utc).timestamp()
    except Exception:
        return None


def entrainement_graphe(passes):
    titres = {}
    for p in passes or []:
        if p.get("deux_niveaux"):
            for n in p.get("arbre") or []:
                titres[(p["tour"], n.get("id"))] = n
    mt = {}

    def jeu_ok(jeu, t):   # mesure faite sur le fichier ACTUEL de ce jeu (pas une version reecrite depuis)
        if jeu not in mt:
            try: mt[jeu] = os.path.getmtime(M + "donnees/" + jeu)
            except Exception: mt[jeu] = None
        return mt[jeu] is not None and t is not None and t >= mt[jeu]

    def lire(chemin):
        lignes = _jl(chemin)
        rac = {o.get("tour"): o for o in lignes if o.get("noeud") == 0}
        pts = []
        for o in lignes:
            if o.get("noeud") in (0, None) or not isinstance(o.get("moyenne"), (int, float)):
                continue
            t = _utc(o.get("quand_mesure") or o.get("quand"))
            if t is None:
                continue
            jeu = o.get("jeu") or (rac.get(o.get("tour")) or {}).get("jeu")
            pts.append({"t": t, "note": o.get("moyenne"), "tour": o.get("tour"), "id": o.get("noeud"), "jeu": jeu,
                        "famille": acc(o.get("famille") or "") or None, "classe": CLASSE.get(o.get("decision"), "autre"),
                        "decision": DECISION.get(o.get("decision"), o.get("decision") or ""), "_o": o})
        return rac, pts

    rac, pts = lire(M + "journal-arbre.jsonl")
    for x in pts:
        n = titres.get((x["tour"], x["id"])) or {}
        x["titre"] = n.get("court") or n.get("changement") or fr(x["_o"].get("changement") or "") or "essai"
        if n.get("decision_txt"):
            x["decision"] = n["decision_txt"]
        if n.get("famille"):
            x["famille"] = n["famille"]
        del x["_o"]
    racines = sorted([{"t": _utc(o.get("quand")), "note": o.get("moyenne"), "tour": o.get("tour"), "jeu": o.get("jeu"), "palier": o.get("palier")}
                      for o in rac.values() if isinstance(o.get("moyenne"), (int, float)) and _utc(o.get("quand"))], key=lambda r: r["t"])
    archives, exclues = [], []
    for ch in sorted(set(glob.glob(M + "journal-arbre.*.jsonl") + glob.glob(M + "archive-*/journal-arbre.jsonl"))):
        if ".bak" in ch:
            continue
        _, ap = lire(ch)
        if not ap:
            continue
        for x in ap:
            x["titre"] = fr(x["_o"].get("changement") or "") or "essai"
            del x["_o"]
        jeux = {x["jeu"] for x in ap}
        nom = "nuit invalidée" if "nuit-invalidee" in ch else "archive"
        if len(jeux) == 1 and all(jeu_ok(x["jeu"], x["t"]) for x in ap):
            for x in ap:
                x["archive"] = nom
            archives += ap
        else:
            exclues.append({"nom": nom, "n": len(ap), "debut": min(x["t"] for x in ap), "fin": max(x["t"] for x in ap),
                            "raison": "jeux mélangés" if len(jeux) > 1 else "ancien jeu"})
    return {"points": sorted(pts + archives, key=lambda x: x["t"]), "racines": racines, "exclues": exclues}


histoire = main_histoire

if __name__ == "__main__":
    print(json.dumps(main_histoire(), ensure_ascii=False, indent=1))
