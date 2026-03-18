#!/usr/bin/env python3
"""VERHILL RADAR — 골프장 설정 (원클릭)"""
import json, os, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config", "courses.py")
JSX_PATH = os.path.join(SCRIPT_DIR, "golf_price_dashboard_v5.jsx")
COLORS = ["#6366F1","#0EA5E9","#10B981","#F59E0B","#EF4444","#8B5CF6","#EC4899","#14B8A6","#F97316","#06B6D4","#84CC16","#E11D48","#7C3AED","#0891B2","#CA8A04","#DC2626"]

def load_current():
    try:
        ns = {}; exec(open(CONFIG_PATH, encoding="utf-8").read(), ns)
        return ns.get("COURSES", [])
    except: return []

def save_config(names, colors):
    if os.path.exists(CONFIG_PATH):
        txt = open(CONFIG_PATH, encoding="utf-8").read()
        new = "COURSES = [\n" + "".join(f'    "{c}",\n' for c in names) + "]"
        txt = re.sub(r'COURSES\s*=\s*\[.*?\]', new, txt, count=1, flags=re.DOTALL) if re.search(r'COURSES\s*=\s*\[', txt) else new + "\n\n" + txt
        open(CONFIG_PATH, "w", encoding="utf-8").write(txt)
    if os.path.exists(JSX_PATH):
        jsx = open(JSX_PATH, encoding="utf-8").read()
        entries = ", ".join(f'"{c}": "{colors.get(c, COLORS[i%len(COLORS)])}"' for i, c in enumerate(names))
        jsx = re.sub(r'const COURSE_COLORS\s*=\s*\{.*?\};', f"const COURSE_COLORS = {{\n  {entries}\n}};", jsx, count=1, flags=re.DOTALL)
        open(JSX_PATH, "w", encoding="utf-8").write(jsx)

GOLF_DB = json.loads(r'''[{"name":"360도","detail":"경기 여주","region":"경기"},{"name":"H1 클럽","detail":"경기 이천","region":"경기"},{"name":"JNJ","detail":"전남 장흥","region":"전남"},{"name":"NEW 순창","detail":"전북 순창","region":"전북"},{"name":"SG아름다운","detail":"충남 아산","region":"충남"},{"name":"YJC골프클럽(구 여주)","detail":"경기 여주","region":"경기"},{"name":"가산(구 마이다스구미)","detail":"경북 칠곡","region":"경북"},{"name":"가야퍼블릭","detail":"경남 김해","region":"경남"},{"name":"가평베네스트","detail":"경기 가평","region":"경기"},{"name":"감곡","detail":"충북 음성","region":"충북"},{"name":"강남300","detail":"경기 광주","region":"경기"},{"name":"강동디아너스(구 블루원디아너스)","detail":"경북 경주","region":"경북"},{"name":"강화 웰빙","detail":"인천 강화","region":"인천"},{"name":"거제뷰","detail":"경남 거제","region":"경남"},{"name":"거창CC","detail":"경남 거창","region":"경남"},{"name":"경주","detail":"경북 경주","region":"경북"},{"name":"경주신라","detail":"경북 경주","region":"경북"},{"name":"고령오펠","detail":"경북 고령","region":"경북"},{"name":"고성","detail":"경남 고성","region":"경남"},{"name":"고성노벨","detail":"경남 고성","region":"경남"},{"name":"고창","detail":"전북 고창","region":"전북"},{"name":"골드","detail":"경기 용인","region":"경기"},{"name":"골드레이크","detail":"전남 나주","region":"전남"},{"name":"골드리버","detail":"충남 공주","region":"충남"},{"name":"골든베이","detail":"충남 태안","region":"충남"},{"name":"골프존카운티감포","detail":"경북 경주","region":"경북"},{"name":"골프존카운티경남","detail":"경남 함안","region":"경남"},{"name":"골프존카운티구미","detail":"경북 구미","region":"경북"},{"name":"골프존카운티더골프","detail":"울산 울산","region":"울산"},{"name":"골프존카운티드래곤","detail":"전북 남원","region":"전북"},{"name":"골프존카운티무주","detail":"전북 무주","region":"전북"},{"name":"골프존카운티사천","detail":"경남 사천","region":"경남"},{"name":"골프존카운티선산","detail":"경북 구미","region":"경북"},{"name":"골프존카운티선운","detail":"전북 고창","region":"전북"},{"name":"골프존카운티송도","detail":"경기 인천","region":"경기"},{"name":"골프존카운티순천","detail":"전남 순천","region":"전남"},{"name":"골프존카운티안성H","detail":"경기 안성","region":"경기"},{"name":"골프존카운티안성W","detail":"경기 안성","region":"경기"},{"name":"골프존카운티영암45_짐앵(2인전용)","detail":"전남 영암","region":"전남"},{"name":"골프존카운티영암45_카일","detail":"전남 영암","region":"전남"},{"name":"골프존카운티오라","detail":"제주 제주시","region":"제주"},{"name":"골프존카운티진천","detail":"충북 진천","region":"충북"},{"name":"골프존카운티천안","detail":"충남 천안","region":"충남"},{"name":"골프존카운티청통","detail":"경북 영천","region":"경북"},{"name":"골프존카운티화랑","detail":"충북 진천","region":"충북"},{"name":"골프클럽Q","detail":"경기 안성","region":"경기"},{"name":"광주","detail":"전남 곡성","region":"전남"},{"name":"구니","detail":"경북 군위","region":"경북"},{"name":"군산 (레귤러)","detail":"전북 군산","region":"전북"},{"name":"군산 (토너먼트)","detail":"전북 군산","region":"전북"},{"name":"군산(레귤러)","detail":"전북 군산","region":"전북"},{"name":"군산(토너먼트)","detail":"전북 군산","region":"전북"},{"name":"군위 칼레이트","detail":"경북 군위","region":"경북"},{"name":"군위오펠","detail":"경북 군위","region":"경북"},{"name":"군위칼레이트CC","detail":"경북 군위","region":"경북"},{"name":"그랜드(청주)","detail":"충북 청주","region":"충북"},{"name":"그레이스","detail":"대구 대구권","region":"대구"},{"name":"그린필드","detail":"제주 제주","region":"제주"},{"name":"그린힐","detail":"경기 광주","region":"경기"},{"name":"글렌로스","detail":"경기 용인","region":"경기"},{"name":"금강","detail":"경기 여주","region":"경기"},{"name":"금산에딘버러","detail":"충남 금산","region":"충남"},{"name":"기장동원로얄","detail":"부산 기장","region":"부산"},{"name":"김제스파힐스","detail":"전북 김제","region":"전북"},{"name":"김포씨사이드","detail":"경기 김포","region":"경기"},{"name":"남서울","detail":"경기 성남","region":"경기"},{"name":"남안동","detail":"경북 안동","region":"경북"},{"name":"남양주","detail":"경기 남양주","region":"경기"},{"name":"남여주","detail":"경기 여주","region":"경기"},{"name":"남원상록","detail":"전북 남원","region":"전북"},{"name":"남춘천","detail":"강원 춘천","region":"강원"},{"name":"내장산","detail":"전북 정읍","region":"전북"},{"name":"내포골프클럽","detail":"충남 예산","region":"충남"},{"name":"노스팜","detail":"경기 파주","region":"경기"},{"name":"뉴서울","detail":"경기 광주","region":"경기"},{"name":"뉴스프링빌","detail":"경기 이천","region":"경기"},{"name":"뉴스프링빌2","detail":"경북 상주","region":"경북"},{"name":"뉴코리아","detail":"경기 고양","region":"경기"},{"name":"다산베아채","detail":"전남 강진","region":"전남"},{"name":"다이아몬드","detail":"경남 양산","region":"경남"},{"name":"담양레이나","detail":"전남 담양","region":"전남"},{"name":"대가야","detail":"경북 고령","region":"경북"},{"name":"대구","detail":"경북 경산","region":"경북"},{"name":"대영베이스","detail":"충북 충주","region":"충북"},{"name":"대영힐스","detail":"충북 충주","region":"충북"},{"name":"대호단양","detail":"충북 단양","region":"충북"},{"name":"더나인","detail":"전북 김제","region":"전북"},{"name":"더반","detail":"경기 이천","region":"경기"},{"name":"더시에나","detail":"제주 제주","region":"제주"},{"name":"더시에나벨루토 (구 세라지오)","detail":"경기 여주","region":"경기"},{"name":"더시에나서울(구 중부)","detail":"경기 광주","region":"경기"},{"name":"더크로스비","detail":"경기 이천","region":"경기"},{"name":"더헤븐","detail":"경기 안산","region":"경기"},{"name":"더힐","detail":"충남 논산","region":"충남"},{"name":"동강시스타","detail":"강원 영월","region":"강원"},{"name":"동래베네스트","detail":"부산 금정","region":"부산"},{"name":"동부산","detail":"경남 양산","region":"경남"},{"name":"동서울컨트리클럽","detail":"강원 원주","region":"강원"},{"name":"동전주써미트","detail":"전북 진안","region":"전북"},{"name":"동촌","detail":"충북 충주","region":"충북"},{"name":"드비치","detail":"경남 거제","region":"경남"},{"name":"디오션","detail":"전남 여수","region":"전남"},{"name":"떼제베","detail":"충북 청주","region":"충북"},{"name":"라데나","detail":"강원 춘천","region":"강원"},{"name":"라비돌","detail":"경기 화성","region":"경기"},{"name":"라비에벨듄스","detail":"강원 춘천","region":"강원"},{"name":"라비에벨올드","detail":"강원 춘천","region":"강원"},{"name":"라싸","detail":"경기 포천","region":"경기"},{"name":"라온","detail":"제주 제주","region":"제주"},{"name":"라헨느","detail":"제주 제주","region":"제주"},{"name":"락가든","detail":"경기 포천권","region":"경기"},{"name":"레이크사이드","detail":"경기 용인","region":"경기"},{"name":"레이크우드","detail":"경기 양주","region":"경기"},{"name":"로드힐스","detail":"강원 춘천","region":"강원"},{"name":"로얄포레","detail":"충북 충주","region":"충북"},{"name":"로제비앙","detail":"경기 광주","region":"경기"},{"name":"롯데스카이힐부여","detail":"충남 부여","region":"충남"},{"name":"롯데스카이힐부여(9홀)","detail":"충남 부여","region":"충남"},{"name":"롯데스카이힐제주","detail":"제주 서귀포","region":"제주"},{"name":"루트52","detail":"경기 여주","region":"경기"},{"name":"르오네뜨","detail":"전남 곡성","region":"전남"},{"name":"리더스","detail":"경남 밀양","region":"경남"},{"name":"리앤리","detail":"경기 가평","region":"경기"},{"name":"링크나인","detail":"경기 화성","region":"경기"},{"name":"마론","detail":"충남 천안","region":"충남"},{"name":"마스터피스","detail":"경북 고령","region":"경북"},{"name":"마에스트로","detail":"경기 안성","region":"경기"},{"name":"마우나오션","detail":"경북 경주","region":"경북"},{"name":"마이다스레이크이천","detail":"경기 이천","region":"경기"},{"name":"메이플비치","detail":"강원 동해권","region":"강원"},{"name":"몽베르","detail":"경기 포천","region":"경기"},{"name":"무등산","detail":"전남 화순","region":"전남"},{"name":"무안클린밸리","detail":"전남 무안","region":"전남"},{"name":"무주덕유산","detail":"전북 무주","region":"전북"},{"name":"문경","detail":"경북 문경","region":"경북"},{"name":"밀양노벨","detail":"경남 밀양","region":"경남"},{"name":"발리오스","detail":"경기 화성","region":"경기"},{"name":"백양우리","detail":"전남 장성","region":"전남"},{"name":"백제","detail":"충남 부여","region":"충남"},{"name":"베뉴지","detail":"경기 가평","region":"경기"},{"name":"베르힐","detail":"전남 함평","region":"전남"},{"name":"베르힐CC영종","detail":"인천 중구","region":"인천"},{"name":"베르힐영종","detail":"경기 인천","region":"경기"},{"name":"베스트밸리","detail":"경기 파주","region":"경기"},{"name":"베이사이드골프클럽","detail":"부산 부산","region":"부산"},{"name":"베이스타즈","detail":"울산 북구","region":"울산"},{"name":"벨라45","detail":"강원 횡성","region":"강원"},{"name":"벨라스톤","detail":"강원 횡성","region":"강원"},{"name":"보라","detail":"울산 울주","region":"울산"},{"name":"보령베이스","detail":"충남 보령","region":"충남"},{"name":"보문","detail":"경북 경주","region":"경북"},{"name":"보성","detail":"전남 보성","region":"전남"},{"name":"볼카노(구 클럽L)","detail":"제주 서귀포","region":"제주"},{"name":"부곡","detail":"경남 창녕","region":"경남"},{"name":"부산","detail":"부산 금정","region":"부산"},{"name":"블랙밸리","detail":"강원 삼척","region":"강원"},{"name":"블랙스톤 벨포레","detail":"충북 증평","region":"충북"},{"name":"블랙스톤벨포레","detail":"충북 증평","region":"충북"},{"name":"블랙스톤제주","detail":"제주 제주","region":"제주"},{"name":"블루원상주","detail":"경북 상주","region":"경북"},{"name":"블루원용인","detail":"경기 용인","region":"경기"},{"name":"블루헤런","detail":"경기 여주","region":"경기"},{"name":"비에이비스타","detail":"경기 이천","region":"경기"},{"name":"비에이비스타(대중제)","detail":"경기 이천","region":"경기"},{"name":"비콘힐스","detail":"강원 홍천","region":"강원"},{"name":"빅토리아","detail":"경기 여주","region":"경기"},{"name":"사우스스프링스","detail":"경기 이천","region":"경기"},{"name":"사우스케이프 오너스 클럽","detail":"경남 남해","region":"경남"},{"name":"사이프러스","detail":"제주 서귀포","region":"제주"},{"name":"삼삼","detail":"경남 사천","region":"경남"},{"name":"샌드파인","detail":"강원 강릉","region":"강원"},{"name":"샤인데일","detail":"강원 홍천","region":"강원"},{"name":"샤인빌파크","detail":"제주 서귀포","region":"제주"},{"name":"샴발라","detail":"경기 포천","region":"경기"},{"name":"서귀포팬텀(구 우리들)","detail":"제주 서귀포","region":"제주"},{"name":"서라벌","detail":"경북 경주권","region":"경북"},{"name":"서산수","detail":"충남 서산","region":"충남"},{"name":"서서울","detail":"경기 파주","region":"경기"},{"name":"서울한양","detail":"경기 파주","region":"경기"},{"name":"서원힐스","detail":"경기 파주","region":"경기"},{"name":"석정힐","detail":"전북 고창","region":"전북"},{"name":"성문안","detail":"강원 원주","region":"강원"},{"name":"세레니티","detail":"충북 청주","region":"충북"},{"name":"세레니티 강촌(구 파가니카)","detail":"강원 춘천","region":"강원"},{"name":"세레니티강촌(구 파가니카)","detail":"강원 춘천","region":"강원"},{"name":"세븐밸리","detail":"경북 칠곡","region":"경북"},{"name":"세이지우드 여수경도","detail":"전남 여수","region":"전남"},{"name":"세이지우드 홍천","detail":"강원 홍천","region":"강원"},{"name":"세이지우드홍천","detail":"강원 홍천","region":"강원"},{"name":"세일","detail":"충북 충주","region":"충북"},{"name":"세종레이캐슬","detail":"세종 전의","region":"세종"},{"name":"세현","detail":"경기 용인","region":"경기"},{"name":"센추리21","detail":"강원 원주","region":"강원"},{"name":"센테리움","detail":"충북 충주","region":"충북"},{"name":"소노펠리체CC 델피노","detail":"강원 고성","region":"강원"},{"name":"소노펠리체CC 마운틴","detail":"강원 홍천","region":"강원"},{"name":"소노펠리체CC 웨스트","detail":"강원 홍천","region":"강원"},{"name":"소노펠리체CC 이스트","detail":"강원 홍천","region":"강원"},{"name":"속리산","detail":"충북 보은","region":"충북"},{"name":"솔라고","detail":"충남 태안","region":"충남"},{"name":"솔라시도","detail":"전남 해남","region":"전남"},{"name":"솔트베이","detail":"경기 시흥","region":"경기"},{"name":"수서골프앤리조트","detail":"경북 군위","region":"경북"},{"name":"수원","detail":"경기 용인","region":"경기"},{"name":"순천 CC","detail":"전남 순천","region":"전남"},{"name":"순천부영","detail":"전남 순천","region":"전남"},{"name":"스마트KU","detail":"경기 파주","region":"경기"},{"name":"스카이밸리","detail":"경기 여주","region":"경기"},{"name":"스카이뷰","detail":"경남 함양","region":"경남"},{"name":"스타","detail":"충북 충주","region":"충북"},{"name":"스톤게이트","detail":"부산 부산","region":"부산"},{"name":"스톤비치","detail":"충남 태안","region":"충남"},{"name":"스프링베일","detail":"강원 춘천","region":"강원"},{"name":"시그너스","detail":"충북 충주","region":"충북"},{"name":"시엘","detail":"경북 영천","region":"경북"},{"name":"신안","detail":"경기 안성","region":"경기"},{"name":"실크밸리","detail":"경기 이천","region":"경기"},{"name":"써닝포인트","detail":"경기 용인","region":"경기"},{"name":"썬힐","detail":"경기 가평","region":"경기"},{"name":"아난티 중앙","detail":"충북 충주","region":"충북"},{"name":"아난티중앙","detail":"충북 진천","region":"충북"},{"name":"아델스코트","detail":"경남 합천","region":"경남"},{"name":"아도니스","detail":"경기 포천","region":"경기"},{"name":"아리스타","detail":"충남 논산","region":"충남"},{"name":"아리지","detail":"경기 여주","region":"경기"},{"name":"아세코밸리","detail":"경기 시흥","region":"경기"},{"name":"아크로","detail":"전남 영암","region":"전남"},{"name":"안강레전드","detail":"경북 경주","region":"경북"},{"name":"안동레이크","detail":"경북 안동","region":"경북"},{"name":"안동리버힐","detail":"경북 안동","region":"경북"},{"name":"안성","detail":"경기 안성","region":"경기"},{"name":"알펜시아","detail":"강원 평창","region":"강원"},{"name":"알펜시아700","detail":"강원 평창","region":"강원"},{"name":"알펜시아700GC","detail":"강원 평창","region":"강원"},{"name":"알프스대영","detail":"강원 횡성","region":"강원"},{"name":"애플밸리","detail":"경북 김천","region":"경북"},{"name":"양산","detail":"경남 양산","region":"경남"},{"name":"양산동원로얄","detail":"경남 양산","region":"경남"},{"name":"양주","detail":"경기 남양주","region":"경기"},{"name":"양지파인","detail":"경기 용인","region":"경기"},{"name":"양평TPC","detail":"경기 양평","region":"경기"},{"name":"어등산","detail":"광주 광산","region":"광주"},{"name":"에덴밸리","detail":"경남 양산","region":"경남"},{"name":"에덴블루","detail":"경기 안성","region":"경기"},{"name":"에딘버러","detail":"충남 금산","region":"충남"},{"name":"에버리스","detail":"제주 제주","region":"제주"},{"name":"에스앤골프클럽","detail":"충남 보령","region":"충남"},{"name":"에이원","detail":"경남 양산","region":"경남"},{"name":"에코랜드","detail":"제주 제주","region":"제주"},{"name":"엘리시안강촌","detail":"강원 춘천","region":"강원"},{"name":"엘리시안제주","detail":"제주 제주","region":"제주"},{"name":"엠스클럽의성","detail":"경북 의성","region":"경북"},{"name":"여수시티파크","detail":"전남 여수","region":"전남"},{"name":"여주","detail":"경기 여주","region":"경기"},{"name":"여주신라","detail":"경기 여주","region":"경기"},{"name":"여주썬밸리","detail":"경기 여주","region":"경기"},{"name":"영랑호","detail":"강원 속초","region":"강원"},{"name":"영천오펠골프클럽","detail":"경북 영천","region":"경북"},{"name":"오너스","detail":"강원 춘천","region":"강원"},{"name":"오렌지듄스 영종","detail":"인천 중구","region":"인천"},{"name":"오렌지듄스영종","detail":"경기 인천","region":"경기"},{"name":"오로라","detail":"강원 원주","region":"강원"},{"name":"오르비스","detail":"울산 울주","region":"울산"},{"name":"오션비치","detail":"경북 영덕","region":"경북"},{"name":"오션힐스영천","detail":"경북 영천","region":"경북"},{"name":"오션힐스청도","detail":"경북 청도","region":"경북"},{"name":"오션힐스포항","detail":"경북 포항","region":"경북"},{"name":"오창에딘버러","detail":"충북 오창","region":"충북"},{"name":"오크밸리","detail":"강원 원주","region":"강원"},{"name":"오크힐스","detail":"강원 원주","region":"강원"},{"name":"옥스필드","detail":"강원 횡성","region":"강원"},{"name":"올데이","detail":"충북 충주","region":"충북"},{"name":"올데이 골프리조트","detail":"충북 충주","region":"충북"},{"name":"올림픽","detail":"경기 고양","region":"경기"},{"name":"용원","detail":"경남 창원","region":"경남"},{"name":"용인","detail":"경기 용인","region":"경기"},{"name":"용평","detail":"강원 평창","region":"강원"},{"name":"울산","detail":"울산 울주","region":"울산"},{"name":"울진마린","detail":"경북 울진","region":"경북"},{"name":"웅포","detail":"전북 익산","region":"전북"},{"name":"월송리","detail":"강원 원주","region":"강원"},{"name":"웨스트오션","detail":"전남 영광","region":"전남"},{"name":"웰리힐리","detail":"강원 횡성","region":"강원"},{"name":"윈체스트안성","detail":"경기 안성","region":"경기"},{"name":"유니아일랜드","detail":"인천 강화","region":"인천"},{"name":"유성","detail":"대전 유성","region":"대전"},{"name":"은화삼","detail":"경기 용인","region":"경기"},{"name":"음성힐데스하임","detail":"충북 음성","region":"충북"},{"name":"의령리온","detail":"경남 의령","region":"경남"},{"name":"이글몬트","detail":"경기 안성","region":"경기"},{"name":"이븐데일","detail":"충북 청주","region":"충북"},{"name":"이스턴","detail":"경북 포항","region":"경북"},{"name":"이지스카이","detail":"경북 군위","region":"경북"},{"name":"이천실크밸리","detail":"경기 이천","region":"경기"},{"name":"이포","detail":"경기 여주","region":"경기"},{"name":"익산(구 상떼힐익산)","detail":"전북 익산","region":"전북"},{"name":"인서울27","detail":"서울 강서","region":"서울"},{"name":"인천그랜드","detail":"인천 서구","region":"인천"},{"name":"인터불고원주","detail":"강원 원주","region":"강원"},{"name":"일라이트","detail":"충북 영동","region":"충북"},{"name":"일레븐","detail":"충북 충주","region":"충북"},{"name":"일산스프링힐스","detail":"경기 고양","region":"경기"},{"name":"임페리얼레이크","detail":"충북 충주","region":"충북"},{"name":"자유","detail":"경기 여주","region":"경기"},{"name":"자유로","detail":"경기 연천","region":"경기"},{"name":"장수","detail":"전북 장수","region":"전북"},{"name":"전주샹그릴라","detail":"전북 임실","region":"전북"},{"name":"정산","detail":"경남 김해","region":"경남"},{"name":"제이퍼블릭","detail":"경기 파주","region":"경기"},{"name":"제주부영","detail":"제주 서귀포","region":"제주"},{"name":"제주아덴힐","detail":"제주 제주","region":"제주"},{"name":"젠스필드","detail":"충북 음성","region":"충북"},{"name":"조아밸리","detail":"전남 화순","region":"전남"},{"name":"죽향","detail":"전남 담양","region":"전남"},{"name":"중원","detail":"충북 충주","region":"충북"},{"name":"진양밸리","detail":"충북 음성","region":"충북"},{"name":"천룡","detail":"충북 진천","region":"충북"},{"name":"천안상록","detail":"충남 천안","region":"충남"},{"name":"천지","detail":"전남 함평","region":"전남"},{"name":"청주그랜드","detail":"충북 청주","region":"충북"},{"name":"칠곡아이위시(카트불포함)","detail":"경북 칠곡","region":"경북"},{"name":"카스카디아","detail":"강원 홍천","region":"강원"},{"name":"캐슬렉스제주","detail":"제주 서귀포","region":"제주"},{"name":"캐슬파인","detail":"경기 여주","region":"경기"},{"name":"코리아","detail":"경기 용인","region":"경기"},{"name":"코브스윙(구 참밸리)","detail":"경기 포천","region":"경기"},{"name":"코스모스링스","detail":"전남 영암","region":"전남"},{"name":"코스카","detail":"충북 음성","region":"충북"},{"name":"코오롱가든","detail":"경북 경주","region":"경북"},{"name":"크라운","detail":"제주 제주","region":"제주"},{"name":"크리스밸리","detail":"경기 안성","region":"경기"},{"name":"크리스탈밸리","detail":"경기 가평","region":"경기"},{"name":"클럽72(구 스카이72)","detail":"경기 인천","region":"경기"},{"name":"클럽디 더플레이어스","detail":"강원 춘천","region":"강원"},{"name":"클럽디거창","detail":"경남 거창","region":"경남"},{"name":"클럽디더플레이어스","detail":"강원 춘천","region":"강원"},{"name":"클럽디보은","detail":"충북 보은","region":"충북"},{"name":"클럽모우","detail":"강원 홍천","region":"강원"},{"name":"킹스데일","detail":"충북 충주","region":"충북"},{"name":"킹즈락","detail":"충북 제천","region":"충북"},{"name":"타이거","detail":"경기 파주","region":"경기"},{"name":"태광","detail":"경기 용인","region":"경기"},{"name":"태광(P9)퍼블릭","detail":"경기 용인","region":"경기"},{"name":"태기산","detail":"강원 평창","region":"강원"},{"name":"태인","detail":"전북 정읍","region":"전북"},{"name":"테디밸리","detail":"제주 서귀포","region":"제주"},{"name":"통영동원로얄","detail":"경남 통영","region":"경남"},{"name":"파나시아","detail":"충남 당진","region":"충남"},{"name":"파라지오","detail":"경북 의성","region":"경북"},{"name":"파미힐스","detail":"대구 대구권","region":"대구"},{"name":"파인리즈골프앤리조트","detail":"강원 고성","region":"강원"},{"name":"파인밸리","detail":"강원 삼척","region":"강원"},{"name":"파인비치","detail":"전남 해남","region":"전남"},{"name":"파인스톤","detail":"충남 당진","region":"충남"},{"name":"파인크리크","detail":"경기 안성","region":"경기"},{"name":"파인파크 AT 군산 파3","detail":"전북 군산","region":"전북"},{"name":"파인힐스","detail":"전남 순천","region":"전남"},{"name":"파인힐스골프&호텔","detail":"전남 순천","region":"전남"},{"name":"파주","detail":"경기 파주","region":"경기"},{"name":"파크밸리","detail":"강원 원주","region":"강원"},{"name":"팔공","detail":"대구 대구","region":"대구"},{"name":"페럼","detail":"경기 여주","region":"경기"},{"name":"펜타뷰","detail":"경북 청도","region":"경북"},{"name":"포도","detail":"경북 김천","region":"경북"},{"name":"포라이즌(구 승주)","detail":"전남 순천","region":"전남"},{"name":"포레스트힐","detail":"경기 포천","region":"경기"},{"name":"포세븐금강CC(구 클럽디금강)","detail":"전북 익산","region":"전북"},{"name":"포세븐금강_(구 클럽디금강)","detail":"전북 익산","region":"전북"},{"name":"포웰CC 김해","detail":"경남 김해","region":"경남"},{"name":"포웰CC김해(구 스카이힐김해)","detail":"경남 김해","region":"경남"},{"name":"포웰CC안성","detail":"경기 안성","region":"경기"},{"name":"포천아도니스","detail":"경기 포천","region":"경기"},{"name":"포천아도니스(9홀)","detail":"경기 포천","region":"경기"},{"name":"포천힐스","detail":"경기 포천","region":"경기"},{"name":"포항","detail":"경북 포항","region":"경북"},{"name":"푸른솔장성","detail":"전남 장성","region":"전남"},{"name":"푸른솔포천","detail":"경기 포천","region":"경기"},{"name":"프리스틴밸리","detail":"경기 가평","region":"경기"},{"name":"프린세스","detail":"충남 공주","region":"충남"},{"name":"플라밍고","detail":"충남 당진","region":"충남"},{"name":"플라자CC 제주","detail":"제주 제주","region":"제주"},{"name":"플라자CC설악","detail":"강원 속초","region":"강원"},{"name":"플라자CC용인","detail":"경기 용인","region":"경기"},{"name":"플라자CC제주","detail":"제주 제주시","region":"제주"},{"name":"플라자설악","detail":"강원 속초","region":"강원"},{"name":"플라자용인","detail":"경기 용인","region":"경기"},{"name":"필로스","detail":"경기 포천","region":"경기"},{"name":"하동골프클럽","detail":"경남 하동","region":"경남"},{"name":"하이원","detail":"강원 정선","region":"강원"},{"name":"한림광릉","detail":"경기 남양주","region":"경기"},{"name":"한림안성","detail":"경기 안성","region":"경기"},{"name":"한림용인","detail":"경기 용인","region":"경기"},{"name":"한맥","detail":"경북 예천","region":"경북"},{"name":"한미르대덕","detail":"대전 유성","region":"대전"},{"name":"한성","detail":"경기 용인","region":"경기"},{"name":"한양파인","detail":"경기 고양","region":"경기"},{"name":"한원","detail":"경기 용인","region":"경기"},{"name":"한탄강","detail":"강원 철원","region":"강원"},{"name":"함양스카이뷰","detail":"경남 함양","region":"경남"},{"name":"함평엘리체","detail":"전남 함평","region":"전남"},{"name":"해내다CC","detail":"경북 경산","region":"경북"},{"name":"해비치제주","detail":"제주 서귀포","region":"제주"},{"name":"해비치컨트리클럽 제주","detail":"제주 서귀포","region":"제주"},{"name":"해솔리아","detail":"경기 용인","region":"경기"},{"name":"해운대","detail":"부산 기장","region":"부산"},{"name":"해운대비치","detail":"부산 기장","region":"부산"},{"name":"해운대비치9골프클럽","detail":"부산 기장","region":"부산"},{"name":"해운대비치퍼블릭골프클럽","detail":"부산 부산","region":"부산"},{"name":"해피니스","detail":"전남 나주","region":"전남"},{"name":"화성","detail":"경기 화성","region":"경기"},{"name":"화성GC","detail":"경기 화성","region":"경기"},{"name":"화성상록","detail":"경기 화성","region":"경기"},{"name":"화순","detail":"전남 화순","region":"전남"},{"name":"화순엘리체","detail":"전남 화순","region":"전남"},{"name":"휘닉스","detail":"강원 평창","region":"강원"},{"name":"히든밸리","detail":"충북 진천","region":"충북"},{"name":"힐데스하임 음성 노캐디","detail":"충북 음성","region":"충북"},{"name":"힐드로사이","detail":"강원 홍천","region":"강원"},{"name":"힐마루","detail":"경남 창녕","region":"경남"},{"name":"힐마루 포천","detail":"경기 포천","region":"경기"},{"name":"힐마루포천","detail":"경기 포천","region":"경기"},{"name":"힐스카이(구 루나엑스)","detail":"경북 경주","region":"경북"}]''')

HTML = r'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>골프장 설정 — VERHILL RADAR</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,'Pretendard',sans-serif;background:#0B1120;color:#E2E8F0;min-height:100vh}
.hd{background:linear-gradient(135deg,#1E293B,#0F172A);border-bottom:1px solid #1E3A5F;padding:24px 28px;display:flex;align-items:center;gap:16px}
.hd h1{font-size:20px;font-weight:800}.hd h1 b{color:#4F46E5}
.hd .badge{background:#4F46E520;color:#4F46E5;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:600}
.wrap{display:flex;max-width:1100px;margin:0 auto;padding:24px;gap:20px;min-height:calc(100vh - 80px)}
@media(max-width:768px){.wrap{flex-direction:column}}
.left{flex:1;min-width:0}.right{width:340px;flex-shrink:0}
@media(max-width:768px){.right{width:100%}}
.card{background:#1E293B;border:1px solid #334155;border-radius:14px;padding:20px;margin-bottom:16px}
.card-t{font-size:14px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.card-t .cnt{margin-left:auto;color:#64748B;font-size:12px}
.sb{display:flex;gap:8px}
.sb input{flex:1;padding:12px 16px;border-radius:10px;border:1px solid #334155;background:#0F172A;color:#E2E8F0;font-size:14px;outline:none}
.sb input:focus{border-color:#4F46E5;box-shadow:0 0 0 3px #4F46E520}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin:12px 0}
.tag{padding:6px 12px;border-radius:16px;border:1px solid #334155;background:transparent;color:#94A3B8;font-size:11px;cursor:pointer;transition:all .15s}
.tag:hover,.tag.on{border-color:#4F46E5;color:#E2E8F0;background:#4F46E515}
.tag.on{background:#4F46E530;color:#fff}
.list{max-height:calc(100vh - 340px);overflow-y:auto;scrollbar-width:thin;scrollbar-color:#334155 transparent}
.list::-webkit-scrollbar{width:5px}.list::-webkit-scrollbar-thumb{background:#334155;border-radius:3px}
.it{display:flex;align-items:center;padding:11px 14px;border-radius:10px;cursor:pointer;gap:10px;transition:background .12s}
.it:hover{background:#33415580}
.it.off{opacity:.3;pointer-events:none}
.it-i{flex:1;min-width:0}.it-n{font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.it-d{color:#64748B;font-size:11px;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.it-b{padding:5px 14px;border-radius:7px;border:1px solid #4F46E5;background:transparent;color:#4F46E5;font-size:11px;font-weight:600;cursor:pointer;flex-shrink:0;transition:all .12s}
.it-b:hover{background:#4F46E520}.it-b.x{border-color:#334155;color:#475569;pointer-events:none}
.si{display:flex;align-items:center;gap:8px;padding:10px 14px;background:#0F172A;border:1px solid #334155;border-radius:10px;margin-bottom:6px;transition:all .2s}
.si:hover{border-color:#475569}
.si .dot{width:16px;height:16px;border-radius:50%;border:2px solid #fff3;cursor:pointer;flex-shrink:0;transition:transform .12s}
.si .dot:hover{transform:scale(1.2)}
.si .sn{flex:1;font-weight:600;font-size:13px}
.si .sx{width:24px;height:24px;border-radius:5px;border:none;background:0;color:#475569;font-size:14px;cursor:pointer;display:flex;align-items:center;justify-content:center}
.si .sx:hover{background:#EF444420;color:#EF4444}
.arrow{width:22px;height:22px;border-radius:4px;border:1px solid #334155;background:0;color:#64748B;font-size:11px;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;transition:all .12s}
.arrow:hover:not(:disabled){background:#33415580;color:#E2E8F0}.arrow:disabled{opacity:.2;cursor:default}
.clr-btn{padding:8px 14px;border-radius:8px;border:1px solid #EF4444;background:0;color:#EF4444;font-size:11px;font-weight:600;cursor:pointer;transition:all .15s;margin-top:8px}
.clr-btn:hover{background:#EF444415}
.si .idx{color:#475569;font-size:11px;width:18px;text-align:center}
.mr{display:flex;gap:8px;margin-top:10px}
.mr input{flex:1;padding:10px 14px;border-radius:8px;border:1px solid #334155;background:#0F172A;color:#E2E8F0;font-size:13px;outline:none}
.mr input:focus{border-color:#10B981}
.mr button{padding:10px 16px;border-radius:8px;border:1px solid #10B981;background:0;color:#10B981;font-size:12px;font-weight:600;cursor:pointer}
.mr button:hover{background:#10B98115}
.sv{padding:14px 0;border-radius:10px;border:none;background:#10B981;color:#fff;font-size:15px;font-weight:700;cursor:pointer;width:100%;transition:all .2s;margin-top:10px}
.sv:hover{background:#059669;transform:translateY(-1px);box-shadow:0 4px 15px #10B98140}
.sv:disabled{background:#334155;transform:none;box-shadow:none;cursor:not-allowed}
.empty{color:#475569;font-size:13px;text-align:center;padding:30px 16px}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%) translateY(60px);background:#1E293B;border:1px solid #334155;color:#E2E8F0;padding:12px 24px;border-radius:10px;font-weight:600;font-size:13px;z-index:100;box-shadow:0 8px 30px rgba(0,0,0,.4);transition:all .3s;opacity:0;pointer-events:none}
.toast.show{transform:translateX(-50%) translateY(0);opacity:1}
.done{text-align:center;padding:32px 20px}
.done em{font-size:48px;display:block;margin-bottom:12px;font-style:normal}
.done h2{font-size:20px;font-weight:800;margin-bottom:8px}
.done p{color:#94A3B8;font-size:13px;line-height:1.7}
.code{background:#0F172A;border:1px solid #334155;border-radius:10px;padding:16px;font-family:'SF Mono',monospace;font-size:12px;color:#94A3B8;line-height:1.8;white-space:pre-wrap;margin-top:16px;text-align:left}
.code b{color:#E2E8F0}
</style></head><body>
<div class="hd"><h1><b>VERHILL</b> RADAR</h1><span class="badge">골프장 설정</span></div>
<div class="wrap">
<div class="left">
  <div class="card">
    <div class="card-t">🔍 골프장 검색 <span class="cnt" id="rc"></span></div>
    <div class="sb"><input id="q" placeholder="이름 또는 지역으로 검색" oninput="filter()" autofocus /></div>
    <div class="tags" id="tags"></div>
  </div>
  <div class="card"><div class="card-t">📋 골프장 목록 <span class="cnt" id="fc"></span></div><div class="list" id="list"></div></div>
</div>
<div class="right">
  <div class="card">
    <div class="card-t">⛳ 선택 목록 <span class="cnt" id="sc"></span></div>
    <div id="sel"></div>
    <div class="mr"><input id="mi" placeholder="골프장명 직접 입력" /><button onclick="addM()">+ 추가</button></div>
    <button class="clr-btn" onclick="clearAll()">🗑 전체 초기화</button>
  </div>
  <button class="sv" id="svb" onclick="doSave()" disabled>💾 저장</button>
  <div id="doneArea" style="display:none"></div>
</div>
</div>
<div class="toast" id="toast"></div>
<script>
const C=["#6366F1","#0EA5E9","#10B981","#F59E0B","#EF4444","#8B5CF6","#EC4899","#14B8A6","#F97316","#06B6D4","#84CC16","#E11D48","#7C3AED","#0891B2","#CA8A04","#DC2626"];
let db=[],sel=[],activeTag='';
fetch('/api/db').then(r=>r.json()).then(d=>{db=d;filter()});
fetch('/api/current').then(r=>r.json()).then(d=>{(d.courses||[]).forEach((n,i)=>sel.push({name:n,color:C[i%C.length]}));renderSel()});

const regions=["전체","경기","강원","경북","전남","제주","충북","경남","전북","충남","부산","인천","울산","대전","서울","세종","광주"];
document.getElementById('tags').innerHTML=regions.map(r=>`<button class="tag${r==='전체'?' on':''}" onclick="toggleTag('${r}')">${r}</button>`).join('');
document.getElementById('mi').addEventListener('keydown',e=>{if(e.key==='Enter')addM()});

function toggleTag(r){
  activeTag=r==='전체'?'':r;
  document.querySelectorAll('.tag').forEach(t=>t.classList.toggle('on',t.textContent===r));
  filter();
}
function filter(){
  const q=document.getElementById('q').value.trim().toLowerCase();
  const added=new Set(sel.map(s=>s.name));
  let filtered=db.filter(c=>{
    if(activeTag&&c.region!==activeTag)return false;
    if(q&&!c.name.toLowerCase().includes(q)&&!(c.detail||'').toLowerCase().includes(q))return false;
    return true;
  });
  document.getElementById('fc').textContent=filtered.length+'/'+db.length+'개';
  const el=document.getElementById('list');
  if(!filtered.length){el.innerHTML='<div class="empty">검색 결과 없음</div>';return}
  el.innerHTML=filtered.map(c=>{
    const has=added.has(c.name);
    return `<div class="it${has?' off':''}" onclick="${has?'':`add('${esc(c.name)}')`}"><div class="it-i"><div class="it-n">${c.name}</div><div class="it-d">${c.detail||''}</div></div><button class="it-b${has?' x':''}">${has?'✓':'+ 추가'}</button></div>`;
  }).join('');
}
function add(n){if(sel.find(s=>s.name===n))return;sel.push({name:n,color:C[sel.length%C.length]});renderSel();filter();toast('✅ '+n)}
function rem(n){sel=sel.filter(s=>s.name!==n);sel.forEach((s,i)=>s.color=C[i%C.length]);renderSel();filter()}
function mv(i,dir){const j=i+dir;if(j<0||j>=sel.length)return;[sel[i],sel[j]]=[sel[j],sel[i]];sel.forEach((s,k)=>s.color=C[k%C.length]);renderSel()}
function clearAll(){if(!sel.length)return;if(!confirm(sel.length+'개 골프장을 모두 제거할까요?'))return;sel=[];renderSel();filter();toast('🗑 전체 초기화')}
function addM(){const v=document.getElementById('mi').value.trim();if(!v)return;add(v);document.getElementById('mi').value=''}
function pick(i){const inp=document.createElement('input');inp.type='color';inp.value=sel[i].color;inp.onchange=()=>{sel[i].color=inp.value;renderSel()};inp.click()}
function renderSel(){
  const el=document.getElementById('sel');
  document.getElementById('sc').textContent=sel.length+'개';
  document.getElementById('svb').disabled=!sel.length;
  if(!sel.length){el.innerHTML='<div class="empty">골프장을 선택하세요</div>';return}
  el.innerHTML=sel.map((s,i)=>`<div class="si"><span class="idx">${i+1}</span><button class="arrow" onclick="mv(${i},-1)" ${i===0?'disabled':''}>↑</button><button class="arrow" onclick="mv(${i},1)" ${i===sel.length-1?'disabled':''}>↓</button><div class="dot" style="background:${s.color}" onclick="pick(${i})" title="색상"></div><span class="sn">${s.name}</span><button class="sx" onclick="rem('${esc(s.name)}')">×</button></div>`).join('');
}
async function doSave(){
  const colors={};sel.forEach(s=>colors[s.name]=s.color);
  const r=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({courses:sel.map(s=>s.name),colors})});
  const d=await r.json();
  if(d.ok){
    toast('✅ 저장 완료!');
    // 확인 팝업
    const overlay=document.createElement('div');
    overlay.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:200;display:flex;align-items:center;justify-content:center;animation:fadeIn .2s';
    const box=document.createElement('div');
    box.style.cssText='background:#1E293B;border:1px solid #334155;border-radius:16px;padding:32px;max-width:480px;width:90%;max-height:80vh;overflow-y:auto';
    box.innerHTML=`<div style="text-align:center;margin-bottom:20px"><div style="font-size:48px;margin-bottom:8px">✅</div><div style="font-size:20px;font-weight:800">저장 완료</div><div style="color:#94A3B8;font-size:13px;margin-top:6px">${sel.length}개 골프장이 설정되었습니다</div></div>`
      +`<div style="background:#0F172A;border-radius:10px;padding:16px;margin-bottom:20px">`
      +sel.map((s,i)=>`<div style="display:flex;align-items:center;gap:10px;padding:6px 0;${i?'border-top:1px solid #334155;':''}"><span style="color:#475569;font-size:11px;width:20px;text-align:center">${i+1}</span><div style="width:14px;height:14px;border-radius:50%;background:${s.color};flex-shrink:0"></div><span style="font-size:13px;font-weight:600">${s.name}</span></div>`).join('')
      +`</div>`
      +`<div style="display:flex;gap:8px;justify-content:center"><button onclick="this.closest('div[style*=fixed]').remove()" style="padding:12px 28px;border-radius:10px;border:1px solid #334155;background:transparent;color:#94A3B8;font-size:14px;font-weight:600;cursor:pointer">닫기</button><button onclick="this.closest('div[style*=fixed]').remove();doSave()" style="padding:12px 28px;border-radius:10px;border:none;background:#4F46E5;color:#fff;font-size:14px;font-weight:600;cursor:pointer">다시 저장</button></div>`;
    overlay.appendChild(box);
    overlay.addEventListener('click',e=>{if(e.target===overlay)overlay.remove()});
    document.body.appendChild(overlay);
  } else toast('❌ 저장 실패');
}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2500)}
function esc(s){return s.replace(/'/g,"\\'")}
</script></body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def _j(self,d):
        self.send_response(200);self.send_header("Content-Type","application/json;charset=utf-8");self.end_headers()
        self.wfile.write(json.dumps(d,ensure_ascii=False).encode())
    def do_GET(self):
        p=urlparse(self.path).path
        if p in ("/","/index.html"):
            self.send_response(200);self.send_header("Content-Type","text/html;charset=utf-8");self.end_headers()
            self.wfile.write(HTML.encode())
        elif p=="/api/db": self._j(GOLF_DB)
        elif p=="/api/current": self._j({"courses":load_current()})
        else: self.send_error(404)
    def do_POST(self):
        if self.path=="/api/save":
            body=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))))
            try:
                save_config(body.get("courses",[]),body.get("colors",{}))
                print(f"  ✅ 저장: {', '.join(body.get('courses',[]))}")
                self._j({"ok":True})
            except Exception as e: self._j({"ok":False,"error":str(e)})
        else: self.send_error(404)

if __name__=="__main__":
    port=5577
    print(f"\n  VERHILL RADAR — 골프장 설정\n  🌐 http://localhost:{port}\n  {len(GOLF_DB)}개 골프장 내장 · Ctrl+C 종료\n")
    cur=load_current()
    if cur: print(f"  현재: {', '.join(cur)}\n")
    try:
        import subprocess;subprocess.Popen(["open",f"http://localhost:{port}"])
    except:pass
    try:HTTPServer(("0.0.0.0",port),H).serve_forever()
    except KeyboardInterrupt:print("\n  종료")
