// Solar Floor Boost dashboard card: an entities card preconfigured with the
// integration's entities. Shows up under "By card" in the card picker.

const DOMAIN = "solar_floor_boost";
// Must match manifest.json (a test checks). The device's sw_version is the
// version that is running; when it is newer, this file is stale in the
// browser and the card asks for a reload.
const CARD_VERSION = "1.9.2";

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

// "Started manually" / "Started by automation X", from the switch's attributes.
function startedBy(attributes) {
  if (attributes.started_by === "manual") return "Started manually";
  if (attributes.started_by === "automation") {
    return attributes.automation
      ? `Started by ${attributes.automation}`
      : "Started by an automation";
  }
  return undefined;
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
    const stateObj = hass.states[this._config.entity];
    this._row.hass = hass;
    // Who started it, under the name while the mode runs (for debugging
    // automations; see the "automation" field of the start actions).
    this._row.secondaryText =
      stateObj?.state === "on" ? startedBy(stateObj.attributes) : undefined;
    this._toggle.hass = hass;
    this._toggle.stateObj = stateObj;
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
    // Hover for a real mouse only: a tap on a phone fires mouseenter and then
    // click, which would show and hide it at once. A tap or click toggles.
    this._info.addEventListener("pointerenter", (ev) => ev.pointerType === "mouse" && show());
    this._info.addEventListener("pointerleave", (ev) => ev.pointerType === "mouse" && hide());
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

// --- History card -----------------------------------------------------------
// One line for the day: red blocks while a boost ran, blue while a setback
// did, a "now" marker, and a tooltip per block with who started it, the
// amount and the times. Data comes from the recorder's history of the two
// switches, whose attributes say who started each session.
//   type: custom:solar-floor-boost-history-card
//   title: Floor heating today   # optional
//   days: 1                      # optional: 1 = today, 2 = since yesterday, ...

const HISTORY_COLORS = {
  boost: "var(--solar-floor-boost-boost-color, var(--error-color, #db4437))",
  setback: "var(--solar-floor-boost-setback-color, var(--info-color, #4285f4))",
};
const HOUR = 3600000;

// Local midnight ``daysAgo`` days before today.
function midnight(daysAgo) {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - daysAgo);
  return d;
}

function timeFormatter(hass, withDate) {
  const tf = hass.locale?.time_format;
  const hour12 = tf === "12" ? true : tf === "24" ? false : undefined;
  return new Intl.DateTimeFormat(hass.locale?.language || undefined, {
    hour: "numeric",
    minute: "2-digit",
    hour12,
    ...(withDate ? { weekday: "short" } : {}),
  });
}

// "Started by Solar surplus", "Started manually", "Started by an automation"
// (startedBy above), with the command for the automation cases.
function startedByLine(attributes) {
  const who = startedBy(attributes);
  if (!who) return "";
  return attributes.started_by === "manual" || !attributes.command
    ? who
    : `${who} (${attributes.command})`;
}

class SolarFloorBoostHistoryCard extends HTMLElement {
  static getStubConfig() {
    return { title: "Floor heating today" };
  }

  setConfig(config) {
    this._config = config || {};
    this._days = Math.max(1, Math.min(14, Number(this._config.days) || 1));
    this._periods = undefined;
    this._fetched = 0;
    this._render();
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (!this._card) this._render();
    const ids = (this._ids = this._ids || findEntities(hass));
    // Refetch when a switch changed state, after a minute, or on a new day;
    // otherwise only move the "now" marker.
    const changed = ["boost", "setback"].some(
      (m) => hass.states[ids[m]]?.last_changed !== previous?.states[ids[m]]?.last_changed
    );
    const stale = Date.now() - this._fetched > 60000;
    if (changed || stale) this._fetch();
    // hass updates arrive constantly; redrawing on each would replace the
    // bar under a finger. The "now" marker only needs to move now and then.
    else if (Date.now() - (this._drawn || 0) > 30000) this._draw();
  }

  connectedCallback() {
    this._timer = setInterval(() => this._hass && this._fetch(), 60000);
    this._resize = new ResizeObserver(() => this._draw());
    this._resize.observe(this);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._resize?.disconnect();
    document.removeEventListener("click", this._onDocClick);
  }

  _render() {
    const style = document.createElement("style");
    style.textContent = `
      .content { padding: 0 16px 12px; }
      svg {
        display: block; width: 100%; overflow: visible;
        user-select: none; -webkit-user-select: none; -webkit-touch-callout: none;
      }
      .axis { stroke: var(--secondary-text-color); stroke-width: 2; }
      .tick { stroke: var(--secondary-text-color); stroke-width: 2; }
      .label { fill: var(--primary-text-color); font-size: 14px; }
      .now-line { stroke: var(--primary-color); stroke-width: 2; stroke-dasharray: 4 3; }
      .now-tag { fill: var(--primary-color); }
      .now-text { fill: var(--text-primary-color, #fff); font-size: 12px; }
      .block { stroke-width: 2; cursor: pointer; touch-action: manipulation; }
      .block:hover { filter: brightness(1.25); }
      .empty { color: var(--secondary-text-color); font-size: 14px; padding: 8px 0 12px; }
      .legend {
        display: flex; justify-content: center; gap: 24px; margin-top: 8px;
        font-size: 14px; color: var(--primary-text-color);
      }
      .legend span { display: inline-flex; align-items: center; gap: 6px; }
      .dot { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.6); }
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
    const card = document.createElement("ha-card");
    card.header = this._config.title ?? "Floor heating today";
    this._content = Object.assign(document.createElement("div"), { className: "content" });
    this._svgHost = document.createElement("div");
    this._legend = Object.assign(document.createElement("div"), { className: "legend" });
    for (const [mode, name] of [["boost", "Boost"], ["setback", "Setback"]]) {
      const item = document.createElement("span");
      const dot = Object.assign(document.createElement("i"), { className: "dot" });
      dot.style.background = HISTORY_COLORS[mode];
      item.append(dot, name);
      this._legend.append(item);
    }
    this._tip = Object.assign(document.createElement("div"), { className: "tip", hidden: true });
    this._tip.setAttribute("role", "tooltip");
    this._onDocClick = (ev) => {
      if (!ev.composedPath().some((el) => el.classList?.contains("block"))) this._hideTip();
    };
    document.addEventListener("click", this._onDocClick);
    this._content.append(this._svgHost, this._legend);
    card.append(style, this._content, this._tip);
    this.replaceChildren(card);
    this._card = card;
  }

  async _fetch() {
    const hass = this._hass;
    const ids = this._ids;
    this._fetched = Date.now();
    const start = midnight(this._days - 1);
    const end = new Date(start.getTime() + this._days * 24 * HOUR);
    let result;
    try {
      result = await hass.callWS({
        type: "history/history_during_period",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: [ids.boost, ids.setback],
        include_start_time_state: true,
        significant_changes_only: false,
        minimal_response: false,
        no_attributes: false,
      });
    } catch (e) {
      // Recorder disabled or an old frontend: show the live state at least.
      result = {};
    }
    const periods = [];
    for (const mode of ["boost", "setback"]) {
      const entries = result[ids[mode]] || [];
      entries.forEach((entry, i) => {
        if (entry.s !== "on") return;
        const from = (entry.lc ?? entry.lu) * 1000;
        const next = entries[i + 1];
        const to = next ? (next.lc ?? next.lu) * 1000 : undefined; // undefined: still on
        periods.push({ mode, from, to, attributes: entry.a || {} });
      });
      // Nothing recorded (recorder off) but the switch is on right now.
      const state = hass.states[ids[mode]];
      if (!entries.length && state?.state === "on") {
        periods.push({
          mode,
          from: new Date(state.last_changed).getTime(),
          to: undefined,
          attributes: state.attributes,
        });
      }
    }
    this._periods = periods;
    this._draw();
  }

  _draw() {
    if (!this._hass || !this._svgHost) return;
    this._drawn = Date.now();
    const width = this._content.clientWidth || 300;
    const start = midnight(this._days - 1).getTime();
    const span = this._days * 24 * HOUR;
    const now = Date.now();
    const left = 8;
    const right = 8;
    const plotW = Math.max(50, width - left - right);
    const top = 30;
    const axisY = 100;
    const height = 140;
    const x = (t) => left + ((Math.min(Math.max(t, start), start + span) - start) / span) * plotW;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("height", height);
    const el = (tag, attrs, text) => {
      const node = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      if (text !== undefined) node.textContent = text;
      svg.append(node);
      return node;
    };

    // Axis with a tick every 4 hours (every 12 for several days).
    el("line", { class: "axis", x1: left, x2: left + plotW, y1: axisY, y2: axisY });
    const tickEvery = (this._days > 2 ? 12 : this._days > 1 ? 6 : 4) * HOUR;
    const fmt = timeFormatter(this._hass, this._days > 1);
    for (let t = start + tickEvery; t < start + span; t += tickEvery) {
      el("line", { class: "tick", x1: x(t), x2: x(t), y1: axisY, y2: axisY + 8 });
      el("text", { class: "label", x: x(t), y: axisY + 28, "text-anchor": "middle" }, fmt.format(new Date(t)));
    }

    // Blocks.
    const timeFmt = timeFormatter(this._hass, this._days > 1);
    for (const period of this._periods || []) {
      const from = Math.max(period.from, start);
      const to = Math.min(period.to ?? now, start + span);
      if (to <= from) continue;
      const rect = el("rect", {
        class: "block",
        x: x(from),
        y: top,
        width: Math.max(2, x(to) - x(from)),
        height: axisY - top,
        fill: HISTORY_COLORS[period.mode],
        "fill-opacity": 0.6,
        stroke: HISTORY_COLORS[period.mode],
        tabindex: 0,
      });
      const key = `${period.mode}:${period.from}`;
      rect.setAttribute("data-key", key);
      const text = this._describe(period, timeFmt);
      const show = () => this._showTip(rect, text, key);
      const shown = () => !this._tip.hidden && this._tipFor === rect;
      const toggle = () => (shown() ? this._hideTip() : show());
      // Mouse: hover shows, click toggles.
      rect.addEventListener("pointerenter", (ev) => ev.pointerType === "mouse" && show());
      rect.addEventListener("pointerleave", (ev) => ev.pointerType === "mouse" && this._hideTip());
      // Finger: shown while it rests on the bar. A short tap leaves it shown
      // and a second tap hides it; lifting after a long press, or scrolling
      // away, hides it. The click that follows a touch is ignored.
      rect.addEventListener("pointerdown", (ev) => {
        if (ev.pointerType === "mouse") return;
        this._press = { rect, at: Date.now(), wasShown: shown() };
        show();
      });
      const release = (ev) => {
        if (ev.pointerType === "mouse" || this._press?.rect !== rect) return;
        const { at, wasShown } = this._press;
        this._press = undefined;
        this._touched = Date.now();
        if (ev.type === "pointercancel" || wasShown || Date.now() - at > 400) this._hideTip();
      };
      rect.addEventListener("pointerup", release);
      rect.addEventListener("pointercancel", release);
      rect.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (Date.now() - (this._touched || 0) < 700) return;
        toggle();
      });
      rect.addEventListener("contextmenu", (ev) => ev.preventDefault());
      rect.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          toggle();
        }
      });
      // Losing focus hides it, except when the bar was just redrawn.
      rect.addEventListener("blur", () => rect.isConnected && shown() && this._hideTip());
    }

    // "now" marker, only inside the shown span.
    if (now >= start && now <= start + span) {
      const nx = x(now);
      el("line", { class: "now-line", x1: nx, x2: nx, y1: top - 10, y2: axisY });
      const tagW = 34;
      const tagX = Math.min(nx - tagW / 2, left + plotW - tagW);
      el("rect", { class: "now-tag", x: Math.max(left, tagX), y: 2, width: tagW, height: 18, rx: 4 });
      el("text", { class: "now-text", x: Math.max(left, tagX) + tagW / 2, y: 15, "text-anchor": "middle" }, "now");
    }

    this._svgHost.replaceChildren(svg);
    // Keep an open tooltip on its bar across the redraw.
    if (!this._tip.hidden && this._tipKey) {
      const bar = svg.querySelector(`[data-key="${this._tipKey}"]`);
      if (bar) {
        this._tipFor = bar;
        this._positionTip(bar);
      } else {
        this._hideTip();
      }
    }
    const empty = this._periods && !this._periods.length;
    this._legend.hidden = false;
    if (empty && !this._empty) {
      this._empty = Object.assign(document.createElement("div"), {
        className: "empty",
        textContent: this._days > 1 ? "No boost or setback in this period." : "No boost or setback yet today.",
      });
      this._content.prepend(this._empty);
    } else if (!empty && this._empty) {
      this._empty.remove();
      this._empty = undefined;
    }
  }

  // Tooltip text: mode and amount, times, who started it, parameters given.
  _describe(period, fmt) {
    const a = period.attributes || {};
    const unit = this._hass.config?.unit_system?.temperature || "";
    const sign = period.mode === "setback" ? "−" : "+";
    const amount = a.delta != null ? ` ${sign}${a.delta} ${unit}`.trimEnd() : "";
    const name = period.mode === "setback" ? "Setback" : "Boost";
    const when = `${fmt.format(new Date(period.from))} – ${period.to ? fmt.format(new Date(period.to)) : "now"}`;
    const lines = [`${name}${amount}`, when];
    const who = startedByLine(a);
    if (who) lines.push(who);
    const params = a.parameters && Object.keys(a.parameters).length
      ? Object.entries(a.parameters)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
          .join(", ")
      : undefined;
    if (params) lines.push(params);
    return lines.join("\n");
  }

  _showTip(anchor, text, key) {
    this._tipFor = anchor;
    this._tipKey = key;
    this._tip.textContent = text;
    this._tip.hidden = false;
    this._positionTip(anchor);
  }

  _positionTip(anchor) {
    const r = anchor.getBoundingClientRect();
    const width = this._tip.offsetWidth;
    const height = this._tip.offsetHeight;
    const above = r.top - height - 6;
    this._tip.style.top = `${above > 8 ? above : r.bottom + 6}px`;
    const center = r.left + r.width / 2 - width / 2;
    this._tip.style.left = `${Math.max(16, Math.min(center, window.innerWidth - width - 16))}px`;
  }

  _hideTip() {
    this._tip.hidden = true;
    this._tipFor = undefined;
    this._tipKey = undefined;
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 3 };
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
  registry.define("solar-floor-boost-history-card", SolarFloorBoostHistoryCard);
  window.customCards = window.customCards || [];
  // HA 2026.6+: offer the cards in "By entity" for any of our entities.
  const suggest = (label, type) => (hass, entityId) =>
    hass.entities?.[entityId]?.platform === DOMAIN
      ? [{ label, config: { type: `custom:${type}` } }]
      : null;
  window.customCards.push(
    {
      type: "solar-floor-boost-card",
      name: "Solar Floor Boost",
      description: "Boost or set back the floor heating: amount, duration, and when it ends.",
      preview: true,
      getEntitySuggestion: suggest("Solar Floor Boost", "solar-floor-boost-card"),
      documentationURL: "https://github.com/alarmatwork/ha-solar-floor-boost",
    },
    {
      type: "solar-floor-boost-history-card",
      name: "Solar Floor Boost History",
      description: "Today's boosts (red) and setbacks (blue) on a timeline; each block shows who started it, the amount and the times.",
      preview: true,
      getEntitySuggestion: suggest("Solar Floor Boost History", "solar-floor-boost-history-card"),
      documentationURL: "https://github.com/alarmatwork/ha-solar-floor-boost#history-card",
    }
  );
}

whenAppReady().then(register);
