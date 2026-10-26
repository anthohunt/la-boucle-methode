#!/usr/bin/env python3
"""Fabrique un jeu de donnees SYNTHETIQUE pour le tableau de la boucle.

Tout est invente : une bibliotheque municipale fictive (« Valbourg ») dont un petit modele doit tirer
les reservations d'un message. Aucune donnee reelle, aucun nom reel. Les dates sont en 2030.

Usage : python3 generer-donnees.py [dossier-de-sortie]      (defaut : ce dossier)
Ecrit  <sortie>/etat-boucle/   (ce que la boucle ecrit : chantier, journal de l'arbre, gestes, strategies, audits)
       <sortie>/tableau/       (config du tableau, mesures, resumes ecrits a la main)
puis lancer, depuis modele/ :
  DASH_MOTEUR=<sortie>/etat-boucle DASH_DIR=<sortie>/tableau python3 generer.py
"""
import json
import os
import random
import sys

SORTIE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
E_ = os.path.join(SORTIE, "etat-boucle")
T_ = os.path.join(SORTIE, "tableau")
for d in (E_, os.path.join(E_, "gestes"), T_):
    os.makedirs(d, exist_ok=True)

CATS = ["claire", "multiple", "floue", "vide", "piege", "hostile"]
P = "vb"                      # prefixe des essais
rnd = random.Random(7)


def ecrire(chemin, obj):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def jsonl(chemin, lignes):
    with open(chemin, "w", encoding="utf-8") as f:
        for o in lignes:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")


def vecteur(moy, etalement=14.0):
    """6 notes (une par categorie) dont la moyenne vaut `moy` a 0,1 pres."""
    base = [rnd.uniform(-etalement, etalement) for _ in CATS]
    m = sum(base) / len(base)
    v = [max(0.0, min(100.0, moy + b - m)) for b in base]
    ecart = moy - sum(v) / len(v)
    v = [max(0.0, min(100.0, x + ecart)) for x in v]
    return {c: round(x, 1) for c, x in zip(CATS, v)}


def moyenne(v):
    return round(sum(v.values()) / len(v), 1)


# ---------------------------------------------------------------- configuration du tableau
ecrire(os.path.join(T_, "dashboard.config.json"), {
    "titre": "Tickets → réservations (données d'exemple)",
    "surtitre": "Boucle d'amélioration automatique",
    "intro": "Données synthétiques : un petit modèle lit un message adressé à la bibliothèque fictive de Valbourg et doit en tirer les réservations à enregistrer. La boucle entraîne ses essais sur des cas dont elle voit les fautes, puis envoie à l'examen l'essai qui franchit un palier.",
    "unite": ["message", "messages"], "unite_vitesse": "message",
    "categories": {
        "claire": {"nom": "Une réservation claire", "court": "Claire"},
        "multiple": {"nom": "Plusieurs réservations", "court": "Plusieurs"},
        "floue": {"nom": "Réservation floue", "court": "Floue"},
        "vide": {"nom": "Aucune réservation", "court": "Aucune"},
        "piege": {"nom": "Piège (fausse date)", "court": "Piège"},
        "hostile": {"nom": "Message malveillant", "court": "Hostile"}},
    "tailles": {"entrainement": 120, "examen": 240, "verification": 90},
    "progres_min": 5.0,
    "noms_postes": {"poste-a": "machine-A", "poste-b": "machine-B"}})

ecrire(os.path.join(E_, "chantier-valbourg.json"), {
    "prefixe": P, "serie_debut": "2030-03-01T00:00:00",
    "objectif": {"qualite_pct_par_categorie": {c: {"minimum": 80, "ideal": 92} for c in CATS},
                 "temps_par_cas_s": {"minimum": 4.0, "ideal": 2.0}}})

# ---------------------------------------------------------------- mesures (resultats-moteur.jsonl)
res = []


def mesure(tag, jeu, moy, n, t, vit=3.1, tok=410, vs=None):
    o = {"tag": tag, "ok": True, "jeu": jeu, "sealed_moy": moy, "sealed": vecteur(moy), "n": n, "ts": t,
         "vitesse": {"moy": vit}, "tokens": {"moy": tok}}
    if vs:
        o["vs_parent"] = vs
    res.append(o)
    return o


mesure(P + "dep-ex", "examen", 28.0, 240, "2030-03-01T09:00:00Z")

# ---------------------------------------------------------------- l'arbre, passe par passe
arbre, gestes, strategies, audits, examens = [], {}, [], [], []
FAM = {"consigne": "retouche de la consigne", "prog": "le programme aide le modèle", "trier": "trier puis spécialiser par type de message",
       "relire": "relecture / vérification"}


def noeud(tour, n, parent, tag, famille, dec, moy, quand, changement, titre, probleme, idee, attendu, raison=""):
    v = vecteur(moy) if moy is not None else None
    arbre.append({"tour": tour, "noeud": n, "parent": parent, "tag": tag, "famille": famille, "decision": dec,
                  "moyenne": moy, "notes": v, "changement": changement, "raison": raison, "quand": quand,
                  "quand_mesure": quand, "jeu": "entrainement-v1.jsonl", "conditions": {"poste": "machine-A", "gpu": False},
                  "vitesse": 3.0})
    gestes[tag] = {"titre": titre, "description": changement, "famille": famille, "parent": None,
                   "journal": {"probleme": probleme, "idee": idee, "attendu": attendu}}


def racine(tour, moy, palier, quand, issue=""):
    arbre.append({"tour": tour, "noeud": 0, "moyenne": moy, "notes": vecteur(moy), "palier": palier, "quand": quand,
                  "jeu": "entrainement-v1.jsonl", "issue": issue})


# passe 1
racine(1, 30.0, 50.0, "2030-03-01 10:00")
noeud(1, 1, 0, P + "r1n1", FAM["consigne"], "developper", 41.0, "2030-03-01 10:40", "Consigne avec exemples de réservations multiples", "Consigne corrigée, exemples multiples",
      "Le modèle ne rend qu'une réservation quand le message en contient plusieurs.", "Ajouter trois exemples de messages à plusieurs réservations.", "Les messages multiples montent.")
noeud(1, 2, 0, P + "r1n2", FAM["prog"], "developper", 46.0, "2030-03-01 10:50", "Le programme refuse les dates passées", "Dates passées refusées par le programme",
      "Les fausses dates (le jour de l'envoi recopié) passent.", "Un contrôle de code écarte toute date antérieure à l'envoi.", "Les pièges tombent.")
noeud(1, 3, 0, P + "r1n3", FAM["consigne"], "elaguer", 29.0, "2030-03-01 11:00", "Réponse en lignes simples", "Réponse en lignes simples",
      "Le format de réponse est parfois illisible.", "Demander des lignes simples plutôt qu'un objet structuré.", "Moins de réponses illisibles.", "plus bas que sa racine")
noeud(1, 4, 2, P + "r1n4", FAM["trier"], "examen", 53.5, "2030-03-01 12:30", "Classer le message, puis consigne adaptée", "Trier le message puis consigne adaptée",
      "Une seule consigne ne convient pas à tous les types de messages.", "Un premier appel classe le message, le second utilise la consigne de sa classe.", "Les cas flous et multiples montent ensemble.")
mesure(P + "r1n4", "examen", 36.2, 240, "2030-03-01 14:00:00Z", 6.4, 790, {"delta_moy": 8.2, "gagnes": 31, "perdus": 11})
mesure(P + "r1n4c", "examen", 35.4, 240, "2030-03-01 15:30:00Z", 6.4, 790, {"delta_moy": 7.4, "gagnes": 29, "perdus": 11})
examens.append({"tour": 1, "essai": 4, "tag": P + "r1n4", "examen": 36.2, "examen_vec": vecteur(36.2), "delta": 8.2, "gagnes": 31, "perdus": 11,
                "note_entrainement": 53.5, "recorrection": {"delta": 7.4}, "verification": {"note": 35.1, "ancienne": 27.0},
                "verdict": "nouvelle meilleure version", "vitesse": 6.4, "conditions": {"poste": "machine-A", "gpu": False}})
strategies.append({"tour": 1, "niveau": 1, "en_clair": "Nettoyage par code, puis trier avant de répondre",
                   "strategie": "Trois pistes : exemples multiples, contrôle de dates par le programme, réponse simplifiée."})
audits.append({"tour": 1, "audit": {"en_clair": "Trois causes expliquent la plupart des fautes.", "causes": [
    {"en_clair": "Message malveillant non refusé · 14 pts", "nb_cas": 22, "categories": ["hostile"]},
    {"en_clair": "Plusieurs réservations : une seule rendue · 11 pts", "nb_cas": 25, "categories": ["multiple"]},
    {"en_clair": "Date d'envoi recopiée comme date de réservation · 8 pts", "nb_cas": 18, "categories": ["piege"]}]}})
# passe 2
racine(2, 53.5, 73.5, "2030-03-02 09:00")
noeud(2, 1, 0, P + "r2n1", FAM["relire"], "developper", 60.0, "2030-03-02 09:40", "Relecture des dates par un second appel", "Relecture des dates par un second appel",
      "Les dates relatives (« jeudi prochain ») sont mal résolues.", "Un second appel relit les dates du résultat.", "Moins d'erreurs de date.")
noeud(2, 2, 0, P + "r2n2", FAM["consigne"], "elaguer", 51.0, "2030-03-02 09:50", "Consigne plus longue avec règles", "Consigne plus longue",
      "Les règles de la consigne se contredisent.", "Réécrire les règles dans l'ordre.", "Moins de contradictions.", "plus bas que sa racine")
noeud(2, 3, 0, P + "r2n3", FAM["trier"], "developper", 63.8, "2030-03-02 10:10", "Une consigne par type de message", "Une consigne par type de message",
      "Les messages flous reçoivent la consigne des messages clairs.", "Écrire une consigne dédiée aux messages flous.", "Les cas flous montent.")
noeud(2, 4, 3, P + "r2n4", FAM["prog"], "developper", 70.1, "2030-03-02 11:30", "Contrôle de cohérence des heures par le programme", "Heures incohérentes écartées par le programme",
      "Des heures hors des horaires d'ouverture passent.", "Le programme refuse une heure hors horaires.", "Moins de réservations impossibles.")
noeud(2, 5, 4, P + "r2n5", FAM["relire"], "examen", 75.0, "2030-03-02 12:40", "Relecture finale de la liste de réservations", "Relecture finale de la liste",
      "Des doublons apparaissent dans la liste rendue.", "Un dernier appel supprime les doublons.", "La liste est propre.")
mesure(P + "r2n5", "examen", 37.5, 240, "2030-03-02 14:30:00Z", 9.8, 1210, {"delta_moy": 1.3, "gagnes": 20, "perdus": 17})
examens.append({"tour": 2, "essai": 5, "tag": P + "r2n5", "examen": 37.5, "examen_vec": vecteur(37.5), "delta": 1.3, "gagnes": 20, "perdus": 17,
                "note_entrainement": 75.0, "recorrection": None, "verification": None, "verdict": "echec examen", "vitesse": 9.8,
                "conditions": {"poste": "machine-A", "gpu": False}})
strategies.append({"tour": 2, "niveau": 1, "en_clair": "Une consigne par type, puis contrôles par le programme"})
audits.append({"tour": 2, "audit": {"en_clair": "L'entraînement trompe sur les messages flous.", "causes": [
    {"en_clair": "Heures hors horaires acceptées · 9 pts", "nb_cas": 15, "categories": ["floue"]}],
    "ecarts_entrainement_examen": [{"categorie": "floue", "constat": "Très bon à l'entraînement, faible à l'examen", "corriger_donnees": True}]}})
# passe 3
racine(3, 75.0, 95.0, "2030-03-03 09:00")
noeud(3, 1, 0, P + "r3n1", FAM["consigne"], "developper", 80.1, "2030-03-03 09:40", "Exemples plus variés dans la consigne", "Exemples plus variés",
      "Les exemples se ressemblent trop.", "Remplacer deux exemples par des cas plus différents.", "Meilleure généralisation.")
noeud(3, 2, 0, P + "r3n2", FAM["prog"], "elaguer", 72.0, "2030-03-03 09:50", "Normalisation des heures par le programme", "Normalisation des heures",
      "Les heures sont écrites de plusieurs façons.", "Le programme normalise le format des heures.", "Moins d'heures illisibles.", "plus bas que sa racine")
noeud(3, 3, 1, P + "r3n3", FAM["trier"], "examen", 96.0, "2030-03-03 11:30", "Classer, puis consigne adaptée et exemples variés", "Classer puis consigne adaptée, exemples variés",
      "Le tri et les exemples doivent aller ensemble.", "Combiner le tri par type et des exemples variés.", "Tous les types montent.")
mesure(P + "r3n3", "examen", 44.8, 240, "2030-03-03 13:30:00Z", 7.1, 980, {"delta_moy": 7.3, "gagnes": 33, "perdus": 15})
mesure(P + "r3n3c", "examen", 43.6, 240, "2030-03-03 15:00:00Z", 7.1, 980, {"delta_moy": 6.1, "gagnes": 31, "perdus": 16})
examens.append({"tour": 3, "essai": 3, "tag": P + "r3n3", "examen": 44.8, "examen_vec": vecteur(44.8), "delta": 7.3, "gagnes": 33, "perdus": 15,
                "note_entrainement": 96.0, "recorrection": {"delta": 6.1}, "verification": {"note": 43.0, "ancienne": 35.1},
                "verdict": "nouvelle meilleure version", "vitesse": 7.1, "conditions": {"poste": "machine-A", "gpu": False}})
strategies.append({"tour": 3, "niveau": 1, "en_clair": "Repartir du meilleur essai, tri puis exemples variés"})
# passe 4 : en cours
racine(4, 96.0, 100.0, "2030-03-04 09:00")
noeud(4, 1, 0, P + "r4n1", FAM["relire"], "a entrainer", None, "2030-03-04 09:30", "Relecture des heures par un second appel", "Relecture des heures",
      "Quelques heures restent incohérentes.", "Un second appel relit les heures.", "Moins d'erreurs d'heure.")
noeud(4, 2, 0, P + "r4n2", FAM["consigne"], "a entrainer", None, "2030-03-04 09:30", "Consigne raccourcie", "Consigne raccourcie",
      "La consigne est longue et lente.", "Retirer les règles redondantes.", "Même qualité, plus rapide.")
strategies.append({"tour": 4, "niveau": 1, "en_clair": "Raccourcir et fiabiliser les heures"})

jsonl(os.path.join(E_, "journal-arbre.jsonl"), arbre)
jsonl(os.path.join(E_, "strategies.jsonl"), strategies)
jsonl(os.path.join(E_, "audits-erreurs.jsonl"), audits)
for tag, g in gestes.items():
    ecrire(os.path.join(E_, "gestes", tag + ".json"), g)
jsonl(os.path.join(T_, "resultats-moteur.jsonl"), res)

ecrire(os.path.join(E_, "journal-wf-etat.json"), {
    "champion": {"tag": P + "r3n3", "vec": vecteur(44.8), "entrainement": {"moy": 96.0, "jeu": "entrainement-v1.jsonl"},
                 "verification": {"moy": 43.0}},
    "examens": examens, "paliers": [50.0, 73.5, 95.0, 100.0], "echecsExamen": 0,
    "n1": {"tour": 4, "phase": "entrainement", "tourEntrainement": 1, "palier": 100.0, "racineN1": {"moy": 96.0}}})

ecrire(os.path.join(T_, "mesures-live.json"), {
    "postes": ["poste-a", "poste-b"], "postes_etat": {"poste-a": {"libre": False}, "poste-b": {"libre": True}},
    "mesures": [{"id": P + "r4n1-ent", "tag": P + "r4n1", "graine": "entrainement", "etat": "mesure", "machine": "poste-a",
                 "demande": "2030-03-04T09:35:00",
                 "progres": {"fait": 47, "total": 120, "phase": "entrainement"},
                 "progres_juge": {"total": 120, "fait": 47, "paquets": 6, "paquets_faits": 2, "par_poste": {"poste-a": 47}, "en_cours": {"poste-a": 2}}}]})
ecrire(os.path.join(T_, "resumes-journal.json"), {
    "depart": "Sans aide : la consigne simple, un seul appel au petit modèle",
    "strategie-t1": "Exemples multiples · dates contrôlées · réponse simplifiée"})
print("jeu synthetique ecrit dans", SORTIE, "-", len(arbre), "lignes d'arbre,", len(res), "mesures")
