# 🖨️ Smart 3D Printer Maintenance — Home Assistant Integration

> **[English](#english) | [Français](#français)**

---

## English

### Overview

**Smart 3D Printer Maintenance** is a custom Home Assistant integration that tracks the real usage of your 3D printer and helps you plan component maintenance before failures occur.

Designed first for the **Creality K1C**, it is fully extensible to any brand or model supported by Home Assistant (Bambu Lab, Prusa, Voron, etc.).

### Features

- **Automatic print-time tracking** — detects printing state via any HA entity (works with `ha_creality_ws`, OctoPrint, Moonraker, etc.)
- **11 tracked components** with configurable maintenance intervals
- **4 maintenance statuses**: `OK` · `Soon` · `Due` · `Overdue`
- **33 sensors** (global stats + per-component hours used / remaining / status)
- **11 reset buttons** (one per component)
- **3 services**: reset a counter, set an interval, add hours manually
- **Compact Lovelace card** — auto-registered, no manual resource setup needed
- **Persistent storage** — survives HA restarts, resumes ongoing print sessions
- **Multi-printer** — add one integration entry per printer
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
4. **Step 2 — Entities**: select the HA sensor that reports the print status and enter the state value(s) that mean "printing" (comma-separated, e.g. `printing`)

> **K1C + ha_creality_ws example**
> - Status entity: `sensor.k1c_print_status`
> - Printing states: `printing`

To adjust maintenance intervals, go to the integration's **Options** after setup.

### Lovelace Card

The card is automatically available after installation. Add it to any dashboard:

```yaml
type: custom:printer-maintenance-card
printer: k1c              # slugified printer name (lowercase, spaces → _)
title: "K1C Maintenance"  # optional
status_entity: sensor.k1c_print_status  # optional
```

The card displays:
- Printer name and current print status
- Global stats (total hours · filament used · job count)
- Per-component progress bars, remaining hours, status badges and reset buttons

### Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `printer_maintenance.reset_component` | `component`, `entry_id`(opt) | Reset a component counter after maintenance |
| `printer_maintenance.set_interval` | `component`, `interval_hours`, `entry_id`(opt) | Update a maintenance interval |
| `printer_maintenance.add_hours` | `hours`, `component`(opt), `entry_id`(opt) | Manually add print hours |

### Status Logic

| Status   | Condition |
|----------|-----------|
| ✅ OK     | Remaining life > 20% of interval |
| 🟡 Soon  | Remaining life ≤ 20% of interval |
| 🔴 Due   | Hours used = interval |
| 🟣 Overdue | Hours used > interval |

### Roadmap

- [ ] Lovelace card visual editor (GUI config)
- [ ] Maintenance history log
- [ ] Automatic HA notifications on status change
- [ ] Native filament tracking (from printer API)
- [ ] OctoPrint / Moonraker / Klipper connectors

---

## Français

### Présentation

**Smart 3D Printer Maintenance** est une intégration Home Assistant personnalisée qui suit l'utilisation réelle de votre imprimante 3D et vous aide à planifier la maintenance des composants avant toute défaillance.

Conçue en priorité pour la **Creality K1C**, elle est entièrement extensible à toute marque ou modèle supporté par Home Assistant (Bambu Lab, Prusa, Voron, etc.).

### Fonctionnalités

- **Suivi automatique du temps d'impression** — détecte l'état d'impression via n'importe quelle entité HA (compatible `ha_creality_ws`, OctoPrint, Moonraker, etc.)
- **11 composants suivis** avec intervalles de maintenance configurables
- **4 statuts de maintenance** : `OK` · `Bientôt` · `Requis` · `En retard`
- **33 capteurs** (statistiques globales + heures utilisées / restantes / statut par composant)
- **11 boutons de réinitialisation** (un par composant)
- **3 services** : réinitialiser un compteur, définir un intervalle, ajouter des heures manuellement
- **Carte Lovelace compacte** — enregistrée automatiquement, aucune ressource à ajouter manuellement
- **Stockage persistant** — résiste aux redémarrages HA, reprend les sessions d'impression en cours
- **Multi-imprimantes** — ajoutez une entrée d'intégration par imprimante
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
4. **Étape 2 — Entités** : sélectionner le capteur HA qui rapporte l'état d'impression et saisir la ou les valeurs correspondant à « en impression » (séparées par des virgules, ex. `printing`)

> **Exemple K1C + ha_creality_ws**
> - Entité état : `sensor.k1c_print_status`
> - Valeurs d'impression : `printing`

Pour modifier les intervalles de maintenance, accédez aux **Options** de l'intégration après la configuration initiale.

### Carte Lovelace

La carte est automatiquement disponible après l'installation. Ajoutez-la à n'importe quel tableau de bord :

```yaml
type: custom:printer-maintenance-card
printer: k1c              # nom de l'imprimante en minuscules (espaces → _)
title: "K1C Maintenance"  # optionnel
status_entity: sensor.k1c_print_status  # optionnel
```

La carte affiche :
- Le nom de l'imprimante et l'état d'impression en cours
- Les statistiques globales (heures totales · filament utilisé · nombre d'impressions)
- Par composant : barre de progression, heures restantes, badge de statut et bouton de réinitialisation

### Services

| Service | Paramètres | Description |
|---------|-----------|-------------|
| `printer_maintenance.reset_component` | `component`, `entry_id`(opt) | Réinitialise le compteur d'un composant après maintenance |
| `printer_maintenance.set_interval` | `component`, `interval_hours`, `entry_id`(opt) | Modifie l'intervalle de maintenance |
| `printer_maintenance.add_hours` | `hours`, `component`(opt), `entry_id`(opt) | Ajoute des heures d'impression manuellement |

### Logique des statuts

| Statut         | Condition |
|----------------|-----------|
| ✅ OK           | Vie restante > 20% de l'intervalle |
| 🟡 Bientôt     | Vie restante ≤ 20% de l'intervalle |
| 🔴 Requis      | Heures utilisées = intervalle |
| 🟣 En retard   | Heures utilisées > intervalle |

### Feuille de route

- [ ] Éditeur visuel pour la carte Lovelace
- [ ] Historique des maintenances
- [ ] Notifications HA automatiques au changement de statut
- [ ] Suivi natif du filament (depuis l'API imprimante)
- [ ] Connecteurs OctoPrint / Moonraker / Klipper

---

*Made with ❤️ for the Home Assistant community*
