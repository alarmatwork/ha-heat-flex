// Solar Floor Boost dashboard card: an entities card preconfigured with the
// integration's entities. Shows up under "By card" in the card picker.

const DOMAIN = "solar_floor_boost";
// Must match manifest.json (a test checks). The device's sw_version is the
// version that is running; when it is newer, this file is stale in the
// browser and the card asks for a reload.
const CARD_VERSION = "1.7.2";

// translation_key -> [default entity_id, row name]. Amount and duration are
// shared by both modes (installs from before 1.7.1 have them as
// number.solar_floor_boost_boost_amount/_boost_duration; the registry lookup
// below finds them either way).
const ROWS = {
  boost: ["switch.solar_floor_boost_boost", "Boost"],
  setback: ["switch.solar_floor_boost_setback", "Setback"],
  delta: ["number.solar_floor_boost_amount", "Amount"],
  duration: ["number.solar_floor_boost_duration", "Duration"],
  boost_end: ["sensor.solar_floor_boost_boost_ends", "Boost ends"],
  setback_end: ["sensor.solar_floor_boost_setback_ends", "Setback ends"],
};

// Shown by the (i) next to each mode's switch.
const HINTS = {
  boost:
    "Raises the thermostats for a while, then puts them back.\n" +
    "Use it when you have more energy than you need: the battery is full " +
    "and the sun is still shining, or electricity is cheap right now.",
  setback:
    "Lowers the thermostats for a while, then puts them back.\n" +
    "Use it when energy is scarce or expensive: a price peak, a low " +
    "battery, or a grid alert.",
};

// Entity IDs can be renamed by the user, so look them up in the registry.
function findEntities(hass) {
  const ids = Object.fromEntries(
    Object.entries(ROWS).map(([key, [entityId]]) => [key, entityId])
  );
  for (const entry of Object.values(hass.entities || {})) {
    const key = entry.translation_key;
    // Same domain as the default (1.4.0 also had a "duration" select).
    if (
      entry.platform === DOMAIN &&
      key in ROWS &&
      entry.entity_id.split(".")[0] === ROWS[key][0].split(".")[0]
    ) {
      ids[key] = entry.entity_id;
    }
  }
  return ids;
}

function switchRow(ids, mode) {
  return {
    type: "custom:solar-floor-boost-switch-row",
    entity: ids[mode],
    name: ROWS[mode][1],
    hint: HINTS[mode],
  };
}

// "Boost ends" / "Setback ends", only while that mode runs.
function endsRow(config, ids, mode, endKey) {
  return {
    type: "conditional",
    conditions: [{ entity: ids[mode], state: "on" }],
    row: {
      entity: ids[endKey],
      name: ROWS[endKey][1],
      format: config.end_format ?? "relative",
    },
  };
}

// Version of the integration that is running, from the device registry.
function runningVersion(hass, ids) {
  const deviceId = hass.entities?.[ids.boost]?.device_id;
  return (deviceId && hass.devices?.[deviceId]?.sw_version) || undefined;
}

function entitiesCardConfig(config, ids, staleVersion) {
  return {
    type: "entities",
    title: config.title ?? "Floor heating",
    show_header_toggle: false,
    entities: [
      ...(staleVersion
        ? [{ type: "custom:solar-floor-boost-reload-row", version: staleVersion }]
        : []),
      switchRow(ids, "boost"),
      switchRow(ids, "setback"),
      { entity: ids.delta, name: ROWS.delta[1] },
      {
        type: "custom:solar-floor-boost-duration-row",
        entity: ids.duration,
        name: ROWS.duration[1],
      },
      endsRow(config, ids, "boost", "boost_end"),
      endsRow(config, ids, "setback", "setback_end"),
    ],
  };
}

class SolarFloorBoostCard extends HTMLElement {
  static getStubConfig() {
    return { title: "Floor heating" };
  }

  setConfig(config) {
    this._config = config || {};
    this._card = undefined;
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    this._checkVersion(hass);
    if (this._card) {
      this._card.hass = hass;
    } else if (!this._building) {
      // hass updates arrive constantly; only start a build if none is
      // running, otherwise a busy home would restart it forever.
      this._build();
    }
  }

  // The integration was updated while this page was open: its new card file
  // is only picked up by a reload. Reload silently if nobody is looking,
  // otherwise add a notice row.
  _checkVersion(hass) {
    if (this._stale) return;
    const version = runningVersion(hass, findEntities(hass));
    if (!version || version === CARD_VERSION) return;
    this._stale = version;
    let reloaded;
    try {
      reloaded = sessionStorage.getItem(RELOAD_KEY);
    } catch (e) {
      reloaded = undefined;
    }
    if (document.visibilityState === "hidden" && reloaded !== version) {
      // Once per version per tab, so a stale file served again can't loop.
      try {
        sessionStorage.setItem(RELOAD_KEY, version);
      } catch (e) {
        // Private mode: still reload once; the guard above just won't hold.
      }
      location.reload();
      return;
    }
    this._card = undefined;
    this._build();
  }

  async _build() {
    if (!this._config || !this._hass) return;
    const build = (this._buildId = (this._buildId || 0) + 1);
    this._building = true;
    try {
      const helpers = await window.loadCardHelpers();
      // A newer setConfig started another build meanwhile.
      if (build !== this._buildId) return;
      const card = helpers.createCardElement(
        entitiesCardConfig(this._config, findEntities(this._hass), this._stale)
      );
      card.hass = this._hass;
      this.replaceChildren(card);
      this._card = card;
    } finally {
      if (build === this._buildId) this._building = false;
    }
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }
}

const RELOAD_KEY = "solar_floor_boost_reloaded_for";

// Notice row shown when the integration is newer than this file.
class SolarFloorBoostReloadRow extends HTMLElement {
  setConfig(config) {
    this._config = config;
    const style = document.createElement("style");
    style.textContent = `
      .notice {
        display: flex; align-items: center; gap: 12px;
        padding: 8px 12px; margin: 0 -4px;
        border-radius: var(--ha-card-border-radius, 12px);
        background: var(--warning-color, #ffa600); color: #000;
        font-size: 0.9em; line-height: 1.3;
      }
      .notice ha-icon { --mdc-icon-size: 20px; flex: none; }
      .text { flex: 1; }
      button {
        flex: none; border: 0; border-radius: 4px; padding: 6px 12px;
        background: rgba(0, 0, 0, 0.15); color: inherit; font: inherit;
        font-weight: 500; text-transform: uppercase; cursor: pointer;
      }
      button:hover { background: rgba(0, 0, 0, 0.25); }
    `;
    const notice = document.createElement("div");
    notice.className = "notice";
    const icon = document.createElement("ha-icon");
    icon.setAttribute("icon", "mdi:update");
    const text = Object.assign(document.createElement("span"), {
      className: "text",
      textContent: `Solar Floor Boost was updated to ${config.version}. Reload the page to get the new card.`,
    });
    const button = Object.assign(document.createElement("button"), {
      type: "button",
      textContent: "Reload",
    });
    button.addEventListener("click", (ev) => {
      ev.stopPropagation();
      location.reload();
    });
    notice.append(icon, text, button);
    this.replaceChildren(style, notice);
  }

  set hass(hass) {}
}

// Toggle row with an (i) that explains when to use the mode. Hover shows the
// hint on desktop; a tap toggles it on touch screens. Usable in any entities
// card:
//   - type: custom:solar-floor-boost-switch-row
//     entity: switch.solar_floor_boost_boost
//     hint: Use when ...
class SolarFloorBoostSwitchRow extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this._config = config;
    this._row = undefined;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._row) this._render();
    this._row.hass = hass;
    this._toggle.hass = hass;
    this._toggle.stateObj = hass.states[this._config.entity];
  }

  _render() {
    const style = document.createElement("style");
    style.textContent = `
      .wrap { display: flex; align-items: center; gap: 4px; }
      .info {
        display: inline-flex; align-items: center; justify-content: center;
        width: 36px; height: 36px; border-radius: 50%; border: 0;
        background: none; cursor: pointer; padding: 0;
        color: var(--secondary-text-color);
      }
      .info:hover, .info:focus-visible { color: var(--primary-color); outline: none; }
      .info ha-icon { --mdc-icon-size: 20px; }
      .tip {
        position: fixed; z-index: 10; max-width: min(320px, calc(100vw - 32px));
        padding: 10px 12px; border-radius: var(--ha-card-border-radius, 12px);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        border: 1px solid var(--divider-color);
        font-size: 0.9em; line-height: 1.4; white-space: pre-line;
      }
      .tip[hidden] { display: none; }
    `;
    const row = document.createElement("hui-generic-entity-row");
    row.config = this._config;
    const wrap = document.createElement("div");
    wrap.className = "wrap";
    this._info = Object.assign(document.createElement("button"), {
      className: "info",
      type: "button",
      title: "",
    });
    this._info.setAttribute("aria-label", "What is this for?");
    const icon = document.createElement("ha-icon");
    icon.setAttribute("icon", "mdi:information-outline");
    this._info.append(icon);
    this._tip = Object.assign(document.createElement("div"), {
      className: "tip",
      hidden: true,
      textContent: this._config.hint ?? "",
    });
    this._tip.setAttribute("role", "tooltip");
    // HA's own toggle: same look and behaviour as a toggle entity row.
    this._toggle = document.createElement("ha-entity-toggle");

    const show = () => {
      if (!this._config.hint) return;
      const r = this._info.getBoundingClientRect();
      this._tip.hidden = false;
      // Below the icon, right-aligned to it, kept inside the viewport.
      const width = this._tip.offsetWidth;
      this._tip.style.top = `${r.bottom + 4}px`;
      this._tip.style.left = `${Math.max(16, Math.min(r.right - width, window.innerWidth - width - 16))}px`;
    };
    const hide = () => {
      this._tip.hidden = true;
    };
    this._info.addEventListener("mouseenter", show);
    this._info.addEventListener("mouseleave", hide);
    this._info.addEventListener("focus", show);
    this._info.addEventListener("blur", hide);
    this._info.addEventListener("click", (ev) => {
      ev.stopPropagation();
      this._tip.hidden ? show() : hide();
    });
    this._onDocClick = (ev) => {
      if (!ev.composedPath().includes(this._info)) hide();
    };
    [this._info, this._toggle].forEach((el) =>
      el.addEventListener("click", (ev) => ev.stopPropagation())
    );
    wrap.append(this._info, this._toggle);
    row.append(wrap);
    this.replaceChildren(style, row, this._tip);
    this._row = row;
  }

  connectedCallback() {
    if (this._onDocClick) document.addEventListener("click", this._onDocClick);
  }

  disconnectedCallback() {
    if (this._onDocClick) document.removeEventListener("click", this._onDocClick);
  }
}

// Minutes. Fine steps in the first hour, coarser after.
const DURATION_PRESETS = [15, 30, 45, 60, 90, 120, 150, 180, 210, 240, 300, 360, 480, 720];

// 15 -> "15m", 60 -> "1h", 90 -> "1h 30m"
function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = Math.round(minutes % 60);
  if (!hours) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

function nearestPreset(minutes) {
  let best = 0;
  DURATION_PRESETS.forEach((preset, i) => {
    if (Math.abs(preset - minutes) < Math.abs(DURATION_PRESETS[best] - minutes)) best = i;
  });
  return best;
}

// Slider row for the duration number entity: one evenly spaced step per
// preset and a "1h 30m" label. Usable in any entities card:
//   - type: custom:solar-floor-boost-duration-row
//     entity: number.solar_floor_boost_boost_duration
class SolarFloorBoostDurationRow extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this._config = config;
    this._row = undefined;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._row) this._render();
    this._row.hass = hass;
    if (this._dragging) return;
    const state = hass.states[this._config.entity];
    // The duration number is in hours since 1.6.0 (minutes before).
    this._minutesPerUnit = state?.attributes.unit_of_measurement === "h" ? 60 : 1;
    const minutes = Number(state?.state) * this._minutesPerUnit;
    const known = Number.isFinite(minutes);
    this._input.value = known ? nearestPreset(minutes) : 0;
    this._input.disabled = !known;
    this._label.textContent = known ? formatDuration(minutes) : state?.state ?? "";
  }

  _render() {
    const style = document.createElement("style");
    style.textContent = `
      .wrap { display: flex; align-items: center; gap: 8px; }
      input { width: 110px; accent-color: var(--primary-color); cursor: pointer; }
      .label { min-width: 3.6em; text-align: end; white-space: nowrap; }
    `;
    // HA's own row element gives the icon/name layout of the other rows.
    const row = document.createElement("hui-generic-entity-row");
    row.config = this._config;
    const wrap = document.createElement("div");
    wrap.className = "wrap";
    this._input = Object.assign(document.createElement("input"), {
      type: "range",
      min: 0,
      max: DURATION_PRESETS.length - 1,
      step: 1,
    });
    this._label = Object.assign(document.createElement("span"), {
      className: "label",
    });
    this._input.addEventListener("click", (ev) => ev.stopPropagation());
    this._input.addEventListener("input", () => {
      this._dragging = true;
      this._label.textContent = formatDuration(DURATION_PRESETS[this._input.value]);
    });
    this._input.addEventListener("change", () => {
      this._dragging = false;
      this._hass.callService("number", "set_value", {
        entity_id: this._config.entity,
        value: DURATION_PRESETS[this._input.value] / this._minutesPerUnit,
      });
    });
    wrap.append(this._input, this._label);
    row.append(wrap);
    this.replaceChildren(style, row);
    this._row = row;
  }
}

// The frontend's app bundle installs a scoped custom element registry
// polyfill that replaces window.customElements. This module is loaded in
// parallel and can run first; elements defined on the old registry are then
// invisible to Lovelace (endless spinner in the card picker). So wait until
// the app has defined <home-assistant> on the current registry.
async function whenAppReady(timeoutMs = 60000) {
  const start = Date.now();
  while (
    !window.customElements.get("home-assistant") &&
    Date.now() - start < timeoutMs
  ) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

function register() {
  const registry = window.customElements;
  if (!registry.get("solar-floor-boost-duration-row")) {
    registry.define("solar-floor-boost-duration-row", SolarFloorBoostDurationRow);
  }
  if (!registry.get("solar-floor-boost-switch-row")) {
    registry.define("solar-floor-boost-switch-row", SolarFloorBoostSwitchRow);
  }
  if (!registry.get("solar-floor-boost-reload-row")) {
    registry.define("solar-floor-boost-reload-row", SolarFloorBoostReloadRow);
  }
  if (registry.get("solar-floor-boost-card")) return;
  registry.define("solar-floor-boost-card", SolarFloorBoostCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "solar-floor-boost-card",
    name: "Solar Floor Boost",
    description: "Boost or set back the floor heating: amount, duration, and when it ends.",
    preview: true,
    // HA 2026.6+: offer this card in "By entity" for any of our entities.
    getEntitySuggestion: (hass, entityId) =>
      hass.entities?.[entityId]?.platform === DOMAIN
        ? [
            {
              label: "Solar Floor Boost",
              config: { type: "custom:solar-floor-boost-card" },
            },
          ]
        : null,
    documentationURL: "https://github.com/alarmatwork/ha-solar-floor-boost",
  });
}

whenAppReady().then(register);
