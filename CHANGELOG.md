# Changelog

## [0.0.6] - 2026-11-23

### Corrige

- **Travaux termines non comptes** : l'etat `finished` (PrusaLink) est ajoute
  aux etats termines par defaut, et une migration de l'entree (1.1 vers 1.2)
  l'ajoute aux options deja enregistrees. Avant, aucun travail n'etait compte
  comme reussi avec une Prusa.
- **Coupure pendant une impression** : un etat `unavailable` ou `unknown` ne
  cloture plus la session. Le dernier etat reel est memorise (et persiste) ;
  la session reprend au retour de l'imprimante, y compris apres un
  redemarrage de Home Assistant.
- **Appel bloquant au demarrage** : la version de la carte Lovelace est lue
  via le loader de Home Assistant, sans lecture de fichier dans la boucle.

### Ajoute

- Module pur `session.py` (machine a etats), tests pytest, workflow Tests
  (pytest 3.12 et 3.13, ruff), codeowners.
