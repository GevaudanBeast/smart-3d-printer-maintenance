/**
 * Printer Maintenance Card — compact Lovelace card
 * Part of the smart-3d-printer-maintenance integration
 *
 * Config example:
 *   type: custom:printer-maintenance-card
 *   printer: k1c              # slugified printer name (lowercase, spaces → _)
 *   title: "K1C Maintenance"  # optional
 *   status_entity: sensor.k1c_print_status  # optional — shown in header
 */

const COMPONENTS = [
  { id: "nozzle",           name: "Nozzle",            category: "Extrusion" },
  { id: "heatbreak",        name: "Heatbreak",          category: "Extrusion" },
  { id: "extruder_gear",    name: "Extruder Gear",      category: "Extrusion" },
  { id: "belts",            name: "Belts",              category: "Movement"  },
  { id: "linear_rods",      name: "Linear Rods",        category: "Movement"  },
  { id: "linear_rails",     name: "Linear Rails",       category: "Movement"  },
  { id: "build_plate",      name: "Build Plate",        category: "Platform"  },
  { id: "build_surface",    name: "Build Surface",      category: "Platform"  },
  { id: "hotend_fan",       name: "Hotend Fan",         category: "Cooling"   },
  { id: "part_cooling_fan", name: "Part Cooling Fan",   category: "Cooling"   },
  { id: "ptfe_tube",        name: "PTFE Tube",          category: "Misc"      },
];

const CATEGORIES = ["Extrusion", "Movement", "Platform", "Cooling", "Misc"];

const STATUS = {
  ok:      { color: "var(--success-color,  #4CAF50)", label: "OK"      },
  soon:    { color: "var(--warning-color,  #FF9800)", label: "Soon"    },
  due:     { color: "var(--error-color,    #F44336)", label: "Due"     },
  overdue: { color: "#9C27B0",                        label: "Overdue" },
};

const PRINT_COLORS = {
  printing: "var(--success-color, #4CAF50)",
  busy:     "var(--success-color, #4CAF50)",
  paused:   "var(--warning-color, #FF9800)",
  idle:     "var(--disabled-color, #9E9E9E)",
  off:      "var(--disabled-color, #9E9E9E)",
};

// ─── Card class ───────────────────────────────────────────────────────────────

class PrinterMaintenanceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  // Called once by HA when the card is first rendered
  setConfig(config) {
    if (!config.printer) {
      throw new Error(
        'Please set "printer" to the slugified printer name (e.g. k1c)'
      );
    }
    this._config = config;
    this._render();
  }

  // Called every time HA state changes
  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  _sid(suffix) {
    return `sensor.${this._config.printer}_${suffix}`;
  }

  _bid(comp) {
    return `button.${this._config.printer}_reset_${comp}`;
  }

  _state(eid) {
    return this._hass?.states?.[eid];
  }

  _val(eid, fb = "—") {
    const s = this._state(eid);
    return s ? s.state : fb;
  }

  _attr(eid, attr, fb = null) {
    return this._state(eid)?.attributes?.[attr] ?? fb;
  }

  async _reset(comp) {
    await this._hass.callService("button", "press", {
      entity_id: this._bid(comp),
    });
  }

  // ── render ─────────────────────────────────────────────────────────────────

  _render() {
    if (!this._config.printer || !this._hass) return;

    const title      = this._config.title || this._config.printer.toUpperCase();
    const rawStatus  = this._config.status_entity
      ? this._val(this._config.status_entity, null)
      : null;

    const totalHours    = parseFloat(this._val(this._sid("total_print_hours"), 0)).toFixed(1);
    const totalFilament = parseFloat(this._val(this._sid("total_filament_used"), 0)).toFixed(1);
    const totalJobs     = this._val(this._sid("total_print_jobs"), "0");

    // ── status pill ──────────────────────────────────────────────────────────
    const pillHtml = rawStatus
      ? (() => {
          const col = PRINT_COLORS[rawStatus.toLowerCase()] ?? PRINT_COLORS.idle;
          return `<span class="pill" style="background:${col}">${rawStatus}</span>`;
        })()
      : "";

    // ── component rows ───────────────────────────────────────────────────────
    let rows = "";
    for (const cat of CATEGORIES) {
      const comps = COMPONENTS.filter((c) => c.category === cat);
      rows += `<div class="cat-label">${cat}</div>`;

      for (const comp of comps) {
        const sid       = this._sid(`${comp.id}_status`);
        const status    = this._val(sid, "ok");
        const used      = parseFloat(this._attr(sid, "hours_used", 0));
        const interval  = parseFloat(this._attr(sid, "interval_hours", 1));
        const pct       = Math.min(100, (used / interval) * 100).toFixed(1);
        const sc        = STATUS[status] || STATUS.ok;
        const lastReset = this._attr(sid, "last_reset");
        const dateHtml  = lastReset
          ? `<span class="last-date">${new Date(lastReset).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}</span>`
          : `<span class="last-date never">—</span>`;

        rows += `
          <div class="comp-row">
            <div class="comp-name-wrap">
              <span class="comp-name">${comp.name}</span>
              ${dateHtml}
            </div>
            <div class="bar">
              <div class="bar-fill" style="width:${pct}%;background:${sc.color}"></div>
            </div>
            <span class="comp-time">${used.toFixed(0)}<span class="dim">/${interval.toFixed(0)}h</span></span>
            <span class="badge" style="color:${sc.color}">${sc.label}</span>
            <button class="rbtn" data-comp="${comp.id}" title="Reset ${comp.name}">↺</button>
          </div>`;
      }
    }

    // ── shadow DOM ───────────────────────────────────────────────────────────
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }

        ha-card {
          background: var(--ha-card-background, var(--card-background-color));
          border-radius: var(--ha-card-border-radius, 12px);
          overflow: hidden;
        }

        .body {
          padding: 14px 16px 16px;
          font-family: var(--primary-font-family, sans-serif);
          color: var(--primary-text-color);
        }

        /* ── header ── */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
        }
        .title {
          display: flex;
          align-items: center;
          gap: 7px;
          font-size: 1.05em;
          font-weight: 600;
        }
        .pill {
          font-size: 0.68em;
          font-weight: 700;
          padding: 3px 10px;
          border-radius: 20px;
          color: #fff;
          text-transform: capitalize;
          letter-spacing: .4px;
        }

        /* ── stats row ── */
        .stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-bottom: 12px;
        }
        .stat {
          background: var(--secondary-background-color, rgba(255,255,255,.06));
          border-radius: 8px;
          padding: 8px 4px 7px;
          text-align: center;
        }
        .stat-val  { font-size: 1.05em; font-weight: 700; line-height: 1.2; }
        .stat-lbl  {
          font-size: 0.62em;
          opacity: .55;
          text-transform: uppercase;
          letter-spacing: .6px;
          margin-top: 2px;
        }

        /* ── divider ── */
        .sep {
          border: none;
          border-top: 1px solid var(--divider-color, rgba(255,255,255,.08));
          margin: 10px 0 0;
        }

        /* ── category label ── */
        .cat-label {
          font-size: 0.6em;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 1px;
          opacity: .45;
          margin: 9px 0 3px;
        }

        /* ── component row ── */
        .comp-row {
          display: grid;
          grid-template-columns: 108px 1fr 66px 52px 22px;
          align-items: center;
          gap: 6px;
          padding: 2px 0;
        }
        .comp-name-wrap {
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .comp-name {
          font-size: 0.8em;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .last-date {
          font-size: 0.6em;
          opacity: .45;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          margin-top: 1px;
        }
        .last-date.never { opacity: .25; }
        .bar {
          height: 5px;
          background: rgba(255,255,255,.09);
          border-radius: 3px;
          overflow: hidden;
        }
        .bar-fill {
          height: 100%;
          border-radius: 3px;
          transition: width .4s ease;
        }
        .comp-time {
          font-size: 0.7em;
          text-align: right;
          white-space: nowrap;
        }
        .dim { opacity: .45; }
        .badge {
          font-size: 0.68em;
          font-weight: 700;
          text-align: center;
        }
        .rbtn {
          background: none;
          border: none;
          cursor: pointer;
          color: var(--secondary-text-color, #aaa);
          font-size: 1em;
          line-height: 1;
          padding: 0;
          opacity: .55;
          transition: opacity .15s, transform .35s;
        }
        .rbtn:hover { opacity: 1; transform: rotate(-180deg); }
      </style>

      <ha-card>
        <div class="body">
          <div class="header">
            <div class="title">
              <ha-icon icon="mdi:printer-3d"></ha-icon>
              ${title}
            </div>
            ${pillHtml}
          </div>

          <div class="stats">
            <div class="stat">
              <div class="stat-val">${totalHours} h</div>
              <div class="stat-lbl">Print time</div>
            </div>
            <div class="stat">
              <div class="stat-val">${totalFilament} m</div>
              <div class="stat-lbl">Filament</div>
            </div>
            <div class="stat">
              <div class="stat-val">${totalJobs}</div>
              <div class="stat-lbl">Jobs</div>
            </div>
          </div>

          <hr class="sep">
          ${rows}
        </div>
      </ha-card>`;

    // attach reset listeners after DOM is written
    this.shadowRoot.querySelectorAll(".rbtn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._reset(btn.dataset.comp);
      });
    });
  }

  setConfig(config) {
    if (!config.printer) throw new Error("Veuillez définir 'printer: k1c'");
    this._config = config;
  }
}

if (!customElements.get("printer-maintenance-card")) {
  customElements.define("printer-maintenance-card", PrinterMaintenanceCard);
}

// Ajout pour l'interface visuelle HA
window.customCards = window.customCards || [];
window.customCards.push({
  type:        "printer-maintenance-card",
  name:        "Printer Maintenance Card",
  description: "Compact maintenance dashboard for 3D printers",
  preview:     false,
});
