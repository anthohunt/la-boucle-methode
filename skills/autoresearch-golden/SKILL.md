---
name: autoresearch-golden
description: "Build the golden: the frozen, maximum-quality reference set an auto-research task is scored against. Step 2 of autoresearch-pipeline. Use when you need a high-quality reference over a sample of inputs (texts, images, audio). Triggers: 'build the golden', 'generate the reference', 'construis le golden', 'fais le corrigé type'."
---

# Golden : le corrigé de référence figé

Produit la **vérité-terrain** d'une tâche : un échantillon traité par un gros modèle en qualité maximale (puis relu), figé, contre lequel on mesure ensuite les petits modèles. Composant de `autoresearch-pipeline`.

## Méthode

1. **Échantillonner.** Choisir la taille et la justifier (un taux mesuré sur n≈30 cas a un intervalle de confiance d'environ ±15 points). Échantillon **diversifié et représentatif** du vrai usage ; écarter les lots homogènes qui écraseraient la variété (pondérer par diversité, pas par volume). Pour une boucle complète, viser plusieurs dizaines de cas par catégorie.
2. **Traiter par des agents parallèles du gros modèle** : N agents, quelques éléments chacun, chacun écrit un fichier de lot ; consolider ensuite. Qualité homogène, contexte préservé.
3. **Format JSON structuré.** Des champs objectivables (types, nombres, listes d'étiquettes) plus, si utile, une description libre. Ce sont les champs structurés qui servent de métrique dure (cf. `autoresearch-verifier`), pas la prose.
4. **Consolider et persister** dans un dossier durable (pas un répertoire temporaire), trié par identifiant, avec un `manifest.json` (identifiant, source, date).
5. **Figer** : calculer l'empreinte (SHA-256) du fichier consolidé et la noter ; toute modification ultérieure doit être détectable.

## Pièges

• **Le golden est figé ensuite.** Bidouillé, la métrique ment.
• **Relire un échantillon à la main.** Le gros modèle peut se tromper ; sur une tâche de distillation c'est tolérable (le but est de l'égaler), mais il faut le signaler.
• **Données sensibles.** Signaler tout contenu identifiant (personnes, documents, signatures, visages) repéré dans l'échantillon ; garder local, ne rien envoyer à un tiers sans accord.
• **Encodage.** Forcer UTF-8 partout.
• **Fabrication de cas** : un cas fabriqué doit être contrôlé par du code (format, doublons contre les autres jeux) avant d'entrer dans un jeu.

## Exemple de schéma

Tâche « décrire une photo » : `{id, fichier, resume, type, nombre_de_personnes, lieu, objets[], texte_visible, etiquettes[], description}`. Les champs `type`, `nombre_de_personnes` et `etiquettes` sont notés ; `description` ne l'est pas.
