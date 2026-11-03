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
 * Rest countdown timers. Any element with [data-rest-timer] gets a
 * "Start rest" button that counts down and flashes when it hits zero.
 * The duration comes from a [data-rest-seconds-input] number field,
 * pre-filled with the goal-calculated recommended rest (shown alongside
 * as a label, never hidden) but editable before starting - some people
 * genuinely need more or less than the recommendation, and the timer
 * should work with whatever they actually rested, not silently ignore
 * it. Purely client-side; nothing is sent to the server.
 */
(function () {
  const MIN_SECONDS = 5;
  const MAX_SECONDS = 600;

  document.querySelectorAll("[data-rest-timer]").forEach(function (root) {
    const recommendedSeconds = parseInt(root.dataset.recommendedSeconds, 10) || 60;
    const button = root.querySelector("[data-rest-start]");
    const display = root.querySelector("[data-rest-display]");
    const input = root.querySelector("[data-rest-seconds-input]");
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

    function currentDuration() {
      const raw = input ? parseInt(input.value, 10) : recommendedSeconds;
      if (!Number.isFinite(raw)) return recommendedSeconds;
      return Math.min(MAX_SECONDS, Math.max(MIN_SECONDS, raw));
    }

    if (!button || !display) return;

    render(recommendedSeconds);

    button.addEventListener("click", function () {
      stop();
      root.classList.remove("rest-timer--done");
      let secondsLeft = currentDuration();
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
