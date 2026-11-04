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

/**
 * Active workout mode: shows one exercise card at a time instead of the
 * whole session as a long scroll, with Previous/Next and a progress bar.
 * Without JS the page still works (every card just stays visible), so
 * this only enables itself once it can actually drive the navigation.
 * Position is kept in sessionStorage (keyed by session id) because
 * logging a set submits a normal form and reloads the page - without
 * that, every log would bounce the user back to exercise one.
 */
(function () {
  const root = document.querySelector("[data-workout-progress]");
  if (!root) return;

  const steps = Array.from(document.querySelectorAll(".workout-exercise[data-workout-step]"));
  if (!steps.length) return;

  const container = root.parentElement;
  const fill = root.querySelector("[data-workout-progress-fill]");
  const label = root.querySelector("[data-workout-progress-label]");
  const nextPreview = root.querySelector("[data-workout-next-preview]");
  const prevButton = root.querySelector("[data-workout-prev]");
  const nextButton = root.querySelector("[data-workout-next]");
  const storageKey = "peakform-workout-step-" + root.dataset.sessionId;

  function isDone(step) {
    return step.dataset.workoutDone === "1";
  }

  function firstIncompleteIndex() {
    const index = steps.findIndex(function (step) { return !isDone(step); });
    return index === -1 ? steps.length - 1 : index;
  }

  function readStoredIndex() {
    let stored = null;
    try {
      stored = window.sessionStorage.getItem(storageKey);
    } catch (e) {
      stored = null;
    }
    const index = stored === null ? NaN : parseInt(stored, 10);
    if (!Number.isFinite(index) || index < 0 || index >= steps.length) return null;
    return index;
  }

  function storeIndex(index) {
    try {
      window.sessionStorage.setItem(storageKey, String(index));
    } catch (e) {
      // sessionStorage unavailable (private mode, etc.) - navigation still works, just doesn't persist.
    }
  }

  let current = readStoredIndex();
  if (current === null || isDone(steps[current])) current = firstIncompleteIndex();

  function render() {
    steps.forEach(function (step, index) {
      step.classList.toggle("is-active", index === current);
    });
    label.textContent = "Exercise " + (current + 1) + " of " + steps.length;
    fill.style.width = Math.round(((current + 1) / steps.length) * 100) + "%";
    const next = steps[current + 1];
    nextPreview.textContent = next ? "Next: " + next.dataset.workoutName : "Last exercise — finish up below once you're done.";
    prevButton.disabled = current === 0;
    nextButton.disabled = current === steps.length - 1;
    storeIndex(current);
  }

  prevButton.addEventListener("click", function () {
    if (current > 0) {
      current -= 1;
      render();
    }
  });
  nextButton.addEventListener("click", function () {
    if (current < steps.length - 1) {
      current += 1;
      render();
    }
  });

  container.classList.add("workout-focus-enabled");
  render();
})();

/**
 * Equipment checkboxes on the plan-generator form: "No equipment" is
 * exclusive with every other option, since picking a specific piece of
 * equipment while also claiming to have none is contradictory input the
 * generator would otherwise have to silently interpret.
 */
(function () {
  const group = document.querySelector(".checkbox-group");
  if (!group) return;

  const boxes = group.querySelectorAll('input[type="checkbox"]');
  const noneBox = group.querySelector('input[type="checkbox"][value="none"]');
  if (!noneBox || boxes.length < 2) return;

  group.addEventListener("change", function (event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || target.type !== "checkbox") return;

    if (target === noneBox && target.checked) {
      boxes.forEach(function (box) {
        if (box !== noneBox) box.checked = false;
      });
    } else if (target !== noneBox && target.checked) {
      noneBox.checked = false;
    }
  });
})();
