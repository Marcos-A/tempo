/* Compact Catalan calendar picker for every `.date-input` text field.
 *
 * The field stays a plain DD/MM/AAAA text input, so typing by hand, the
 * `pattern` attribute and server-side parsing keep working unchanged. The
 * popup only fills the field in that same format. It is appended to <body>
 * because date inputs live inside <label> elements, which would otherwise
 * forward every click in the popup back to the input.
 */
(() => {
  const MONTH_NAMES = [
    "Gener", "Febrer", "Març", "Abril", "Maig", "Juny",
    "Juliol", "Agost", "Setembre", "Octubre", "Novembre", "Desembre",
  ];
  const WEEKDAY_NAMES = ["dl", "dt", "dc", "dj", "dv", "ds", "dg"];

  let popup = null;
  let activeInput = null;
  let viewYear = 0;
  let viewMonth = 0;

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function formatDate(value) {
    return `${pad(value.getDate())}/${pad(value.getMonth() + 1)}/${value.getFullYear()}`;
  }

  function sameDay(left, right) {
    return Boolean(left && right)
      && left.getFullYear() === right.getFullYear()
      && left.getMonth() === right.getMonth()
      && left.getDate() === right.getDate();
  }

  /* Mirrors app.date_utils.parse_date_input: D/M/AA, D/M/AAAA or ISO. */
  function parseDate(text) {
    const candidate = (text || "").trim();
    let year;
    let month;
    let day;
    let match = candidate.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (match) {
      [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
    } else {
      match = candidate.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2}|\d{4})$/);
      if (!match) return null;
      [day, month, year] = [Number(match[1]), Number(match[2]), Number(match[3])];
      if (match[3].length === 2) year += 2000;
    }
    const parsed = new Date(year, month - 1, day);
    if (parsed.getFullYear() !== year || parsed.getMonth() !== month - 1 || parsed.getDate() !== day) {
      return null;
    }
    return parsed;
  }

  function buildPopup() {
    popup = document.createElement("div");
    popup.className = "datepicker";
    popup.hidden = true;
    popup.setAttribute("role", "dialog");
    popup.setAttribute("aria-label", "Calendari");
    // Keep focus in the text field so typing by hand still works while open.
    popup.addEventListener("mousedown", (event) => event.preventDefault());
    popup.addEventListener("click", onPopupClick);
    document.body.appendChild(popup);
  }

  function render() {
    const selected = parseDate(activeInput.value);
    const today = new Date();
    // Monday-first offset of the 1st of the month.
    const firstWeekday = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7;
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

    const cells = [];
    for (let index = 0; index < firstWeekday; index += 1) {
      cells.push('<span class="datepicker-day is-empty"></span>');
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      const current = new Date(viewYear, viewMonth, day);
      const classes = ["datepicker-day"];
      if (sameDay(current, selected)) classes.push("is-selected");
      if (sameDay(current, today)) classes.push("is-today");
      if ((firstWeekday + day - 1) % 7 >= 5) classes.push("is-weekend");
      cells.push(
        `<button type="button" tabindex="-1" class="${classes.join(" ")}" data-day="${day}"`
        + ` aria-label="${day} de ${MONTH_NAMES[viewMonth].toLowerCase()} de ${viewYear}">${day}</button>`
      );
    }

    popup.innerHTML = `
      <div class="datepicker-header">
        <button type="button" tabindex="-1" class="datepicker-nav" data-step="-1" aria-label="Mes anterior">‹</button>
        <span class="datepicker-title">${MONTH_NAMES[viewMonth]} ${viewYear}</span>
        <button type="button" tabindex="-1" class="datepicker-nav" data-step="1" aria-label="Mes següent">›</button>
      </div>
      <div class="datepicker-grid">
        ${WEEKDAY_NAMES.map((name) => `<span class="datepicker-weekday">${name}</span>`).join("")}
        ${cells.join("")}
      </div>`;
  }

  function position() {
    const rect = activeInput.getBoundingClientRect();
    const popupHeight = popup.offsetHeight;
    const spaceBelow = window.innerHeight - rect.bottom;
    const top = spaceBelow < popupHeight + 8 && rect.top > popupHeight + 8
      ? rect.top - popupHeight - 4
      : rect.bottom + 4;
    const left = Math.min(rect.left, window.innerWidth - popup.offsetWidth - 8);
    popup.style.top = `${top + window.scrollY}px`;
    popup.style.left = `${Math.max(8, left) + window.scrollX}px`;
  }

  function open(input) {
    if (!popup) buildPopup();
    activeInput = input;
    const reference = parseDate(input.value) || new Date();
    viewYear = reference.getFullYear();
    viewMonth = reference.getMonth();
    render();
    popup.hidden = false;
    position();
  }

  function close() {
    if (popup) popup.hidden = true;
    activeInput = null;
  }

  function onPopupClick(event) {
    const button = event.target.closest("button");
    if (!button || !activeInput) return;
    if (button.dataset.step) {
      viewMonth += Number(button.dataset.step);
      if (viewMonth < 0) {
        viewMonth = 11;
        viewYear -= 1;
      } else if (viewMonth > 11) {
        viewMonth = 0;
        viewYear += 1;
      }
      render();
      position();
      return;
    }
    if (button.dataset.day) {
      const input = activeInput;
      input.value = formatDate(new Date(viewYear, viewMonth, Number(button.dataset.day)));
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      close();
    }
  }

  // Listeners are delegated from the document, so fields added after load
  // (such as the internship planner's period dates) get the picker too.
  function dateInputOf(event) {
    const target = event.target;
    return target instanceof HTMLInputElement && target.classList.contains("date-input") ? target : null;
  }

  document.addEventListener("focusin", (event) => {
    const input = dateInputOf(event);
    if (input) open(input);
  });
  document.addEventListener("click", (event) => {
    const input = dateInputOf(event);
    if (input && activeInput !== input) open(input);
  });
  document.addEventListener("focusout", (event) => {
    if (dateInputOf(event)) close();
  });
  document.addEventListener("keydown", (event) => {
    const input = dateInputOf(event);
    if (!input || activeInput !== input) return;
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "Enter") {
      close();
    }
  });
  // Follow hand-typed dates so the calendar shows the month being typed.
  document.addEventListener("input", (event) => {
    const input = dateInputOf(event);
    if (!input || activeInput !== input) return;
    const typed = parseDate(input.value);
    if (typed) {
      viewYear = typed.getFullYear();
      viewMonth = typed.getMonth();
    }
    render();
  });

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input.date-input").forEach((input) => input.setAttribute("autocomplete", "off"));
    window.addEventListener("resize", () => activeInput && position());
    window.addEventListener("scroll", () => activeInput && position(), { passive: true });
  });
})();
