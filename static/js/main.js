const menu = document.querySelector(".nav-toggle");
menu.addEventListener("click", () => {
    menu.setAttribute("aria-expanded", String(menu.getAttribute("aria-expanded") !== "true"));
});
document.querySelector("[data-print]")?.addEventListener("click", () => window.print());
