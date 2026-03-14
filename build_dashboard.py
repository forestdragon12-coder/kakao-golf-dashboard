"""
golf_dashboard.html 빌더 (V5)
generate_dashboard_data.py의 V5 데이터 + golf_price_dashboard_v5.jsx를
합쳐 완전 자립형(오프라인 동작) HTML 파일 생성

사용법:
    python3 build_dashboard.py
    → golf_dashboard.html 생성 (브라우저에서 바로 열기 가능, V5 다크테마)
    → golf_tab8_20260313.json, golf_tab8_20260314.json, golf_tab8_20260315.json 생성 (일자별 슬롯)

의존성:
    - Node.js (JSX 컴파일용, 없으면 Babel CDN 폴백)
    - npm (React/Recharts 라이브러리 다운로드용, 최초 1회)
    - Python 3.8+
"""
import json
import re
import sys
import os
import subprocess
import shutil
import tempfile

# ─────────────────────────────────────────────
# 경로 설정
# ─────────────────────────────────────────────
SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
DB_PATH         = os.path.join(SCRIPT_DIR, "data/golf.db")
JSX_PATH        = os.path.join(SCRIPT_DIR, "golf_price_dashboard_v5.jsx")
OUT_HTML_PATH   = os.path.join(SCRIPT_DIR, "golf_dashboard.html")

# npm 라이브러리 캐시 디렉토리 (최초 1회 설치)
LIB_CACHE_DIR = os.path.join(SCRIPT_DIR, ".dashboard_libs")

REQUIRED_LIBS = ["react@18", "react-dom@18", "prop-types", "recharts@2"]

# ─────────────────────────────────────────────
# 1. 데이터 생성
# ─────────────────────────────────────────────
sys.path.insert(0, SCRIPT_DIR)
from generate_dashboard_data import (
    conn, get_metadata, build_v5_data, get_tab8_by_date, make_embed_data
)

def build_data():
    """V5 데이터 구조 빌드"""
    db = conn()
    data_v5 = build_v5_data(db)
    db.close()
    return data_v5

def build_tab8_files(data_v5, db):
    """
    Generate per-date Tab8 JSON files + return today's data for HTML embed.

    Args:
        data_v5: V5 data structure from build_v5_data()
        db: Database connection

    Returns:
        Today's tab8 slots for HTML embed
    """
    dates = data_v5["metadata"]["all_dates"]
    latest = data_v5["metadata"]["latest_date"]

    for date in dates:
        slots = get_tab8_by_date(db, date)
        # Format date from YYYY-MM-DD to YYYYMMDD
        date_str = date.replace('-', '')
        fname = f"golf_tab8_{date_str}.json"
        path = os.path.join(SCRIPT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"slots": slots}, f, ensure_ascii=False, separators=(',', ':'), default=str)
        print(f"  → {fname} ({len(slots)} slots)")

    # Return today's (latest) data for HTML embed
    today_slots = get_tab8_by_date(db, latest)
    return today_slots

# ─────────────────────────────────────────────
# 2. npm 라이브러리 캐시
# ─────────────────────────────────────────────
def ensure_libs():
    """필요한 UMD JS 파일들을 캐시 디렉토리에 준비"""
    lib_files = {
        "react.js":      f"{LIB_CACHE_DIR}/node_modules/react/umd/react.production.min.js",
        "react-dom.js":  f"{LIB_CACHE_DIR}/node_modules/react-dom/umd/react-dom.production.min.js",
        "prop-types.js": f"{LIB_CACHE_DIR}/node_modules/prop-types/prop-types.min.js",
        "recharts.js":   f"{LIB_CACHE_DIR}/node_modules/recharts/umd/Recharts.js",
    }

    missing = [k for k, v in lib_files.items() if not os.path.exists(v)]
    if missing:
        print(f"  라이브러리 다운로드 중 ({', '.join(missing)})...")
        if not shutil.which("npm"):
            print("  ⚠ npm을 찾을 수 없음 — CDN 폴백 모드 사용")
            return None

        os.makedirs(LIB_CACHE_DIR, exist_ok=True)
        result = subprocess.run(
            ["npm", "install", "--prefix", LIB_CACHE_DIR] + REQUIRED_LIBS,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            print(f"  ⚠ npm install 실패: {result.stderr[:200]}")
            return None

    # 파일 읽기
    try:
        contents = {}
        for name, path in lib_files.items():
            with open(path) as f:
                contents[name] = f.read()
        total_kb = sum(len(v.encode()) for v in contents.values()) / 1024
        print(f"  라이브러리 로드 완료 ({total_kb:.0f} KB)")
        return contents
    except Exception as e:
        print(f"  ⚠ 라이브러리 읽기 실패: {e}")
        return None

# ─────────────────────────────────────────────
# 3-A. JSX 컴파일 (Babel Node.js — 권장)
# ─────────────────────────────────────────────
_BABEL_SETUP_SCRIPT = """
const babel = require('@babel/core');
const fs = require('fs');
const jsx = fs.readFileSync(process.argv[2], 'utf8');

// import/export 처리 (Python 전처리 후 전달)
const result = babel.transformSync(jsx, {
  presets: [['@babel/preset-react', { runtime: 'classic' }]],
  filename: 'dashboard.jsx',
});
process.stdout.write(result.code);
"""

def compile_jsx_with_node(jsx_src: str) -> str | None:
    """Node.js + Babel로 JSX 컴파일"""
    if not shutil.which("node"):
        return None

    # Babel 설치 확인
    babel_cache = os.path.join(LIB_CACHE_DIR, "node_modules/@babel/core")
    if not os.path.exists(babel_cache):
        print("  Babel 설치 중...")
        subprocess.run(
            ["npm", "install", "--prefix", LIB_CACHE_DIR,
             "@babel/core", "@babel/preset-react"],
            capture_output=True, timeout=120
        )

    try:
        # 임시 파일에 JSX 저장
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsx', delete=False) as tmp:
            tmp.write(jsx_src)
            tmp_path = tmp.name

        # 컴파일러 스크립트 생성
        compiler_path = os.path.join(LIB_CACHE_DIR, "_compile.js")
        with open(compiler_path, 'w') as f:
            f.write(f"process.chdir('{LIB_CACHE_DIR}');\n")
            f.write(_BABEL_SETUP_SCRIPT)

        result = subprocess.run(
            ["node", compiler_path, tmp_path],
            capture_output=True, text=True, timeout=60
        )
        os.unlink(tmp_path)

        if result.returncode == 0:
            return result.stdout
        else:
            print(f"  ⚠ Babel 컴파일 오류: {result.stderr[:300]}")
            return None
    except Exception as e:
        print(f"  ⚠ Node.js 컴파일 실패: {e}")
        return None

# ─────────────────────────────────────────────
# 3-B. JSX 변환 (Python — 폴백, Babel CDN 사용 모드)
# ─────────────────────────────────────────────
def transform_jsx_python(jsx_src: str) -> str:
    """
    Python 기반 간이 변환 (Babel CDN 모드에서 사용)
    - import React, ... from 'react' → const { ... } = React;
    - import { ... } from 'recharts' → const { ... } = Recharts;
    - export default function App → function App
    - 끝에 ReactDOM.createRoot 추가

    멀티라인 import 지원:
      import {
        A, B, C
      } from 'recharts';  ← 마지막 줄에 from이 있어도 처리됨
    """
    lines = jsx_src.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # import로 시작하는 줄을 멀티라인 포함해서 완전히 수집
        if line.strip().startswith("import "):
            combined = line
            # from '...' 또는 from "..." 이 나올 때까지 줄을 합친다
            while not re.search(r"from\s+['\"]", combined) and i + 1 < len(lines):
                i += 1
                combined += " " + lines[i].strip()

            combined_clean = combined.replace("\n", " ")

            if re.search(r"from\s+['\"]react['\"]", combined_clean):
                # React import → const { ... } = React;
                m = re.search(r'\{([^}]+)\}', combined_clean)
                if m:
                    hooks = [h.strip() for h in m.group(1).split(",") if h.strip()]
                    out.append(f"const {{ {', '.join(hooks)} }} = React;")
                # import React (without braces) also handled implicitly

            elif re.search(r"from\s+['\"]recharts['\"]", combined_clean):
                # Recharts import → const { ... } = Recharts;
                m = re.search(r'\{([^}]+)\}', combined_clean)
                if m:
                    exports = [h.strip() for h in m.group(1).split(",") if h.strip()]
                    out.append(f"const {{ {', '.join(exports)} }} = Recharts;")

            # 다른 import는 무시 (drop)
            i += 1
            continue

        if line.startswith("export default function"):
            line = line.replace("export default function", "function", 1)
        out.append(line)
        i += 1

    out.extend(["", "// ── 마운트 ──",
                 "const rootEl = document.getElementById('root');",
                 "try {",
                 "  ReactDOM.createRoot(rootEl).render(React.createElement(App, null));",
                 "} catch(e) {",
                 "  rootEl.innerHTML = '<pre style=\"color:#EF4444;padding:24px;font-size:14px\">' + e.message + '\\n' + e.stack + '</pre>';",
                 "  console.error('Dashboard mount error:', e);",
                 "}"])
    return "\n".join(out)

# ─────────────────────────────────────────────
# 4. HTML 조립
# ─────────────────────────────────────────────
def build_html(data: dict, tab8_today: list, js_content: str, libs: dict | None, use_babel_cdn: bool) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=str)
    data_json_safe = data_json.replace("</script>", "<\\/script>")
    kb = len(data_json_safe.encode()) / 1024
    print(f"  데이터 JSON: {kb:.0f} KB")

    # Tab8 today 데이터 JSON
    tab8_today_json = json.dumps({"slots": tab8_today}, ensure_ascii=False, separators=(',', ':'), default=str)
    tab8_today_json_safe = tab8_today_json.replace("</script>", "<\\/script>")
    tab8_kb = len(tab8_today_json_safe.encode()) / 1024
    print(f"  Tab8 Today JSON: {tab8_kb:.0f} KB")

    # 라이브러리 스크립트 블록
    if libs:
        lib_block = f"""
  <!-- React 18 (로컬) -->
  <script>{libs['react.js']}</script>
  <script>{libs['react-dom.js']}</script>
  <!-- PropTypes (로컬) -->
  <script>{libs['prop-types.js']}</script>
  <!-- Recharts 2 (로컬) -->
  <script>{libs['recharts.js']}</script>"""
    else:
        lib_block = """
  <!-- React 18 (CDN) -->
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <!-- PropTypes (CDN) -->
  <script src="https://unpkg.com/prop-types@15/prop-types.min.js"></script>
  <!-- Recharts 2 (CDN) -->
  <script src="https://unpkg.com/recharts@2.12.7/umd/Recharts.js"></script>"""

    # 컴포넌트 스크립트 블록
    if use_babel_cdn:
        # Babel CDN이 JSX를 런타임 컴파일
        component_block = f"""
  <!-- Babel standalone (CDN) -->
  <script src="https://unpkg.com/@babel/standalone@7.24.7/babel.min.js"></script>

  <!-- 대시보드 컴포넌트 (Babel 런타임 컴파일) -->
  <script type="text/babel" data-presets="react">
{js_content}
  </script>"""
    else:
        # 사전 컴파일된 JS (Babel 불필요)
        component_block = f"""
  <!-- 대시보드 컴포넌트 (사전 컴파일) -->
  <script>
{js_content}
  </script>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>⛳ 골프 가격 대시보드 V5.1</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Pretendard', 'Noto Sans KR', sans-serif; background: #0F172A; color: #E2E8F0; font-size: 15px; line-height: 1.5; }}
    ::-webkit-scrollbar {{ width: 6px; height: 10px; }}
    ::-webkit-scrollbar-track {{ background: #1a2f5a; border-radius: 5px; }}
    ::-webkit-scrollbar-thumb {{ background: #64748B; border-radius: 5px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}
    select, input, button {{ font-family: inherit; }}
    @media (max-width: 767px) {{
      body {{ font-size: 14px; }}
    }}
  </style>
</head>
<body>
  <div id="root"></div>

  <!-- 에러 핸들러 -->
  <script>
    window.onerror = function(msg, url, line, col, err) {{
      var root = document.getElementById('root');
      if (root && !root.innerHTML.trim()) {{
        root.innerHTML = '<pre style="color:#EF4444;padding:24px;font-size:14px">ERROR: ' + msg + '\\nLine: ' + line + ', Col: ' + col + '\\n' + (err && err.stack || '') + '</pre>';
      }}
      return false;
    }};
  </script>
{lib_block}

  <!-- 골프 데이터 주입 -->
  <script>
    window.__GOLF_DATA__ = {data_json_safe};
    window.__GOLF_TAB8_TODAY__ = {tab8_today_json_safe};
  </script>
{component_block}
</body>
</html>
"""
    return html

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    print("[build_dashboard V5]")

    # 1. V5 데이터
    print("1. DB 데이터 로드 (V5)...")
    data_v5 = build_data()
    latest_date = data_v5["metadata"]["latest_date"]
    all_dates = data_v5["metadata"]["all_dates"]
    print(f"   최신 수집일: {latest_date} | 전체 {len(all_dates)}개 날짜")

    # 1b. 데이터베이스 재연결하여 Tab8 파일 생성
    print("1b. 일자별 Tab8 JSON 생성...")
    db = conn()
    tab8_today = build_tab8_files(data_v5, db)
    db.close()
    print(f"   오늘 데이터: {len(tab8_today)} slots")

    # embed용 데이터 (Tab8 제외)
    data = make_embed_data(data_v5)

    # 2. 라이브러리
    print("2. 라이브러리 준비...")
    libs = ensure_libs()

    # 3. JSX 컴파일
    print("3. JSX 컴파일...")
    with open(JSX_PATH, "r", encoding="utf-8") as f:
        jsx_src = f.read()

    # JSX에서 import/export 제거 (Babel 사전컴파일 또는 CDN 공용)
    jsx_preprocessed = transform_jsx_python(jsx_src)

    compiled_js = None
    use_babel_cdn = False

    if shutil.which("node"):
        print("  Node.js 감지 → Babel 사전 컴파일 시도...")
        compiled_js = compile_jsx_with_node(jsx_preprocessed)
        if compiled_js:
            print(f"  ✓ Babel 컴파일 성공 ({len(compiled_js)} chars)")
        else:
            print("  Babel 컴파일 실패 → Babel CDN 모드 폴백")

    if compiled_js is None:
        print("  Babel CDN 모드 (런타임 컴파일)")
        compiled_js = jsx_preprocessed
        use_babel_cdn = True

    # 4. HTML 조립
    print("4. HTML 조립 (V5 다크테마)...")
    html = build_html(data, tab8_today, compiled_js, libs, use_babel_cdn)

    # 5. 저장
    with open(OUT_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = os.path.getsize(OUT_HTML_PATH) / 1024 / 1024
    mode = "오프라인 동작 가능" if (libs and not use_babel_cdn) else "인터넷 필요 (CDN 사용)"
    print(f"5. → {os.path.basename(OUT_HTML_PATH)} ({size_mb:.2f} MB) [{mode}]")
    date_files = ", ".join([f"golf_tab8_{d.replace('-', '')}.json" for d in all_dates])
    print(f"   → {date_files}")
    print(f"   → window.__GOLF_TAB8_TODAY__ 임베딩 (HTML 내부, {len(tab8_today)} slots)")
    print(f"   브라우저에서 열기: open {os.path.basename(OUT_HTML_PATH)}")


def build_all():
    """Entry point for run.py pipeline"""
    main()


if __name__ == "__main__":
    main()
