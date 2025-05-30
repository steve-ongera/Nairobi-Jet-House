'use strict';

/**
 * Enhanced navbar toggle with better mobile handling
 */
const overlay = document.querySelector("[data-overlay]");
const navOpenBtn = document.querySelector("[data-nav-open-btn]");
const navbar = document.querySelector("[data-navbar]");
const navCloseBtn = document.querySelector("[data-nav-close-btn]");
const navLinks = document.querySelectorAll("[data-nav-link]");

const navToggleEvent = function (elements) {
  elements.forEach(element => {
    element.addEventListener("click", function () {
      navbar.classList.toggle("active");
      overlay.classList.toggle("active");
      document.body.classList.toggle("nav-active"); // Toggle body scroll lock
    });
  });
};

// Apply to all navigation elements
navToggleEvent([navOpenBtn, navCloseBtn, overlay]);
navToggleEvent(navLinks);

/**
 * Optimized header sticky & go to top functionality
 */
const header = document.querySelector("[data-header]");
const goTopBtn = document.querySelector("[data-go-top]");
const headerBottom = document.querySelector(".header-bottom");

let lastScrollPosition = 0;

window.addEventListener("scroll", function () {
  const currentScrollPosition = window.scrollY;
  
  // Header sticky effect
  if (currentScrollPosition >= 200) {
    header.classList.add("active");
    goTopBtn.classList.add("active");
    
    // Smooth transition for header bottom
    headerBottom.style.transition = "all 0.3s ease";
  } else {
    header.classList.remove("active");
    goTopBtn.classList.remove("active");
  }
  
  lastScrollPosition = currentScrollPosition;
});

// Handle resize events to ensure proper mobile behavior
window.addEventListener("resize", function() {
  if (window.innerWidth >= 992) {
    navbar.classList.remove("active");
    overlay.classList.remove("active");
    document.body.classList.remove("nav-active");
  }
});