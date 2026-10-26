---
name: iterative-prompt-tuning
description: "Iterate an LLM prompt round by round against a labelled benchmark, with a held-out sample, one change per round and a log. Use when the score oscillates between too strict and too liberal, or before whitelisting specific examples to fix failures. Triggers: 'tune this prompt', 'score oscillates', 'améliore ce prompt avec un benchmark'."
---

# Réglage itératif d'une consigne

Application de la boucle « modifier, mesurer, garder ou jeter » (inspirée de [karpathy/autoresearch](https://github.com/karpathy/autoresearch), sans code repris) au réglage d'une consigne de modèle. Chaque tour est une expérience contrôlée : hypothèse, changement, résultat. Objectif : une amélioration **monotone sur un échantillon mis de côté**, pas sur celui qui sert à régler.

## Quand l'utiliser

• Régler une consigne sur un jeu étiqueté (50 exemples ou plus), avec un score mesurable (exactitude, F1, accord avec des verdicts humains), un tour de moins de 30 minutes.
• Le score oscille d'un tour à l'autre, ou des régressions apparaissent.
• On s'apprête à ajouter une exception pour un cas précis (un expéditeur, un sujet) : s'arrêter et appliquer ce skill.

Ne pas l'utiliser pour une consigne écrite d'un coup sans boucle, sans score chiffré, ou quand le besoin n'est pas encore défini. Pour une optimisation complète avec jeu scellé, voir `autoresearch-loop`.

## Méthode

1. **Découper avant le tour 1** : entraînement / mis de côté. Le jeu mis de côté n'est jamais lu. Le score final est celui du jeu mis de côté.
2. **Un seul changement par tour.** Sinon on ne sait pas à quoi attribuer l'écart.
3. **Une entrée de journal par tour** (`tuning-log.md`) : hypothèse, modification précise, scores avant / après sur les deux jeux, variation des faux positifs et faux négatifs, décision (garder / annuler), leçon.
4. **Arrêts** : 2 tours de suite sans progrès à l'entraînement ; le jeu mis de côté recule alors que l'entraînement monte (sur-adaptation) ; plateau à ±1 % sur 3 tours.
5. **Anti-sur-adaptation** : ne jamais inscrire en liste blanche les exemples qui échouent ; si la règle ne s'exprime qu'en énumérant des noms, c'est de la sur-adaptation ; toujours vérifier sur le jeu mis de côté avant de déclarer une victoire.

## Lecture rapide

| Symptôme | Diagnostic | Action |
|---|---|---|
| Entraînement monte, mis de côté baisse | Sur-adaptation | Annuler ; le changement était propre à l'entraînement |
| Faux positifs qui explosent | Règle trop libérale | Resserrer, ajouter des cas « faux par défaut » |
| Faux négatifs qui explosent | Règle trop stricte | Ajouter des cas vrais qui généralisent le motif manquant |
| Zigzag sur plusieurs tours | Pas de direction | Revenir au meilleur état connu et analyser avant de changer |
| Un tour casse d'autres catégories | Effet de bord | Changement plus petit, isolé |

## Modèle d'entrée de journal

```markdown
## Tour N
**Hypothèse :** pourquoi ce changement devrait améliorer le score
**Changement :** la modification de consigne, en une phrase ou en diff
**Score avant (entraînement / mis de côté) :** X % / Y %
**Score après (entraînement / mis de côté) :** X % / Y %
**Variation faux positifs / faux négatifs :** ±A / ±B
**Décision :** garder / annuler
**Leçon :** ce que ce tour apprend du comportement du modèle
```

## Erreurs fréquentes

• Mesurer sur l'entraînement seul : chiffres toujours trop beaux.
• Plusieurs changements par tour.
• Mettre l'exemple raté en liste blanche : résout CE cas, casse la généralisation.
• Viser 100 % : pour un petit modèle sur une classification subjective, le plafond sans personnalisation ni ajustement fin se situe souvent autour de 85 à 92 %.
• Garder une consigne moins bonne en espérant que le tour suivant la rattrape : annuler d'abord, itérer depuis le meilleur état.
• Ne pas tenir le journal : on refait les expériences ratées.

## Exemple illustratif

Réglage d'une consigne de tri « utile / pas utile » sur un petit modèle local, 100 cas d'entraînement et 100 mis de côté : départ 60 % ; ajout d'exemples en tête de consigne 89 % (entraînement seulement) ; règle contre le marketing déguisé 89 % / 89 % (meilleur) ; tour suivant trop strict 85 % ; tour d'après trop libéral 81 % (faux positifs de 7 à 35). Le tour 5 était l'optimum ; « un changement par tour + journal + arrêt sur régression » aurait arrêté là. (Chiffres d'illustration.)
