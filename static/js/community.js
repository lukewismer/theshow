// ─────────────────────────────────────────────────────────────────────────────
// community.js
// Handles both tab‐switching and Firebase “logged‐in” detection
// ─────────────────────────────────────────────────────────────────────────────

// Import the Firebase functions we need:
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.8.1/firebase-auth.js";

document.addEventListener("DOMContentLoaded", () => {
  // ─── Part 1: Tab Switching ──────────────────────────────────────────────
  const tabButtons = document.querySelectorAll(".community-tabs .tab-button");
  const tabSections = document.querySelectorAll(".tab-content");

  tabButtons.forEach(button => {
    button.addEventListener("click", () => {
      // 1) Deactivate all buttons, then activate the clicked one
      tabButtons.forEach(b => b.classList.remove("active"));
      button.classList.add("active");

      // 2) Hide all sections, then show the one that matches data-tab
      tabSections.forEach(section => section.classList.add("hidden"));
      const selectedId = button.dataset.tab; // "chat" or "friends" or "trends"
      const selectedSection = document.getElementById(selectedId);
      if (selectedSection) {
        selectedSection.classList.remove("hidden");
      }
    });
  });

  // ─── Part 2: Firebase Auth State ────────────────────────────────────────
  const auth = getAuth(); 
  const chatContainer = document.querySelector(".chat-container");
  const loginPrompt = document.querySelector(".login-prompt");

  // By default, hide chat container and show the login prompt.
  chatContainer.style.display = "none";
  loginPrompt.style.display = "block";

  onAuthStateChanged(auth, (user) => {
    if (user) {
      // User is signed in → show chat, hide login prompt
      chatContainer.style.display = "block";
      loginPrompt.style.display = "none";
    } else {
      // No user signed in → hide chat, show login prompt
      chatContainer.style.display = "none";
      loginPrompt.style.display = "block";
    }
  });
});
