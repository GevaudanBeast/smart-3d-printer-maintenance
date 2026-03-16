# Smart 3D Printer Maintenance — Home Assistant Integration

> **[English](#english) | [Français](#français)**

---

## English

### Overview

**Smart 3D Printer Maintenance** is a custom Home Assistant integration that tracks the real usage of your 3D printer and helps you plan component maintenance before failures occur.

Designed first for the **Creality K1C** (with [`ha_creality_ws`](https://github.com/3dg1luk43/ha_creality_ws)), it works with any brand or model that exposes a print-status entity in HA (Bambu Lab, Prusa, Voron, OctoPrint, Moonraker, etc.).

### Features

- **Automatic print-time tracking** — event-driven, zero polling, push-based
- **Real-time filament tracking** — accumulates filament consumption incrementally during printing
- **Pause/resume support** — timer pauses with the printer, resumes transparently
- **Job counting (OK / KO)** — per configurable state lists; ambiguous states (idle, standby) are ignored
- **11 tracked components** with individually configurable maintenance intervals
- **4 maintenance statuses**: `OK` · `Soon` · `Due` · `Overdue` (configurable alert threshold)
- **Automatic HA persistent notifications** — fired when a component or plate reaches `Due` or `Overdue`, dismissed on reset
- **Multi build-plate management** — unlimited plates (PEI smooth, PEI textured, PLA sheet…), only the active plate accumulates hours, per-plate status + last maintenance date + HA notifications
- **Filament spool management** — track spools by material, brand, colour and weight; active spool weight auto-decrements from the filament sensor (g/m calculated from material density + diameter)
- **51+ sensors** — 5 global + 44 per-component + 2 active-plate/spool indicators, then +4 per plate and +2 per spool added dynamically (no restart required)
- **Dynamic entities** — adding or removing a plate/spool registers/removes its sensors and buttons instantly
- **11+ reset & control buttons** — 1 reset per component + 2 per plate (reset / activate) + 1 per spool (activate)
- **13 services** — component counters, intervals, hours, filament, plates and spools
- **Compact Lovelace card** — auto-registered, shows last maintenance date, plates section and spools section
- **Persistent storage** — survives HA restarts, resumes in-progress sessions
- **Multi-printer** — one integration entry per printer
- **FR / EN translations**

### Tracked Components

| Category   | Component         | Default interval |
|------------|-------------------|-----------------|
| Extrusion  | Nozzle            | 300 h           |
| Extrusion  | Heatbreak         | 500 h           |
| Extrusion  | Extruder Gear     | 400 h           |
| Movement   | Belts             | 800 h           |
| Movement   | Linear Rods       | 600 h           |
| Movement   | Linear Rails      | 600 h           |
| Platform   | Build Plate       | 1 000 h         |
| Platform   | Build Surface     | 200 h           |
| Cooling    | Hotend Fan        | 600 h           |
| Cooling    | Part Cooling Fan  | 600 h           |
| Misc       | PTFE Tube         | 400 h           |

### Installation

#### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/GevaudanBeast/smart-3d-printer-maintenance` — category **Integration**
3. Install **Smart 3D Printer Maintenance**
4. Restart Home Assistant

#### Manual

1. Copy `custom_components/printer_maintenance/` into your HA `config/custom_components/` folder
2. Restart Home Assistant

### Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **3D Printer Maintenance**
3. **Step 1 — Printer identity**: name, brand, model
4. **Step 2 — Entities**: select the HA sensor that reports the print status and enter the printing state value(s) (comma-separated, e.g. `printing`)

> **K1C + ha_creality_ws example**
> - Status entity: `sensor.k1c_print_status`
> - Printing states: `printing`
> - Filament entity: `sensor.k1c_print_filament` *(optional)*

### Options (after setup)

Go to the integration's **Options** to adjust:

| Option | Description | Default |
|--------|-------------|---------|
| Printing states | State values meaning "active printing" | `printing` |
| Paused states | State values meaning "paused" (timer suspended) | `paused, pause` |
| Completed states → job OK | Successful end states | `completed, complete, finish` |
| Failure states → job KO | Explicit failure states | `stopped, error, cancelled, failed` |
| "Soon" alert threshold | % of interval remaining to trigger Soon | `20 %` |
| Filament entity | Sensor reporting filament used (m) | *(optional)* |
| Maintenance intervals | Per-component maintenance interval (h) | see table above |

> Any state not listed as completed or failure closes the session without counting a job (e.g. `idle` after a completed print goes undetected here since the session already closed on `completed`).

### State Machine

```
idle ──→ printing ──→ completed  →  job OK  ✓
                 ╰──→ paused ──→ printing (resume)
                 ╰──→ stopped / error  →  job KO  ✗
                 ╰──→ idle / other  →  hours counted, no job flagged
```

Sessions shorter than 1 minute are ignored (avoids counting status flickers).

### Lovelace Card

The card is automatically available after installation. Add it to any dashboard:

```yaml
type: custom:printer-maintenance-card
printer: k1c                    # slugified printer name (lowercase, spaces → _)
title: "K1C Maintenance"        # optional
status_entity: sensor.k1c_print_status  # optional — status pill in header
plates:                         # optional — list of plate IDs to display
  - pei_smooth
  - pei_textured
spools:                         # optional — list of spool IDs to display
  - pla_white
  - petg_black
```

The card displays:
- Global stats: total print hours · filament used · jobs count
- Per-component: progress bar, hours used / interval, status badge, **last maintenance date**
- **Plates section**: active indicator (★), hours bar, status badge, last maintenance date, reset + activate buttons
- **Spools section**: active indicator (★), colour dot, material badge, remaining weight bar, % remaining, activate button

### Services

**Components**

| Service | Parameters | Description |
|---------|-----------|-------------|
| `printer_maintenance.reset_component` | `component`, `entry_id` *(opt)* | Reset a component counter after maintenance |
| `printer_maintenance.set_interval` | `component`, `interval_hours`, `entry_id` *(opt)* | Update a maintenance interval |
| `printer_maintenance.add_hours` | `hours`, `component` *(opt)*, `entry_id` *(opt)* | Manually add print hours |
| `printer_maintenance.set_total_hours` | `hours`, `entry_id` *(opt)* | Set the global print-hour total |
| `printer_maintenance.set_total_filament` | `meters`, `entry_id` *(opt)* | Set the global filament total |

**Build plates**

| Service | Parameters | Description |
|---------|-----------|-------------|
| `printer_maintenance.add_plate` | `name`, `interval_hours` *(opt, default 200)*, `entry_id` *(opt)* | Add a new build plate |
| `printer_maintenance.remove_plate` | `plate_id`, `entry_id` *(opt)* | Remove a plate and its entities |
| `printer_maintenance.set_active_plate` | `plate_id`, `entry_id` *(opt)* | Switch the active plate (only active plate accumulates hours) |
| `printer_maintenance.reset_plate` | `plate_id`, `entry_id` *(opt)* | Reset a plate counter after cleaning |

**Filament spools**

| Service | Parameters | Description |
|---------|-----------|-------------|
| `printer_maintenance.add_spool` | `name`, `material` *(opt)*, `brand` *(opt)*, `color` *(opt)*, `initial_weight_g` *(opt, default 1000)*, `diameter_mm` *(opt, default 1.75)*, `entry_id` *(opt)* | Add a new spool |
| `printer_maintenance.remove_spool` | `spool_id`, `entry_id` *(opt)* | Remove a spool and its entities |
| `printer_maintenance.set_active_spool` | `spool_id`, `entry_id` *(opt)* | Switch the active spool (only active spool decrements) |
| `printer_maintenance.update_spool_weight` | `spool_id`, `remaining_weight_g`, `entry_id` *(opt)* | Manually correct remaining weight |

### Status Logic

| Status | Condition |
|--------|-----------|
| ✅ OK | Remaining life > threshold (default 20%) |
| 🟡 Soon | Remaining life ≤ threshold |
| 🔴 Due | Hours used ≥ interval |
| 🟣 Overdue | Hours used > interval |

The threshold is configurable per integration entry (Options → "Soon" alert threshold, 5–50%).

### Requirements

- Home Assistant 2024.4+
- Python 3.12+ (bundled with HA)

### Roadmap

- [ ] Lovelace card visual editor (GUI config)
- [ ] Maintenance history log
- [x] Automatic HA notifications on status change
- [x] Multi build-plate management (per-plate hours, status, last maintenance)
- [x] Filament spool management (material, brand, weight auto-decrement)
- [ ] Per-component greasing tracking: dedicated greasing date + configurable greasing interval (separate from the general maintenance interval)
- [ ] OctoPrint / Moonraker / Klipper connectors

---

## Français

### Présentation

**Smart 3D Printer Maintenance** est une intégration Home Assistant personnalisée qui suit l'utilisation réelle de votre imprimante 3D et vous aide à planifier la maintenance des composants avant toute défaillance.

Conçue en priorité pour la **Creality K1C** (avec [`ha_creality_ws`](https://github.com/3dg1luk43/ha_creality_ws)), elle fonctionne avec toute marque ou modèle exposant une entité d'état d'impression dans HA (Bambu Lab, Prusa, Voron, OctoPrint, Moonraker, etc.).

### Fonctionnalités

- **Suivi automatique du temps d'impression** — événementiel, sans polling
- **Suivi du filament en temps réel** — accumulation incrémentale pendant l'impression
- **Support pause/reprise** — le timer se suspend et reprend avec l'imprimante
- **Comptage des jobs (OK / KO)** — basé sur des listes d'états configurables ; les états ambigus (idle, standby) sont ignorés
- **11 composants suivis** avec intervalles de maintenance individuellement configurables
- **4 statuts de maintenance** : `OK` · `Bientôt` · `Requis` · `En retard` (seuil d'alerte configurable)
- **Notifications HA persistantes automatiques** — déclenchées quand un composant ou un plateau passe en `Requis` ou `En retard`, supprimées à la réinitialisation
- **Gestion multi-plateaux** — plateaux illimités (PEI lisse, PEI texturé, feuille PLA…), seul le plateau actif accumule les heures, statut + date d'entretien + notifications par plateau
- **Gestion des bobines de filament** — suivi par matière, marque, couleur et poids ; le poids du spool actif se décrémente automatiquement depuis le capteur filament (g/m calculé selon densité matière + diamètre)
- **51+ capteurs** — 5 globaux + 44 par composant + 2 indicateurs plateau/spool actifs, puis +4 par plateau et +2 par bobine ajoutés dynamiquement (sans redémarrage)
- **Entités dynamiques** — l'ajout ou la suppression d'un plateau/bobine enregistre/supprime ses entités instantanément
- **11+ boutons** — 1 reset par composant + 2 par plateau (reset / activer) + 1 par bobine (activer)
- **13 services** — compteurs composants, intervalles, heures, filament, plateaux et bobines
- **Carte Lovelace compacte** — enregistrée automatiquement, date d'entretien, section plateaux et section bobines
- **Stockage persistant** — résiste aux redémarrages HA, reprend les sessions en cours
- **Multi-imprimantes** — une entrée d'intégration par imprimante
- **Traductions FR / EN**

### Composants suivis

| Catégorie  | Composant           | Intervalle par défaut |
|------------|---------------------|-----------------------|
| Extrusion  | Buse                | 300 h                 |
| Extrusion  | Heatbreak           | 500 h                 |
| Extrusion  | Engrenage extrudeur | 400 h                 |
| Mouvement  | Courroies           | 800 h                 |
| Mouvement  | Tiges linéaires     | 600 h                 |
| Mouvement  | Rails linéaires     | 600 h                 |
| Plateau    | Plateau d'impression| 1 000 h               |
| Plateau    | Surface d'impression| 200 h                 |
| Refroid.   | Ventilateur hotend  | 600 h                 |
| Refroid.   | Ventilateur pièce   | 600 h                 |
| Divers     | Tube PTFE           | 400 h                 |

### Installation

#### Via HACS (recommandé)

1. Ouvrir HACS → Intégrations → ⋮ → **Dépôts personnalisés**
2. Ajouter `https://github.com/GevaudanBeast/smart-3d-printer-maintenance` — catégorie **Intégration**
3. Installer **Smart 3D Printer Maintenance**
4. Redémarrer Home Assistant

#### Manuelle

1. Copier `custom_components/printer_maintenance/` dans le dossier `config/custom_components/` de votre HA
2. Redémarrer Home Assistant

### Configuration

1. Aller dans **Paramètres → Appareils & Services → Ajouter une intégration**
2. Rechercher **3D Printer Maintenance**
3. **Étape 1 — Identité** : nom, marque, modèle
4. **Étape 2 — Entités** : sélectionner le capteur HA qui rapporte l'état d'impression et saisir la ou les valeurs « en impression » (séparées par des virgules, ex. `printing`)

> **Exemple K1C + ha_creality_ws**
> - Entité état : `sensor.k1c_print_status`
> - États d'impression : `printing`
> - Entité filament : `sensor.k1c_print_filament` *(optionnel)*

### Options (après configuration)

Accédez aux **Options** de l'intégration pour ajuster :

| Option | Description | Défaut |
|--------|-------------|--------|
| États d'impression | Valeurs signifiant « en cours d'impression » | `printing` |
| États de pause | Valeurs signifiant « en pause » (timer suspendu) | `paused, pause` |
| États de fin réussie → job OK | États de fin normale | `completed, complete, finish` |
| États d'échec → job KO | États d'échec explicites | `stopped, error, cancelled, failed` |
| Seuil d'alerte « Bientôt » | % de vie restante déclenchant le statut Soon | `20 %` |
| Entité filament | Capteur indiquant le filament utilisé (m) | *(optionnel)* |
| Intervalles de maintenance | Intervalle par composant (h) | voir tableau |

> Tout état absent des listes « terminé » ou « échec » ferme la session sans comptabiliser de job (ex. `idle` après une impression réussie ne déclenche rien car la session s'est déjà fermée sur `completed`).

### Machine d'états

```
idle ──→ printing ──→ completed  →  job OK  ✓
                 ╰──→ paused ──→ printing (reprise)
                 ╰──→ stopped / error  →  job KO  ✗
                 ╰──→ idle / autre  →  heures comptées, aucun job enregistré
```

Les sessions de moins de 1 minute sont ignorées (évite le comptage des changements d'état transitoires).

### Carte Lovelace

La carte est disponible automatiquement après installation. Ajoutez-la à n'importe quel tableau de bord :

```yaml
type: custom:printer-maintenance-card
printer: k1c                    # nom en minuscules (espaces → _)
title: "K1C Maintenance"        # optionnel
status_entity: sensor.k1c_print_status  # optionnel — pilule d'état dans l'en-tête
plates:                         # optionnel — liste des IDs de plateaux à afficher
  - pei_smooth
  - pei_textured
spools:                         # optionnel — liste des IDs de bobines à afficher
  - pla_white
  - petg_black
```

La carte affiche :
- Statistiques globales : heures totales · filament utilisé · nombre de jobs
- Par composant : barre de progression, heures utilisées / intervalle, badge de statut, **date du dernier entretien**
- **Section plateaux** : indicateur actif (★), barre d'heures, badge statut, date dernier entretien, boutons reset + activer
- **Section bobines** : indicateur actif (★), point couleur, badge matière, barre poids restant, % restant, bouton activer

### Services

**Composants**

| Service | Paramètres | Description |
|---------|-----------|-------------|
| `printer_maintenance.reset_component` | `component`, `entry_id` *(opt)* | Réinitialise le compteur d'un composant après maintenance |
| `printer_maintenance.set_interval` | `component`, `interval_hours`, `entry_id` *(opt)* | Modifie l'intervalle de maintenance |
| `printer_maintenance.add_hours` | `hours`, `component` *(opt)*, `entry_id` *(opt)* | Ajoute des heures d'impression manuellement |
| `printer_maintenance.set_total_hours` | `hours`, `entry_id` *(opt)* | Définit le total d'heures global |
| `printer_maintenance.set_total_filament` | `meters`, `entry_id` *(opt)* | Définit le total de filament global |

**Plateaux**

| Service | Paramètres | Description |
|---------|-----------|-------------|
| `printer_maintenance.add_plate` | `name`, `interval_hours` *(opt, défaut 200)*, `entry_id` *(opt)* | Ajoute un nouveau plateau |
| `printer_maintenance.remove_plate` | `plate_id`, `entry_id` *(opt)* | Supprime un plateau et ses entités |
| `printer_maintenance.set_active_plate` | `plate_id`, `entry_id` *(opt)* | Change le plateau actif (seul le plateau actif accumule les heures) |
| `printer_maintenance.reset_plate` | `plate_id`, `entry_id` *(opt)* | Réinitialise le compteur d'un plateau après nettoyage |

**Bobines de filament**

| Service | Paramètres | Description |
|---------|-----------|-------------|
| `printer_maintenance.add_spool` | `name`, `material` *(opt)*, `brand` *(opt)*, `color` *(opt)*, `initial_weight_g` *(opt, défaut 1000)*, `diameter_mm` *(opt, défaut 1.75)*, `entry_id` *(opt)* | Ajoute une nouvelle bobine |
| `printer_maintenance.remove_spool` | `spool_id`, `entry_id` *(opt)* | Supprime une bobine et ses entités |
| `printer_maintenance.set_active_spool` | `spool_id`, `entry_id` *(opt)* | Change la bobine active (seule la bobine active se décrémente) |
| `printer_maintenance.update_spool_weight` | `spool_id`, `remaining_weight_g`, `entry_id` *(opt)* | Corrige manuellement le poids restant |

### Logique des statuts

| Statut | Condition |
|--------|-----------|
| ✅ OK | Vie restante > seuil (20% par défaut) |
| 🟡 Bientôt | Vie restante ≤ seuil |
| 🔴 Requis | Heures utilisées ≥ intervalle |
| 🟣 En retard | Heures utilisées > intervalle |

Le seuil est configurable par entrée d'intégration (Options → Seuil d'alerte « Bientôt », 5–50%).

### Prérequis

- Home Assistant 2024.4+
- Python 3.12+ (inclus avec HA)

### Feuille de route

- [ ] Éditeur visuel pour la carte Lovelace
- [ ] Historique des maintenances
- [x] Notifications HA automatiques au changement de statut
- [x] Gestion multi-plateaux (heures, statut, date d'entretien par plateau)
- [x] Gestion des bobines de filament (matière, marque, décrémentation automatique du poids)
- [ ] Suivi de graissage par composant : date de dernier graissage + intervalle de graissage configurable (distinct de l'intervalle de maintenance général)
- [ ] Connecteurs OctoPrint / Moonraker / Klipper

---

*Made with ❤️ for the Home Assistant community*
