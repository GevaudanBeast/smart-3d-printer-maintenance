class PrinterMaintenanceCard extends HTMLElement {
  set editMode(editMode) {
    this._editMode = editMode;
  }

  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div id="container" style="padding: 16px;"></div>
        </ha-card>
      `;
      this.content = this.querySelector("#container");
    }

    const config = this._config;
    const printer = config.printer;

    // Récupération des entités dynamiques basées sur le nom de l'imprimante
    const nozzleHours = hass.states[`input_number.${printer}_aur_maint_nozzle_hours`]?.state || "0";
    const nozzleLimit = hass.states[`input_number.${printer}_aur_thr_nozzle_replace_h`]?.state || "300";
    const totalHours = hass.states[`input_number.${printer}_aur_maint_total_hours`]?.state || "0";
    const totalFilament = hass.states[`input_number.${printer}_aur_maint_total_filament_m`]?.state || "0";
    const jobsOk = hass.states[`counter.${printer}_aur_maint_jobs_ok`]?.state || "0";
    const jobsKo = hass.states[`counter.${printer}_aur_maint_jobs_ko`]?.state || "0";

    const nozzlePercent = Math.min(Math.round((nozzleHours / nozzleLimit) * 100), 100);
    const statusColor = jobsKo > 0 ? "#e74c3c" : "#2ecc71";

    this.content.innerHTML = `
      <style>
        .maint-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 10px; }
        .maint-item { background: var(--secondary-background-color); padding: 10px; border-radius: 8px; text-align: center; }
        .maint-label { font-size: 0.8em; color: var(--secondary-text-color); }
        .maint-value { font-size: 1.1em; font-weight: bold; }
        .progress-bar { background: var(--divider-color); border-radius: 5px; height: 10px; margin: 5px 0; overflow: hidden; }
        .progress-fill { background: ${nozzlePercent > 90 ? '#e74c3c' : '#3498db'}; height: 100%; width: ${nozzlePercent}%; transition: width 0.5s; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
        .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 0.75em; color: white; background: ${statusColor}; }
      </style>
      
      <div class="header">
        <div style="font-size: 1.2em; font-weight: bold;">${config.title || "Printer Maintenance"}</div>
        <div class="status-badge">${jobsKo > 0 ? 'Erreur' : 'OK'}</div>
      </div>

      <div class="maint-label">Usure Buse (${nozzleHours}h / ${nozzleLimit}h)</div>
      <div class="progress-bar"><div class="progress-fill"></div></div>

      <div class="maint-grid">
        <div class="maint-item">
          <div class="maint-label">Total Heures</div>
          <div class="maint-value">${totalHours}h</div>
        </div>
        <div class="maint-item">
          <div class="maint-label">Filament</div>
          <div class="maint-value">${totalFilament}m</div>
        </div>
        <div class="maint-item">
          <div class="maint-label">Jobs OK</div>
          <div class="maint-value" style="color: #2ecc71;">${jobsOk}</div>
        </div>
        <div class="maint-item">
          <div class="maint-label">Jobs KO</div>
          <div class="maint-value" style="color: #e74c3c;">${jobsKo}</div>
        </div>
      </div>

      <div style="margin-top: 15px; display: flex; gap: 5px;">
        <mwc-button raised label="Reset Buse" id="reset-nozzle" style="flex: 1;"></mwc-button>
        <mwc-button raised label="Reset All" id="reset-all" style="flex: 1; --mdc-theme-primary: #e74c3c;"></mwc-button>
      </div>
    `;

    this.content.querySelector("#reset-nozzle").addEventListener("click", () => {
      hass.callService("script", `${printer}_aur_maint_nozzle_replaced`);
    });

    this.content.querySelector("#reset-all").addEventListener("click", () => {
      if (confirm("Réinitialiser tous les compteurs ?")) {
        hass.callService("script", `${printer}_aur_maint_reset_all`);
      }
    });
  }

  setConfig(config) {
    if (!config.printer) {
      throw new Error("Veuillez définir l'imprimante (ex: printer: k1c)");
    }
    this._config = config;
  }

  getCardSize() {
    return 3;
  }
}

// Sécurité pour éviter l'erreur "already been used"
if (!customElements.get('printer-maintenance-card')) {
  customElements.define('printer-maintenance-card', PrinterMaintenanceCard);
}

// Déclaration pour que HA reconnaisse la carte dans l'interface
window.customCards = window.customCards || [];
window.customCards.push({
  type: "printer-maintenance-card",
  name: "Printer Maintenance Card",
  description: "Carte personnalisée pour le suivi d'entretien d'imprimante 3D",
  preview: true
});
