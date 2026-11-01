const CARD_TYPE = "pentair-pump-display-card";

const SIBLING_KEYS = {
  power: ["power"],
  display: ["display_active"],
  rpm: ["rpm_reading"],
  gpm: ["gpm_reading"],
  watts: ["watts"],
  mode: ["mode"],
  drive: ["drive_state"],
  clock: ["clock"],
  error: ["error"],
};

const ID_HINTS = {
  power: ["_marche", "_power"],
  display: ["_afficheur", "_display_active"],
  rpm: ["_rpm_actuel", "_current_rpm", "_rpm_reading"],
  gpm: ["_gpm_actuel", "_current_gpm", "_gpm_reading"],
  watts: ["_puissance", "_power_draw", "_watts"],
  mode: ["_mode_de_fonctionnement", "_operating_mode", "_mode"],
  drive: ["_etat", "_drive_state"],
  clock: ["_horloge", "_clock"],
  error: ["_erreur", "_error"],
};

function siblingEntity(hass, anchor, kind, config) {
  const override = config && config[kind];
  if (override) return override;
  const entities = hass.entities || {};
  const meta = entities[anchor];
  const deviceId = meta && meta.device_id;
  const keys = SIBLING_KEYS[kind] || [];
  if (deviceId) {
    for (const [eid, info] of Object.entries(entities)) {
      if (info.device_id !== deviceId) continue;
      if (keys.includes(info.translation_key)) return eid;
    }
  }
  const hints = ID_HINTS[kind] || [];
  const prefix = anchor.replace(/_(marche|power)$/, "");
  for (const hint of hints) {
    const candidate = prefix + hint;
    if (hass.states[candidate]) return candidate;
  }
  if (deviceId) {
    for (const [eid, info] of Object.entries(entities)) {
      if (info.device_id !== deviceId) continue;
      if (hints.some((h) => eid.endsWith(h))) return eid;
    }
  }
  return null;
}

function st(hass, eid) {
  if (!eid) return null;
  return hass.states[eid] || null;
}

class PentairPumpDisplayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Indiquez entity : le switch Marche de la pompe");
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return { entity: "switch.pool_pump_marche" };
  }

  _pick(kind) {
    if (this._config[kind]) return this._config[kind];
    return siblingEntity(this._hass, this._config.entity, kind, this._config);
  }

  _render() {
    const hass = this._hass;
    if (!hass) return;
    const power = st(hass, this._config.entity);
    const rpm = st(hass, this._pick("rpm"));
    const gpm = st(hass, this._pick("gpm"));
    const watts = st(hass, this._pick("watts"));
    const mode = st(hass, this._pick("mode"));
    const drive = st(hass, this._pick("drive"));
    const clock = st(hass, this._pick("clock"));
    const error = st(hass, this._pick("error"));
    const display = st(hass, this._pick("display"));

    const on = power && power.state === "on";
    const remote = display && display.state === "off";
    const lock = Boolean(this._config.lock_when_remote) && remote;
    const rpmVal = rpm && rpm.state !== "unavailable" ? rpm.state : "----";
    const wattVal = watts && watts.state !== "unavailable" ? watts.state : "---";
    const gpmVal = gpm && gpm.state !== "unavailable" && Number(gpm.state) > 0 ? gpm.state : null;
    const modeVal = (mode && mode.state) || (on ? "RUN" : "OFF");
    const driveVal = (drive && drive.state) || "";
    const clockVal = (clock && clock.state) || "--:--";
    const errVal = error && error.state && error.state !== "ok" && error.state !== "OK" ? error.state : "";
    const name = this._config.name || (power && power.attributes.friendly_name) || "INTELLIFLO";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .bezel {
          background: linear-gradient(160deg, #2b2b2b 0%, #141414 55%, #0a0a0a 100%);
          border-radius: 14px;
          padding: 14px 14px 12px;
          box-shadow: inset 0 1px 0 #555, 0 8px 22px rgba(0,0,0,.45);
          font-family: "Share Tech Mono", "Lucida Console", "Courier New", monospace;
        }
        .brand {
          color: #9aa0a6;
          font-size: 11px;
          letter-spacing: .18em;
          text-transform: uppercase;
          display: flex;
          justify-content: space-between;
          margin: 0 4px 8px;
        }
        .lcd {
          background: radial-gradient(ellipse at 50% 0%, #3d6b22 0%, #1c3d12 70%, #13280c 100%);
          border-radius: 6px;
          min-height: 168px;
          padding: 10px 14px 12px;
          color: #b6ff6a;
          text-shadow: 0 0 6px rgba(150,255,70,.35);
          position: relative;
          overflow: hidden;
          box-shadow: inset 0 0 0 2px #0b1a08, inset 0 8px 16px rgba(0,0,0,.25);
        }
        .lcd::after {
          content: "";
          position: absolute;
          inset: 0;
          background: repeating-linear-gradient(
            to bottom,
            rgba(0,0,0,.07) 0 2px,
            transparent 2px 4px
          );
          pointer-events: none;
        }
        .row { display: flex; justify-content: space-between; font-size: 13px; }
        .rpm {
          text-align: center;
          font-size: 52px;
          line-height: 1;
          margin: 14px 0 0;
          letter-spacing: .04em;
        }
        .unit { text-align: center; font-size: 13px; opacity: .85; margin-bottom: 10px; }
        .grid {
          display: flex;
          justify-content: space-between;
          font-size: 13px;
          margin-top: 4px;
        }
        .err { color: #ffe36a; margin-top: 8px; font-size: 12px; }
        .lock {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(10, 24, 8, .72);
          font-size: 16px;
          letter-spacing: .08em;
          text-align: center;
          padding: 12px;
        }
        .keys {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-top: 10px;
        }
        button {
          background: #222;
          color: #d0d0d0;
          border: 1px solid #444;
          border-radius: 6px;
          padding: 7px 4px;
          font-size: 11px;
          letter-spacing: .06em;
          text-transform: uppercase;
          cursor: pointer;
        }
        button:hover { background: #2c2c2c; }
        .off .rpm, .off .unit, .off .grid { opacity: .45; }
      </style>
      <div class="bezel">
        <div class="brand"><span>PENTAIR</span><span>INTELLIFLO</span></div>
        <div class="lcd ${on ? "" : "off"}">
          <div class="row"><span>${this._esc(name)}</span><span>${this._esc(clockVal)}</span></div>
          <div class="rpm">${this._esc(String(on ? rpmVal : "0"))}</div>
          <div class="unit">RPM${gpmVal ? " &nbsp;|&nbsp; " + this._esc(String(gpmVal)) + " GPM" : ""}</div>
          <div class="grid">
            <span>WATTS ${this._esc(String(wattVal))}</span>
            <span>${this._esc(String(modeVal)).toUpperCase()}</span>
          </div>
          <div class="grid">
            <span>${this._esc(String(driveVal)).toUpperCase()}</span>
            <span>${remote ? "REMOTE" : "LOCAL"}</span>
          </div>
          ${errVal ? `<div class="err">ERR ${this._esc(String(errVal)).toUpperCase()}</div>` : ""}
          ${lock ? `<div class="lock">DISPLAY<br>NOT ACTIVE</div>` : ""}
        </div>
        <div class="keys">
          <button data-act="power">${on ? "Stop" : "Start"}</button>
          <button data-act="display">${remote ? "LCD on" : "LCD off"}</button>
          <button data-act="more">Entités</button>
        </div>
      </div>
    `;

    this.shadowRoot.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", (ev) => this._onKey(ev.currentTarget.dataset.act));
    });
  }

  _esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  _onKey(act) {
    const hass = this._hass;
    if (!hass) return;
    if (act === "power") {
      const state = st(hass, this._config.entity);
      if (!state) return;
      hass.callService("switch", state.state === "on" ? "turn_off" : "turn_on", {
        entity_id: this._config.entity,
      });
      return;
    }
    if (act === "display") {
      const eid = this._pick("display");
      const state = st(hass, eid);
      if (!eid || !state) return;
      hass.callService("switch", state.state === "on" ? "turn_off" : "turn_on", {
        entity_id: eid,
      });
      return;
    }
    if (act === "more") {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          bubbles: true,
          composed: true,
          detail: { entityId: this._config.entity },
        })
      );
    }
  }
}

customElements.define(CARD_TYPE, PentairPumpDisplayCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TYPE,
  name: "Pentair — afficheur pompe",
  description: "Écran LCD style IntelliFlo (RPM, watts, mode)",
  preview: true,
});
