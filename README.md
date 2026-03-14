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
- **Automatic HA persistent notifications** — fired when a component reaches `Due` or `Overdue`, dismissed automatically on reset
- **49 sensors** (global stats + per-component hours used / remaining / status / last maintenance date)
- **11 reset buttons** (one per component, configurable category)
- **5 services**: reset a counter, set an interval, add hours, set total hours, set total filament
- **Compact Lovelace card** — auto-registered, no manual resource setup, shows last maintenance date per component
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
printer: k1c              # slugified printer name (lowercase, spaces → _)
title: "K1C Maintenance"  # optional
```

The card displays (designed to complement ha_creality_ws, no duplication):
- Global stats: total print hours · filament used · jobs count
- Per-component: progress bar, hours used / interval, status badge, **last maintenance date**
- Inline reset button per component (appears on hover)

### Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `printer_maintenance.reset_component` | `component`, `entry_id` *(opt)* | Reset a component counter after maintenance |
| `printer_maintenance.set_interval` | `component`, `interval_hours`, `entry_id` *(opt)* | Update a maintenance interval |
| `printer_maintenance.add_hours` | `hours`, `component` *(opt)*, `entry_id` *(opt)* | Manually add print hours |
| `printer_maintenance.set_total_hours` | `hours`, `entry_id` *(opt)* | Set the global print-hour total without touching component counters |
| `printer_maintenance.set_total_filament` | `meters`, `entry_id` *(opt)* | Set the global filament total without touching component counters |

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
- [ ] Per-component greasing tracking: dedicated greasing date + configurable greasing interval (separate from the general maintenance interval)
- [ ] Filament spool management (brand, material, weight, stock)
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
- **Notifications HA persistantes automatiques** — déclenchées quand un composant passe en `Requis` ou `En retard`, supprimées automatiquement à la réinitialisation
- **49 capteurs** (statistiques globales + heures utilisées / restantes / statut / date dernier entretien par composant)
- **11 boutons de réinitialisation** (un par composant)
- **5 services** : réinitialiser un compteur, définir un intervalle, ajouter des heures, définir le total d'heures, définir le total de filament
- **Carte Lovelace compacte** — enregistrée automatiquement, affiche la date de dernier entretien par composant
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
printer: k1c              # nom en minuscules (espaces → _)
title: "K1C Maintenance"  # optionnel
```

La carte affiche (conçue pour compléter ha_creality_ws, sans duplication) :
- Statistiques globales : heures totales · filament utilisé · nombre de jobs
- Par composant : barre de progression, heures utilisées / intervalle, badge de statut, **date du dernier entretien**
- Bouton de réinitialisation par composant (visible au survol)

### Services

| Service | Paramètres | Description |
|---------|-----------|-------------|
| `printer_maintenance.reset_component` | `component`, `entry_id` *(opt)* | Réinitialise le compteur d'un composant après maintenance |
| `printer_maintenance.set_interval` | `component`, `interval_hours`, `entry_id` *(opt)* | Modifie l'intervalle de maintenance |
| `printer_maintenance.add_hours` | `hours`, `component` *(opt)*, `entry_id` *(opt)* | Ajoute des heures d'impression manuellement |
| `printer_maintenance.set_total_hours` | `hours`, `entry_id` *(opt)* | Définit le total d'heures global sans toucher aux compteurs des composants |
| `printer_maintenance.set_total_filament` | `meters`, `entry_id` *(opt)* | Définit le total de filament global sans toucher aux compteurs des composants |

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
- [ ] Suivi de graissage par composant : date de dernier graissage + intervalle de graissage configurable (distinct de l'intervalle de maintenance général)
- [ ] Gestion des bobines de filament (marque, matière, poids, stock)
- [ ] Connecteurs OctoPrint / Moonraker / Klipper

---

*Made with ❤️ for the Home Assistant community*
