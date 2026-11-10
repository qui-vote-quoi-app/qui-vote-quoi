# Qui vote quoi ?

Site : https://qui-vote-quoi-app.github.io/qui-vote-quoi

Les scrutins publics de l'Assemblée nationale, député par député, dans un hémicycle interactif. Mise à jour automatique chaque matin à partir de l'open data officiel, avec une synthèse des débats pour les votes sur l'ensemble d'un texte.

> Site indépendant et non officiel, sans lien avec l'Assemblée nationale.
> Projet très largement inspiré du travail du compte Instagram [@votes_assemblee_nationale](https://www.instagram.com/votes_assemblee_nationale/).

## Fonctionnement

Chaque jour, un workflow GitHub Actions :

1. vérifie si les dumps open data de l'Assemblée ont changé (scrutins, députés et groupes) ;
2. détecte les nouveaux scrutins et les classe (vote sur l'ensemble, motion, article, amendement, procédure) ;
3. pour les **votes sur l'ensemble d'un texte uniquement**, cherche le compte rendu de la séance, isole par script le passage du débat (explications de vote) et demande à une IA d'en extraire les arguments pour et contre ;
4. **vérifie automatiquement** la synthèse (citations mot pour mot, aucun nom dans les résumés, orateurs déterminés par le script) et ne la publie que si tout est conforme ;
5. régénère le site statique et le publie sur GitHub Pages ;
6. envoie un récapitulatif sur Telegram avec l'image de l'hémicycle du vote majeur du jour.

| Horaire (Paris, hiver) | Ce qui tourne |
|---|---|
| 5 h 23 | passage complet |
| 6 h 53 | passage de secours, seulement si celui de 5 h 23 n'a pas eu lieu |
| 13 h 37 | uniquement les synthèses en attente de compte rendu |

Les heures évitent l'heure pile, où GitHub retarde ou saute parfois les tâches planifiées. En été, ajoutez une heure.

## Installation (une seule fois)

1. **Secrets** : *Settings → Secrets and variables → Actions → New repository secret*
   | Nom | Valeur |
   |---|---|
   | `GEMINI_API_KEY` | clé créée sur aistudio.google.com (palier gratuit, sans facturation) |
   | `TELEGRAM_TOKEN` | token donné par @BotFather |
   | `TELEGRAM_CHAT_ID` | votre identifiant de conversation avec le bot |
2. **Pages** : *Settings → Pages → Build and deployment → Source : GitHub Actions*.
3. **Actions** : *Settings → Actions → General → Workflow permissions : Read and write*.
4. Premier lancement : *Actions → Mise à jour quotidienne → Run workflow*. Le premier passage charge toute la législature et ne prépare des synthèses que pour les votes sur l'ensemble des 7 derniers jours.

## Rattraper les synthèses d'une période passée

*Actions → Mise à jour quotidienne → Run workflow*, puis indiquez un nombre de jours dans « Rattrapage » (par exemple 60). Les synthèses sont traitées par lots de 12 par passage pour rester dans le quota gratuit de l'IA ; le reste est traité automatiquement aux passages suivants (matin et début d'après-midi).

## Retirer une synthèse

*Actions → Retirer une synthèse → Run workflow*, indiquez le numéro du scrutin et le motif. La synthèse est dépubliée en quelques minutes et le motif est conservé dans `data/retraits.txt`. Ça marche aussi depuis l'appli GitHub sur téléphone.

## Changer de fournisseur d'IA

Variables d'environnement du workflow : `IA_FOURNISSEUR` (`gemini`, `mistral` ou `anthropic`) et `IA_MODELE`, avec le secret correspondant (`MISTRAL_API_KEY`, `ANTHROPIC_API_KEY`). Voir `pipeline/config.py`.

## Tester en local

```bash
pip install -r requirements.txt
python -m pipeline.run --fixtures tests/fixtures --sans-ia   # hors ligne, sans IA ni Telegram
python -m http.server -d site 8000                           # puis http://localhost:8000
```

## Arborescence

```
pipeline/        script Python (téléchargement, parsing, débats, IA, vérification, export, image, Telegram)
site/            site statique ; site/data/ est généré à chaque passage (non versionné)
data/            état du pipeline, synthèses publiées, retraits, carte des places de l'hémicycle
docs/            méthodologie et dossier RGPD
tests/fixtures/  extraits réels des dumps open data pour les tests
```

## Documents

- [À propos](https://qui-vote-quoi-app.github.io/qui-vote-quoi/#a-propos), [Méthodologie](https://qui-vote-quoi-app.github.io/qui-vote-quoi/#methodologie), [Questions fréquentes](https://qui-vote-quoi-app.github.io/qui-vote-quoi/#faq), [Données personnelles](https://qui-vote-quoi-app.github.io/qui-vote-quoi/#donnees-personnelles), [Mentions légales](https://qui-vote-quoi-app.github.io/qui-vote-quoi/#mentions-legales) — pages du site, sources dans `site/pages/`
- [Dossier RGPD](docs/rgpd/)

## Licences

- Code : MIT (voir `LICENSE`).
- Données : Assemblée nationale, data.assemblee-nationale.fr, Licence Ouverte 2.0.
- Couleurs de vote : codes utilisés par l'Assemblée nationale sur ses pages de scrutin.
