"""plan_depart.py — l'étape « Plan de départ » du tableau de bord fusionne à l'ÉCRAN les 3 étapes du moteur
Stratégie · Critique · Stratégie corrigée (le moteur, lui, ne change pas : les trois continuent d'exister).
Données, rien d'inventé :
  - strategies.jsonl (persistant) : la stratégie définitive de chaque passe ;
  - le journal du workflow (runs */subagents/workflows/wf_*/journal.jsonl) : résultats « reflexion verdict tN » (stratégie avant
    critique), « critique verdict tN » (liste des critiques), « reflexion correction tN » (stratégie corrigée), et heures des agents.
  Le bon run est celui dont la stratégie corrigée == la stratégie de strategies.jsonl pour cette passe (les runs d'une nuit
  invalidée portent aussi des « t2 » : ils ne correspondent pas et sont ignorés).
Cache persistant : plan-depart.json (une entrée par passe + la signature de la stratégie) — survit à la disparition d'un run.
Lecture seule côté moteur."""
import glob, json, os, re
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reglages
D = reglages.DIR   # le cache plan-depart.json vit dans le dossier du tableau
BASES = reglages.TRANSCRIPTS
CACHE = D + "plan-depart.json"
SOUS = [("strategie", r"^reflexion (\d|verdict)"), ("critique", r"^critique (\d|verdict)"), ("correction", r"^reflexion correction")]


def _sig(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()[:400]


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _heures(d, aid):
    deb = fin = None
    try:
        for l in open(os.path.join(d, "agent-%s.jsonl" % aid), encoding="utf-8"):
            try:
                t = _ts(json.loads(l).get("timestamp", ""))
            except Exception:
                continue
            if t:
                deb = deb or t
                fin = t
    except Exception:
        pass
    return deb, fin


def _titre_critique(c):
    """« VERDICT 9 : E3 EST RETIRÉ (consensus…). Le plancher… » -> « E3 est retiré » (le titre que la critique se donne)."""
    c = re.sub(r"^\s*VERDICT\s*\d+\s*:\s*", "", str(c or ""))
    t = re.split(r"\s\(|\.\s|\. ?$|, (?=[A-Z])", c, 1)[0].strip()
    # mots tout en capitales (3 lettres et plus, hors codes comme E3, T0, 1B) -> minuscules ; majuscule en tête
    GARDE = {"RDV", "JSON", "URL", "IA", "API", "HTML", "FR", "EN", "GPU"}
    t = re.sub(r"\b[^\W\d_]{2,}\b", lambda m: m.group(0).lower() if m.group(0).isupper() and m.group(0) not in GARDE else m.group(0), t)
    t = re.sub(r"(?<=\s)([LDNSCJM])(?=['’])|(?<=\s)À\b", lambda m: m.group(0).lower(), t)   # L', D', À isolés
    t = t[:1].upper() + t[1:]
    if len(t) > 70:   # un titre, pas un paragraphe : on garde sa tête entière (avant « : » ou « , »)
        t = re.split(r" : |, ", t, 1)[0]
    return t


def _lire_run(d, tour):
    lab, res = {}, {}
    try:
        for l in open(os.path.join(d, "journal.jsonl"), encoding="utf-8"):
            try:
                o = json.loads(l)
            except Exception:
                continue
            if o.get("type") == "started":
                lab[o["key"]] = (o.get("label") or "", o.get("agentId"))
            elif o.get("type") == "result" and o.get("key") in lab:
                res[o["key"]] = o.get("result")
    except Exception:
        return None
    suf = " t%d" % tour
    agents = [(lb[:-len(suf)], aid, res.get(k)) for k, (lb, aid) in lab.items() if lb.endswith(suf)]
    corr = next((r for lb, _, r in agents if lb == "reflexion correction" and isinstance(r, dict)), None)
    return agents, corr


def plan(tour, strategie):
    """-> {critiques:[titres], n_critiques, corrigee:bool, duree:s, durees:{strategie,critique,correction}} ou None."""
    sig = _sig(strategie)
    if not sig:
        return None
    try:
        C = json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        C = {}
    k = str(tour)
    if C.get(k, {}).get("sig") == sig:
        return C[k]["plan"]
    runs = sorted([r for B in BASES for r in glob.glob(B + "/*/subagents/workflows/wf_*")], key=lambda p: os.stat(p).st_mtime, reverse=True)
    for d in runs:
        lu = _lire_run(d, tour)
        if not lu or not lu[1] or _sig(lu[1].get("strategie")) != sig:
            continue
        agents, corr = lu
        avant = next((r for lb, _, r in agents if lb == "reflexion verdict" and isinstance(r, dict)), {}) or {}
        cv = next((r for lb, _, r in agents if lb == "critique verdict" and isinstance(r, dict)), {}) or {}
        crit = [c for c in (cv.get("critiques") or []) if str(c).strip()]
        durees = {}
        for nom, rx in SOUS:
            h = [_heures(d, aid) for lb, aid, _ in agents if aid and re.search(rx, lb)]
            deb = [a for a, _ in h if a]; fin = [b for _, b in h if b]
            if deb and fin:
                durees[nom] = round(max(fin) - min(deb))
        p = {"critiques": [_titre_critique(c) for c in crit], "n_critiques": len(crit),
             "corrigee": bool(crit) and _sig(corr.get("strategie")) != _sig(avant.get("strategie")),
             "duree": sum(durees.values()) or None, "durees": durees}
        C[k] = {"sig": sig, "plan": p, "run": os.path.basename(d)}
        try:
            json.dump(C, open(CACHE + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(CACHE + ".tmp", CACHE)
        except Exception:
            pass
        return p
    return (C.get(k) or {}).get("plan")   # run disparu et stratégie changée : dernière donnée connue, sinon None


if __name__ == "__main__":
    for l in open(reglages.MOTEUR + "strategies.jsonl", encoding="utf-8"):
        o = json.loads(l)
        print(o["tour"], json.dumps(plan(int(o["tour"]), o.get("strategie")), ensure_ascii=False, indent=1))
