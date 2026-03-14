const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber, PageBreak, LevelFormat, TabStopType, TabStopPosition } = require("docx");

// ── Design Tokens ──
const FONT = "Arial";
const COLOR = {
  bg: "0F172A", cardBg: "1E293B", secondary: "334155",
  accent: "4F46E5", textMain: "E2E8F0", textSec: "94A3B8",
  ok: "10B981", warn: "F59E0B", error: "EF4444",
  gold: "6366F1", blue: "0EA5E9", green: "10B981",
};

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0 };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

const heading = (text, level = HeadingLevel.HEADING_1) =>
  new Paragraph({ heading: level, spacing: { before: 300, after: 150 }, children: [new TextRun({ text, bold: true, font: FONT })] });

const body = (text, opts = {}) =>
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, font: FONT, size: 22, ...opts })] });

const bodyBold = (text) => body(text, { bold: true });

const bullet = (text, ref = "bullets", level = 0) =>
  new Paragraph({ numbering: { reference: ref, level }, spacing: { after: 80 },
    children: [new TextRun({ text, font: FONT, size: 22 })] });

const spacer = () => new Paragraph({ spacing: { after: 60 }, children: [] });

const codeBlock = (text) =>
  new Paragraph({ spacing: { after: 80 }, indent: { left: 360 },
    children: [new TextRun({ text, font: "Courier New", size: 18, color: "94A3B8" })] });

const headerCell = (text, width) =>
  new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "1E293B", type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, font: FONT, size: 20, color: "E2E8F0" })] })]
  });

const dataCell = (text, width) =>
  new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text, font: FONT, size: 20 })] })]
  });

// ── Document ──
const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: FONT, color: "1a1a2e" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: FONT, color: "2d2d5e" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: "3d3d7e" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [
    // ═══════════════════════════════════════
    // COVER PAGE
    // ═══════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      children: [
        spacer(), spacer(), spacer(), spacer(), spacer(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: "Golf Price Dashboard V5.1", font: FONT, size: 56, bold: true, color: "1a1a2e" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
          children: [new TextRun({ text: "Design Specification", font: FONT, size: 36, color: "4F46E5" })] }),
        spacer(), spacer(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
          children: [new TextRun({ text: "2026-03-15", font: FONT, size: 24, color: "666666" })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
          children: [new TextRun({ text: "Based on: 19,515 tee times across 8 courses, 3 collection dates", font: FONT, size: 20, color: "999999" })] }),
        spacer(), spacer(), spacer(), spacer(),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: "Key Changes from V5.0", font: FONT, size: 28, bold: true, color: "1a1a2e" })] }),

        new Table({
          width: { size: 7000, type: WidthType.DXA },
          columnWidths: [2200, 4800],
          rows: [
            new TableRow({ children: [headerCell("항목", 2200), headerCell("변경 내용", 4800)] }),
            new TableRow({ children: [dataCell("기준 골프장", 2200), dataCell("삭제. 8개 전체 동등 분석, AI가 각각 코멘트", 4800)] }),
            new TableRow({ children: [dataCell("글로벌 설정", 2200), dataCell("anchorDate + rangeMode만 유지. baseCourse/weekdayMode 제거", 4800)] }),
            new TableRow({ children: [dataCell("UI 스케일", 2200), dataCell("V1 스타일: KPI 36px, 본문 15px, 테이블 13px. 최소 터치 44px", 4800)] }),
            new TableRow({ children: [dataCell("반응형", 2200), dataCell("Desktop(1200+) + Mobile(375+) 미디어쿼리", 4800)] }),
            new TableRow({ children: [dataCell("Tab2 생애주기", 2200), dataCell("2일 데이터로도 전일 vs 오늘 슬롯 변화 표시", 4800)] }),
            new TableRow({ children: [dataCell("탭 구조", 2200), dataCell("9탭 유지. 탭명/아이콘/순서 재정의", 4800)] }),
          ]
        }),

        new Paragraph({ children: [new PageBreak()] }),
      ]
    },

    // ═══════════════════════════════════════
    // SECTION 1: ARCHITECTURE
    // ═══════════════════════════════════════
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      headers: {
        default: new Header({ children: [
          new Paragraph({
            border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "4F46E5", space: 1 } },
            children: [
              new TextRun({ text: "Golf Dashboard V5.1 Spec", font: FONT, size: 18, color: "999999" }),
              new TextRun({ text: "\t" }),
            ],
            tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
          })
        ] })
      },
      footers: {
        default: new Footer({ children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: "Page ", font: FONT, size: 18, color: "999999" }),
                       new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: "999999" })]
          })
        ] })
      },
      children: [
        // ── 1. Global Architecture ──
        heading("1. Global Architecture"),

        heading("1.1 Design System (V1 Style)", HeadingLevel.HEADING_2),
        body("V1에서 검증된 다크 프리미엄 테마를 유지하되, 폰트 크기를 데스크탑 기준으로 상향 조정한다."),
        spacer(),

        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2400, 2400, 2280, 2280],
          rows: [
            new TableRow({ children: [headerCell("요소", 2400), headerCell("Desktop", 2400), headerCell("Mobile", 2280), headerCell("비고", 2280)] }),
            new TableRow({ children: [dataCell("KPI 숫자", 2400), dataCell("36px bold", 2400), dataCell("28px bold", 2280), dataCell("카드 중앙 정렬", 2280)] }),
            new TableRow({ children: [dataCell("KPI 라벨", 2400), dataCell("14px", 2400), dataCell("12px", 2280), dataCell("textSecondary 색상", 2280)] }),
            new TableRow({ children: [dataCell("섹션 제목", 2400), dataCell("18px bold", 2400), dataCell("16px bold", 2280), dataCell("아이콘 + 텍스트", 2280)] }),
            new TableRow({ children: [dataCell("본문 텍스트", 2400), dataCell("15px", 2400), dataCell("14px", 2280), dataCell("기본 줄간격 1.5", 2280)] }),
            new TableRow({ children: [dataCell("테이블 셀", 2400), dataCell("13px", 2400), dataCell("12px", 2280), dataCell("패딩 12px 16px", 2280)] }),
            new TableRow({ children: [dataCell("탭 버튼", 2400), dataCell("14px", 2400), dataCell("13px", 2280), dataCell("최소 높이 44px", 2280)] }),
            new TableRow({ children: [dataCell("차트 라벨", 2400), dataCell("12px", 2400), dataCell("11px", 2280), dataCell("Recharts tick", 2280)] }),
          ]
        }),
        spacer(),

        heading("1.2 Color Palette", HeadingLevel.HEADING_2),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2340, 2340, 2340, 2340],
          rows: [
            new TableRow({ children: [headerCell("Token", 2340), headerCell("Hex", 2340), headerCell("용도", 2340), headerCell("대비", 2340)] }),
            new TableRow({ children: [dataCell("bg", 2340), dataCell("#0F172A", 2340), dataCell("전체 배경", 2340), dataCell("-", 2340)] }),
            new TableRow({ children: [dataCell("cardBg", 2340), dataCell("#1E293B", 2340), dataCell("카드/패널 배경", 2340), dataCell("bg 대비 1.3:1", 2340)] }),
            new TableRow({ children: [dataCell("accent", 2340), dataCell("#4F46E5", 2340), dataCell("활성 탭, CTA", 2340), dataCell("bg 대비 4.5:1+", 2340)] }),
            new TableRow({ children: [dataCell("textBright", 2340), dataCell("#F1F5F9", 2340), dataCell("숫자, 강조 텍스트", 2340), dataCell("bg 대비 13:1+", 2340)] }),
            new TableRow({ children: [dataCell("textMain", 2340), dataCell("#E2E8F0", 2340), dataCell("본문 텍스트", 2340), dataCell("bg 대비 11:1+", 2340)] }),
            new TableRow({ children: [dataCell("textSecondary", 2340), dataCell("#94A3B8", 2340), dataCell("라벨, 보조 텍스트", 2340), dataCell("bg 대비 5:1+", 2340)] }),
            new TableRow({ children: [dataCell("ok/warn/error", 2340), dataCell("#10B981/#F59E0B/#EF4444", 2340), dataCell("상태 표시", 2340), dataCell("각 4.5:1+", 2340)] }),
          ]
        }),
        spacer(),

        heading("1.3 Global Controls", HeadingLevel.HEADING_2),
        body("SettingsContext에서 baseCourse와 weekdayMode를 제거한다. 남은 글로벌 상태:"),
        bullet("anchorDate: 현재 선택된 수집일 (YYYY-MM-DD). 기본값 = metadata.latest_date"),
        bullet("rangeMode: '1d' | '3d' | '7d' | 'all'. 기본값 = '1d'"),
        body("DateNavigator 컴포넌트가 모든 date-keyed 탭 상단에 표시된다. 설정 모달(기어 아이콘)은 제거하고 DateNavigator만 남긴다."),
        spacer(),

        heading("1.4 Responsive Breakpoints", HeadingLevel.HEADING_2),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2340, 2340, 2340, 2340],
          rows: [
            new TableRow({ children: [headerCell("이름", 2340), headerCell("범위", 2340), headerCell("그리드 칼럼", 2340), headerCell("탭 표시", 2340)] }),
            new TableRow({ children: [dataCell("Desktop", 2340), dataCell("1200px+", 2340), dataCell("auto-fit 220px+", 2340), dataCell("전체 텍스트+아이콘", 2340)] }),
            new TableRow({ children: [dataCell("Tablet", 2340), dataCell("768-1199px", 2340), dataCell("auto-fit 180px+", 2340), dataCell("아이콘+짧은텍스트", 2340)] }),
            new TableRow({ children: [dataCell("Mobile", 2340), dataCell("375-767px", 2340), dataCell("1-2열", 2340), dataCell("아이콘만, 스크롤", 2340)] }),
          ]
        }),
        body("구현: CSS @media 쿼리를 <style> 블록에 인라인. React 컴포넌트 내부에서는 window.innerWidth 체크 없이 CSS만으로 처리."),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══════════════════════════════════════
        // SECTION 2: TAB SPECS
        // ═══════════════════════════════════════
        heading("2. Tab Specifications"),
        body("9개 탭 각각의 데이터 소스, UI 레이아웃, 필드 매핑을 정의한다."),
        spacer(),

        // ── Tab 1 ──
        heading("2.1 Tab 1: 오늘의 브리핑", HeadingLevel.HEADING_2),
        body("수집일 기준 전체 현황을 한 화면에 요약. 대시보드 진입 시 첫 화면."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab1[anchorDate] → { kpi, course_kpi, prev_course_kpi, consumption, price_changes, alerts, calendar }"),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. KPI 카드 (4열 그리드, 데스크탑 / 2열 모바일)"),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2340, 2340, 2340, 2340],
          rows: [
            new TableRow({ children: [headerCell("카드", 2340), headerCell("값", 2340), headerCell("데이터 필드", 2340), headerCell("서브텍스트", 2340)] }),
            new TableRow({ children: [dataCell("잔여 티타임", 2340), dataCell("7,550개", 2340), dataCell("kpi.total_slots_today", 2340), dataCell("전체 8개 골프장", 2340)] }),
            new TableRow({ children: [dataCell("전일 대비", 2340), dataCell("-5.8%", 2340), dataCell("calc: slot_delta/prev*100", 2340), dataCell("-465개 감소", 2340)] }),
            new TableRow({ children: [dataCell("가격 변동", 2340), dataCell("34건", 2340), dataCell("kpi.total_price_changes", 2340), dataCell("인상3 / 인하31", 2340)] }),
            new TableRow({ children: [dataCell("특가 비율", 2340), dataCell("24.1%", 2340), dataCell("kpi.promo_ratio", 2340), dataCell("1,821개 슬롯", 2340)] }),
          ]
        }),
        body("KPI 숫자: 36px bold. 서브텍스트: 13px textSecondary."),
        spacer(),

        bodyBold("B. 알림 배너 (최대 5개)"),
        body("alerts[] 배열. 각 항목: level(warning/error/info), type, course, msg"),
        body("좌측 4px 컬러 보더 + AlertCircle 아이콘 + 코스명 + 메시지. 빨간/노란/파란 구분."),
        spacer(),

        bodyBold("C. 골프장 현황 테이블"),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [1560, 1560, 1560, 1560, 1560, 1560],
          rows: [
            new TableRow({ children: [
              headerCell("컬럼", 1560), headerCell("필드", 1560), headerCell("포맷", 1560),
              headerCell("전일비교", 1560), headerCell("정렬", 1560), headerCell("비고", 1560)] }),
            new TableRow({ children: [
              dataCell("골프장", 1560), dataCell("course_name", 1560), dataCell("CourseBadge", 1560),
              dataCell("-", 1560), dataCell("left", 1560), dataCell("컬러 도트", 1560)] }),
            new TableRow({ children: [
              dataCell("잔여", 1560), dataCell("slots", 1560), dataCell("숫자", 1560),
              dataCell("prev_course_kpi[].slots", 1560), dataCell("right", 1560), dataCell("+/-  표시", 1560)] }),
            new TableRow({ children: [
              dataCell("평균가", 1560), dataCell("avg_price", 1560), dataCell("N만원", 1560),
              dataCell("prev.avg_price", 1560), dataCell("right", 1560), dataCell("만원 단위", 1560)] }),
            new TableRow({ children: [
              dataCell("특가", 1560), dataCell("promo_slots", 1560), dataCell("숫자", 1560),
              dataCell("-", 1560), dataCell("right", 1560), dataCell("특가 수량", 1560)] }),
            new TableRow({ children: [
              dataCell("회원/대중", 1560), dataCell("member_slots/public_slots", 1560), dataCell("N/N", 1560),
              dataCell("-", 1560), dataCell("right", 1560), dataCell("비율표시", 1560)] }),
          ]
        }),
        body("전일 비교: prev_course_kpi 딕셔너리에서 같은 course_name으로 조회. 슬롯 변화량 +/- 컬러 표시."),
        spacer(),

        bodyBold("D. 가격 변동 이벤트 (2열: 인하/인상)"),
        body("price_changes['인하'] / price_changes['인상'] 배열에서 최대 5건씩."),
        body("각 이벤트: course_name, course_sub, play_date, tee_time, old_price_krw, new_price_krw, delta_pct"),
        spacer(),

        bodyBold("E. 향후 7일 캘린더 (7열 그리드)"),
        body("calendar[] 배열: play_date, weekday_type, slots, avg_price, promo_slots, d_day"),
        body("각 카드: 날짜 + 요일타입(주말 노란색) / 잔여 N개 / 평균 N만 / 특가 N개 / D-N"),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 2 ──
        heading("2.2 Tab 2: 슬롯 생애주기", HeadingLevel.HEADING_2),
        body("전일 대비 오늘 슬롯이 어떻게 변했는지 — 소진, 신규 오픈, 유지, 회원제 오픈을 추적한다. 2일 데이터로도 동작."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab1[anchorDate].consumption → [{course_name, prev_slots, today_slots, consumed, new_open, member_open, stayed, consume_rate}]"),
        body("consumption 배열이 이미 tab1 안에 존재한다. 별도 tab2 데이터 생성 불필요 — tab1.consumption을 직접 참조."),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. 전체 요약 KPI (3열)"),
        bullet("총 소진: SUM(consumed) — 전일 대비 사라진 슬롯"),
        bullet("신규 오픈: SUM(new_open) — 새로 등장한 슬롯"),
        bullet("회원제 오픈: SUM(member_open) — 회원제 전환 슬롯"),
        spacer(),

        bodyBold("B. 코스별 슬롯 변화 차트 (BarChart, 가로 막대)"),
        body("X축: 코스명 8개. Y축: 슬롯 수."),
        body("스택 구성: stayed(남은 슬롯, 회색) + consumed(소진, 빨강) + new_open(신규, 초록) + member_open(회원제, 보라)"),
        body("각 바 위에 consume_rate % 표시"),
        spacer(),

        bodyBold("C. 상세 테이블"),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [1560, 1170, 1170, 1170, 1170, 1170, 1950],
          rows: [
            new TableRow({ children: [
              headerCell("골프장", 1560), headerCell("전일", 1170), headerCell("오늘", 1170),
              headerCell("소진", 1170), headerCell("신규", 1170), headerCell("회원제", 1170), headerCell("소진율", 1950)] }),
            new TableRow({ children: [
              dataCell("골드레이크", 1560), dataCell("679", 1170), dataCell("640", 1170),
              dataCell("-47", 1170), dataCell("+4", 1170), dataCell("+4", 1170), dataCell("6.9%  ████░░░░░░", 1950)] }),
          ]
        }),
        body("소진율 셀에 프로그레스 바 인라인 표시. 소진율이 15%+ 이면 경고색, 25%+ 이면 위험색."),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 3 ──
        heading("2.3 Tab 3: 소진 패턴", HeadingLevel.HEADING_2),
        body("요일별, 시간대별 소진율 히트맵. 어떤 조합이 가장 빨리 팔리는지 시각화."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab3[anchorDate] → { heatmap, course_patterns, today_distribution }"),
        body("heatmap: [{weekday, part, total, consumed, consume_rate, promo_consumed}] — 9행 (3요일 x 3시간대)"),
        body("course_patterns: [{course_name, total, consumed, consume_rate, breakdown[]}] — 8개 코스"),
        body("today_distribution: [{weekday_type, part_type, slots, avg_price, promo_slots}] — 9행"),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. 요일 x 시간대 히트맵 테이블"),
        body("행: 평일, 토요일, 일요일. 열: 1부, 2부, (오후가 있으면 오후도)."),
        body("각 셀: consume_rate % 숫자 + consumed/total 소텍스트. 배경색 그라데이션: 0-10% 초록, 10-20% 파랑, 20%+ 빨강."),
        body("셀 크기: 최소 80x60px. 숫자 18px bold 중앙."),
        spacer(),

        bodyBold("B. 코스별 소진율 카드 (4열 그리드)"),
        body("각 카드: 코스명 + consume_rate(24px bold) + total/consumed + 프로그레스 바."),
        body("카드 정렬: consume_rate 내림차순."),
        spacer(),

        bodyBold("C. 분포 차트 (BarChart)"),
        body("today_distribution 기반. X축: weekday_type + part_type 조합. Y축: slots(파란) + promo_slots(노란) 스택."),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 4 ──
        heading("2.4 Tab 4: 가격 흐름", HeadingLevel.HEADING_2),
        body("D-day별 가격 추세, 가격 산점도, 가격대 분포, 가격 변동 이벤트를 보여준다."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab4 → { dday_trend[214], scatter[600], histogram[22], price_events[177] }"),
        body("tab4는 date-keyed가 아님 (모든 수집일 통합). 필터링은 클라이언트에서."),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("서브탭 3개: D-day 추세 | 산점도 | 가격 분포"),
        spacer(),

        bodyBold("A. D-day 추세 (LineChart)"),
        body("dday_trend를 피벗: d_day별로 각 course_name의 avg_price를 만원 단위 변환."),
        body("X축: D-day (역순, 왼쪽이 먼 미래). Y축: 만원 단위."),
        body("8개 코스별 라인, COURSE_COLORS 사용. 범례 하단."),
        spacer(),

        bodyBold("B. 산점도 (ScatterChart)"),
        body("scatter 배열 직접 사용. X: d_day, Y: price_krw."),
        body("코스별 색상 구분. 호버 시 course_sub, tee_time, play_date 표시."),
        spacer(),

        bodyBold("C. 가격 분포 (BarChart)"),
        body("histogram 배열. X: price_bucket(구간명). Y: non_promo + promo 스택."),
        body("X축 라벨 45도 회전. 범례: 정가(파란) + 특가(노란)."),
        spacer(),

        bodyBold("D. 가격 변동 이벤트 테이블 (항상 표시)"),
        body("price_events 배열. 컬럼: 골프장, 코스, 이벤트타입(인상/인하/특가부착/특가해제), 변동(old→new + %), 경기일, 시간."),
        body("최대 15행. 인상=초록 뱃지, 인하=빨강 뱃지."),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 5 ──
        heading("2.5 Tab 5: 할인 반응", HeadingLevel.HEADING_2),
        body("특가/할인이 실제로 가격에 미치는 영향. D-day별 특가 vs 정가 비교."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab5a → { discount_events[167], course_summary[5], promo_distribution[33], dday_comparison[29], data_limitation }"),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. 데이터 제한 안내 배너"),
        body("data_limitation 문자열이 있으면 상단에 info 배너 표시."),
        spacer(),

        bodyBold("B. 골프장별 할인 현황 카드 (5개)"),
        body("course_summary: course_name, event_count, avg_discount_pct, max_discount_pct."),
        body("카드: 코스명 + event_count(28px bold) + 평균 할인율 + 최대 할인율"),
        spacer(),

        bodyBold("C. D-day별 특가 vs 정가 (LineChart)"),
        body("dday_comparison: d_day, avg_promo, avg_non_promo, discount_depth."),
        body("2라인: avg_promo(노란 실선) + avg_non_promo(회색 점선). Y축 만원 단위."),
        spacer(),

        bodyBold("D. 할인 이벤트 테이블"),
        body("discount_events: course_name, course_sub, event_type, discount_pct, discount_amt, play_date, tee_time."),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 6 ──
        heading("2.6 Tab 6: 수익 구조", HeadingLevel.HEADING_2),
        body("정가(baseline) 대비 실제 판매가 비율 = yield. 코스별, 요일별 수익성 분석."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab5b[anchorDate] → { yield_slots[1500], course_summary[7], yield_histogram[15] }"),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. 코스별 Yield 카드 (4열)"),
        body("course_summary: course_name, weekday_avg_yield, weekend_avg_yield, weekday_count, weekend_count, promo_ratio_weekday."),
        body("카드 2열: 평일 yield(큰 숫자) + 주말 yield(큰 숫자). 하단에 슬롯 수 + 특가 비율."),
        spacer(),

        bodyBold("B. Yield 분포 (BarChart)"),
        body("yield_histogram: yield_bucket, total, promo, non_promo."),
        body("스택: non_promo(파란) + promo(노란). X축 라벨 30도 회전."),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 7 ──
        heading("2.7 Tab 7: 코스 x 회원제", HeadingLevel.HEADING_2),
        body("세부 코스별 가격/슬롯 비교 + 회원제 오픈 이벤트 추적."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab6[anchorDate] → { subcourse_rows[27], course_summary{}, member_opens_latest[20] }"),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. 세부 코스 테이블"),
        body("subcourse_rows: course_name, course_sub, membership_type, slots, avg_price, min_price, max_price, promo_slots, slot_delta, member_label, sub_display."),
        body("컬럼: 골프장 | 코스(sub_display) | 타입(회원/대중 뱃지) | 슬롯 | 평균가(만원) | 가격범위 | 특가 | 전일대비"),
        spacer(),

        bodyBold("B. 회원제 오픈 이벤트 카드"),
        body("member_opens_latest: course_name, play_date, member_slot_count, member_sub_names, min/max_price_krw."),
        body("좌측 accent 보더 카드. 코스명 + 경기일 + 슬롯 수 + 가격 범위."),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 8 ──
        heading("2.8 Tab 8: AI 진단", HeadingLevel.HEADING_2),
        body("규칙 기반 자동 진단. 8개 골프장 각각에 대해 findings를 생성하고 AI 코멘트를 단다."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("RAW_DATA.tab7[anchorDate] → { diagnostics[8], rules_applicable[], rules_pending[], data_note, data_days }"),
        body("diagnostics 각 항목: course_name, severity_max, finding_count, findings[]"),
        body("findings 각 항목: rule, severity, title, desc, action, metric"),
        spacer(),

        heading("핵심 변경: 기준 골프장 없이 전체 진단", HeadingLevel.HEADING_3),
        body("V5.0에서는 baseCourse 기준으로 비교했으나, V5.1에서는 8개 전체를 동등하게 진단한다."),
        body("각 골프장 카드에 AI가 자동 생성한 findings를 표시. 향후 LLM 통합 시 자연어 코멘트 추가."),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. 데이터 안내 + 규칙 레전드"),
        body("data_note: 상단 info 배너."),
        body("rules_applicable: 활성 규칙 (밝은 뱃지). rules_pending: 대기 규칙 (흐린 뱃지)."),
        body("10개 규칙: A(적정 재고율), B(가격 안정성), C(특가 효과), D(수익성), E(마진율), F(수요 예측), G(경쟁력), H(운영 효율), I(위험 관리), J(성장성)"),
        spacer(),

        bodyBold("B. 골프장별 진단 카드 (8개)"),
        body("정렬: severity_max 내림차순 (심각한 것이 위)."),
        body("카드 구조:"),
        bullet("헤더: CourseBadge + severity 뱃지(심각/주의/양호) + finding_count"),
        bullet("본문: findings 리스트. 각 finding:"),
        bullet("규칙 코드 뱃지(A-J) + title(12px bold) + desc(11px) + action(accent색, 10px)", "bullets", 1),
        body("각 finding에 좌측 severity 컬러 보더 (error=빨강, warning=노란, info=파랑)."),

        new Paragraph({ children: [new PageBreak()] }),

        // ── Tab 9 ──
        heading("2.9 Tab 9: 티타임 상세", HeadingLevel.HEADING_2),
        body("7,550개 개별 슬롯 데이터 검색. 필터 + 페이지네이션."),
        spacer(),

        heading("데이터 소스", HeadingLevel.HEADING_3),
        codeBlock("window.__GOLF_TAB8_TODAY__ → { slots[7550] }"),
        body("각 슬롯: course_name, course_sub, membership_type, play_date, tee_time, price_krw, promo_flag, promo_text, pax_condition, part_type, weekday_type, d_day, season, sub_display"),
        spacer(),

        heading("레이아웃", HeadingLevel.HEADING_3),
        bodyBold("A. 필터 바 (5열 그리드, 모바일은 2열)"),
        body("골프장(8개 셀렉트) | 특가(전체/있음/없음) | 요일(전체/평일/주말) | 시간대(전체/1부/2부/오후) | 검색(텍스트)"),
        spacer(),

        bodyBold("B. 데이터 테이블"),
        body("컬럼: 골프장 | 코스 | 경기일 | 시간 | 가격(만원) | D-day(컬러뱃지) | 특가(노란뱃지)"),
        body("50행 페이지네이션. 총 N건 / 현재 페이지 표시."),
        body("모바일에서는 코스 컬럼 숨기고 골프장에 합침."),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══════════════════════════════════════
        // SECTION 3: TAB MAPPING
        // ═══════════════════════════════════════
        heading("3. Tab Name / Icon / Order"),
        spacer(),

        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [780, 780, 1950, 1950, 1950, 1950],
          rows: [
            new TableRow({ children: [
              headerCell("#", 780), headerCell("Icon", 780), headerCell("탭명", 1950),
              headerCell("데이터키", 1950), headerCell("Date-keyed", 1950), headerCell("비고", 1950)] }),
            new TableRow({ children: [dataCell("1", 780), dataCell("📋", 780), dataCell("브리핑", 1950), dataCell("tab1[date]", 1950), dataCell("Yes", 1950), dataCell("기본 탭", 1950)] }),
            new TableRow({ children: [dataCell("2", 780), dataCell("🔄", 780), dataCell("생애주기", 1950), dataCell("tab1[date].consumption", 1950), dataCell("Yes", 1950), dataCell("Tab1 내 데이터 재사용", 1950)] }),
            new TableRow({ children: [dataCell("3", 780), dataCell("🔥", 780), dataCell("소진 패턴", 1950), dataCell("tab3[date]", 1950), dataCell("Yes", 1950), dataCell("히트맵 중심", 1950)] }),
            new TableRow({ children: [dataCell("4", 780), dataCell("📈", 780), dataCell("가격 흐름", 1950), dataCell("tab4", 1950), dataCell("No (전체)", 1950), dataCell("서브탭 3개", 1950)] }),
            new TableRow({ children: [dataCell("5", 780), dataCell("🏷️", 780), dataCell("할인 반응", 1950), dataCell("tab5a", 1950), dataCell("No (전체)", 1950), dataCell("특가 분석", 1950)] }),
            new TableRow({ children: [dataCell("6", 780), dataCell("⚖️", 780), dataCell("수익 구조", 1950), dataCell("tab5b[date]", 1950), dataCell("Yes", 1950), dataCell("Yield 분석", 1950)] }),
            new TableRow({ children: [dataCell("7", 780), dataCell("⛳", 780), dataCell("코스 비교", 1950), dataCell("tab6[date]", 1950), dataCell("Yes", 1950), dataCell("세부코스+회원제", 1950)] }),
            new TableRow({ children: [dataCell("8", 780), dataCell("🤖", 780), dataCell("AI 진단", 1950), dataCell("tab7[date]", 1950), dataCell("Yes", 1950), dataCell("전체 코스 동등", 1950)] }),
            new TableRow({ children: [dataCell("9", 780), dataCell("📊", 780), dataCell("티타임 상세", 1950), dataCell("__GOLF_TAB8_TODAY__", 1950), dataCell("Today only", 1950), dataCell("7,550개 검색", 1950)] }),
          ]
        }),

        new Paragraph({ children: [new PageBreak()] }),

        // ═══════════════════════════════════════
        // SECTION 4: IMPLEMENTATION PLAN
        // ═══════════════════════════════════════
        heading("4. Implementation Plan"),
        spacer(),

        heading("Phase 1: Foundation (현재 세션)", HeadingLevel.HEADING_2),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "SettingsContext 리팩토링: baseCourse/weekdayMode 제거, 설정모달 제거", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "CSS 미디어쿼리 반응형 + V1 폰트 스케일 적용", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab1 (브리핑) 완전 재구현 — prev_course_kpi 전일 비교 포함", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab2 (생애주기) 신규 — tab1.consumption 데이터 활용", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "빌드 + 브라우저 검증", font: FONT, size: 22 })] }),
        spacer(),

        heading("Phase 2: Charts & Tables", HeadingLevel.HEADING_2),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab3 (소진 패턴) — 히트맵 + 코스별 카드 + 분포 차트", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab4 (가격 흐름) — 서브탭 3개 + 이벤트 테이블", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab5 (할인 반응) — D-day 비교 차트 + 이벤트 테이블", font: FONT, size: 22 })] }),
        spacer(),

        heading("Phase 3: Advanced", HeadingLevel.HEADING_2),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab6 (수익 구조) — Yield 카드 + 히스토그램", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab7 (코스 비교) — 세부코스 테이블 + 회원제 오픈 카드", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab8 (AI 진단) — 전체 코스 동등 진단, 기준 골프장 없이", font: FONT, size: 22 })] }),
        new Paragraph({ numbering: { reference: "numbers", level: 0 }, spacing: { after: 80 },
          children: [new TextRun({ text: "Tab9 (티타임 상세) — 필터 + 페이지네이션", font: FONT, size: 22 })] }),
        spacer(),

        heading("Phase 4: Polish", HeadingLevel.HEADING_2),
        bullet("모바일 최적화 QA (375px / 768px / 1200px 테스트)"),
        bullet("차트 반응형: ResponsiveContainer + 모바일에서 범례 위치 조정"),
        bullet("로딩 스켈레톤 + 에러 바운더리"),
        bullet("성능: Tab8 가상 스크롤, 차트 lazy render"),
      ]
    },
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/hopeful-pensive-allen/mnt/kakao_golf/DASHBOARD_V5_1_SPEC.docx", buffer);
  console.log("OK: DASHBOARD_V5_1_SPEC.docx created");
});
