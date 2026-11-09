// Anonymous engagement events (engagement-events: "The map page sends engagement events").
// window.permitEvents = { send(type, fields), sessionId(), enabled }
// Fire-and-forget: nothing waits on a send and every error is swallowed (A2).
(function () {
  "use strict";

  var KEY = "permitmap.session";
  var IDLE_MS = 30 * 24 * 60 * 60 * 1000;  // new ID after 30 days unused (D2)

  var nav = window.navigator || {};
  var enabled = !(nav.globalPrivacyControl === true ||
                  nav.doNotTrack === "1" || window.doNotTrack === "1");  // A1

  function newId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID().replace(/-/g, "");
    }
    var bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return Array.prototype.map.call(bytes, function (b) {
      return (b < 16 ? "0" : "") + b.toString(16);
    }).join("");
  }

  var memoryId = null;  // used when storage is unavailable; lasts for the page load

  function readStored() {
    try {
      var s = JSON.parse(window.localStorage.getItem(KEY));
      if (s && typeof s.id === "string" && /^[0-9a-f]{32}$/.test(s.id) &&
          typeof s.last === "number" && Date.now() - s.last <= IDLE_MS) {
        return s.id;
      }
    } catch (e) { /* missing, unparsable or storage blocked */ }
    return null;
  }

  function writeStored(id) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify({ id: id, last: Date.now() }));
      return true;
    } catch (e) {
      return false;
    }
  }

  function sessionId() {
    var id = readStored();
    if (id) return id;
    if (memoryId) {
      writeStored(memoryId);
      return memoryId;
    }
    memoryId = newId();
    writeStored(memoryId);
    return memoryId;
  }

  function send(type, fields) {
    if (!enabled) return;
    try {
      var id = sessionId();
      writeStored(id);  // update `last` on each send
      var body = { event_type: type, session_id: id };
      var ref = (document.referrer || "").slice(0, 500);
      if (ref) body.referrer = ref;
      fields = fields || {};
      Object.keys(fields).forEach(function (k) {
        if (fields[k] !== undefined && fields[k] !== null) body[k] = fields[k];
      });
      fetch("/api/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        keepalive: true
      }).catch(function () {});
    } catch (e) { /* never let analytics break the page */ }
  }

  window.permitEvents = { send: send, sessionId: sessionId, enabled: enabled };
})();
