(() => {
  const shell = document.querySelector(".app-container");
  const toggle = document.getElementById("nav-toggle");
  const links = [...document.querySelectorAll(".urp-menu-link")];
  const page = document.getElementById("urp-page");

  if (window.matchMedia("(max-width: 760px)").matches) {
    shell.classList.add("nav-toggled");
  }

  toggle?.addEventListener("click", () => shell.classList.toggle("nav-toggled"));
  links.forEach(link => {
    link.addEventListener("click", () => {
      const target = document.getElementById(link.dataset.scrollTarget);
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      links.forEach(item => item.classList.toggle("active", item === link));
      if (window.matchMedia("(max-width: 760px)").matches) shell.classList.add("nav-toggled");
    });
  });

  page?.addEventListener("scroll", () => {
    let current = links[0];
    for (const link of links) {
      const target = document.getElementById(link.dataset.scrollTarget);
      if (target && target.getBoundingClientRect().top < 180) current = link;
    }
    links.forEach(item => item.classList.toggle("active", item === current));
  }, { passive: true });
})();
