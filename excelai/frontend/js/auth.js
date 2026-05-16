(function () {
  const loginForm = document.getElementById('loginForm');
  const signupForm = document.getElementById('signupForm');
  const showSignup = document.getElementById('showSignup');

  if (!loginForm || !signupForm) return;

  const token = window.ExcelAI.getToken();
  if (token && window.ExcelAI.isTokenValid(token)) {
    window.location.href = 'app.html';
    return;
  }
  if (token && !window.ExcelAI.isTokenValid(token)) {
    window.ExcelAI.clearToken();
  }

  showSignup.addEventListener('click', () => {
    signupForm.classList.toggle('hidden');
    showSignup.textContent = signupForm.classList.contains('hidden') ? 'Create one' : 'Back to sign in';
  });

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    try {
      const response = await window.ExcelAI.request('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      window.ExcelAI.setToken(response.access_token);
      window.ExcelAI.showToast(`Welcome back, ${response.user.name}`, 'success');
      document.body.style.opacity = '0.92';
      window.setTimeout(() => { window.location.href = 'app.html'; }, 180);
    } catch (error) {
      window.ExcelAI.showToast(error.message || 'Login failed', 'error');
    }
  });

  signupForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;
    if (!name || !email || !password) {
      window.ExcelAI.showToast('Fill out all sign-up fields.', 'warning');
      return;
    }
    try {
      const response = await window.ExcelAI.request('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      });
      window.ExcelAI.setToken(response.access_token);
      window.ExcelAI.showToast(`Account created for ${response.user.name}`, 'success');
      window.setTimeout(() => { window.location.href = 'app.html'; }, 180);
    } catch (error) {
      window.ExcelAI.showToast(error.message || 'Sign up failed', 'error');
    }
  });
})();
