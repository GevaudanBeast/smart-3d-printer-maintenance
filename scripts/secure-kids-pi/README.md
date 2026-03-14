# Raspberry Pi 3 sécurisé pour enfants (~10 ans)

Ce dossier contient un script d'installation automatique qui transforme un
Raspberry Pi 3 (Raspberry Pi OS / Raspbian) en ordinateur familial sécurisé.

---

## Fonctionnalités

| Fonctionnalité | Détail |
|---|---|
| **Compte restreint** | Utilisateur sans `sudo`, sans accès aux outils système |
| **DNS familial** | Cloudflare Family `1.1.1.3` + OpenDNS FamilyShield (bloquent malwares & adultes) |
| **Blocage `/etc/hosts`** | Couche supplémentaire de blocage de domaines |
| **Chromium sécurisé** | SafeSearch forcé, YouTube mode restreint, incognito désactivé, téléchargements bloqués |
| **Limites de temps** | Plages horaires par jour + durée max de session (déconnexion automatique) |
| **Verrouillage d'écran** | Après 10 min d'inactivité avec mot de passe |
| **Bureau restreint** | Pas de terminal, pas de gestionnaire de fichiers avancé |

---

## Installation rapide

### Prérequis

- Raspberry Pi 3 avec **Raspberry Pi OS Desktop** (Bullseye ou Bookworm)
- Connexion internet
- Accès en tant qu'administrateur (`pi` ou un compte avec `sudo`)

### Étapes

```bash
# 1. Télécharger / copier le script sur le Pi
scp scripts/secure-kids-pi/setup.sh pi@raspberrypi.local:~/

# 2. Le rendre exécutable et le lancer
ssh pi@raspberrypi.local
chmod +x setup.sh
sudo bash setup.sh enfants MotDePasseKids
#                  ^^^^^^^  ^^^^^^^^^^^^^^
#                  nom du compte (modifiable)
#                  mot de passe du compte

# 3. Redémarrer
sudo reboot
```

> Le mot de passe peut aussi être saisi de manière interactive si vous omettez
> le 2ème argument (plus sûr) :
> ```bash
> sudo bash setup.sh enfants
> ```

---

## Configuration par défaut

| Paramètre | Valeur |
|---|---|
| Nom du compte | `enfants` |
| Lundi – Vendredi | 14h00 → 18h00 |
| Samedi – Dimanche | 09h00 → 19h00 |
| Durée max / session | 120 minutes |
| Verrouillage écran | après 10 min d'inactivité |

### Modifier les horaires

Éditez la variable dans le script de garde-fou :

```bash
sudo nano /usr/local/bin/kids-session-guard.sh
```

Ou relancez `setup.sh` avec de nouveaux paramètres après avoir modifié les
variables `WEEKDAY_START`, `WEEKDAY_END`, etc. en tête du script.

---

## Politiques Chromium

Le fichier JSON suivant est installé dans
`/etc/chromium/policies/managed/kids_policy.json` :

```json
{
  "IncognitoModeAvailability": 1,     // incognito désactivé
  "ForceGoogleSafeSearch": true,      // SafeSearch obligatoire
  "ForceYouTubeRestrict": 2,          // YouTube mode restreint strict
  "DownloadRestrictions": 3,          // téléchargements bloqués
  "URLBlocklist": ["chrome://settings", "chrome://extensions", ...]
}
```

Vous pouvez modifier ce fichier directement :

```bash
sudo nano /etc/chromium/policies/managed/kids_policy.json
```

---

## Journal d'activité

Les connexions et déconnexions automatiques sont enregistrées dans :

```
/var/log/kids-session.log
```

---

## Ajouter un deuxième enfant

Relancez simplement le script avec un autre nom d'utilisateur :

```bash
sudo bash setup.sh alice MotDePasse2
```

---

## Ce que le script ne fait PAS (limites)

- Il ne remplace pas un **routeur avec contrôle parental** (Freebox, FritzBox, etc.)
- Il ne surveille pas le contenu des conversations ou les réseaux sociaux
- Un enfant très débrouillard avec accès physique au Pi pourrait flasher une
  nouvelle carte SD — protégez le BIOS/firmware si nécessaire
- La liste de blocage `/etc/hosts` est minimaliste ; un DNS familial dédié
  (Pi-hole + liste de blocage) est plus robuste

---

## Désinstallation / réinitialisation

```bash
# Supprimer le compte enfants
sudo userdel -r enfants

# Restaurer le DNS
sudo chattr -i /etc/resolv.conf
sudo rm /etc/resolv.conf
sudo ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

# Supprimer le cron et le script
sudo rm /etc/cron.d/kids-session-guard
sudo rm /usr/local/bin/kids-session-guard.sh

# Supprimer les politiques Chromium
sudo rm /etc/chromium/policies/managed/kids_policy.json
```
