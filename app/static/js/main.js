document.addEventListener("DOMContentLoaded", function () {
  // Sidebar toggle (mobile)
  var toggle = document.getElementById("sidebarToggle");
  var sidebar = document.querySelector(".wiq-sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
  }

  // Confirm destructive actions
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("submit", function (e) {
      if (!window.confirm(el.getAttribute("data-confirm"))) {
        e.preventDefault();
      }
    });
  });

  // Auto-dismiss flash messages
  setTimeout(function () {
    document.querySelectorAll(".alert-dismissible").forEach(function (a) {
      if (window.bootstrap) {
        var inst = bootstrap.Alert.getOrCreateInstance(a);
        if (inst) inst.close();
      }
    });
  }, 6000);
});
