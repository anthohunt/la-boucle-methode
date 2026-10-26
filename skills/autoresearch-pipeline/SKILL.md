---
name: autoresearch-pipeline
description: "Overview of the auto-research method: turn a business goal into a small-model agent by letting a large model improve the harness (prompts, helper code, model choice) against a frozen reference until a measurable quality bar is met, then optimise speed and cost. Orchestrates autoresearch-verifier, autoresearch-golden and autoresearch-loop. Triggers: 'run the auto-research', 'build a task-specific small-model agent', 'lance l'auto-research', 'optimise la pipeline petit modèle'."
---

# Auto-research : de l'objectif métier à un agent sur petit modèle

Méthode en quatre étapes pour obtenir, pour une tâche précise, un agent qui tourne sur un **petit modèle local** avec une qualité **mesurée** et non supposée. Un gros modèle sert de chercheur : il améliore le *harnais* (consigne, code d'aide autour du modèle, découpage en étapes, choix du modèle) ; il ne juge jamais son propre travail.

Inspirations : [karpathy/autoresearch](https://github.com/karpathy/autoresearch) (boucle « modifier, mesurer, garder ou jeter ») et [GEPA](https://github.com/gepa-ai/gepa) (évolution de consignes guidée par les fautes). Aucun code n'en est repris.

## Principes

1. **Qualité d'abord, vitesse ensuite.** Tant que le seuil de qualité n'est pas atteint, aucune idée n'est écartée parce qu'elle est lente ou demande plusieurs appels. Vitesse et coût ne s'optimisent qu'au-dessus du plancher de qualité, sans jamais repasser dessous.
2. **L'étalon est figé.** Le corrigé de référence est produit une fois, en qualité maximale, puis n'est plus touché (sinon la mesure ment).
3. **La mesure est séparée du chercheur.** Trois jeux de cas aux rôles distincts : un jeu d'entraînement dont le chercheur voit les fautes, un jeu d'examen scellé dont il ne reçoit que des notes agrégées, un lot de vérification jamais utilisé pour choisir.
4. **Le code décide, pas un agent.** Paliers, élagage, passage à l'examen et arrêt sont des règles déterministes.
5. **On ne réduit jamais le travail pour aller vite.** L'examen reste complet ; on l'accélère en le répartissant sur davantage de machines ou de processus.
6. **Le chercheur explore l'espace.** Il essaie lui-même consignes, étapes et modèles ; choisir le modèle n'est pas une décision humaine, c'est un levier d'optimisation.

## Les étapes

1. **Définir le but et les métriques objectives** : skill `autoresearch-verifier`. C'est le vrai travail de valeur : sans mesure fiable, rien d'autre ne sert.
2. **Construire le corrigé de référence** : skill `autoresearch-golden`.
3. **Lancer la boucle** : skill `autoresearch-loop`. Le moteur est le dépôt [`la-boucle-engine`](https://github.com/anthohunt/la-boucle-engine) (`python3 -m boucle …`). Suivi : skill `dashboard-boucle`.
4. **Optimiser vitesse et coût** une fois le seuil tenu : modèle plus petit, consigne plus courte, moins d'appels. Chaque chiffre de vitesse est noté avec ses conditions (machine, processeur, carte graphique, calcul GPU ou non).

Pour affiner une seule consigne à la main, voir `iterative-prompt-tuning`.

## Avant de commencer

• Le but tient en une phrase et se mesure sans jugement humain.
• Les cas existent en nombre suffisant (au moins quelques dizaines par catégorie rare) et couvrent aussi les cas piégeux : entrées vides, ambiguës, hostiles.
• Quelqu'un décide du plancher de qualité et de l'échange qualité / vitesse / coût : c'est une décision humaine par cas d'usage, pas celle de la boucle.
