---
name: autoresearch-verifier
description: "Define the objective metrics of an auto-research goal and score a model output against the frozen reference. Step 1 of autoresearch-pipeline: the verifier is the real, billable expertise. Triggers: 'define the metrics', 'how do we verify the goal', 'score against the golden', 'définis les métriques', 'construis le vérificateur'."
---

# Vérificateur : objectiver le but et noter

Définit **comment on sait que « c'est bon »** pour une tâche, et note la sortie d'un petit modèle contre le corrigé de référence (voir `autoresearch-golden`). C'est le cœur de valeur de la méthode.

## Règle d'or

**Ne jamais noter la ressemblance d'un texte libre** (similarité de surface, embeddings, juge LLM indulgent) : c'est un juge subjectif déguisé. Viser du mesurable.

## Deux familles de métriques objectives

**a) Champs structurés du corrigé** : objectifs, immédiats.
• catégoriels (un type) : égalité exacte ;
• numériques (un nombre) : erreur absolue ;
• listes : rappel / précision / F1 des éléments clés ;
• sorties illisibles ou hors format : erreur interdite comptée à part.

**b) Tâche finale** : le vrai test d'usage (ex. retrouver un document par une requête). Jeu de requêtes, bonne réponse connue, moteur de recherche fixé : on ne fait varier que la sortie du modèle testé, qui doit approcher le score du corrigé.

## Trois jeux, trois rôles

| Jeu | Le chercheur… | Sert à |
|---|---|---|
| Entraînement | voit les fautes cas par cas | faire pousser l'arbre d'essais |
| Examen (scellé) | ne reçoit que des notes agrégées par catégorie | seul juge des progrès |
| Vérification | ne voit rien | contrôle de sur-adaptation à l'examen, pour information |

• L'entraînement doit **ressembler** à l'examen. Si les notes agrégées montrent qu'une catégorie trompe (très bon à l'entraînement, mauvais à l'examen), on corrige le jeu d'entraînement par fabrication de nouveaux cas, jamais en lisant l'examen ni en choisissant des cas d'après la note du petit modèle.
• La note finale est la moyenne des taux de réussite **par catégorie** : une catégorie rare pèse autant qu'une catégorie fréquente.
• Un progrès à l'examen se décide par comparaison **appariée** (mêmes cas) à la meilleure version, avec une marge minimale (par défaut +5 points).

## Structure de décision

• **Plancher de qualité = contrainte dure.** Sous le plancher : rejet, quels que soient vitesse et coût.
• Au-dessus : compromis pondérés, dans l'ordre qualité, vitesse, coût. Le plancher et les taux d'échange sont décidés par une personne, par cas d'usage.
• Garde-fous : jeu d'examen jamais optimisé directement ; qualité non linéaire (le seuil d'utilité est une falaise, le plancher la capture mieux qu'un pourcentage moyen).
• Chaque chiffre de vitesse porte ses conditions de mesure.

## Livrables de cette étape

• La liste des catégories de cas et leur définition.
• Le comparateur : une fonction déterministe `(proposition, corrigé) -> réussi / échoué`.
• Le plancher de qualité et la cible, validés par la personne qui décide.
• Les trois jeux de cas, avec l'empreinte (hash) de l'examen et de la vérification.
