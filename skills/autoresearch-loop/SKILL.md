---
name: autoresearch-loop
description: "Run the auto-research optimisation loop: make a small model match the frozen reference on the objective metric by iterating on the harness (prompts, helper code, steps, model), using a visible training set, a sealed exam and a hidden judge, a search tree of trials, idea families, thresholds, a +5 point rule and a stop after two exam failures. The engine is the la-boucle-engine repository (python3 -m boucle). Triggers: 'run the auto-research loop', 'optimise the small model', 'lance la boucle d'auto-research'."
---

# La boucle : l'optimiseur

Étapes 3 et 4 de `autoresearch-pipeline`. Ce skill décrit **la méthode**. Le **moteur** qui l'exécute est le dépôt [`la-boucle-engine`](https://github.com/anthohunt/la-boucle-engine) (Python ≥ 3.10, bibliothèque standard seule) :

```bash
pip install git+https://github.com/anthohunt/la-boucle-engine
python3 -m boucle sceller   donnees/examen.jsonl     # scelle un jeu de cas (empreinte SHA-256)
python3 -m boucle verifier  chantier.json            # contrôle le fichier de chantier et les scellés
python3 -m boucle noter     chantier.json harnais-0  # note une version du harnais (étape 0 : le départ)
python3 -m boucle run       chantier.json            # lance ou reprend la boucle
python3 -m boucle tableau   chantier.json            # page HTML simple (tableau.html)
```

Code de sortie de `run` : `0` but atteint, `3` pause après deux échecs d'examen de suite (le moteur écrit `PAUSE.md` et ne réessaie jamais seul), `4` arrêt (passes ou budget épuisés), `1` erreur. Le fichier de chantier (jeux, comparateur, chercheur, paliers, règle du gain minimal, familles) est décrit dans `docs/chantier.md` du moteur, l'interface publique dans `docs/interface.md`.

Ce skill ne recopie pas le moteur : pour un réglage précis, la documentation du moteur fait foi (en cas d'écart entre ce texte et le moteur, c'est le moteur qui a raison).

## Les acteurs

• **Le sujet** : ce qu'on améliore (un petit modèle et son *harnais* : consigne, code d'aide, étapes).
• **Le chercheur** : un agent (gros modèle) qui lit les fautes visibles du sujet et propose une version modifiée du harnais. Il n'écrit jamais dans le moteur, le barème, le juge ni les jeux.
• **Le juge** : du code déterministe, caché du chercheur. Il fait tourner le sujet sur les cas, applique le comparateur, garde les notes cas par cas et ne rend au chercheur que ce qui est permis.
• **Le chef de boucle** : le code du moteur. Il applique les règles ci-dessous ; un agent n'en décide jamais.

## Trois jeux de cas

• **Entraînement visible** : le chercheur y lit les fautes. L'arbre d'essais y pousse.
• **Examen scellé** : seul juge des progrès. Jamais lu par le chercheur ; seules des notes agrégées par catégorie sortent. Le fichier est protégé par empreinte.
• **Vérification** : lot jamais utilisé pour choisir ; contrôle d'information contre la sur-adaptation à l'examen.

## Le déroulement d'une passe

**Étape 0 (une fois)** : mesurer la version de départ (sans aide) sur l'entraînement et l'examen.

**Niveau 1, autonome, sur l'entraînement :**
1. Noter la meilleure version d'entraînement : c'est la **racine** de l'arbre. Le **palier** à franchir est sa note + 20 points (plafonné à 100). Viser haut empêche les agents de se contenter du minimum.
2. Lire les fautes de la racine (audit par cause).
3. Vérifier l'écart entraînement / examen sur les notes agrégées par catégorie ; si l'entraînement trompe sur une catégorie, corriger le **jeu d'entraînement** (jamais en lisant l'examen).
4. Plan : quelques pistes, critiquées puis corrigées, qui deviennent les premières branches.
5. **Arbre d'essais** : chaque nœud est une version du harnais, notée sur l'entraînement. Un nœud plus bas que son parent est **élagué** ; un nœud qui monte est **développé** (un agent lit ses fautes et écrit un enfant). Une branche sans suite est une impasse. Garde-fou : nombre de nœuds maximal par passe.
6. **Arrêt séquentiel** (optionnel) : le juge note un nœud par tranches de cas, dans un ordre neuf et secret, et s'arrête dès qu'une borne statistique valable à tout moment tranche (écart apparié au parent, note par rapport au seuil). Un nœud arrêté tôt n'a jamais de « note complète » ; tout nœud pouvant atteindre le palier est noté sur le jeu entier.
7. **Décision par le code** : dès qu'une branche atteint le palier, elle monte au niveau 2. Si l'arbre s'épuise sans palier, nouvelle stratégie : ce n'est pas un échec d'examen.

**Niveau 2, l'examen :**
1. Examen complet, **apparié** à la meilleure version (mêmes cas). Il faut **au moins +5 points** (règle des +5).
2. Si oui : **recorrection** des mêmes cas par d'autres processus ou machines (contre la chance d'une mesure ; ce ne sont pas des données neuves), qui doit aussi tenir +5.
3. Puis **vérification** sur le lot neuf, pour information.
4. Nouvelle meilleure version, retour au niveau 1. Sinon : échec d'examen compté.
5. **Après 2 échecs d'examen** : réflexion sur le *système* (pas sur les essais), propositions soumises à la personne responsable, boucle en pause.

## Familles d'idées

Chaque essai porte une famille. Exemples : retoucher la consigne ; le programme aide le modèle (code autour) ; relecture / vérification ; trier puis spécialiser par type d'entrée ; nouvelle famille nommée.
• Le code tient l'archive par famille : meilleure version et essais de suite sans progrès.
• **3 essais de suite sans progrès à l'entraînement : la famille est en impasse** (plus de place dans l'arbre sans justification nouvelle).
• Chaque passe ouvre au moins une famille jamais essayée.
• **Plateau : 2 passes sans progrès à l'examen** : étape de **divergence**, au moins trois approches structurellement différentes.
• « Entraîner le modèle » et « changer de modèle » sont des familles **réservées** : seule la personne responsable les ouvre.

## Règles dures

1. **Le code décide** du palier, de l'élagage, de la montée à l'examen, du couronnement et du déclenchement de la réflexion de niveau 2.
2. **Progrès = au moins +5 points apparié** sur la meilleure version.
3. **Examen toujours complet.** Accélérer = paralléliser.
4. **Aucun entraînement en cachette** : aucun appel au sujet hors du juge. Le chercheur écrit un essai et le rend sans le tester sur des cas ; seul test permis : un contrôle de forme (le code se charge, la sortie est lisible), sans note.
5. **Résultats de mesure validés** : un résultat « réussi » sans banc reconnu, sans nombre de cas ou sans notes par catégorie est rejeté comme une panne. Les tests du moteur travaillent dans un dossier bac à sable.
6. **Reprise** : l'état (cycle en cours, arbre) est repris là où il s'est arrêté ; un résultat déjà arrivé est relu, pas refait.
7. **Garde-fou anti-triche** : un gain à la recorrection anormalement grand (par exemple plus de trois erreurs-types) est relu par un auditeur avant le couronnement.
8. **Charte** : un fichier de règles lu par le chercheur à chaque tour (ce qu'il peut modifier, ce qu'il ne touche jamais). Seule la personne responsable le modifie ; les autres documents y renvoient.
9. **Rédaction lisible** : tout texte qu'un agent écrit pour être lu est « résultat d'abord », une ligne = un libellé court + une valeur, sans code interne.

## Vitesse et coût

Après un bon score seulement. Chaque mesure note ses **conditions** (machine, processeur, carte graphique, GPU ou non, machine partagée ou non). Une mesure dans les conditions réelles de déploiement (par exemple un téléphone) ne se fait qu'une fois le score atteint.

## Journal et suivi

• Un **journal unique** du niveau 1 : une ligne par nœud (passe, nœud, parent, famille, changement en une phrase, notes par catégorie, décision, conditions de mesure). Lu par les agents (ne pas refaire une idée élaguée), par le tableau de bord et par la réflexion de niveau 2.
• Suivi visuel : skill `dashboard-boucle`.
• Un travail de longue durée se surveille avec une liste de suivi et un contrôle périodique qui relance ce qui est bloqué.

## Exécution

La boucle tourne comme un processus long (service ou session dédiée), jamais dans la conversation d'un humain. Un agent chercheur est un processus enfant du moteur. Ne jamais tuer de processus par leur nom ; lancer le chercheur dans un conteneur si son code n'est pas de confiance (le moteur isole les données, pas le système de fichiers).
