(function () {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("primary-nav");

  if (!toggle || !nav) return;

  toggle.addEventListener("click", function () {
    const isOpen = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });
})();

/**
 * Rest countdown timers. Any element with [data-rest-timer] and a
 * data-seconds attribute gets a "Start rest" button that counts down and
 * flashes when it hits zero. Purely client-side; nothing is sent to the
 * server, so it works offline and needs no page reload.
 */
(function () {
  document.querySelectorAll("[data-rest-timer]").forEach(function (root) {
    const totalSeconds = parseInt(root.dataset.seconds, 10) || 60;
    const button = root.querySelector("[data-rest-start]");
    const display = root.querySelector("[data-rest-display]");
    let intervalId = null;

    function render(secondsLeft) {
      const m = Math.floor(secondsLeft / 60);
      const s = secondsLeft % 60;
      display.textContent = `${m}:${String(s).padStart(2, "0")}`;
    }

    function stop() {
      if (intervalId) clearInterval(intervalId);
      intervalId = null;
    }

    if (!button || !display) return;

    render(totalSeconds);

    button.addEventListener("click", function () {
      stop();
      root.classList.remove("rest-timer--done");
      let secondsLeft = totalSeconds;
      render(secondsLeft);
      button.textContent = "Restart";

      intervalId = setInterval(function () {
        secondsLeft -= 1;
        if (secondsLeft <= 0) {
          render(0);
          stop();
          root.classList.add("rest-timer--done");
          return;
        }
        render(secondsLeft);
      }, 1000);
    });
  });
})();
