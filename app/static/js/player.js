// YouTube IFrame API watch-progress tracker.
var wiqPlayer;
var wiqLastSent = 0;

function onYouTubeIframeAPIReady() {
  var holder = document.getElementById("wiq-player");
  if (!holder) return;
  wiqPlayer = new YT.Player("wiq-player", {
    videoId: holder.dataset.videoId,
    playerVars: { rel: 0, modestbranding: 1 },
    events: {
      onStateChange: function (e) {
        if (e.data === YT.PlayerState.PLAYING) {
          startTracking(holder.dataset.moduleId);
        }
      },
    },
  });
}

function startTracking(moduleId) {
  if (window._wiqTracking) return;
  window._wiqTracking = setInterval(function () {
    if (!wiqPlayer || !wiqPlayer.getDuration) return;
    var dur = wiqPlayer.getDuration();
    var cur = wiqPlayer.getCurrentTime();
    if (!dur) return;
    var pct = Math.min(100, (cur / dur) * 100);
    if (pct - wiqLastSent >= 5 || pct >= 90) {
      wiqLastSent = pct;
      sendProgress(moduleId, pct, Math.floor(cur));
    }
  }, 5000);
}

function sendProgress(moduleId, pct, watched) {
  fetch("/api/learning/" + moduleId + "/progress", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ percentage: pct, watched_seconds: watched }),
  })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var bar = document.getElementById("wiq-progress-bar");
      if (bar) {
        bar.style.width = d.watch_percentage + "%";
        bar.textContent = Math.round(d.watch_percentage) + "%";
      }
      if (d.completed) {
        var badge = document.getElementById("wiq-complete-badge");
        if (badge) badge.classList.remove("d-none");
      }
    });
}
