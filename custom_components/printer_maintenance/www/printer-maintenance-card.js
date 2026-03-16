/**
 * Printer Maintenance Card — compact Lovelace card
 * Part of the smart-3d-printer-maintenance integration
 *
 * Config example:
 *   type: custom:printer-maintenance-card
 *   printer: k1c              # slugified printer name (lowercase, spaces → _)
 *   title: "K1C Maintenance"  # optional
 *   status_entity: sensor.k1c_print_status  # optional — shown in header
 *   plates:                   # optional list of plate IDs to display
 *     - pei_smooth
 *     - pei_textured
 *   spools:                   # optional list of spool IDs to display
 *     - pla_white
 *     - petg_black
 */

const COMPONENTS = [
  { id: "nozzle",           name: "Nozzle",            category: "Extrusion" },
  { id: "heatbreak",        name: "Heatbreak",          category: "Extrusion" },
  { id: "extruder_gear",    name: "Extruder Gear",      category: "Extrusion", greasable: true },
  { id: "belts",            name: "Belts",              category: "Movement",  greasable: true },
  { id: "linear_rods",      name: "Linear Rods",        category: "Movement",  greasable: true },
  { id: "linear_rails",     name: "Linear Rails",       category: "Movement",  greasable: true },
  { id: "build_plate",      name: "Build Plate",        category: "Platform"  },
  { id: "build_surface",    name: "Build Surface",      category: "Platform"  },
  { id: "hotend_fan",       name: "Hotend Fan",         category: "Cooling"   },
  { id: "part_cooling_fan", name: "Part Cooling Fan",   category: "Cooling"   },
  { id: "ptfe_tube",        name: "PTFE Tube",          category: "Misc"      },
  { id: "hotend_screws",    name: "Hotend Screws",      category: "Fasteners" },
  { id: "extruder_screws",  name: "Extruder Screws",    category: "Fasteners" },
  { id: "gantry_screws",    name: "Gantry Screws",      category: "Fasteners" },
  { id: "bed_screws",       name: "Bed Screws",         category: "Fasteners" },
  { id: "frame_screws",     name: "Frame Screws",       category: "Fasteners" },
];

const CATEGORIES = ["Extrusion", "Movement", "Platform", "Cooling", "Misc", "Fasteners"];

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
    // Track inline interval edit: { compId, type: 'maintenance'|'greasing' }
    this._editState = null;
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
    // Don't clobber an in-progress interval edit on every HA state update
    if (!this._editState) this._render();
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

  async _grease(comp) {
    await this._hass.callService("button", "press", {
      entity_id: `button.${this._config.printer}_grease_${comp}`,
    });
  }

  _startEdit(compId, type) {
    this._editState = { compId, type };
    this._render();
    // Focus the input after render
    requestAnimationFrame(() => {
      const inp = this.shadowRoot.querySelector(`#int-${compId}-${type[0]}`);
      if (inp) { inp.focus(); inp.select(); }
    });
  }

  _cancelEdit() {
    this._editState = null;
    this._render();
  }

  async _saveInterval(compId, type) {
    const inp = this.shadowRoot.querySelector(`#int-${compId}-${type[0]}`);
    if (!inp) return;
    const hours = parseFloat(inp.value);
    if (isNaN(hours) || hours < 1 || hours > 10000) { this._cancelEdit(); return; }
    const service = type === "greasing" ? "set_greasing_interval" : "set_interval";
    await this._hass.callService("printer_maintenance", service, { component: compId, interval_hours: hours });
    this._editState = null;
    this._render();
  }

  async _pressButton(entityId) {
    await this._hass.callService("button", "press", { entity_id: entityId });
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

        // Inline edit state flags
        const editingM = this._editState?.compId === comp.id && this._editState?.type === "maintenance";
        const editingG = this._editState?.compId === comp.id && this._editState?.type === "greasing";

        // Maintenance time column + action column
        const mTimeHtml = editingM
          ? `<span class="comp-time"><input id="int-${comp.id}-m" class="int-input" type="number" min="1" max="10000" value="${interval.toFixed(0)}"></span>`
          : `<span class="comp-time">${used.toFixed(0)}<span class="dim">/${interval.toFixed(0)}h</span></span>`;
        const mBadgeHtml = editingM
          ? `<span class="edit-actions"><button class="ok-btn" data-comp="${comp.id}" data-type="maintenance">✓</button><button class="cancel-btn">✗</button></span>`
          : `<span class="badge" style="color:${sc.color}">${sc.label}</span>`;
        const mActionHtml = editingM
          ? ``
          : `<span class="row-actions"><button class="rbtn" data-comp="${comp.id}" title="Reset ${comp.name}">↺</button><button class="edit-btn" data-comp="${comp.id}" data-type="maintenance" title="Edit maintenance interval">✎</button></span>`;

        // Greasing sub-row (greasable components only)
        let greasingHtml = "";
        if (comp.greasable) {
          const gsid        = this._sid(`${comp.id}_greasing_status`);
          const gStatus     = this._val(gsid, "ok");
          const gUsed       = parseFloat(this._attr(gsid, "greasing_hours_used", 0));
          const gInterval   = parseFloat(this._attr(gsid, "greasing_interval_hours", 1));
          const gPct        = Math.min(100, (gUsed / gInterval) * 100).toFixed(1);
          const gsc         = STATUS[gStatus] || STATUS.ok;
          const lastGreasing = this._attr(gsid, "last_greasing");
          const gDateHtml   = lastGreasing
            ? `<span class="last-date">${new Date(lastGreasing).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}</span>`
            : `<span class="last-date never">—</span>`;

          const gTimeHtml = editingG
            ? `<span class="comp-time"><input id="int-${comp.id}-g" class="int-input" type="number" min="1" max="10000" value="${gInterval.toFixed(0)}"></span>`
            : `<span class="comp-time">${gUsed.toFixed(0)}<span class="dim">/${gInterval.toFixed(0)}h</span></span>`;
          const gBadgeHtml = editingG
            ? `<span class="edit-actions"><button class="ok-btn" data-comp="${comp.id}" data-type="greasing">✓</button><button class="cancel-btn">✗</button></span>`
            : `<span class="badge" style="color:${gsc.color}">${gsc.label}</span>`;
          const gActionHtml = editingG
            ? ``
            : `<span class="row-actions"><button class="gbtn" data-comp="${comp.id}" title="Grease ${comp.name}">💧</button><button class="edit-btn" data-comp="${comp.id}" data-type="greasing" title="Edit greasing interval">✎</button></span>`;

          greasingHtml = `
          <div class="grease-row">
            <div class="comp-name-wrap">
              <span class="grease-label">💧</span>
              ${gDateHtml}
            </div>
            <div class="bar grease-bar">
              <div class="bar-fill" style="width:${gPct}%;background:${gsc.color}"></div>
            </div>
            ${gTimeHtml}
            ${gBadgeHtml}
            ${gActionHtml}
          </div>`;
        }

        rows += `
          <div class="comp-row">
            <div class="comp-name-wrap">
              <span class="comp-name">${comp.name}</span>
              ${dateHtml}
            </div>
            <div class="bar">
              <div class="bar-fill" style="width:${pct}%;background:${sc.color}"></div>
            </div>
            ${mTimeHtml}
            ${mBadgeHtml}
            ${mActionHtml}
          </div>
          ${greasingHtml}`;
      }
    }

    // ── plates section ───────────────────────────────────────────────────────
    let platesHtml = "";
    const plateIds = this._config.plates || [];
    if (plateIds.length > 0) {
      platesHtml += `<hr class="sep"><div class="cat-label">Plateaux / Build Plates</div>`;
      for (const plateId of plateIds) {
        const sid      = this._sid(`plate_${plateId}_status`);
        const status   = this._val(sid, "ok");
        const used     = parseFloat(this._attr(sid, "hours_used", 0));
        const interval = parseFloat(this._attr(sid, "interval_hours", 1));
        const pct      = Math.min(100, (used / interval) * 100).toFixed(1);
        const sc       = STATUS[status] || STATUS.ok;
        const lastReset = this._attr(sid, "last_reset");
        const isActive  = this._attr(sid, "active", false);
        const nameSid   = this._sid(`plate_${plateId}_hours_used`);
        const plateName = this._attr(nameSid, "name") || plateId;
        const activeIcon = isActive ? `<span class="active-star" title="Active">★</span>` : `<span class="active-star inactive">☆</span>`;
        const dateHtml  = lastReset
          ? `<span class="last-date">${new Date(lastReset).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}</span>`
          : `<span class="last-date never">—</span>`;
        const resetBtnId   = `button.${this._config.printer}_reset_plate_${plateId}`;
        const activateBtnId = `button.${this._config.printer}_activate_plate_${plateId}`;

        platesHtml += `
          <div class="comp-row plate-row">
            <div class="comp-name-wrap">
              <span class="comp-name">${activeIcon} ${plateName}</span>
              ${dateHtml}
            </div>
            <div class="bar">
              <div class="bar-fill" style="width:${pct}%;background:${sc.color}"></div>
            </div>
            <span class="comp-time">${used.toFixed(0)}<span class="dim">/${interval.toFixed(0)}h</span></span>
            <span class="badge" style="color:${sc.color}">${sc.label}</span>
            <span class="plate-btns">
              <button class="rbtn" data-entity="${resetBtnId}" title="Reset ${plateName}">↺</button>
              <button class="abtn" data-entity="${activateBtnId}" title="Activate ${plateName}">▶</button>
            </span>
          </div>`;
      }
    }

    // ── spools section ───────────────────────────────────────────────────────
    let spoolsHtml = "";
    const spoolIds = this._config.spools || [];
    if (spoolIds.length > 0) {
      spoolsHtml += `<hr class="sep"><div class="cat-label">Bobines / Filament Spools</div>`;
      for (const spoolId of spoolIds) {
        const sid       = this._sid(`spool_${spoolId}_remaining`);
        const remaining = parseFloat(this._val(sid, 0));
        const material  = this._attr(sid, "material", "");
        const brand     = this._attr(sid, "brand", "");
        const color     = this._attr(sid, "color", "");
        const remPct    = parseFloat(this._attr(sid, "remaining_pct", 0));
        const isActive  = this._attr(sid, "active", false);
        const spoolName = this._attr(sid, "name") || spoolId;
        const activeIcon = isActive ? `<span class="active-star" title="Active">★</span>` : `<span class="active-star inactive">☆</span>`;
        const pctColor  = remPct < 10 ? STATUS.overdue.color : remPct < 25 ? STATUS.due.color : remPct < 50 ? STATUS.soon.color : STATUS.ok.color;
        const matBadge  = material ? `<span class="mat-badge">${material}</span>` : "";
        const brandTxt  = brand ? `<span class="dim" style="font-size:0.65em"> ${brand}</span>` : "";
        const colorDot  = color ? `<span class="color-dot" style="background:${color}" title="${color}"></span>` : "";
        const activateBtnId = `button.${this._config.printer}_activate_spool_${spoolId}`;

        spoolsHtml += `
          <div class="spool-row">
            <div class="comp-name-wrap">
              <span class="comp-name">${activeIcon} ${colorDot} ${spoolName} ${matBadge}${brandTxt}</span>
            </div>
            <div class="bar">
              <div class="bar-fill" style="width:${Math.min(100, remPct).toFixed(1)}%;background:${pctColor}"></div>
            </div>
            <span class="comp-time">${remaining.toFixed(0)}<span class="dim">g</span></span>
            <span class="badge" style="color:${pctColor}">${remPct.toFixed(0)}%</span>
            <button class="abtn" data-entity="${activateBtnId}" title="Activate ${spoolName}">▶</button>
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
          grid-template-columns: 108px 1fr 66px 52px 38px;
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

        /* ── activate button ── */
        .abtn {
          background: none;
          border: none;
          cursor: pointer;
          color: var(--secondary-text-color, #aaa);
          font-size: 0.8em;
          line-height: 1;
          padding: 0;
          opacity: .45;
          transition: opacity .15s;
        }
        .abtn:hover { opacity: 1; color: var(--primary-color, #03a9f4); }

        /* ── plate buttons group ── */
        .plate-btns {
          display: flex;
          gap: 2px;
          align-items: center;
        }

        /* ── active star ── */
        .active-star {
          color: var(--warning-color, #FF9800);
          font-size: 0.85em;
        }
        .active-star.inactive {
          color: var(--disabled-color, #9E9E9E);
          opacity: .35;
        }

        /* ── greasing sub-row ── */
        .grease-row {
          display: grid;
          grid-template-columns: 108px 1fr 66px 52px 38px;
          align-items: center;
          gap: 6px;
          padding: 1px 0 3px;
          opacity: .8;
        }
        .grease-label {
          font-size: 0.75em;
          line-height: 1;
        }
        .grease-bar {
          height: 3px;
        }
        .gbtn {
          background: none;
          border: none;
          cursor: pointer;
          font-size: 0.85em;
          line-height: 1;
          padding: 0;
          opacity: .45;
          transition: opacity .15s, transform .2s;
        }
        .gbtn:hover { opacity: 1; transform: scale(1.3); }

        /* ── row actions (reset + edit) ── */
        .row-actions {
          display: flex;
          gap: 2px;
          align-items: center;
        }

        /* ── inline interval edit ── */
        .edit-btn {
          background: none;
          border: none;
          cursor: pointer;
          color: var(--secondary-text-color, #aaa);
          font-size: 0.75em;
          line-height: 1;
          padding: 0;
          opacity: 0;
          transition: opacity .15s;
        }
        .comp-row:hover .edit-btn,
        .grease-row:hover .edit-btn { opacity: .45; }
        .edit-btn:hover { opacity: 1 !important; }

        .int-input {
          width: 52px;
          background: var(--secondary-background-color, rgba(255,255,255,.08));
          border: 1px solid var(--primary-color, #03a9f4);
          border-radius: 4px;
          color: var(--primary-text-color);
          font-size: 0.75em;
          padding: 1px 3px;
          text-align: right;
          -moz-appearance: textfield;
        }
        .int-input::-webkit-inner-spin-button { display: none; }

        .edit-actions {
          display: flex;
          gap: 2px;
          align-items: center;
        }
        .ok-btn, .cancel-btn {
          background: none;
          border: none;
          cursor: pointer;
          font-size: 0.85em;
          line-height: 1;
          padding: 0;
          opacity: .7;
          transition: opacity .15s;
        }
        .ok-btn { color: var(--success-color, #4CAF50); }
        .cancel-btn { color: var(--error-color, #F44336); }
        .ok-btn:hover, .cancel-btn:hover { opacity: 1; }

        /* ── spool row ── */
        .spool-row {
          display: grid;
          grid-template-columns: 108px 1fr 66px 42px 22px;
          align-items: center;
          gap: 6px;
          padding: 2px 0;
        }

        /* ── material badge ── */
        .mat-badge {
          font-size: 0.6em;
          font-weight: 700;
          padding: 1px 5px;
          border-radius: 4px;
          background: var(--secondary-background-color, rgba(255,255,255,.1));
          vertical-align: middle;
        }

        /* ── color dot ── */
        .color-dot {
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          vertical-align: middle;
          border: 1px solid rgba(255,255,255,.3);
          margin-right: 2px;
        }
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
          ${platesHtml}
          ${spoolsHtml}
        </div>
      </ha-card>`;

    // attach reset listeners for component buttons (use data-comp)
    this.shadowRoot.querySelectorAll(".rbtn[data-comp]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._reset(btn.dataset.comp);
      });
    });

    // attach listeners for plate/spool entity buttons (use data-entity)
    this.shadowRoot.querySelectorAll(".rbtn[data-entity], .abtn[data-entity]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._pressButton(btn.dataset.entity);
      });
    });

    // attach grease button listeners
    this.shadowRoot.querySelectorAll(".gbtn[data-comp]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._grease(btn.dataset.comp);
      });
    });

    // attach edit-interval button listeners
    this.shadowRoot.querySelectorAll(".edit-btn[data-comp]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._startEdit(btn.dataset.comp, btn.dataset.type);
      });
    });

    // attach save listeners
    this.shadowRoot.querySelectorAll(".ok-btn[data-comp]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._saveInterval(btn.dataset.comp, btn.dataset.type);
      });
    });

    // attach cancel listeners
    this.shadowRoot.querySelectorAll(".cancel-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._cancelEdit();
      });
    });

    // keyboard: Enter = save, Escape = cancel
    this.shadowRoot.querySelectorAll(".int-input").forEach((inp) => {
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && this._editState) {
          this._saveInterval(this._editState.compId, this._editState.type);
        } else if (e.key === "Escape") {
          this._cancelEdit();
        }
      });
    });
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
