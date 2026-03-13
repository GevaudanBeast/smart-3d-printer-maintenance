class PrinterMaintenanceCard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
      const card = document.createElement('ha-card');
      this.content = document.createElement('div');
      this.content.style.padding = '16px';
      card.appendChild(this.content);
      this.appendChild(card);
    }

    const printer = this._config.printer;
    const title = this._config.title || "Maintenance Imprimante";

    // Récupération des entités dynamiques
    const nozzleHours = hass.states[`input_number.${printer}_aur_maint_nozzle_hours`]?.state || "0";
    const nozzleMax = hass.states[`input_number.${printer}_aur_thr_nozzle_replace_h`]?.state || "300";
    const totalHours = hass.states[`input_number.${printer}_aur_maint_total_hours`]?.state || "0";
    const jobsOk = hass.states[`counter.${printer}_aur_maint_jobs_ok`]?.state || "0";
    const jobsKo = hass.states[`counter.${printer}_aur_maint_jobs_ko`]?.state || "0";

    const percent = Math.min(Math.round((parseFloat(nozzleHours) / parseFloat(nozzleMax)) * 100), 100);
    const color = percent > 90 ? "#e74c3c" : "#2ecc71";

    this.content.innerHTML = `
      <style>
        .pm-header { font-size: 1.1em; font-weight: bold; margin-bottom: 10px; display: flex; justify-content: space-between; }
        .pm-bar-container { background: var(--secondary-background-color); border-radius: 4px; height: 12px; margin: 8px 0; }
        .pm-bar-fill { background: ${color}; height: 100%; border-radius: 4px; width: ${percent}%; transition: width 0.5s; }
        .pm-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 10px; }
        .pm-stat { background: var(--card-background-color); border: 1px solid var(--divider-color); padding: 8px; border-radius: 4px; text-align: center; }
        .pm-label { font-size: 0.7em; color: var(--secondary-text-color); text-transform: uppercase; }
        .pm-value { font-size: 1em; font-weight: bold; }
      </style>
      
      <div class="pm-header">
        <span>${title}</span>
        <span style="color: ${jobsKo > 0 ? '#e74c3c' : '#2ecc71'}">●</span>
      </div>

      <div class="pm-label">Usure Buse : ${nozzleHours}h / ${nozzleMax}h</div>
      <div class="pm-bar-container"><div class="pm-bar-fill"></div></div>

      <div class="pm-grid">
        <div class="pm-stat"><div class="pm-label">Total</div><div class="pm-value">${totalHours}h</div></div>
        <div class="pm-stat"><div class="pm-label">Succès</div><div class="pm-value">${jobsOk}</div></div>
      </div>

      <mwc-button label="Reset Buse" id="btn-reset" style="width: 100%; margin-top: 12px;"></mwc-button>
    `;

    this.content.querySelector('#btn-reset').onclick = () => {
      hass.callService("script", `${printer}_aur_maint_nozzle_replaced`);
    };
  }

  setConfig(config) {
    if (!config.printer) throw new Error("Veuillez définir 'printer: k1c'");
    this._config = config;
  }
}

// PROTECTION CONTRE LES DOUBLONS ET ANCIENS NOMS
// On utilise le nom définitif 'printer-maintenance-card'
if (!customElements.get('printer-maintenance-card')) {
    customElements.define('printer-maintenance-card', PrinterMaintenanceCard);
}

// Ajout pour l'interface visuelle HA
window.customCards = window.customCards || [];
window.customCards.push({
  type: "printer-maintenance-card",
  name: "Printer Maintenance Card",
  description: "Suivi de maintenance pour K1C",
  preview: true
});
