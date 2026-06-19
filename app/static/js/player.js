// YouTube IFrame API — handles both module-level and resource-level progress.
// Globals set by the template:
//   wiqMode      = "module" | "resource"
//   wiqModuleId  = integer
//   wiqResourceId = integer | null
var wiqPlayer;
var wiqLastSent = 0;

function onYouTubeIframeAPIReady() {
  var holder = document.getElementById("wiq-player");
  if (!holder) return;
  wiqPlayer = new YT.Player("wiq-player", {
    videoId: holder.dataset.videoId,
    width: "100%",
    playerVars: { rel: 0, modestbranding: 1 },
    events: {
      onReady: function() {
        // Restore progress bar label on load
        var pctLabel = document.getElementById("wiq-pct-label");
        if (pctLabel) {
          var initialPct = parseFloat(pctLabel.textContent) || 0;
          _updateRing(initialPct);
        }
      },
      onStateChange: function(e) {
        if (e.data === YT.PlayerState.PLAYING) {
          startTracking();
        }
      },
    },
  });
}

function startTracking() {
  if (window._wiqTracking) return;
  window._wiqTracking = setInterval(function() {
    if (!wiqPlayer || !wiqPlayer.getDuration) return;
    var dur = wiqPlayer.getDuration();
    var cur = wiqPlayer.getCurrentTime();
    if (!dur) return;
    var pct = Math.min(100, (cur / dur) * 100);
    if (pct - wiqLastSent >= 5 || pct >= 90) {
      wiqLastSent = pct;
      sendProgress(pct, Math.floor(cur));
    }
  }, 5000);
}

function sendProgress(pct, watched) {
  var url, body;
  if (typeof wiqMode !== "undefined" && wiqMode === "resource" && wiqResourceId) {
    url = "/api/resources/" + wiqResourceId + "/progress";
    body = JSON.stringify({ percentage: pct });
  } else {
    url = "/api/learning/" + wiqModuleId + "/progress";
    body = JSON.stringify({ percentage: pct, watched_seconds: watched });
  }

  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body,
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      // Update progress bar (legacy module viewer)
      var bar = document.getElementById("wiq-progress-bar");
      if (bar) {
        var displayPct = d.watch_percentage !== undefined ? d.watch_percentage : (d.progress_percentage || pct);
        bar.style.width = displayPct + "%";
        bar.textContent = Math.round(displayPct) + "%";
      }

      // Update ring (new viewer)
      var ringPct = d.watch_percentage !== undefined ? d.watch_percentage : (d.progress_percentage || pct);
      _updateRing(ringPct);
      var pctLabel = document.getElementById("wiq-pct-label");
      if (pctLabel) pctLabel.textContent = Math.round(ringPct) + "%";

      // Mark complete
      var completed = d.completed || (d.watch_percentage !== undefined && d.watch_percentage >= 90);
      if (completed) {
        var badge = document.getElementById("wiq-complete-badge");
        if (badge) badge.classList.remove("d-none");

        // Mark resource item in sidebar as done
        if (wiqResourceId) {
          var navItem = document.querySelector('[href*="resource=' + wiqResourceId + '"] .lms-resource-icon');
          if (navItem) navItem.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i>';
        }
      }
    })
    .catch(function() {}); // silently ignore network errors
}

function _updateRing(pct) {
  var fill = document.querySelector(".lms-ring-fill");
  if (!fill) return;
  var circumference = 2 * Math.PI * 34; // r=34 => ~213.6
  var dash = Math.min(pct / 100 * circumference, circumference);
  fill.style.strokeDasharray = dash.toFixed(1) + " " + circumference.toFixed(1);
}
