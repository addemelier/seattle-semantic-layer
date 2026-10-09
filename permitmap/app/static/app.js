// Seattle permit map. Plain JS, no build step (design A2).
(function () {
  "use strict";

  var SEATTLE = [-122.3321, 47.6062];
  var MIN_ZOOM_FOR_PERMITS = 12;           // A6
  var COLORS = { in_review: "#D97706", issued: "#2563EB" };  // A8
  var MOVE_DEBOUNCE_MS = 250;
  var EMPTY = { type: "FeatureCollection", features: [] };

  var statusEl = document.getElementById("status");
  var messages = {};   // keyed status messages; shown joined

  function setMessage(key, text) {
    if (text) messages[key] = text; else delete messages[key];
    var parts = Object.keys(messages).map(function (k) { return messages[k]; });
    statusEl.textContent = parts.join(" · ");
    statusEl.hidden = parts.length === 0;
  }

  // Test/debug hook: "loading" while pins are being fetched and drawn, "ready" after.
  function setPinsState(s) { document.body.dataset.permits = s; }
  setPinsState("loading");

  // ---- Detail panel -------------------------------------------------------
  var WORK_TYPE_LABELS = {
    new_building: "New building", addition_alteration: "Addition / alteration",
    demolition: "Demolition", adu: "ADU"
  };
  var STAGE_LABELS = { in_review: "In review", issued: "Issued" };
  var usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  var panel = document.getElementById("permit-panel");

  function present(v) { return v !== null && v !== undefined && v !== ""; }

  function panelText(field, p) {
    var v = p[field];
    switch (field) {
      case "valuation_usd": return present(v) ? usd.format(Number(v)) : "Not stated";
      case "contractor": return present(v) ? v : "Not listed";
      case "work_type": return WORK_TYPE_LABELS[v] || v || "";
      case "stage": return STAGE_LABELS[v] || v || "";
      default: return present(v) ? String(v) : "\u2014";
    }
  }

  function openPanel(p) {
    panel.querySelectorAll("[data-field]").forEach(function (el) {
      var field = el.getAttribute("data-field");
      el.textContent = (field === "description" && !present(p.description)) ? "" : panelText(field, p);
    });
    panel.setAttribute("aria-label", p.address || "Permit details");
    var link = panel.querySelector(".panel-link");
    if (present(p.permit_url)) { link.href = p.permit_url; link.hidden = false; }
    else { link.removeAttribute("href"); link.hidden = true; }
    panel.dataset.permitId = p.permit_id;
    panel.hidden = false;
  }

  function closePanel() { panel.hidden = true; delete panel.dataset.permitId; }
  panel.querySelector(".panel-close").addEventListener("click", closePanel);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closePanel(); });

  var app = window.permitApp = {
    // Extra query params for /api/permits (filters set these).
    permitParams: function () { return {}; },
    refresh: null,
    setMessage: setMessage
  };

  // ---- Filters ------------------------------------------------------------
  // All boxes in a group checked -> no filter. None checked -> empty param (no pins).
  var filtersForm = document.getElementById("filters");
  app.permitParams = function () {
    var params = {};
    filtersForm.querySelectorAll("fieldset[data-param]").forEach(function (fs) {
      var boxes = Array.prototype.slice.call(fs.querySelectorAll("input[type=checkbox]"));
      var checked = boxes.filter(function (b) { return b.checked; }).map(function (b) { return b.value; });
      if (checked.length < boxes.length) params[fs.getAttribute("data-param")] = checked.join(",");
    });
    return params;
  };
  filtersForm.addEventListener("change", function () { if (app.refresh) app.refresh(); });
  filtersForm.addEventListener("submit", function (e) { e.preventDefault(); });

  fetch("/api/config").then(function (r) { return r.json(); }).then(function (cfg) {
    var map = new maplibregl.Map({
      container: "map",
      style: cfg.style_url,
      center: SEATTLE,
      zoom: 12,
      hash: true                            // A5
    });
    window.permitMap = map;                 // A7
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

    var controller = null;
    var timer = null;

    function refresh() {
      if (controller) { controller.abort(); controller = null; }
      var src = map.getSource("permits");
      if (!src) return;

      if (map.getZoom() < MIN_ZOOM_FOR_PERMITS) {
        src.setData(EMPTY);
        setMessage("truncated", null);
        setMessage("zoom", "Zoom in to see permits");
        map.once("idle", function () { setPinsState("ready"); });
        map.triggerRepaint();
        return;
      }
      setMessage("zoom", null);

      var b = map.getBounds();
      var params = new URLSearchParams({
        bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
          .map(function (v) { return v.toFixed(6); }).join(",")
      });
      var extra = app.permitParams();
      Object.keys(extra).forEach(function (k) { params.set(k, extra[k]); });

      var ctl = controller = new AbortController();
      setPinsState("loading");
      fetch("/api/permits?" + params.toString(), { signal: ctl.signal })
        .then(function (r) {
          if (!r.ok) throw new Error("permits request failed: " + r.status);
          return r.json();
        })
        .then(function (body) {
          if (ctl !== controller) return;
          controller = null;
          app.lastPermits = body;
          src.setData(body);
          setMessage("truncated", body.truncated
            ? "Showing only the most recent 2,000 permits here. Zoom in to see all." : null);
          map.once("idle", function () { if (!controller) setPinsState("ready"); });
          map.triggerRepaint();
        })
        .catch(function (err) {
          if (err.name === "AbortError") return;
          if (ctl === controller) controller = null;
          setMessage("error", "Couldn't load permits right now");
          setTimeout(function () { setMessage("error", null); }, 4000);
          setPinsState("ready");
        });
    }

    function scheduleRefresh() {
      setPinsState("loading");
      clearTimeout(timer);
      timer = setTimeout(refresh, MOVE_DEBOUNCE_MS);
    }
    app.refresh = refresh;
    app.scheduleRefresh = scheduleRefresh;

    map.on("load", function () {
      map.addSource("permits", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "permits",
        type: "circle",
        source: "permits",
        paint: {
          "circle-radius": 6,
          "circle-color": ["match", ["get", "stage"], "issued", COLORS.issued, COLORS.in_review],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff"
        }
      });
      map.on("moveend", scheduleRefresh);
      map.on("click", "permits", function (e) {
        if (!e.features || !e.features.length) return;
        var id = e.features[0].properties.permit_id;
        // Use the API's feature (keeps nulls exactly) rather than the tiled copy.
        var full = (app.lastPermits ? app.lastPermits.features : []).filter(function (f) {
          return f.properties.permit_id === id;
        })[0];
        openPanel(full ? full.properties : e.features[0].properties);
      });
      map.on("mouseenter", "permits", function () { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "permits", function () { map.getCanvas().style.cursor = ""; });
      if (app.onLoad) app.onLoad(map);
      refresh();
    });
  });
})();
