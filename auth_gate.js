/**
 * Verhill Radar — 인증 게이트 + 보안 모듈
 * Firebase Auth (Google) + Firestore 등급 기반 접근 제어
 */

// ─── Firebase 초기화 ───
import { initializeApp } from 'https://www.gstatic.com/firebasejs/12.10.0/firebase-app.js';
import { getAuth, signInWithPopup, GoogleAuthProvider, onAuthStateChanged, signOut }
  from 'https://www.gstatic.com/firebasejs/12.10.0/firebase-auth.js';
import { getFirestore, doc, getDoc, setDoc, updateDoc, deleteDoc, addDoc, getDocs, collection, query, orderBy, limit, serverTimestamp, increment }
  from 'https://www.gstatic.com/firebasejs/12.10.0/firebase-firestore.js';
import { getStorage, ref, getDownloadURL }
  from 'https://www.gstatic.com/firebasejs/12.10.0/firebase-storage.js';

const firebaseConfig = {
  apiKey: "AIzaSyDuZiLf7uI-XnGbi8xuLjuyx3bNOtQ4RnY",
  authDomain: "verhill-radar.firebaseapp.com",
  projectId: "verhill-radar",
  storageBucket: "verhill-radar.firebasestorage.app",
  messagingSenderId: "299027564474",
  appId: "1:299027564474:web:a851f64990b5c804adff83",
  measurementId: "G-7JC1XJQ897"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const storageRef = getStorage(app);
const IS_LOCAL_DEV = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const LOCAL_DEV_ADMIN_EMAIL = 'local-admin@localhost';
const LOCAL_FUNCTIONS_URL = 'http://127.0.0.1:5001/verhill-radar/us-central1';

// ─── 세션 관리 ───
const SESSION_DURATIONS = { admin: 5, manager: 5, viewer: 5, guest: 1 }; // 시간
const GUEST_LIFETIME_HOURS = 1; // 게스트 첫 로그인 후 총 이용 가능 시간
const SESSION_CHECK_INTERVAL = 60 * 1000; // 실시간 만료 체크 간격 (1분)

function generateSessionId() {
  return 'sess_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

// ─── 접속 로그 ───
async function logAccess(email, role, action, sessionId) {
  try {
    await addDoc(collection(db, 'access_logs'), {
      email,
      role,
      action,
      session_id: sessionId || '',
      user_agent: navigator.userAgent,
      timestamp: serverTimestamp(),
    });
  } catch (e) {
    console.warn('접속 로그 실패:', e.message);
  }
}

// ─── 워터마크 ───
function applyWatermark(displayName, role, sessionId) {
  const existing = document.getElementById('__watermark__');
  if (existing) existing.remove();

  const isAdmin = role === 'admin';
  const opacity = isAdmin ? 0.15 : role === 'manager' ? 0.08 : 0.20;
  const now = new Date();
  const timeStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const text = `${displayName} · ${timeStr}`;

  const canvas = document.createElement('canvas');
  canvas.width = 600;
  canvas.height = 280;
  const ctx = canvas.getContext('2d');
  ctx.font = '14px sans-serif';
  ctx.fillStyle = `rgba(255,255,255,${opacity * 0.5})`;
  ctx.translate(300, 140);
  ctx.rotate(-30 * Math.PI / 180);
  ctx.textAlign = 'center';
  ctx.fillText(text, 0, 0);

  const overlay = document.createElement('div');
  overlay.id = '__watermark__';
  overlay.style.cssText = `
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background-image: url(${canvas.toDataURL()});
    background-repeat: repeat;
    pointer-events: none;
    z-index: 999999;
    display: ${isAdmin ? 'none' : 'block'};
  `;
  document.body.appendChild(overlay);
}

// ─── 캡처 / DevTools 방지 ───
function applySecurityRestrictions(role) {
  if (role === 'admin' || role === 'manager') return;

  // 텍스트 선택 / 우클릭 / 드래그 차단
  document.body.style.userSelect = 'none';
  document.body.style.webkitUserSelect = 'none';
  document.addEventListener('contextmenu', e => e.preventDefault());
  document.addEventListener('dragstart', e => e.preventDefault());

  // 키보드 단축키 차단
  document.addEventListener('keydown', e => {
    // PrintScreen
    if (e.key === 'PrintScreen') {
      e.preventDefault();
      flashScreen();
      logAccess(window.__AUTH_USER__?.email, role, 'capture_attempt', window.__SESSION_ID__);
    }
    // Ctrl+P (인쇄), Ctrl+S (저장), Ctrl+U (소스보기)
    if (e.ctrlKey && ['p','s','u'].includes(e.key.toLowerCase())) {
      e.preventDefault();
    }
    // F12, Ctrl+Shift+I/J/C (개발자도구)
    if (e.key === 'F12' || (e.ctrlKey && e.shiftKey && ['i','j','c'].includes(e.key.toLowerCase()))) {
      e.preventDefault();
      handleDevTools(role);
    }
  });

  // DevTools 열림 감지 (크기 차이)
  let devtoolsOpen = false;
  const checkDevTools = () => {
    const threshold = 160;
    const widthDiff = window.outerWidth - window.innerWidth > threshold;
    const heightDiff = window.outerHeight - window.innerHeight > threshold;
    if ((widthDiff || heightDiff) && !devtoolsOpen) {
      devtoolsOpen = true;
      handleDevTools(role);
    } else if (!widthDiff && !heightDiff) {
      devtoolsOpen = false;
    }
  };
  setInterval(checkDevTools, 1500);

  // 인쇄 차단
  const printStyle = document.createElement('style');
  printStyle.textContent = '@media print { body { display: none !important; } }';
  document.head.appendChild(printStyle);
}

function flashScreen() {
  const flash = document.createElement('div');
  flash.style.cssText = `
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: white; z-index: 9999999;
  `;
  document.body.appendChild(flash);
  setTimeout(() => flash.remove(), 1000);
}

function handleDevTools(role) {
  if (role === 'guest') {
    // guest: 세션 종료
    signOut(auth);
    document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#0F172A;color:#EF4444;font-size:20px;font-family:sans-serif;">보안 위반 — 세션이 종료되었습니다.</div>';
  } else {
    // viewer: 경고
    flashScreen();
    logAccess(window.__AUTH_USER__?.email, role, 'devtools_detected', window.__SESSION_ID__);
  }
}

// ─── 게스트 탭 제한 ───
function applyTabRestrictions(role) {
  if (role !== 'guest') return;
  // guest는 Tab1, Tab4만 허용 — 대시보드 로드 후 적용
  window.__GUEST_ALLOWED_TABS__ = [0, 3]; // 0-indexed: 브리핑, 가격흐름
}

// ─── 로그인 UI ───
function showLoginScreen() {
  document.getElementById('__app_root__').style.display = 'none';
  const gate = document.createElement('div');
  gate.id = '__auth_gate__';
  gate.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
      <div style="background:#1E293B;border-radius:16px;padding:48px;text-align:center;
                  border:1px solid #334155;max-width:400px;width:90%;">
        <div style="font-size:32px;font-weight:800;margin-bottom:8px;color:#6366F1;">
          VERHILL RADAR
        </div>
        <div style="font-size:14px;color:#64748B;margin-bottom:36px;">
          베르힐 기획실 · 골프 시장 모니터링
        </div>
        <button id="__google_login__" style="
          display:flex;align-items:center;justify-content:center;gap:12px;
          width:100%;padding:14px 24px;border-radius:10px;border:1px solid #334155;
          background:#1E293B;color:#E2E8F0;font-size:16px;font-weight:600;
          cursor:pointer;transition:all 0.2s;">
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Google 계정으로 로그인
        </button>
        <div id="__login_status__" style="margin-top:20px;font-size:13px;color:#64748B;min-height:20px;"></div>
      </div>
    </div>
  `;
  document.body.appendChild(gate);

  document.getElementById('__google_login__').addEventListener('click', async () => {
    const statusEl = document.getElementById('__login_status__');
    statusEl.textContent = '로그인 중...';
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
    } catch (err) {
      statusEl.textContent = '로그인 실패: ' + err.message;
      statusEl.style.color = '#EF4444';
    }
  });
}

function showNameInput(user) {
  const gate = document.getElementById('__auth_gate__');
  if (!gate) return;

  // 1단계: 가입신청 확인 화면
  gate.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
      <div style="background:#1E293B;border-radius:16px;padding:48px;text-align:center;
                  border:1px solid #334155;max-width:420px;width:90%;">
        <div style="font-size:48px;margin-bottom:16px;">📋</div>
        <div style="font-size:22px;font-weight:700;margin-bottom:8px;">가입 신청</div>
        <div style="font-size:14px;color:#94A3B8;margin-bottom:8px;">${user.email}</div>
        <div style="font-size:14px;color:#64748B;margin-bottom:28px;line-height:1.6;">
          VERHILL RADAR는 승인된 사용자만 이용할 수 있습니다.<br>
          가입을 신청하시겠습니까?
        </div>
        <div style="display:flex;gap:12px;justify-content:center;">
          <button id="__confirm_signup__" style="
            flex:1;padding:14px;border-radius:10px;border:none;
            background:#4F46E5;color:white;font-size:16px;font-weight:600;cursor:pointer;">
            가입 신청하기
          </button>
          <button id="__cancel_signup__" style="
            flex:1;padding:14px;border-radius:10px;border:1px solid #334155;
            background:transparent;color:#94A3B8;font-size:16px;cursor:pointer;">
            취소
          </button>
        </div>
      </div>
    </div>
  `;

  document.getElementById('__cancel_signup__').addEventListener('click', async () => {
    await signOut(auth);
    location.reload();
  });

  document.getElementById('__confirm_signup__').addEventListener('click', () => {
    // 2단계: 이름 입력 화면으로 전환
    _showNameForm(user, gate);
  });
}

function _showNameForm(user, gate) {
  gate.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
      <div style="background:#1E293B;border-radius:16px;padding:48px;text-align:center;
                  border:1px solid #334155;max-width:400px;width:90%;">
        <div style="font-size:24px;font-weight:700;margin-bottom:8px;">접속 요청</div>
        <div style="font-size:14px;color:#64748B;margin-bottom:24px;">${user.email}</div>
        <input id="__name_input__" type="text" placeholder="이름을 입력해주세요"
          style="width:100%;padding:12px 16px;border-radius:8px;border:1px solid #334155;
                 background:#0F172A;color:#E2E8F0;font-size:16px;margin-bottom:16px;
                 box-sizing:border-box;" />
        <button id="__submit_request__" style="
          width:100%;padding:14px;border-radius:10px;border:none;
          background:#4F46E5;color:white;font-size:16px;font-weight:600;cursor:pointer;">
          접속 요청하기
        </button>
        <div id="__request_status__" style="margin-top:16px;font-size:13px;color:#64748B;"></div>
      </div>
    </div>
  `;

  document.getElementById('__name_input__').focus();

  document.getElementById('__submit_request__').addEventListener('click', async () => {
    const name = document.getElementById('__name_input__').value.trim();
    const statusEl = document.getElementById('__request_status__');
    if (!name) {
      statusEl.textContent = '이름을 입력해주세요.';
      statusEl.style.color = '#EF4444';
      return;
    }
    statusEl.textContent = '요청 중...';
    try {
      await setDoc(doc(db, 'pending_requests', user.email), {
        email: user.email,
        self_name: name,
        requested_at: serverTimestamp(),
        status: 'pending',
      });

      try {
        await logAccess(user.email, 'none', 'access_request', '');
      } catch (logError) {
        console.warn('접속 요청 로그 실패:', logError.message);
      }

      showPendingScreen(user.email);
    } catch (err) {
      statusEl.textContent = '요청 실패: ' + err.message;
      statusEl.style.color = '#EF4444';
    }
  });
}

function showPendingScreen(email) {
  const gate = document.getElementById('__auth_gate__');
  if (!gate) return;
  gate.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
      <div style="background:#1E293B;border-radius:16px;padding:48px;text-align:center;
                  border:1px solid #334155;max-width:400px;width:90%;">
        <div style="font-size:48px;margin-bottom:16px;">⏳</div>
        <div style="font-size:20px;font-weight:700;margin-bottom:8px;">승인 대기 중</div>
        <div style="font-size:14px;color:#64748B;margin-bottom:24px;">
          관리자가 접속을 승인하면 이용할 수 있습니다.
        </div>
        <button onclick="location.reload()" style="
          padding:10px 24px;border-radius:8px;border:1px solid #334155;
          background:#0F172A;color:#94A3B8;font-size:14px;cursor:pointer;">
          새로고침
        </button>
      </div>
    </div>
  `;
}

function showDeniedScreen() {
  const gate = document.getElementById('__auth_gate__');
  if (!gate) return;
  gate.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
      <div style="background:#1E293B;border-radius:16px;padding:48px;text-align:center;
                  border:1px solid #334155;max-width:400px;width:90%;">
        <div style="font-size:48px;margin-bottom:16px;">🚫</div>
        <div style="font-size:20px;font-weight:700;color:#EF4444;">접근이 차단되었습니다</div>
      </div>
    </div>
  `;
}

// ─── 제한 안내 화면들 ───
function _restrictionScreen(icon, title, subtitle) {
  const gate = document.getElementById('__auth_gate__');
  if (!gate) return;
  gate.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
      <div style="background:#1E293B;border-radius:16px;padding:48px;text-align:center;
                  border:1px solid #334155;max-width:400px;width:90%;">
        <div style="font-size:48px;margin-bottom:16px;">${icon}</div>
        <div style="font-size:20px;font-weight:700;margin-bottom:8px;">${title}</div>
        <div style="font-size:14px;color:#64748B;margin-bottom:24px;">${subtitle}</div>
        <button onclick="window.__vrLogout__()" style="
          padding:10px 24px;border-radius:8px;border:1px solid #334155;
          background:#0F172A;color:#94A3B8;font-size:14px;cursor:pointer;">
          로그아웃
        </button>
      </div>
    </div>
  `;
}

function showExpiredScreen(expiresAt) {
  _restrictionScreen('⏰', '이용 기간이 만료되었습니다', `만료일: ${expiresAt}`);
}

function showNotYetScreen(startsAt) {
  _restrictionScreen('📅', '아직 이용 기간이 아닙니다', `시작일: ${startsAt}`);
}

function showLimitReachedScreen(maxLogins) {
  _restrictionScreen('🔒', '접속 횟수를 초과했습니다', `허용 횟수: ${maxLogins}회`);
}

function showTimeRestrictedScreen(startH, endH) {
  _restrictionScreen('🕐', '접속 가능 시간이 아닙니다', `허용 시간: ${startH}:00 ~ ${endH}:00`);
}

// ─── 데이터 로드 (Firebase Storage) ───
function showLoadingScreen(msg) {
  const gate = document.getElementById('__auth_gate__');
  if (!gate) return;
  gate.style.display = 'block';
  gate.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
      <div style="font-size:32px;font-weight:800;color:#6366F1;margin-bottom:16px;">VERHILL RADAR</div>
      <div style="font-size:14px;color:#64748B;">${msg}</div>
      <div style="margin-top:20px;width:40px;height:40px;border:3px solid #334155;border-top-color:#6366F1;border-radius:50%;animation:spin 1s linear infinite;"></div>
      <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
    </div>
  `;
}

async function loadDashboardData() {
  try {
    // dashboard_data.json 로드
    const dataRef = ref(storageRef, 'dashboard/dashboard_data.json');
    const dataUrl = await getDownloadURL(dataRef);
    const dataResp = await fetch(dataUrl);
    window.__GOLF_DATA__ = await dataResp.json();

    // tab8 today 로드
    const tab8Ref = ref(storageRef, 'dashboard/golf_tab8_today.json');
    const tab8Url = await getDownloadURL(tab8Ref);
    const tab8Resp = await fetch(tab8Url);
    window.__GOLF_TAB8_TODAY__ = await tab8Resp.json();

    window.__DATA_FROM_STORAGE__ = true;
    console.log('✅ Firebase Storage에서 데이터 로드 완료');
  } catch (e) {
    console.warn('Storage 로드 실패:', e.message);
    throw e;
  }
}

function enableLocalDevMode() {
  window.__SESSION_ID__ = `local_${Date.now().toString(36)}`;
  window.__DISPLAY_NAME__ = 'Local Admin';
  window.__USER_ROLE__ = 'admin';
  window.__USER_PHOTO__ = '';
  window.__USER_EMAIL__ = LOCAL_DEV_ADMIN_EMAIL;
  window.__FIREBASE_ID_TOKEN__ = '';
  window.__LOCAL_DEV_ADMIN_EMAIL__ = LOCAL_DEV_ADMIN_EMAIL;
  window.__FIREBASE_FUNCTIONS_URL__ = LOCAL_FUNCTIONS_URL;

  const gate = document.getElementById('__auth_gate__');
  if (gate) gate.style.display = 'none';
  document.getElementById('__app_root__').style.display = 'block';

  const rootEl = document.getElementById('root');
  if (rootEl && window.ReactDOM && window.App) {
    rootEl.innerHTML = '';
    const root = ReactDOM.createRoot(rootEl);
    root.render(React.createElement(window.App));
  }
}

// ─── 메인 인증 로직 ───
function initAuthGate() {
  if (IS_LOCAL_DEV) {
    enableLocalDevMode();
    return;
  }

  showLoginScreen();

  onAuthStateChanged(auth, async (user) => {
    try {
      if (!user) {
        document.getElementById('__app_root__').style.display = 'none';
        const gate = document.getElementById('__auth_gate__');
        if (!gate) showLoginScreen();
        else gate.style.display = 'block';
        return;
      }

      window.__AUTH_USER__ = { email: user.email, uid: user.uid };

      // Firestore에서 승인 여부 확인
      const userDoc = await getDoc(doc(db, 'approved_users', user.email));

      if (!userDoc.exists()) {
        // 미등록 → pending 확인
        const pendingDoc = await getDoc(doc(db, 'pending_requests', user.email));
        if (pendingDoc.exists()) {
          const data = pendingDoc.data();
          if (data.status === 'denied') {
            showDeniedScreen();
          } else {
            showPendingScreen(user.email);
          }
        } else {
          showNameInput(user);
        }
        return;
      }

      const userData = userDoc.data();

      if (!userData.active) {
        showDeniedScreen();
        return;
      }

    const role = userData.role || 'viewer';

    // ── 접근 제한 체크 ──

    // 1) 기간 제한: expires_at 이후 자동 차단
    if (userData.expires_at) {
      const now = new Date();
      const expires = new Date(userData.expires_at);
      if (now > expires) {
        showExpiredScreen(userData.expires_at);
        await logAccess(user.email, role, 'expired', '');
        return;
      }
    }

    // 2) 시작일 제한: starts_at 이전 접속 불가
    if (userData.starts_at) {
      const now = new Date();
      const starts = new Date(userData.starts_at);
      if (now < starts) {
        showNotYetScreen(userData.starts_at);
        return;
      }
    }

    // 3) 접속 횟수 제한: max_logins 초과 시 차단
    if (userData.max_logins && userData.max_logins > 0) {
      const currentCount = userData.login_count || 0;
      if (currentCount >= userData.max_logins) {
        showLimitReachedScreen(userData.max_logins);
        await logAccess(user.email, role, 'login_limit', '');
        return;
      }
    }

    // 4) 시간대 제한: allowed_hours [시작, 종료] 범위 밖이면 차단
    if (userData.allowed_hours && userData.allowed_hours.length === 2) {
      const currentHour = new Date().getHours();
      const [startH, endH] = userData.allowed_hours;
      if (currentHour < startH || currentHour >= endH) {
        showTimeRestrictedScreen(startH, endH);
        await logAccess(user.email, role, 'time_restricted', '');
        return;
      }
    }

    // 5) 게스트 영구차단: 첫 로그인 후 GUEST_LIFETIME_HOURS 경과 시 차단
    if (role === 'guest') {
      const firstLogin = userData.first_login_at;
      if (firstLogin) {
        const elapsed = (Date.now() - new Date(firstLogin).getTime()) / (1000 * 60 * 60);
        if (elapsed > GUEST_LIFETIME_HOURS) {
          // 자동 비활성화
          try {
            await updateDoc(doc(db, 'approved_users', user.email), { active: false });
          } catch (e) {}
          _restrictionScreen('🔒', '이용 시간이 만료되었습니다', `게스트 이용 가능 시간(${GUEST_LIFETIME_HOURS}시간)이 종료되었습니다.<br>관리자에게 문의하세요.`);
          await logAccess(user.email, role, 'guest_expired', '');
          return;
        }
      }
    }

    // 6) 세션 시간 만료 (로그인 후 N시간)
    const maxHours = userData.session_hours || SESSION_DURATIONS[role] || 5;
    if (maxHours > 0) {
      const lastLogin = localStorage.getItem('__vr_last_login__');
      if (lastLogin) {
        const elapsed = (Date.now() - parseInt(lastLogin)) / (1000 * 60 * 60);
        if (elapsed > maxHours) {
          localStorage.removeItem('__vr_last_login__');
          await signOut(auth);
          return;
        }
      }
    }
    localStorage.setItem('__vr_last_login__', Date.now().toString());

    // ── 접속 횟수 증가 + 게스트 첫 로그인 시각 기록 ──
    try {
      const updates = {
        login_count: increment(1),
        last_login_at: new Date().toISOString(),
      };
      // 게스트 첫 로그인 시각 기록 (한번만)
      if (role === 'guest' && !userData.first_login_at) {
        updates.first_login_at = new Date().toISOString();
      }
      await updateDoc(doc(db, 'approved_users', user.email), updates);
    } catch (e) {
      console.warn('접속 정보 업데이트 실패:', e.message);
    }

    // 세션 시작
    const sessionId = generateSessionId();
    window.__SESSION_ID__ = sessionId;
    const displayName = userData.admin_name || userData.self_name || user.email;
    window.__DISPLAY_NAME__ = displayName;
    window.__USER_ROLE__ = role;
    window.__USER_PHOTO__ = user.photoURL || '';
    window.__USER_EMAIL__ = user.email;
    // AI 채팅용 ID 토큰 (50분마다 자동 갱신)
    try { window.__FIREBASE_ID_TOKEN__ = await user.getIdToken(); } catch(e) { window.__FIREBASE_ID_TOKEN__ = ''; }
    setInterval(async () => {
      try { window.__FIREBASE_ID_TOKEN__ = await user.getIdToken(true); } catch(e) { /* ignore */ }
    }, 50 * 60 * 1000);

    // 접속 로그
    await logAccess(user.email, role, 'login', sessionId);

    // 보안 적용
    applyWatermark(displayName, role, sessionId);
    applySecurityRestrictions(role);
    applyTabRestrictions(role);

    // 실시간 세션 만료 체크 (1분마다)
    setInterval(() => {
      const loginTime = localStorage.getItem('__vr_last_login__');
      if (!loginTime) return;
      const elapsed = (Date.now() - parseInt(loginTime)) / (1000 * 60 * 60);
      const limit = maxHours || 5;
      if (limit > 0 && elapsed > limit) {
        window.__vrLogout__();
      }
      // 게스트 실시간 체크
      if (role === 'guest' && userData.first_login_at) {
        const guestElapsed = (Date.now() - new Date(userData.first_login_at).getTime()) / (1000 * 60 * 60);
        if (guestElapsed > GUEST_LIFETIME_HOURS) {
          window.__vrLogout__();
        }
      }
    }, SESSION_CHECK_INTERVAL);

    // 데이터 로드 (Firebase Storage에서 또는 임베딩된 데이터 사용)
    if (!window.__GOLF_DATA__ || Object.keys(window.__GOLF_DATA__).length === 0) {
      showLoadingScreen('데이터 로드 중...');
      try {
        await loadDashboardData();
      } catch (e) {
        console.warn('Storage 데이터 로드 실패, 임베딩 데이터 확인:', e.message);
      }
    }

    // 대시보드 표시
    const gate = document.getElementById('__auth_gate__');
    if (gate) gate.style.display = 'none';
    document.getElementById('__app_root__').style.display = 'block';

    // Storage에서 데이터 로드한 경우에만 React 재마운트
      if (window.__DATA_FROM_STORAGE__) {
        const rootEl = document.getElementById('root');
        if (rootEl && window.ReactDOM && window.App) {
          rootEl.innerHTML = '';
          const root = ReactDOM.createRoot(rootEl);
          root.render(React.createElement(window.App));
        }
      }
    } catch (e) {
      console.error('인증 게이트 오류:', e);
      const gate = document.getElementById('__auth_gate__');
      if (gate) {
        gate.style.display = 'block';
        gate.innerHTML = `
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                      height:100vh;background:#0F172A;font-family:sans-serif;color:#E2E8F0;">
            <div style="background:#1E293B;border-radius:16px;padding:48px;text-align:center;
                        border:1px solid #334155;max-width:440px;width:90%;">
              <div style="font-size:48px;margin-bottom:16px;">⚠️</div>
              <div style="font-size:20px;font-weight:700;margin-bottom:10px;">로그인 처리 중 오류가 발생했습니다</div>
              <div style="font-size:14px;color:#94A3B8;line-height:1.6;white-space:pre-wrap;">${e.message || '알 수 없는 오류'}</div>
              <button onclick="location.reload()" style="
                margin-top:24px;padding:10px 24px;border-radius:8px;border:1px solid #334155;
                background:#0F172A;color:#94A3B8;font-size:14px;cursor:pointer;">
                새로고침
              </button>
            </div>
          </div>
        `;
      }
    }
  });
}

// ─── 관리자 API (외부에서 호출용) ───
window.__vrAdmin__ = {
  // 승인 대기 목록 조회
  async getPendingRequests() {
    const snap = await getDocs(collection(db, 'pending_requests'));
    return snap.docs.map(d => ({ id: d.id, ...d.data() }));
  },
  // 승인된 사용자 목록 조회
  async getApprovedUsers() {
    const snap = await getDocs(collection(db, 'approved_users'));
    return snap.docs.map(d => ({ id: d.id, ...d.data() }));
  },
  // 사용자 승인 (pending → approved)
  async approveUser(email, selfName, role, adminName, options = {}) {
    await setDoc(doc(db, 'approved_users', email), {
      email,
      self_name: selfName,
      admin_name: adminName || selfName,
      role: role || 'viewer',
      active: true,
      approved_at: serverTimestamp(),
      approved_by: window.__USER_EMAIL__ || 'admin',
      login_count: 0,
      ...options,
    });
    // pending에서 삭제
    try { await deleteDoc(doc(db, 'pending_requests', email)); } catch(e) {}
    return true;
  },
  // 사용자 거부
  async denyUser(email) {
    await updateDoc(doc(db, 'pending_requests', email), { status: 'denied' });
    return true;
  },
  // 사용자 정보 수정 (등급, 기간, 이름 등)
  async updateUser(email, fields) {
    await updateDoc(doc(db, 'approved_users', email), fields);
    return true;
  },
  // 사용자 차단/활성
  async toggleUser(email, active) {
    await updateDoc(doc(db, 'approved_users', email), { active });
    return true;
  },
  // 사용자 삭제
  async removeUser(email) {
    await deleteDoc(doc(db, 'approved_users', email));
    return true;
  },
  // 접속 로그 조회 (최근 50건)
  async getAccessLogs() {
    const snap = await getDocs(query(collection(db, 'access_logs'), orderBy('timestamp', 'desc'), limit(50)));
    return snap.docs.map(d => ({ id: d.id, ...d.data() }));
  },
  // ─── 채팅 내역 ───
  async saveChatHistory({ id, tabName, title, messages, tokenStats, model }) {
    const email = window.__USER_EMAIL__ || '';
    if (id) {
      await updateDoc(doc(db, 'chat_histories', id), {
        messages, tokenStats, model, updatedAt: serverTimestamp(),
      });
      return id;
    }
    const ref = await addDoc(collection(db, 'chat_histories'), {
      email, tabName, title, messages, tokenStats, model,
      createdAt: serverTimestamp(), updatedAt: serverTimestamp(),
    });
    return ref.id;
  },
  async getChatHistories() {
    const email = window.__USER_EMAIL__ || '';
    const snap = await getDocs(query(collection(db, 'chat_histories'), orderBy('createdAt', 'desc'), limit(50)));
    return snap.docs.filter(d => d.data().email === email).map(d => ({ id: d.id, ...d.data() }));
  },
  async deleteChatHistory(id) {
    await deleteDoc(doc(db, 'chat_histories', id));
    return true;
  },
};

// ─── 로그아웃 함수 (외부에서 호출용) ───
window.__vrLogout__ = async () => {
  await logAccess(window.__AUTH_USER__?.email, window.__USER_ROLE__, 'logout', window.__SESSION_ID__);
  localStorage.removeItem('__vr_last_login__');
  await signOut(auth);
  location.reload();
};

// 시작
initAuthGate();
