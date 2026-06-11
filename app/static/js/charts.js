// Chart.js helpers for WorkforceIQ dashboards.
function wiqColors(n) {
  var base = ["#2d72d9", "#0d9488", "#d97706", "#6d28d9", "#dc2626", "#0891b2", "#65a30d"];
  var out = [];
  for (var i = 0; i < n; i++) out.push(base[i % base.length]);
  return out;
}

function renderScoreRadar(canvasId, endpoint) {
  fetch(endpoint)
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var ctx = document.getElementById(canvasId);
      if (!ctx) return;
      new Chart(ctx, {
        type: "radar",
        data: {
          labels: d.labels,
          datasets: [{
            label: "Growth components",
            data: d.values,
            backgroundColor: "rgba(45,114,217,0.18)",
            borderColor: "#2d72d9",
            pointBackgroundColor: "#1f3a5f",
          }],
        },
        options: {
          responsive: true,
          scales: { r: { min: 0, max: 100, ticks: { stepSize: 20 } } },
          plugins: { legend: { display: false } },
        },
      });
    });
}

function renderLine(canvasId, endpoint, label) {
  fetch(endpoint)
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var ctx = document.getElementById(canvasId);
      if (!ctx) return;
      new Chart(ctx, {
        type: "line",
        data: {
          labels: d.labels,
          datasets: [{
            label: label || "Score %",
            data: d.values,
            borderColor: "#0d9488",
            backgroundColor: "rgba(13,148,136,0.12)",
            fill: true,
            tension: 0.3,
          }],
        },
        options: { responsive: true, scales: { y: { min: 0, max: 100 } } },
      });
    });
}

function renderBar(canvasId, labels, values, label) {
  var ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{ label: label, data: values, backgroundColor: wiqColors(values.length) }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

function renderDoughnut(canvasId, labels, values) {
  var ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: "doughnut",
    data: { labels: labels, datasets: [{ data: values, backgroundColor: wiqColors(values.length) }] },
    options: { responsive: true },
  });
}
