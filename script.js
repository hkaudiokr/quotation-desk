const API_BASE_URL = window.location.origin;
const USER_KEY = 'demo-login-user';

const loginForm = document.getElementById('loginForm');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');
const passwordToggle = document.getElementById('passwordToggle');
const statusMessage = document.getElementById('statusMessage');

function setStatus(el, message, type = 'error') {
  if (!el) return;
  el.textContent = message;
  el.className = `status-message ${type}`;
}

function setLoading(button, isLoading, loadingText, defaultText) {
  if (!button) return;
  button.disabled = isLoading;
  button.textContent = isLoading ? loadingText : defaultText;
}

function validateEmail(email) {
  return email === 'admin' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

if (passwordToggle) {
  passwordToggle.addEventListener('click', () => {
    const isVisible = passwordInput.type === 'text';
    passwordInput.type = isVisible ? 'password' : 'text';
    passwordToggle.textContent = isVisible ? '보기' : '숨기기';
    passwordToggle.setAttribute('aria-label', isVisible ? '비밀번호 보기' : '비밀번호 숨기기');
    passwordToggle.setAttribute('aria-pressed', String(!isVisible));
  });
}

function redirectToQuotation() {
  window.location.href = 'quotation.html';
}

async function apiRequest(url, payload) {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  return { response, data };
}

document.addEventListener('DOMContentLoaded', () => {
  const savedUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null');

  if (loginForm && savedUser) {
    setStatus(statusMessage, `${savedUser.name}님, 이미 로그인된 상태입니다.`, 'success');
    setTimeout(redirectToQuotation, 700);
  }

});

if (loginForm) {
  const submitButton = loginForm.querySelector('button[type="submit"]');

  loginForm.addEventListener('submit', async function (event) {
    event.preventDefault();

    const email = emailInput.value.trim();
    const password = passwordInput.value.trim();

    if (!email || !password) {
      setStatus(statusMessage, '이메일과 비밀번호를 모두 입력해주세요.', 'error');
      return;
    }

    if (!validateEmail(email)) {
      setStatus(statusMessage, '관리자 ID 또는 올바른 이메일을 입력해주세요.', 'error');
      emailInput.focus();
      return;
    }

    setLoading(submitButton, true, '로그인 중...', '로그인');
    setStatus(statusMessage, '로그인 정보를 확인하는 중입니다...', 'info');

    try {
      const { response, data } = await apiRequest('/api/login', { email, password });

      if (!response.ok) {
        setLoading(submitButton, false, '로그인 중...', '로그인');
        setStatus(statusMessage, data.message || '로그인에 실패했습니다.', 'error');
        passwordInput.focus();
        return;
      }

      localStorage.setItem(
        USER_KEY,
        JSON.stringify({
          email: data.user.email,
          name: data.user.name,
          role: data.user.role,
          loggedInAt: new Date().toISOString(),
        })
      );

      setStatus(statusMessage, `${data.user.name}님, 로그인에 성공했습니다!`, 'success');
      setLoading(submitButton, false, '로그인 중...', '로그인');

      setTimeout(redirectToQuotation, 900);
    } catch (error) {
      setLoading(submitButton, false, '로그인 중...', '로그인');
      setStatus(statusMessage, '서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.', 'error');
    }
  });
}
