# Modèle du tableau de la boucle

Fichiers :
• `tpl.html` : la page (autonome, CSS et JavaScript dedans). `generer.py` y injecte les données et écrit `index.html`.
• `journal.py` : construit l'histoire (départ, passes, essais, champion) depuis les fichiers persistants de la boucle. Lecture seule.
• `etat-passe.py` : écrit `etat-passe.json` (étape en cours, mesures en cours, histoire) ; la page le relit toutes les 30 s.
• `plan_depart.py` : reconstitue l'étape « Plan de départ » (stratégie, critique, correction) depuis des transcriptions de sessions Claude Code, si elles existent.
• `noms_postes.py` : renomme à l'écran les machines de mesure (table `noms_postes` de la configuration).
• `reglages.py` : tous les réglages (variables d'environnement + `dashboard.config.json`).

## Réglages

| Variable | Rôle | Défaut |
|---|---|---|
| `DASH_MOTEUR` | dossier d'état de la boucle | `./etat-boucle/` |
| `DASH_DIR` | dossier du tableau (entrées et sorties) | `./tableau/` |
| `DASH_CONFIG` | fichier de configuration | `$DASH_DIR/dashboard.config.json` |
| `DASH_TRANSCRIPTS` | dossiers de transcriptions Claude Code (séparés par `:`) | `~/.claude/projects` |
| `DASH_JOURNAL_JUGE` | journal du juge (JSON par ligne) pour l'arrêt séquentiel | aucun |

`dashboard.config.json` : `titre`, `surtitre`, `intro`, `unite` (singulier, pluriel), `unite_vitesse`, `categories` (id → `nom`, `court`), `tailles` (entrainement, examen, verification), `progres_min`, `lien` (`{url, texte}`), `noms_postes`.

## Fichiers lus

Dans `DASH_MOTEUR` :
• `chantier-*.json` : `prefixe` (début du nom des essais), `objectif.qualite_pct_par_categorie` (`{categorie: {minimum, ideal}}`), `objectif.temps_par_cas_s`, `serie_debut`.
• `journal-arbre.jsonl` : une ligne par nœud : `tour`, `noeud` (0 = racine), `parent`, `tag`, `famille`, `decision` (`a entrainer`, `garder`, `developper`, `elaguer`, `impasse`, `examen`, `ecarte`, `panne`), `moyenne`, `notes` (par catégorie), `changement`, `raison`, `quand`, `jeu` ; pour la racine : `palier`, `issue`.
• `journal-wf-etat.json` : `champion` (`tag`, `vec`, `entrainement`, `verification`), `examens` (un par passe : `essai`, `tag`, `examen`, `delta`, `gagnes`, `perdus`, `recorrection`, `verification`, `verdict` = `nouvelle meilleure version` ou `echec examen`), `n1` (cycle en cours : `tour`, `phase`, `palier`).
• `gestes/<tag>.json` : `titre`, `description`, `famille`, `journal` (`probleme`, `idee`, `attendu`).
• `strategies.jsonl`, `audits-erreurs.jsonl`, `propositions*.jsonl` : textes d'une passe.

Dans `DASH_DIR` :
• `resultats-moteur.jsonl` : une ligne par mesure : `tag`, `ok`, `jeu`, `sealed_moy`, `sealed` (par catégorie), `n`, `vitesse`, `tokens`, `vs_parent`.
• `mesures-live.json` : mesures en cours (`mesures[]`, `postes`, `postes_etat`).
• `resumes-journal.json` (facultatif, textes écrits à la main), `pilotage.json` (facultatif, annonce et état forcé d'étapes).

`donnees-exemple/generer-donnees.py` écrit un jeu complet et inventé qui montre le format de chacun.
