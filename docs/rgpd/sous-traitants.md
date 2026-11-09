# Sous-traitants et transferts hors UE

> Dernière vérification : {{DATE}}. À revoir si la Cour de justice de l'UE invalide le Data Privacy Framework (pourvoi Latombe, introduit le 31 octobre 2025).

| Service | Rôle | Ce qu'il reçoit | Localisation | Base du transfert | Vérifié sur dataprivacyframework.gov |
|---|---|---|---|---|---|
| GitHub (Microsoft) | Hébergement du code, exécution quotidienne, hébergement du site | Toutes les données publiées (déjà publiques) | États-Unis | Data Privacy Framework | {{oui/non, date}} |
| Google (API Gemini, palier gratuit) | Rédaction des synthèses | Extraits de comptes rendus, **sans nom d'orateur** | États-Unis | Data Privacy Framework ; pour les utilisateurs de l'EEE, les requêtes ne servent pas à améliorer les produits selon les conditions affichées | {{oui/non, date}} |
| Telegram | Notification privée de l'éditeur | Récapitulatif et image de l'hémicycle | Hors UE | Usage personnel de l'éditeur, données déjà publiques | — |

## Plan B européen

Si le Data Privacy Framework est invalidé :
- hébergement : **Codeberg** (association allemande) avec Codeberg Pages et l'intégration continue de Forgejo ;
- IA : **Mistral** (France), sur une offre où les requêtes ne servent pas à l'entraînement ;
- le site étant statique et le fournisseur d'IA interchangeable (`IA_FOURNISSEUR`), la bascule ne demande pas de réécriture.
