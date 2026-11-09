# Analyse d'impact simplifiée — Qui vote quoi ?

> Analyse documentée à la manière d'une AIPD, à revoir en cas de changement important (ajout de photos, de comptes utilisateurs, de commentaires…). Ce document n'est pas un avis juridique. Dernière mise à jour : {{DATE}}.

## 1. Description

Le site republie, sous forme visuelle, des données que l'Assemblée nationale diffuse elle-même en open data : positions de vote des députés aux scrutins publics et comptes rendus des séances. Pour les votes majeurs, une IA produit une synthèse des arguments, vérifiée automatiquement avant publication.

## 2. Nécessité et proportionnalité

- **Finalité légitime** : information des citoyens sur l'activité de leurs représentants, déjà assurée par l'Assemblée elle-même.
- **Licéité du traitement des opinions politiques** : les positions de vote sont exprimées publiquement par les députés dans l'exercice de leur mandat. La CNIL, dans ses recommandations aux réutilisateurs de données publiées sur internet, cite l'exemple d'une analyse des votes d'élus et le considère licite pour ce motif.
- **Minimisation** : seules les données liées au mandat sont conservées (voir le registre).
- **Exactitude** : resynchronisation quotidienne avec la source officielle. Le résultat officiel n'est jamais recalculé.
- **Information** : mentions légales publiques et courriel individuel aux députés lors du lancement.

## 3. Risques pour les personnes concernées

| Risque | Gravité | Vraisemblance | Mesures |
|---|---|---|---|
| Attribution d'une phrase à la mauvaise personne (atteinte à la réputation) | élevée | faible | L'IA ne voit pas les noms. L'orateur est déterminé par le script à partir du compte rendu officiel. Les noms n'apparaissent qu'à côté de citations exactes, vérifiées mot pour mot. |
| Déformation d'un argument dans un résumé | moyenne | moyenne | Résumés non nominatifs, mention « généré par IA, sans relecture » sur chaque synthèse, lien vers la source, signalement et retrait en quelques minutes. |
| Erreur sur une position de vote | moyenne | faible | Données reprises telles quelles du fichier officiel ; tests de non-régression ; mises au point affichées à part. |
| Biais politique de la présentation | moyenne | faible | Classement des votes sur des critères procéduraux uniquement ; même nombre maximal d'arguments par camp ; consignes de neutralité. |
| Réutilisation des données hors du site | faible | moyenne | Les données sont déjà publiques à la source ; aucune donnée supplémentaire n'est ajoutée. |
| Accès d'une autorité étrangère aux données hébergées (CLOUD Act) | faible | faible | Toutes les données publiées sont déjà publiques. Voir `sous-traitants.md`. |

## 4. Conclusion

Le risque résiduel pour les personnes concernées est jugé **faible**, compte tenu du caractère public des données, de leur lien exclusif avec le mandat et des garde-fous sur les synthèses. Le traitement peut être mis en œuvre. Point de vigilance : l'arrêt attendu de la Cour de justice de l'UE sur le Data Privacy Framework.
