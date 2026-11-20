const form = document.querySelector("#booking-form");
const date = form.elements.show_date;
const time = form.elements.show_time;
const buttons = [...form.querySelectorAll(".seat")];
const selected = new Set();
const price = Number(form.dataset.price);
const status = document.querySelector("#seat-status");
const confirm = document.querySelector("#confirm-booking");
const refresh = document.querySelector("#refresh-seats");
let requestNumber = 0;
let loading = false;
let submitting = false;
let booked = new Set();
let available = false;

function render() {
    const inputs = document.querySelector("#selected-inputs");
    inputs.replaceChildren();
    for (const seat of selected) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "seats";
        input.value = seat;
        inputs.append(input);
    }
    for (const button of buttons) {
        const seat = button.dataset.seat;
        const occupied = booked.has(seat);
        const picked = selected.has(seat);
        button.disabled = occupied || loading || !available;
        button.classList.toggle("booked", occupied);
        button.classList.toggle("picked", picked);
        button.setAttribute("aria-pressed", String(picked));
        button.setAttribute("aria-label", "Seat " + seat + (occupied ? ", booked" : ""));
        button.textContent = occupied ? "×" : picked ? "✓" : seat.slice(1);
    }
    document.querySelector("#selection").textContent = selected.size
        ? selected.size + " selected · " + [...selected].join(", ")
        : "No seats selected";
    const total = "₹" + (selected.size * price).toLocaleString("en-IN");
    document.querySelector("#subtotal").textContent = total;
    document.querySelector("#total").textContent = total;
    confirm.disabled = !selected.size || !available || loading || submitting;
}

async function loadSeats(keepTime, keepSelection = false) {
    const currentRequest = ++requestNumber;
    const params = new URLSearchParams({
        movie_id: form.elements.movie_id.value,
        theater_id: form.elements.theater_id.value,
        show_date: date.value,
    });
    if (keepTime && time.value) params.set("show_time", time.value);
    if (!keepSelection) selected.clear();
    booked = new Set();
    loading = true;
    status.textContent = "Loading seats…";
    time.disabled = true;
    refresh.disabled = true;
    render();
    try {
        const response = await fetch(form.dataset.api + "?" + params, {cache: "no-store"});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Seat availability is temporarily unavailable.");
        if (currentRequest !== requestNumber) return;
        time.replaceChildren(...data.showtimes.map(slot => new Option(slot, slot)));
        time.value = data.show_time || "";
        time.disabled = !data.showtimes.length;
        booked = new Set(data.booked);
        for (const seat of booked) selected.delete(seat);
        available = Boolean(data.show_time);
        status.textContent = available ? (buttons.length - booked.size) + " seats available."
            : "No remaining shows on this date. Choose another date.";
    } catch (error) {
        if (currentRequest !== requestNumber) return;
        available = false;
        status.textContent = error.message + " Refresh availability to retry.";
    } finally {
        if (currentRequest === requestNumber) {
            loading = false;
            refresh.disabled = false;
            render();
        }
    }
}

for (const button of buttons) {
    button.addEventListener("click", () => {
        const seat = button.dataset.seat;
        if (selected.has(seat)) selected.delete(seat);
        else selected.add(seat);
        render();
    });
}
date.addEventListener("change", () => loadSeats(false));
time.addEventListener("change", () => loadSeats(true));
refresh.addEventListener("click", () => loadSeats(true, true));
form.addEventListener("submit", event => {
    if (submitting || confirm.disabled) {
        event.preventDefault();
        return;
    }
    submitting = true;
    confirm.textContent = "Confirming…";
    render();
});
loadSeats(false);
window.addEventListener("pageshow", event => {
    if (event.persisted) {
        submitting = false;
        confirm.textContent = "Confirm booking";
        loadSeats(true, true);
    }
});
