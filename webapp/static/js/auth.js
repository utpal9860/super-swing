// Authentication utilities for frontend

function requireAuth() {
    // Check if user is logged in
    const token = localStorage.getItem('auth_token');
    
    if (!token) {
        // Redirect to login if not authenticated
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
        return false;
    }
    
    return true;
}

// Fetch with authentication token
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('auth_token');
    
    // Add auth header if token exists
    if (token) {
        options.headers = {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        };
    }
    
    const response = await fetch(url, options);
    
    // Handle unauthorized
    if (response.status === 401) {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    
    return response;
}

// Logout function
function logout() {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
}

// Check if user is authenticated (without redirect)
function isAuthenticated() {
    return !!localStorage.getItem('auth_token');
}

