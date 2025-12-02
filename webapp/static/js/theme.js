/**
 * Theme Manager - Light/Dark Mode Toggle
 * Applies to all pages globally
 */

// Initialize theme on page load
(function() {
    // Get saved theme or default to 'light'
    const savedTheme = localStorage.getItem('app_theme') || 'light';
    applyTheme(savedTheme);
})();

/**
 * Apply theme to the document
 * @param {string} theme - 'light' or 'dark'
 */
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('app_theme', theme);
    
    // Update theme toggle button if it exists
    updateThemeToggleUI(theme);
    
    // Dispatch custom event for other scripts
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
}

/**
 * Toggle between light and dark theme
 */
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
    
    // Show toast notification
    if (typeof showToast === 'function') {
        showToast(`Switched to ${newTheme} mode`, 'info');
    }
}

/**
 * Get current theme
 * @returns {string} - 'light' or 'dark'
 */
function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'light';
}

/**
 * Update theme toggle button UI
 * @param {string} theme - Current theme
 */
function updateThemeToggleUI(theme) {
    // Update radio buttons in settings
    const lightRadio = document.getElementById('theme-light');
    const darkRadio = document.getElementById('theme-dark');
    
    if (lightRadio && darkRadio) {
        if (theme === 'light') {
            lightRadio.checked = true;
            darkRadio.checked = false;
        } else {
            lightRadio.checked = false;
            darkRadio.checked = true;
        }
    }
    
    // Update navbar toggle button if exists
    const navbarToggle = document.querySelector('.theme-toggle-btn');
    if (navbarToggle) {
        navbarToggle.textContent = theme === 'light' ? '🌙' : '☀️';
        navbarToggle.title = theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode';
    }
}

// Make functions globally available
window.applyTheme = applyTheme;
window.toggleTheme = toggleTheme;
window.getCurrentTheme = getCurrentTheme;











