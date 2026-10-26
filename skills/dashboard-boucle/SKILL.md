---
name: dashboard-boucle
description: "Standard, fixed-layout web dashboard to follow an auto-research loop (passes, search tree, champion, exam scores, per-category charts). Generates a static HTML page from the loop's state files; ships with a synthetic example data set. Triggers: 'dashboard of the loop', 'show the passes of the research agent', 'tableau de bord de la boucle'."
---

# Tableau de bord de la boucle

Une boucle d'auto-recherche (voir `autoresearch-loop`) se suit **toujours avec le même tableau** : même mise en page, mêmes sections, quel que soit le chantier. On ne réinvente ni les colonnes ni les couleurs ; ce qui change d'un chantier à l'autre tient dans un fichier de configuration (titre, catégories, unité, tailles des jeux).

C'est une page statique (HTML + JavaScript, thème clair et sombre, lisible sur téléphone). Elle n'est jamais servie sur Internet sans protection : le tableau n'a pas d'authentification (voir README du dépôt).

## Contenu de la page

• **Meilleure version** : sa note à l'examen, l'écart au départ, la zone à viser.
• **Passe en cours** : frise verticale des étapes, une ligne de résultat par étape faite, étapes conditionnelles visibles et barrées avec leur raison.
• **Passes précédentes** : une carte par passe (niveau 1 entraînement, niveau 2 examen), l'arbre d'essais, la décision.
• **Progrès, passe par passe** : onglets Qualité / Vitesse / Coût ; un seul point par passe = le meilleur essai ; la meilleure version en escalier ; la zone à viser en bande.
• **Par catégorie** : mêmes petits graphiques pour chaque catégorie de cas.

## Règles du tableau

1. **Un chiffre, une source, et le jeu écrit à côté.** La note d'entraînement et celle d'examen ne se mélangent jamais ; les graphiques ne montrent que l'examen.
2. **Rien de tapé à la main.** Compteurs, statuts et résumés se calculent depuis les fichiers d'état ; les textes écrits à la main (`resumes-journal.json`) sont l'exception, et prioritaires.
3. **Aucun chiffre en double** à l'écran ; une ligne = un libellé court + une valeur.
4. **Des données figées le disent** (« figé depuis… »).
5. **« Active » veut dire qu'une mesure avance** (battements, cas traités), jamais « un processus existe ».
6. **Une prévision se lit comme une prévision.**
7. **Un texte technique n'est jamais tronqué au milieu** : texte écrit à la main, sinon champ « en clair » du moteur, sinon phrases de tête entières sans code interne.

## Utilisation

```bash
cd skills/dashboard-boucle
python3 donnees-exemple/generer-donnees.py /tmp/exemple          # jeu synthétique (bibliothèque fictive)
cd modele
DASH_MOTEUR=/tmp/exemple/etat-boucle DASH_DIR=/tmp/exemple/tableau python3 generer.py
# -> /tmp/exemple/tableau/index.html
DASH_MOTEUR=… DASH_DIR=… python3 etat-passe.py                    # facultatif : etat-passe.json relu par la page toutes les 30 s
```

Pour un vrai chantier : copier `modele/dashboard.config.example.json` dans le dossier du tableau sous le nom `dashboard.config.json` et l'adapter (catégories, unité, tailles) ; pointer `DASH_MOTEUR` vers le dossier d'état de la boucle ; relancer `generer.py` (toutes les 5 minutes) et `etat-passe.py` (toutes les minutes). Le détail des fichiers lus et des réglages est dans `modele/LISEZMOI.md`.

## Limites à connaître

• Le moteur `la-boucle-engine` écrit déjà une page simple (`python3 -m boucle tableau chantier.json`). Le tableau de ce skill est la version riche (frise, arbre, graphiques par catégorie) ; il lit un format de fichiers différent de celui du moteur (voir `modele/LISEZMOI.md`) et demande donc un petit script d'adaptation du journal du moteur vers ces fichiers. Cet adaptateur n'est pas fourni.
• Les fichiers lus (journal de l'arbre, gestes, résultats de mesure…) sont ceux décrits dans `modele/LISEZMOI.md`. Si le moteur utilisé écrit un autre format, il faut un petit script d'adaptation : le tableau ne devine rien.
• `etat-passe.py` sait lire, s'il y en a, les transcriptions de sessions Claude Code d'un workflow pour afficher la frise d'une passe en cours ; sans elles la frise reste vide et l'historique s'affiche quand même.
• La répartition de la mesure sur plusieurs machines (`mesures-live.json`) est décrite, pas fournie : c'est un fichier que le dispositif de mesure écrit.
