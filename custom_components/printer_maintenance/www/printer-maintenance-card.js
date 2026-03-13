console.info("Printer Maintenance Card: script start");
/**
 * Printer Maintenance Card — compact Lovelace card
 * Designed to complement ha_creality_ws (no duplication of print status,
 * temperatures, progress, etc.).
 *
 * Config:
 *   type: custom:printer-maintenance-card
 *   printer: k1c              # slugified printer name (lowercase, spaces → _)
 *   title: "K1C Maintenance"  # optional
 */

const COMPONENTS = [
  { id: "nozzle",           name: "Nozzle",           category: "Extrusion" },
  { id: "heatbreak",        name: "Heatbreak",         category: "Extrusion" },
  { id: "extruder_gear",    name: "Extruder Gear",     category: "Extrusion" },
  { id: "belts",            name: "Belts",             category: "Movement"  },
  { id: "linear_rods",      name: "Linear Rods",       category: "Movement"  },
  { id: "linear_rails",     name: "Linear Rails",      category: "Movement"  },
  { id: "build_plate",      name: "Build Plate",       category: "Platform"  },
  { id: "build_surface",    name: "Build Surface",     category: "Platform"  },
  { id: "hotend_fan",       name: "Hotend Fan",        category: "Cooling"   },
  { id: "part_cooling_fan", name: "Part Cooling Fan",  category: "Cooling"   },
  { id: "ptfe_tube",        name: "PTFE Tube",         category: "Misc"      },
];

const CATEGORIES = ["Extrusion", "Movement", "Platform", "Cooling", "Misc"];

const STATUS = {
  ok:      { color: "var(--success-color,  #4CAF50)", label: "OK"      },
  soon:    { color: "var(--warning-color,  #FF9800)", label: "Soon"    },
  due:     { color: "var(--error-color,    #F44336)", label: "Due"     },
  overdue: { color: "#9C27B0",                        label: "Overdue" },
};

// ─── Card ─────────────────────────────────────────────────────────────────────

class PrinterMaintenanceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config     = {};
    this._hass       = null;
    this._resetOpen  = false;   // persists between hass updates
  }

  setConfig(config) {
    if (!config.printer) {
      throw new Error('Please set "printer" to the slugified printer name (e.g. k1c)');
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  _sid(suffix) { return `sensor.${this._config.printer}_${suffix}`; }
  _bid(comp)   { return `button.${this._config.printer}_reset_${comp}`; }

  _val(eid, fb = "—") {
    return this._hass?.states?.[eid]?.state ?? fb;
  }
  _attr(eid, attr, fb = null) {
    return this._hass?.states?.[eid]?.attributes?.[attr] ?? fb;
  }

  async _reset(comp) {
    await this._hass.callService("button", "press", { entity_id: this._bid(comp) });
  }

  // ── render ─────────────────────────────────────────────────────────────────

  _render() {
    if (!this._config.printer || !this._hass) return;

    const title         = this._config.title || this._config.printer.toUpperCase();
    const totalHours    = parseFloat(this._val(this._sid("total_print_hours"), 0)).toFixed(1);
    const totalFilament = parseFloat(this._val(this._sid("total_filament_used"), 0)).toFixed(1);
    const totalJobsOk   = this._val(this._sid("total_jobs_ok"),  "0");
    const totalJobsKo   = this._val(this._sid("total_jobs_failed"), "0");

    // ── component rows ───────────────────────────────────────────────────────
    let rows = "";
    for (const cat of CATEGORIES) {
      const comps = COMPONENTS.filter((c) => c.category === cat);
      rows += `<div class="cat-label">${cat}</div>`;

      for (const comp of comps) {
        const sid      = this._sid(`${comp.id}_status`);
        const status   = this._val(sid, "ok");
        const used     = parseFloat(this._attr(sid, "hours_used",     0));
        const interval = parseFloat(this._attr(sid, "interval_hours", 1));
        const pct      = Math.min(100, (used / interval) * 100).toFixed(1);
        const sc       = STATUS[status] || STATUS.ok;

        rows += `
          <div class="comp-row">
            <span class="comp-name">${comp.name}</span>
            <div class="bar"><div class="bar-fill" style="width:${pct}%;background:${sc.color}"></div></div>
            <span class="comp-time">${used.toFixed(0)}<span class="dim">/${interval.toFixed(0)}h</span></span>
            <span class="badge" style="color:${sc.color}">${sc.label}</span>
          </div>`;
      }
    }

    // ── reset drawer (hidden by default) ─────────────────────────────────────
    let resetGrid = "";
    for (const comp of COMPONENTS) {
      resetGrid += `
        <div class="reset-item">
          <span class="reset-name">${comp.name}</span>
          <button class="rbtn" data-comp="${comp.id}" title="Reset ${comp.name}">↺</button>
        </div>`;
    }

    const drawerClass = this._resetOpen ? "drawer open" : "drawer";

    // ── shadow DOM ───────────────────────────────────────────────────────────
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }

        ha-card {
          background: var(--ha-card-background, var(--card-background-color));
          border-radius: var(--ha-card-border-radius, 12px);
          overflow: hidden;
        }

        .body { padding: 14px 16px 16px; font-family: var(--primary-font-family, sans-serif); color: var(--primary-text-color); }

        /* header */
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
        .title  { display: flex; align-items: center; gap: 7px; font-size: 1.05em; font-weight: 600; }

        /* stats */
        .stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 12px; }
        .stat  { background: var(--secondary-background-color, rgba(255,255,255,.06)); border-radius: 8px; padding: 8px 4px 7px; text-align: center; }
        .stat-val { font-size: 1.05em; font-weight: 700; line-height: 1.2; }
        .stat-lbl { font-size: 0.62em; opacity: .55; text-transform: uppercase; letter-spacing: .6px; margin-top: 2px; }

        /* divider */
        .sep { border: none; border-top: 1px solid var(--divider-color, rgba(255,255,255,.08)); margin: 10px 0 0; }

        /* category + rows */
        .cat-label { font-size: 0.6em; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; opacity: .45; margin: 9px 0 3px; }
        .comp-row  { display: grid; grid-template-columns: 108px 1fr 66px 52px; align-items: center; gap: 6px; padding: 2px 0; }
        .comp-name { font-size: 0.8em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .bar  { height: 5px; background: rgba(255,255,255,.09); border-radius: 3px; overflow: hidden; }
        .bar-fill { height: 100%; border-radius: 3px; transition: width .4s ease; }
        .comp-time { font-size: 0.7em; text-align: right; white-space: nowrap; }
        .dim   { opacity: .45; }
        .badge { font-size: 0.68em; font-weight: 700; text-align: center; }

        /* reset toggle button */
        .reset-toggle {
          width: 100%;
          margin-top: 12px;
          background: rgba(255,255,255,.05);
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 8px;
          color: var(--secondary-text-color, #aaa);
          font-size: 0.78em;
          padding: 6px 12px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: space-between;
          transition: background .15s;
        }
        .reset-toggle:hover { background: rgba(255,255,255,.1); }
        .toggle-arrow { transition: transform .25s; }
        .open .toggle-arrow { transform: rotate(180deg); }

        /* reset drawer */
        .drawer {
          display: grid;
          grid-template-rows: 0fr;
          transition: grid-template-rows .28s ease;
          overflow: hidden;
        }
        .drawer.open { grid-template-rows: 1fr; }
        .drawer-inner { min-height: 0; }

        .reset-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 6px;
          padding: 10px 0 2px;
        }
        .reset-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: rgba(255,255,255,.04);
          border-radius: 7px;
          padding: 5px 8px;
        }
        .reset-name { font-size: 0.75em; opacity: .8; }
        .rbtn {
          background: none;
          border: 1px solid rgba(255,255,255,.15);
          border-radius: 5px;
          cursor: pointer;
          color: var(--secondary-text-color, #aaa);
          font-size: 1em;
          padding: 2px 6px;
          line-height: 1;
          opacity: .7;
          transition: opacity .15s, transform .35s, border-color .15s;
        }
        .rbtn:hover { opacity: 1; transform: rotate(-180deg); border-color: rgba(255,255,255,.4); }
      </style>

      <ha-card>
        <div class="body">
          <div class="header">
            <div class="title">
              <ha-icon icon="mdi:printer-3d"></ha-icon>
              ${title}
            </div>
            <ha-icon icon="mdi:wrench-clock" style="opacity:.5"></ha-icon>
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
              <div class="stat-val" style="color:var(--success-color,#4CAF50)">${totalJobsOk} ✓</div>
              <div class="stat-lbl">Jobs OK</div>
            </div>
            <div class="stat">
              <div class="stat-val" style="color:var(--error-color,#F44336)">${totalJobsKo} ✗</div>
              <div class="stat-lbl">Jobs KO</div>
            </div>
          </div>

          <hr class="sep">
          ${rows}

          <button class="reset-toggle ${this._resetOpen ? "open" : ""}" id="toggleBtn">
            <span>🔧 Reset a component</span>
            <span class="toggle-arrow">▼</span>
          </button>

          <div class="${drawerClass}">
            <div class="drawer-inner">
              <div class="reset-grid">
                ${resetGrid}
              </div>
            </div>
          </div>
        </div>
      </ha-card>`;

    // toggle drawer
    this.shadowRoot.getElementById("toggleBtn").addEventListener("click", () => {
      this._resetOpen = !this._resetOpen;
      this._render();
    });

    // reset buttons
    this.shadowRoot.querySelectorAll(".rbtn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._reset(btn.dataset.comp);
      });
    });
  }

  getCardSize() { return 9; }

  static getStubConfig() {
    return { printer: "k1c", title: "K1C Maintenance" };
  }
}

if (!customElements.get("printer-maintenance-card")) {
  customElements.define("printer-maintenance-card", PrinterMaintenanceCard);
  console.info("Printer Maintenance Card loaded");
} else {
  console.warn("Printer Maintenance Card already registered — skipping");
}

window.customCards = window.customCards || [];
window.customCards.push({
  type:        "printer-maintenance-card",
  name:        "Printer Maintenance Card",
  description: "Compact maintenance dashboard — complements ha_creality_ws",
  preview:     false,
});
