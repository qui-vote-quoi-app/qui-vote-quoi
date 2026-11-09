# Méthodologie

## Sources

| Données | Fichier open data | Mise à jour constatée |
|---|---|---|
| Scrutins publics | `loi/scrutins/Scrutins.json.zip` | quotidienne |
| Députés, groupes, places | `amo/…/AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip` | quotidienne |
| Comptes rendus de séance | `vp/syceronbrut/syseron.xml.zip` | quotidienne, quelques jours après la séance |
| Carte des places de l'hémicycle | page « Situez votre député dans l'hémicycle » du site de l'Assemblée | relevé ponctuel (`data/places_hemicycle.json`) |

Seuls les **scrutins publics** ont un détail nominatif. Les votes à main levée, qui concernent la majorité des amendements, n'apparaissent pas : on ne peut pas savoir qui a voté quoi.

## Résultat et chiffres

Le résultat affiché (« L'Assemblée a adopté / n'a pas adopté ») et tous les décomptes viennent directement du fichier officiel du scrutin. Le site ne recalcule pas le résultat, car les règles de majorité varient selon le type de vote.

Le groupe affiché pour chaque vote est **le groupe du député au moment du vote**, tel qu'il figure dans le scrutin.

Les mises au point (un député déclare après coup qu'il voulait voter autrement) sont conservées dans les données mais **ne modifient pas** le résultat officiel.

## Catégories et « votes majeurs »

Le classement se fait sur l'intitulé officiel du scrutin, jamais sur son sujet :

| Catégorie | Exemples d'intitulé | Niveau |
|---|---|---|
| Vote sur l'ensemble | « l'ensemble du projet de loi… », « la première partie du projet de loi de finances… », « la proposition de résolution… » | majeur |
| Motion de censure, déclaration du Gouvernement | | majeur |
| Motion de procédure | « la motion de rejet préalable… », « la motion de renvoi en commission… » | majeur |
| Article | « l'article 3… » | intermédiaire |
| Amendement | « l'amendement n° … », « le sous-amendement… » | mineur |
| Procédure | « la proposition du Gouvernement de prolonger la séance… » | mineur |

Tout **scrutin solennel** est classé majeur.

## Synthèse « Le débat en bref »

Réservée aux votes majeurs.

1. **Script** : le compte rendu de la séance est retrouvé grâce à l'identifiant de séance du scrutin. L'annonce du résultat est localisée en comparant les chiffres annoncés à ceux du scrutin officiel.
2. **Script** : le passage retenu est le point « Explications de vote » qui précède le vote, ou à défaut le point qui contient le vote (par exemple la discussion d'une motion). Sont retirés : la présidence de séance, les interruptions, les didascalies (applaudissements, exclamations). Les interventions consécutives d'un même orateur sont regroupées.
3. **IA (un seul appel)** : le passage, **sans le nom des orateurs**, est envoyé au modèle, qui renvoie un contexte et au plus quatre arguments par camp, chacun avec le numéro du passage d'origine et une citation exacte.
4. **Script** : vérification. La synthèse est rejetée si une citation ne figure pas mot pour mot dans le passage indiqué, si un résumé contient un nom ou une formule désignant une personne, ou si le format est invalide. Une relance est faite avec la liste des erreurs, puis la synthèse est bloquée.
5. **Script** : chaque citation est rattachée à son orateur à partir du compte rendu officiel. L'IA ne désigne jamais qui a dit quoi.

Les synthèses sont publiées **sans relecture humaine**, avec une mention explicite sur chaque page. Elles peuvent être retirées à tout moment (voir README).

## Limites connues

- Les résumés reformulés peuvent simplifier un argument ; seules les citations font foi.
- Le compte rendu utilisé est la version publiée avant le Journal officiel. Il peut être légèrement corrigé ensuite.
- Le classement automatique des intitulés peut se tromper sur des formulations rares.
- La position des sièges provient d'un relevé de la carte officielle. Pour les sièges sans vote enregistré, le site n'affiche volontairement aucun nom.
