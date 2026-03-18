import React, { useState, useContext, createContext, useMemo, useCallback, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Cell, ComposedChart, Area, AreaChart, PieChart, Pie,
  ReferenceArea, ReferenceLine
} from 'recharts';

// ── Inline SVG Icon Components (lucide-react 대체) ──
const _icon = (d, props = {}) => {
  const { size = 24, color = 'currentColor', style = {}, ...rest } = props;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
         style={{ display: 'inline-block', verticalAlign: 'middle', ...style }} {...rest}>
      {d}
    </svg>
  );
};
const ChevronLeft = (props) => _icon(<polyline points="15 18 9 12 15 6" />, props);
const ChevronRight = (props) => _icon(<polyline points="9 18 15 12 9 6" />, props);
const AlertCircle = (props) => _icon(<><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>, props);
const TrendingUp = (props) => _icon(<><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></>, props);
const TrendingDown = (props) => _icon(<><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></>, props);
const Info = (props) => _icon(<><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></>, props);
const Search = (props) => _icon(<><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>, props);

// ═══════════════════════════════════════════════════
// V5.1 Design System
// ═══════════════════════════════════════════════════
const COLORS = {
  bg: '#0F172A',
  cardBg: '#1E293B',
  secondary: '#334155',
  textMain: '#E2E8F0',
  textSecondary: '#94A3B8',
  textMuted: '#64748B',
  textBright: '#F1F5F9',
  accent: '#4F46E5',
  accentLight: '#6366F1',
};

const COURSE_COLORS = {
  "광주CC": "#6366F1", "르오네뜨": "#0EA5E9", "어등산": "#10B981", "베르힐": "#F59E0B", "푸른솔장성": "#EF4444", "해피니스": "#8B5CF6", "골드레이크": "#EC4899", "무등산": "#14B8A6"
};

const EVENT_COLORS = { "인하": "#EF4444", "인상": "#10B981", "특가부착": "#F59E0B", "특가해제": "#6B7280" };
const SEVERITY_COLORS = { error: '#EF4444', warning: '#F59E0B', info: '#3B82F6', ok: '#10B981' };

const RULE_LABELS = {
  A: "적정 재고율", B: "가격 안정성", C: "특가 효과", D: "수익성", E: "마진율",
  F: "수요 예측", G: "경쟁력", H: "운영 효율", I: "위험 관리", J: "성장성"
};

// V5.1 Font Scale (V1 style)
const FONT = {
  kpi: { fontSize: 36, fontWeight: 700 },
  kpiLabel: { fontSize: 14 },
  sectionTitle: { fontSize: 18, fontWeight: 700 },
  body: { fontSize: 15, lineHeight: 1.5 },
  table: { fontSize: 13 },
  tableHeader: { fontSize: 13, fontWeight: 600 },
  tab: { fontSize: 14 },
  chartLabel: { fontSize: 12 },
  small: { fontSize: 12 },
  tiny: { fontSize: 11 },
};

const fmt = (n) => n == null ? '-' : Number(n).toLocaleString();
const fmtMan = (n) => {
  if (n == null) return '-';
  const man = n / 10000;
  return man % 1 === 0 ? `${man}만` : `${parseFloat(man.toFixed(1))}만`;
};
const fmtPct = (n, digits = 1) => n == null ? '-' : `${Number(n).toFixed(digits)}%`;
const fmtCount = (n) => {
  if (n == null) return '-';
  if (n >= 100000000) return `${(n / 100000000).toFixed(1)}억`;
  if (n >= 10000) return `${(n / 10000).toFixed(1).replace(/\.0$/, '')}만`;
  return Number(n).toLocaleString();
};
const fmtLoss = (n) => {
  if (n == null) return '-';
  if (n >= 100000000) return `${(n / 100000000).toFixed(1)}억원`;
  if (n >= 10000) return `${parseFloat((n / 10000).toFixed(1)).toLocaleString()}만원`;
  return `${Number(n).toLocaleString()}원`;
};

// ═══════════════════════════════════════════════════
// Settings Context (V5.1: baseCourse/weekdayMode 제거)
// ═══════════════════════════════════════════════════
const SettingsContext = createContext();

const SettingsProvider = ({ children }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const [anchorDate, setAnchorDate] = useState(RAW_DATA.metadata?.latest_date || '');
  const [rangeMode, setRangeMode] = useState('1d');

  return (
    <SettingsContext.Provider value={{ anchorDate, setAnchorDate, rangeMode, setRangeMode }}>
      {children}
    </SettingsContext.Provider>
  );
};

// ═══════════════════════════════════════════════════
// Shared Components (V5.1 style)
// ═══════════════════════════════════════════════════
const KpiCard = ({ title, value, unit, subtext, color, icon: Icon, tooltip }) => (
  <div className="kpi-hover" title={tooltip} style={{
    background: COLORS.cardBg,
    borderLeft: `4px solid ${color || COLORS.accent}`,
    borderRadius: 12,
    padding: '20px 24px',
    minHeight: 130,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between'
  }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <span style={{ color: COLORS.textSecondary, ...FONT.kpiLabel }}>{title}</span>
      {Icon && <Icon size={20} color={color || COLORS.accent} />}
    </div>
    <div>
      <div style={{ ...FONT.kpi, color: COLORS.textBright }}>{value}<span style={{ ...FONT.kpiLabel, color: COLORS.textSecondary, marginLeft: 4 }}>{unit}</span></div>
      {subtext && <div style={{ color: COLORS.textMuted, ...FONT.small, marginTop: 4 }}>{subtext}</div>}
    </div>
  </div>
);

const CourseBadge = ({ name, small = false }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 6,
  }}>
    <span style={{
      width: small ? 8 : 10, height: small ? 8 : 10, borderRadius: '50%',
      background: COURSE_COLORS[name] || COLORS.accent, display: 'inline-block', flexShrink: 0
    }} />
    <span style={{ color: COLORS.textMain, fontSize: small ? 12 : 14, fontWeight: 500 }}>{name}</span>
  </span>
);

const SectionTitle = ({ title, icon = '📋' }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, marginTop: 32 }}>
    <div style={{ width: 4, height: 28, background: COLORS.accent, borderRadius: 2 }} />
    <span style={{ ...FONT.sectionTitle, color: COLORS.textBright }}>{icon} {title}</span>
  </div>
);

const InfoBanner = ({ text, level = 'info' }) => {
  const color = SEVERITY_COLORS[level] || SEVERITY_COLORS.info;
  return (
    <div style={{
      background: `${color}15`, border: `1px solid ${color}40`, borderRadius: 8,
      padding: '12px 16px', marginBottom: 20, display: 'flex', gap: 12, alignItems: 'flex-start'
    }}>
      <Info size={16} color={color} style={{ flexShrink: 0, marginTop: 2 }} />
      <span style={{ ...FONT.small, color: COLORS.textSecondary, lineHeight: 1.5 }}>{text}</span>
    </div>
  );
};

const DateNavigator = ({ context, metadata }) => {
  const allDates = metadata?.all_dates || [];
  const moveDate = (offset) => {
    const idx = allDates.indexOf(context.anchorDate);
    const newIdx = idx + offset;
    if (newIdx >= 0 && newIdx < allDates.length) {
      context.setAnchorDate(allDates[newIdx]);
    }
  };

  return (
    <div style={{
      background: COLORS.cardBg, border: `1px solid ${COLORS.secondary}`,
      borderRadius: 10, padding: '12px 20px', marginBottom: 24,
      display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ color: COLORS.textSecondary, ...FONT.small }}>📅 수집일</span>
        <button onClick={() => moveDate(-1)} style={{
          background: 'none', border: 'none', color: COLORS.accent, cursor: 'pointer', ...FONT.sectionTitle, padding: '4px 8px'
        }}>&lt;</button>
        <span style={{ color: COLORS.textBright, ...FONT.body, fontWeight: 600, minWidth: 120, textAlign: 'center' }}>
          {context.anchorDate}
        </span>
        <button onClick={() => moveDate(1)} style={{
          background: 'none', border: 'none', color: COLORS.accent, cursor: 'pointer', ...FONT.sectionTitle, padding: '4px 8px'
        }}>&gt;</button>
      </div>
    </div>
  );
};

const DdayFilter = ({ value, onChange }) => {
  const options = [
    { key: 'near', label: '임박 D1-3', range: [1, 3] },
    { key: 'week', label: '1주 D1-7', range: [1, 7] },
    { key: 'two_weeks', label: '2주 D1-14', range: [1, 14] },
    { key: 'all', label: '전체 D1-30', range: [1, 30] },
  ];
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
      <span style={{ color: COLORS.textSecondary, ...FONT.small, display: 'flex', alignItems: 'center' }}>📅 경기일</span>
      {options.map(o => (
        <button key={o.key} className="btn-hover" onClick={() => onChange(o.range)} style={{
          padding: '8px 16px', borderRadius: 20,
          border: `1px solid ${value[0] === o.range[0] && value[1] === o.range[1] ? COLORS.accent : COLORS.secondary}`,
          background: value[0] === o.range[0] && value[1] === o.range[1] ? COLORS.accent : 'transparent',
          color: value[0] === o.range[0] && value[1] === o.range[1] ? '#fff' : COLORS.textSecondary,
          cursor: 'pointer', ...FONT.small, fontWeight: 500, minHeight: 36
        }}>
          {o.label}
        </button>
      ))}
    </div>
  );
};

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: COLORS.bg, border: `1px solid ${COLORS.secondary}`,
        borderRadius: 8, padding: 12, color: COLORS.textMain, ...FONT.small
      }}>
        <p style={{ marginBottom: 4, fontWeight: 600 }}>{label}</p>
        {payload.map((entry, idx) => (
          <p key={idx} style={{ color: entry.color, margin: '2px 0' }}>
            {entry.name}: {typeof entry.value === 'number' ? fmt(entry.value) : entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

// 드래그 스크롤 + 커스텀 인디케이터
const useChartScroll = () => {
  const scrollRef = React.useRef(null);
  const [scrollPct, setScrollPct] = React.useState(0);
  const isDragging = React.useRef(false);
  const startX = React.useRef(0);
  const startScroll = React.useRef(0);

  const onMouseDown = (e) => {
    if (!scrollRef.current) return;
    isDragging.current = true;
    startX.current = e.clientX;
    startScroll.current = scrollRef.current.scrollLeft;
    scrollRef.current.style.cursor = 'grabbing';
  };
  const onMouseMove = (e) => {
    if (!isDragging.current || !scrollRef.current) return;
    e.preventDefault();
    const dx = e.clientX - startX.current;
    scrollRef.current.scrollLeft = startScroll.current - dx;
  };
  const onMouseUp = () => {
    isDragging.current = false;
    if (scrollRef.current) scrollRef.current.style.cursor = 'grab';
  };
  const onScroll = () => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    const maxScroll = el.scrollWidth - el.clientWidth;
    setScrollPct(maxScroll > 0 ? el.scrollLeft / maxScroll : 0);
  };

  const bind = { ref: scrollRef, onMouseDown, onMouseMove, onMouseUp, onMouseLeave: onMouseUp, onScroll };
  return { bind, scrollPct, scrollRef };
};

const ScrollIndicator = ({ scrollPct, scrollRef, visible }) => {
  if (!visible) return null;
  const trackW = 160;
  const thumbW = 48;
  const left = scrollPct * (trackW - thumbW);
  const onIndicatorDrag = (e) => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    const maxScroll = el.scrollWidth - el.clientWidth;
    const rect = e.currentTarget.parentElement.getBoundingClientRect();
    const handleMove = (ev) => {
      const x = (ev.clientX || ev.touches?.[0]?.clientX || 0) - rect.left;
      const pct = Math.max(0, Math.min(1, x / trackW));
      el.scrollLeft = pct * maxScroll;
    };
    const handleUp = () => { document.removeEventListener('mousemove', handleMove); document.removeEventListener('mouseup', handleUp); };
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
  };
  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 8 }}>
      <div style={{ width: trackW, height: 4, background: '#1E293B', borderRadius: 2, position: 'relative', cursor: 'pointer' }}
        onMouseDown={onIndicatorDrag}>
        <div style={{ position: 'absolute', left, width: thumbW, height: 4, background: '#475569', borderRadius: 2, transition: 'left 0.1s' }} />
      </div>
    </div>
  );
};

const NoData = ({ msg }) => (
  <div style={{ background: COLORS.cardBg, borderRadius: 12, padding: 40, textAlign: 'center', color: COLORS.textMuted, ...FONT.body }}>
    {msg || '해당 날짜의 데이터가 없습니다.'}
  </div>
);

// ═══════════════════════════════════════════════════
// Tab 1: 브리핑
// ═══════════════════════════════════════════════════
const Tab1 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tabData = (RAW_DATA.tab1 || {})[context.anchorDate] || null;

  if (!tabData) return <NoData />;

  const { kpi, course_kpi, prev_course_kpi, alerts, price_changes, calendar, consumption, unsold_summary, weather } = tabData;
  const consumeRate = kpi?.consume_rate;
  const consumedCount = kpi?.consumed_count || 0;
  const newOpenCount = kpi?.new_open_count || 0;
  const cancelReopenCount = kpi?.cancel_reopen_count || 0;
  const unsoldCount = kpi?.unsold_count || 0;

  const [briefPeriod, setBriefPeriod] = useState(1);
  const allDates = metadata?.all_dates || [];
  const dataDays = allDates.length;

  // Period aggregation from multiple dates' tab1 data
  const periodData = useMemo(() => {
    if (briefPeriod <= 1) return null;
    const tab1All = RAW_DATA.tab1 || {};
    const idx = allDates.indexOf(context.anchorDate);
    if (idx < 0) return null;

    const periodDates = allDates.slice(Math.max(0, idx - briefPeriod + 1), idx + 1);
    if (periodDates.length < 2) return null;

    let totalConsumed = 0, totalUnsold = 0, totalCancel = 0, totalNewOpen = 0;
    const dailyRates = [];

    periodDates.forEach(d => {
      const dayKpi = (tab1All[d] || {}).kpi;
      if (dayKpi) {
        totalConsumed += dayKpi.consumed_count || 0;
        totalUnsold += dayKpi.unsold_count || 0;
        totalCancel += dayKpi.cancel_reopen_count || 0;
        totalNewOpen += dayKpi.new_open_count || 0;
        if (dayKpi.consume_rate != null) dailyRates.push(dayKpi.consume_rate);
      }
    });

    const avgRate = dailyRates.length > 0 ? Math.round(dailyRates.reduce((a,b)=>a+b,0) / dailyRates.length * 10) / 10 : null;

    return {
      days: periodDates.length,
      totalConsumed,
      totalUnsold,
      totalCancel,
      totalNewOpen,
      avgRate,
      dailyRates,
    };
  }, [briefPeriod, context.anchorDate, allDates, RAW_DATA.tab1]);

  // 기상 영향 요약
  const weatherRainDays = (weather?.forecasts || []).filter(f => f.rain_prob >= 60).length;
  const weatherNote = weatherRainDays > 0 ? ` · 우천예보 ${weatherRainDays}일` : '';

  return (
    <div>
      <InfoBanner text={"📊 8개 골프장의 오늘 가격과 남은 티타임, 특가 정보를 한눈에 확인할 수 있어요.\n소진 = 어제 있다 오늘 없는 티 · 미판매 = 팔리지 않고 경기일 지난 티 · 증감 = (신규+티취소) - (소진+미판매)"} />
      <DateNavigator context={context} metadata={metadata} />

      {/* 브리핑 구간 선택 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, alignItems: 'center' }}>
        <span style={{ color: COLORS.textSecondary, ...FONT.small }}>분석 구간</span>
        {[
          { key: 1, label: '1일' },
          { key: 3, label: '3일' },
          { key: 7, label: '7일' },
          { key: 30, label: '30일' },
          { key: 365, label: '1년' },
        ].map(o => {
          const available = o.key <= 1 || dataDays >= Math.min(o.key, 30);
          return (
            <button key={o.key} onClick={() => available && setBriefPeriod(o.key)} style={{
              padding: '8px 16px', borderRadius: 20,
              border: `1px solid ${briefPeriod === o.key ? COLORS.accent : COLORS.secondary}`,
              background: briefPeriod === o.key ? COLORS.accent : 'transparent',
              color: briefPeriod === o.key ? '#fff' : available ? COLORS.textSecondary : COLORS.textMuted,
              cursor: available ? 'pointer' : 'default',
              opacity: available ? 1 : 0.4,
              ...FONT.small, fontWeight: 500,
            }}>{o.label}{!available && ` (${Math.min(o.key, 30) - dataDays}일 후)`}</button>
          );
        })}
      </div>

      {/* 기간 합산 요약 */}
      {periodData && briefPeriod > 1 && (
        <div style={{ background: `${COLORS.accent}10`, border: `1px solid ${COLORS.accent}30`, borderRadius: 10, padding: '14px 18px', marginBottom: 20 }}>
          <div style={{ ...FONT.small, color: COLORS.accent, fontWeight: 600, marginBottom: 8 }}>
            {briefPeriod >= 365 ? '연간' : briefPeriod >= 30 ? '월간' : briefPeriod >= 7 ? '주간' : `${periodData.days}일간`} 합산 ({periodData.days}일 데이터)
          </div>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', ...FONT.small, color: COLORS.textSecondary }}>
            <span>소진 <strong style={{ color: COLORS.textBright }}>{fmtCount(periodData.totalConsumed)}</strong>건</span>
            <span>미판매 <strong style={{ color: SEVERITY_COLORS.error }}>{fmtCount(periodData.totalUnsold)}</strong>건</span>
            <span>신규오픈 <strong style={{ color: SEVERITY_COLORS.ok }}>{fmtCount(periodData.totalNewOpen)}</strong>건</span>
            <span>티취소 <strong style={{ color: '#3B82F6' }}>{fmtCount(periodData.totalCancel)}</strong>건</span>
            <span>평균 소진율 <strong style={{ color: COLORS.textBright }}>{periodData.avgRate != null ? periodData.avgRate + '%' : '-'}</strong></span>
          </div>
        </div>
      )}

      {/* A. KPI Cards (4열) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, marginBottom: 28 }}>
        <KpiCard title="잔여 티타임" value={fmt(kpi?.total_slots_today)} unit="개" icon={TrendingUp} color={COLORS.accent}
          tooltip="현재 카카오골프에서 판매 중인 전체 티타임 수. 전일 대비 증감과 미판매 건수를 포함합니다."
          subtext={`증감 ${kpi?.slot_delta > 0 ? '+' : ''}${fmt(kpi?.slot_delta)} (미판매 ${fmt(unsoldCount)})${weatherNote}`} />
        <KpiCard title="전일 소진" value={fmt(consumedCount)} unit="건"
          tooltip="어제까지 있었으나 오늘 사라진 티타임 수. 예약(판매)된 것으로 추정합니다. 소진율 = 소진 ÷ 전일 잔여 × 100"
          subtext={`소진율 ${consumeRate != null ? consumeRate + '%' : '-'}`}
          color={consumeRate > 5 ? SEVERITY_COLORS.warning : SEVERITY_COLORS.ok} icon={consumeRate > 5 ? TrendingDown : TrendingUp} />
        <KpiCard title="신규오픈 / 티취소" value={`${fmt(newOpenCount)} / ${fmt(cancelReopenCount)}`} unit="건"
          tooltip="신규오픈: 새로운 경기일의 티타임이 처음 등장. 티취소(재오픈): 기존 예약이 취소되어 다시 판매 가능해진 티타임."
          subtext={`신규 ${fmt(newOpenCount)} + 재오픈 ${fmt(cancelReopenCount)}`}
          color={SEVERITY_COLORS.ok} icon={TrendingUp} />
        <KpiCard title="특가 프로모션" value={fmtPct(kpi?.promo_ratio)} unit=""
          tooltip="전체 잔여 티타임 중 특가(할인 라벨) 비율. 특가부착 = 골프장이 할인 라벨을 새로 붙인 건수."
          subtext={`특가 ${fmt(kpi?.total_promo_slots || 0)}티 · 부착 ${kpi?.changes_by_type?.['특가부착'] || 0}건`} color="#F59E0B" />
      </div>

      {/* B. 미판매 현황 (KPI 직후) */}
      {unsold_summary && unsold_summary.total > 0 && (
        <>
          <SectionTitle title="전일 미판매 현황" icon="📉" />
          <div style={{ background: COLORS.cardBg, borderRadius: 12, padding: 20, border: `1px solid ${COLORS.secondary}`, marginBottom: 28 }}>
            <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
              <div>
                <div style={{ ...FONT.kpi, color: SEVERITY_COLORS.error, fontSize: 28 }}>{fmt(unsold_summary.total)}<span style={{ ...FONT.kpiLabel, marginLeft: 4 }}>건</span></div>
                <div style={{ ...FONT.small, color: COLORS.textMuted }}>미판매 티</div>
              </div>
              <div>
                <div style={{ ...FONT.kpi, color: SEVERITY_COLORS.warning, fontSize: 28 }}>{fmtLoss(unsold_summary.total_loss_krw)}</div>
                <div style={{ ...FONT.small, color: COLORS.textMuted }}>추정 손실액</div>
              </div>
              <div>
                <div style={{ ...FONT.kpi, color: '#F59E0B', fontSize: 28 }}>{unsold_summary.promo_unsold}<span style={{ ...FONT.kpiLabel, marginLeft: 4 }}>건 ({unsold_summary.promo_unsold_pct}%)</span></div>
                <div style={{ ...FONT.small, color: COLORS.textMuted }}>특가인데 미판매</div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 8, alignItems: 'center' }}>
              {(unsold_summary.by_course || []).map((c, idx) => {
                const maxCount = unsold_summary.by_course[0]?.count || 1;
                return (
                  <React.Fragment key={idx}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CourseBadge name={c.course_name} small />
                      <div style={{ flex: 1, height: 8, background: COLORS.secondary, borderRadius: 4, overflow: 'hidden' }}>
                        <div className="bar-fill" style={{ width: `${(c.count / maxCount) * 100}%`, height: '100%', background: SEVERITY_COLORS.error, borderRadius: 4, opacity: 0.7 }} />
                      </div>
                    </div>
                    <span style={{ ...FONT.small, color: COLORS.textSecondary, minWidth: 40, textAlign: 'right' }}>{c.count}건</span>
                    <span style={{ ...FONT.small, color: SEVERITY_COLORS.warning, minWidth: 60, textAlign: 'right' }}>{fmtLoss(c.loss_krw)}</span>
                  </React.Fragment>
                );
              })}
            </div>
            {unsold_summary.by_part && (
              <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 12 }}>
                시간대: {Object.entries(unsold_summary.by_part).map(([k, v]) => `${k} ${v}건`).join(' · ')}
              </div>
            )}
            {unsold_summary.by_weather_cause && Object.keys(unsold_summary.by_weather_cause).length > 0 && (
              <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 8 }}>
                기상원인: {Object.entries(unsold_summary.by_weather_cause).map(([k, v]) => `${k === '우천예보' ? '🌧️' : k === '맑음전환' ? '☀️' : ''} ${k} ${v}건`).join(' · ')}
              </div>
            )}
          </div>
        </>
      )}

      {/* C. 알림 배너 */}
      {alerts && alerts.length > 0 && (
        <>
          <SectionTitle title="주의사항" icon="⚠️" />
          <div style={{ display: 'grid', gap: 10, marginBottom: 28 }}>
            {alerts.slice(0, 5).map((alert, idx) => (
              <div key={idx} className="alert-hover" style={{
                background: COLORS.cardBg, borderLeft: `4px solid ${SEVERITY_COLORS[alert.level] || COLORS.secondary}`,
                borderRadius: 8, padding: '12px 16px', display: 'flex', gap: 12, alignItems: 'center'
              }}>
                <AlertCircle size={18} color={SEVERITY_COLORS[alert.level]} style={{ flexShrink: 0 }} />
                <div>
                  <span style={{ color: COLORS.textBright, ...FONT.body, fontWeight: 600 }}>{alert.course}</span>
                  <span style={{ color: COLORS.textSecondary, ...FONT.small, marginLeft: 12 }}>{alert.msg}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* C. 골프장 현황 카드 (재설계) */}
      <SectionTitle title="골프장 현황" icon="⛳" />
      {(() => {
        // 최소화 상태 + 순서 관리
        const MINI_STORAGE_KEY = 'verhill_minimized_courses';
        const ORDER_STORAGE_KEY = 'verhill_card_order';
        const [minimized, setMinimized] = React.useState(() => {
          try { return JSON.parse(localStorage.getItem(MINI_STORAGE_KEY) || '[]'); }
          catch { return []; }
        });
        const [cardOrder, setCardOrder] = React.useState(() => {
          try { return JSON.parse(localStorage.getItem(ORDER_STORAGE_KEY) || '[]'); }
          catch { return []; }
        });
        const doMinimize = (name) => {
          setMinimized(prev => {
            const next = [...prev, name];
            localStorage.setItem(MINI_STORAGE_KEY, JSON.stringify(next));
            return next;
          });
          // 순서에서 제거
          setCardOrder(prev => {
            const next = prev.filter(n => n !== name);
            localStorage.setItem(ORDER_STORAGE_KEY, JSON.stringify(next));
            return next;
          });
        };
        const doRestore = (name) => {
          setMinimized(prev => {
            const next = prev.filter(n => n !== name);
            localStorage.setItem(MINI_STORAGE_KEY, JSON.stringify(next));
            return next;
          });
          // 순서 맨 뒤에 추가
          setCardOrder(prev => {
            const next = [...prev.filter(n => n !== name), name];
            localStorage.setItem(ORDER_STORAGE_KEY, JSON.stringify(next));
            return next;
          });
        };
        // 애니메이션
        const [animating, setAnimating] = React.useState(null);
        const handleMinimize = (name) => {
          setAnimating(name);
          setTimeout(() => { doMinimize(name); setAnimating(null); }, 350);
        };
        const handleRestore = (name) => {
          doRestore(name);
          setAnimating('restore_' + name);
          setTimeout(() => setAnimating(null), 350);
        };
        // 순서 정렬: cardOrder에 있으면 그 순서, 없으면 기본순서(슬롯수) 뒤에 붙임
        const defaultSorted = (consumption || []).sort((a, b) => (b.today_slots || 0) - (a.today_slots || 0));
        const sortedConsumption = [...defaultSorted].sort((a, b) => {
          const ai = cardOrder.indexOf(a.course_name);
          const bi = cardOrder.indexOf(b.course_name);
          if (ai === -1 && bi === -1) return 0; // 둘 다 순서 없음 → 기본순서 유지
          if (ai === -1) return -1; // a는 순서 없음(기본) → 앞에
          if (bi === -1) return 1;  // b는 순서 없음(기본) → 앞에
          return ai - bi;           // 둘 다 순서 있음 → 순서대로
        });
        const miniStyle = `
          @keyframes shrinkToDock { 0% { transform: scale(1); opacity: 1; } 100% { transform: scale(0.15) translateY(80px); opacity: 0; } }
          @keyframes growFromDock { 0% { transform: scale(0.15) translateY(80px); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
          .card-shrink { animation: shrinkToDock 0.35s ease-in forwards; }
          .card-grow { animation: growFromDock 0.35s ease-out forwards; }
          .dock-pill { transition: all 0.2s ease; cursor: pointer; }
          .dock-pill:hover { transform: scale(1.08); }
          .dock-pill:active { transform: scale(0.95); }
        `;

        return <>
          <style>{miniStyle}</style>

          {/* 최소화된 구장 독(dock) */}
          {minimized.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
              {minimized.map(name => (
                <div key={name} className="dock-pill" onClick={() => handleRestore(name)}
                  style={{ background: COLORS.cardBg, border: `1px solid ${COLORS.secondary}`, borderRadius: 20,
                    padding: '6px 14px', ...FONT.small, color: COLORS.textSecondary, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>{'⛳'}</span>
                  <span>{name}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16, marginBottom: 28 }}>
            {sortedConsumption.filter(c => !minimized.includes(c.course_name)).map((c, idx) => {
              const sp = c.sales_power;
              const dd = c.dday_dist || {};
              const maxDday = Math.max(...Object.values(dd).map(d => d.slots || 0), 1);
              const tiers = c.membership_tiers;
              const isAnimating = animating === c.course_name;
              const isRestoring = animating === 'restore_' + c.course_name;

              const TierBlock = ({ label, t }) => {
                const tsp = t.sales_power;
                return (
                  <div style={{ background: COLORS.bg, borderRadius: 8, padding: '10px 14px', marginTop: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ ...FONT.small, color: COLORS.textSecondary, fontWeight: 600 }}>[{label}]</span>
                      <span style={{ ...FONT.small, fontWeight: 600 }}>
                        {t.slots}티 <span style={{ color: COLORS.textMuted }}>({t.slots_per_unit}/9홀)</span>
                        {tsp && <span style={{ marginLeft: 8 }}>{tsp.icon} {tsp.grade}</span>}
                      </span>
                    </div>
                    <div style={{ ...FONT.tiny, color: COLORS.textMuted }}>
                      {Object.entries(t.sub_slot_counts || {}).map(([sub, cnt]) => `${sub.replace(/\(.*\)/, '')} ${cnt}`).join(' · ')}
                    </div>
                    {t.consumed != null && (
                      <div style={{ ...FONT.tiny, color: COLORS.textSecondary, marginTop: 4 }}>
                        소진 <span style={{ color: SEVERITY_COLORS.error }}>{t.consumed}</span>
                        {t.cancel_reopen > 0 && <> · 티취소 <span style={{ color: SEVERITY_COLORS.ok }}>+{t.cancel_reopen}</span></>}
                        {t.consume_rate != null && <> · 소진율 {t.consume_rate}%</>}
                      </div>
                    )}
                  </div>
                );
              };

              return (
                <div key={c.course_name} className={isAnimating ? 'card-shrink' : isRestoring ? 'card-grow' : ''}
                  style={{ background: COLORS.cardBg, borderRadius: 12, padding: '18px 20px', border: `1px solid ${COLORS.secondary}` }}>
                  {/* 헤더: 골프장명 + 판매력 + 최소화 버튼 */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <CourseBadge name={c.course_name} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {sp && <span title={`판매력 등급: ${sp.grade}\n잔여 티 수, 소진율, 가격 경쟁력 등을 종합 평가한 판매 강도 지표`} style={{ ...FONT.body, fontWeight: 700, cursor: 'help' }}>{sp.icon} {sp.grade}</span>}
                      <button onClick={() => handleMinimize(c.course_name)}
                        style={{ background: COLORS.secondary, border: 'none', borderRadius: 6, width: 24, height: 24,
                          color: COLORS.textMuted, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 14, lineHeight: 1 }}
                        title="카드 최소화">{'−'}</button>
                    </div>
                  </div>

              {/* 프로필 정보 */}
              {c.profile && (
                <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 8 }}>
                  {c.profile.holes && `${c.profile.holes}홀`}
                  {c.profile.type && ` · ${c.profile.type}`}
                  {c.profile.member_count != null && ` · 회원권 ${fmt(c.profile.member_count)}구좌`}
                </div>
              )}

              {/* 구장별 날씨 */}
              {c.weather && c.weather.observation && (
                <div style={{ ...FONT.tiny, color: COLORS.textSecondary, marginBottom: 4 }}>
                  {c.weather.observation.precip_type > 0 ? '🌧️' : '☀️'} {c.weather.observation.temperature}°
                  {c.weather.observation.rainfall > 0 ? ` · 강수 ${c.weather.observation.rainfall}mm` : ''}
                  {c.weather.observation.wind_speed ? ` · 풍속 ${c.weather.observation.wind_speed}m/s` : ''}
                </div>
              )}
              {c.weather && c.weather.forecasts && c.weather.forecasts.length > 0 && (
                <div style={{ display: 'flex', gap: 8, marginBottom: 8, ...FONT.tiny }}>
                  {c.weather.forecasts.map((f, fi) => (
                    <span key={fi} title={`${f.play_date} 경기일 기상예보\n강수확률: ${f.rain_prob}%${f.changed ? ` · 예보변화: ${f.changed}` : ''}${f.rain_prob >= 60 ? '\n⚠️ 우천 가능성 높음 — 소진 둔화 예상' : ''}`}
                      style={{ color: f.rain_prob >= 60 ? '#EF4444' : COLORS.textMuted, cursor: 'help' }}>
                      {f.play_date.slice(5)} {f.icon} {f.rain_prob}%
                      {f.changed === '악화' && <span style={{ color: '#EF4444' }}> ⚠️</span>}
                    </span>
                  ))}
                </div>
              )}

              {/* 잔여 + 정규화 */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <div>
                  <span style={{ ...FONT.kpi, color: COLORS.textBright, fontSize: 28 }}>{fmt(c.today_slots)}</span>
                  <span style={{ ...FONT.small, color: COLORS.textMuted, marginLeft: 6 }}>({c.slots_per_unit}/9홀)</span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ ...FONT.body, color: c.slot_delta > 0 ? SEVERITY_COLORS.ok : c.slot_delta < 0 ? SEVERITY_COLORS.error : COLORS.textMuted, fontWeight: 600 }}>
                    {c.slot_delta != null ? `${c.slot_delta > 0 ? '+' : ''}${c.slot_delta}` : '-'}
                  </span>
                </div>
              </div>

              {/* 변동 내역 */}
              <div style={{ ...FONT.tiny, color: COLORS.textSecondary, marginBottom: 12 }}>
                소진 <span style={{ color: SEVERITY_COLORS.error }}>{c.consumed ?? '-'}</span>
                {' · '}미판매 {c.unsold ?? 0}
                {c.cancel_reopen > 0 && <> · 티취소 <span style={{ color: SEVERITY_COLORS.ok }}>+{c.cancel_reopen}</span></>}
                {c.new_open > 0 && <> · 신규 <span style={{ color: SEVERITY_COLORS.ok }}>+{c.new_open}</span></>}
                {c.consume_rate != null && <> · 소진율 <strong>{c.consume_rate}%</strong></>}
                {c.consumption_velocity && c.consumption_velocity.acceleration !== '판단보류' && (
                  <span title={c.consumption_velocity.acceleration === '가속' ? '소진 속도가 빨라지고 있음 — 최근 소진율이 이전보다 증가 추세' : c.consumption_velocity.acceleration === '주춤' ? '소진 속도가 둔화됨 — 최근 소진율이 이전보다 감소 추세' : '소진 속도가 일정함 — 큰 변화 없이 유지 중'}
                    style={{ marginLeft: 4, cursor: 'help', color: c.consumption_velocity.acceleration === '가속' ? '#EF4444' : c.consumption_velocity.acceleration === '주춤' ? '#F59E0B' : COLORS.textMuted }}>
                    {c.consumption_velocity.acceleration === '가속' ? '🔥가속' : c.consumption_velocity.acceleration === '주춤' ? '⚠️주춤' : '➡️유지'}
                  </span>
                )}
                {c.weather_note && <> · <span style={{ color: c.weather_note === '우천예보' ? '#3B82F6' : '#10B981' }}>{c.weather_note === '우천예보' ? '🌧️' : '☀️'} {c.weather_note}</span></>}
              </div>

              {/* D-day 분포 바 */}
              <div style={{ marginBottom: 12 }}>
                {['D1-7', 'D8-14', 'D15+'].map(bucket => {
                  const d = dd[bucket] || { slots: 0 };
                  const pct = maxDday > 0 ? (d.slots / maxDday) * 100 : 0;
                  return (
                    <div key={bucket} title={bucket === 'D1-7' ? `임박 경기일 (1~7일 뒤) — ${d.slots}개 티타임` : bucket === 'D8-14' ? `중기 경기일 (8~14일 뒤) — ${d.slots}개 티타임` : `장기 경기일 (15일 이후) — ${d.slots}개 티타임`}
                      style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ ...FONT.tiny, color: COLORS.textMuted, width: 40, textAlign: 'right' }}>{bucket}</span>
                      <div style={{ flex: 1, height: 10, background: COLORS.secondary, borderRadius: 5, overflow: 'hidden' }}>
                        <div className="bar-fill" style={{ width: `${pct}%`, height: '100%', background: bucket === 'D1-7' ? '#EF4444' : bucket === 'D8-14' ? '#F59E0B' : '#3B82F6', borderRadius: 5 }} />
                      </div>
                      <span style={{ ...FONT.tiny, color: COLORS.textSecondary, width: 40 }}>{d.slots}</span>
                    </div>
                  );
                })}
              </div>

              {/* 시간대별 현황 (4행 고정) */}
              {c.demand_density && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', gap: 4, marginBottom: 6, ...FONT.tiny, color: COLORS.textMuted }}>
                    <span style={{ width: 55 }}></span>
                    <span style={{ width: 45, textAlign: 'center' }}>수요</span>
                    <span style={{ flex: 1, textAlign: 'center' }}>소진율</span>
                    <span style={{ width: 40, textAlign: 'right' }}>잔여</span>
                  </div>
                  {['06~09시', '09~12시', '12~15시', '15~17시'].map((label, di) => {
                    const d = (c.demand_density || []).find(x => x.label === label);
                    if (!d) return (
                      <div key={di} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                        <span style={{ ...FONT.tiny, color: COLORS.textMuted, width: 55, textAlign: 'right' }}>{label}</span>
                        <span style={{ ...FONT.tiny, width: 45, textAlign: 'center', color: COLORS.textMuted }}>-</span>
                        <div style={{ flex: 1 }}><div style={{ height: 8, background: COLORS.secondary, borderRadius: 4, opacity: 0.3 }} /></div>
                        <span style={{ ...FONT.tiny, color: COLORS.textMuted, width: 40, textAlign: 'right' }}>0개</span>
                      </div>
                    );
                    const barColor = d.consume_rate >= 95 ? '#DC2626' : d.consume_rate >= 80 ? '#EF4444' : d.consume_rate >= 50 ? '#F59E0B' : '#3B82F6';
                    return (
                      <div key={di} style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                        <span style={{ ...FONT.tiny, color: COLORS.textMuted, width: 55, textAlign: 'right' }}>{d.label}</span>
                        <span style={{ ...FONT.tiny, width: 45, textAlign: 'center' }}>{d.signal}{d.demand}</span>
                        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <div style={{ flex: 1, height: 8, background: COLORS.secondary, borderRadius: 4, overflow: 'hidden' }}>
                            <div className="bar-fill" style={{ width: `${d.consume_rate}%`, height: '100%', background: barColor, borderRadius: 4 }} />
                          </div>
                          <span style={{ ...FONT.tiny, color: barColor, width: 30, fontWeight: 600 }}>{d.consume_rate}%</span>
                        </div>
                        <span style={{ ...FONT.tiny, color: COLORS.textSecondary, width: 40, textAlign: 'right' }}>{d.remaining}개</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 예상 내장객 그린피+카트 */}
              {c.revenue && c.revenue.total_revenue > 0 && (() => {
                const rev = c.revenue;
                const cartPerTeam = rev.cart_fee_team || 0;
                return (
                <div style={{ background: COLORS.bg, borderRadius: 8, padding: '10px 14px', marginBottom: 8 }}>
                  {/* 1행: 명칭 + 총액 */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 2 }}>
                    <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>{'💰 예상 내장객 그린피+카트'}</span>
                    <span style={{ ...FONT.small, color: COLORS.textBright, fontWeight: 700 }}>{fmtLoss(rev.total_revenue)}</span>
                  </div>
                  {/* 2행: play_date, 팀수 */}
                  <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 2 }}>
                    {rev.play_date ? `${rev.play_date.slice(5)}(${rev.weekday_type || ''})` : ''}{' '}
                    {rev.booked_teams ?? rev.reserved_teams ?? '-'}/{rev.daily_max}팀
                  </div>
                  {/* 3행: 산출 공식 */}
                  <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 6, fontSize: 10 }}>
                    산출: (시간대 평균가 × 4명 + 카트) × 팀수
                  </div>
                  {/* 시간대별 breakdown */}
                  {rev.by_part && Object.keys(rev.by_part).length > 0 && (
                    <div style={{ ...FONT.tiny, marginBottom: 6 }}>
                      {['1부', '2부', '오후'].map(pt => {
                        const p = rev.by_part[pt];
                        if (!p || p.max_teams === 0) return null;
                        const teamPrice = p.avg_green_fee * 4 + cartPerTeam;
                        return React.createElement('div', {
                          key: pt,
                          style: { display: 'flex', justifyContent: 'space-between', marginBottom: 1 }
                        }, [
                          React.createElement('span', { key: 'l', style: { color: COLORS.textSecondary } },
                            `${pt}  ${p.booked}팀  팀단가 ${(teamPrice/10000).toFixed(1)}만`),
                          React.createElement('span', { key: 'r', style: { color: COLORS.textBright } },
                            fmtLoss(p.revenue)),
                        ]);
                      })}
                    </div>
                  )}
                  {/* 미판매 손실 */}
                  {rev.unsold_loss > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', ...FONT.tiny, borderTop: `1px solid ${COLORS.secondary}33`, paddingTop: 4 }}>
                      <span style={{ color: SEVERITY_COLORS.error }}>미판매 손실</span>
                      <span style={{ color: SEVERITY_COLORS.error }}>-{fmtLoss(rev.unsold_loss)}</span>
                    </div>
                  )}
                </div>
                );
              })()}

              {/* 대중/회원 분리 (골드레이크, 해피니스) */}
              {tiers && (
                <div>
                  <TierBlock label="대중제" t={tiers['대중제']} />
                  <TierBlock label="회원제" t={tiers['회원제']} />
                </div>
              )}
            </div>
          );
        })}
          </div>
        </>;
      })()}

      {/* D. 가격 변동 이벤트 */}
      {price_changes && (
        <>
          <SectionTitle title="가격 변동 이벤트" icon="📊" />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
            {['인하', '인상'].map(type => (
              <div key={type}>
                <h4 style={{ color: EVENT_COLORS[type], ...FONT.body, fontWeight: 700, marginBottom: 12 }}>
                  {type === '인하' ? '📉' : '📈'} {type} ({(price_changes[type] || []).length}건)
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 400, overflowY: 'auto' }}>
                  {(price_changes[type] || []).map((evt, idx) => (
                    <div key={idx} style={{ background: COLORS.secondary, padding: '12px 14px', borderRadius: 8, ...FONT.small }}>
                      <div style={{ color: COLORS.textBright, fontWeight: 600, marginBottom: 4 }}>{evt.course_name} · {evt.course_sub}</div>
                      <div style={{ color: COLORS.textSecondary }}>{evt.play_date} {evt.tee_time}: {fmtMan(evt.old_price_krw)} → {fmtMan(evt.new_price_krw)} ({evt.delta_pct > 0 ? '+' : ''}{evt.delta_pct}%)</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* E. 기상 현황 */}
      {weather && weather.forecasts && weather.forecasts.length > 0 && (
        <>
          <SectionTitle title="기상 영향 추적" icon="⛅" />
          <div style={{ background: COLORS.cardBg, borderRadius: 12, padding: 20, border: `1px solid ${COLORS.secondary}`, marginBottom: 28 }}>
            {/* Per-course weather matrix using consumption data */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.tiny }}>
                <thead>
                  <tr>
                    <th style={{ padding: '6px 10px', textAlign: 'left', color: COLORS.textSecondary }}>골프장</th>
                    {weather.forecasts.map((f, i) => {
                      const dayOfWeek = new Date(f.play_date).getDay();
                      const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
                      return (
                        <th key={i} style={{ padding: '6px 8px', textAlign: 'center', color: isWeekend ? '#F59E0B' : COLORS.textMuted }}>
                          {f.play_date.slice(5)}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {(consumption || []).map((c, ci) => (
                    <tr key={ci} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                      <td style={{ padding: '4px 10px' }}><CourseBadge name={c.course_name} small /></td>
                      {(c.weather?.forecasts || weather.forecasts).map((f, fi) => (
                        <td key={fi} style={{ padding: '4px 8px', textAlign: 'center' }}>
                          <span style={{ color: f.rain_prob >= 60 ? '#EF4444' : COLORS.textMuted }}>
                            {f.icon} {f.rain_prob}%
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* (미판매 섹션 → KPI 직후로 이동됨) */}

      {/* F. 향후 7일 캘린더 */}
      {calendar && calendar.length > 0 && (
        <>
          <SectionTitle title="향후 7일 요약" icon="📅" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, marginBottom: 28 }}>
            {calendar.map((day, idx) => {
              const isWeekend = day.weekday_type === '토요일' || day.weekday_type === '일요일';
              return (
                <div key={idx} className="card-hover" title={`${day.play_date} (${day.weekday_type}) — D-${day.d_day}\n잔여 티타임: ${fmt(day.slots)}개\n평균 가격: ${fmtMan(day.avg_price)}\n특가 티타임: ${day.promo_slots}개${isWeekend ? '\n📅 주말 — 수요 높음' : ''}`}
                  style={{
                  background: COLORS.cardBg, borderRadius: 10, padding: 14,
                  border: `1px solid ${COLORS.secondary}`, ...FONT.small
                }}>
                  <div style={{ color: COLORS.textBright, fontWeight: 700, marginBottom: 6, fontSize: 14 }}>
                    {day.play_date} <span style={{ color: isWeekend ? '#F59E0B' : COLORS.textMuted }}>({day.weekday_type})</span>
                  </div>
                  <div style={{ color: COLORS.textSecondary }}>잔여 {fmt(day.slots)}개 · 평균 {fmtMan(day.avg_price)}</div>
                  <div style={{ color: COLORS.textMuted, marginTop: 2 }}>특가 {day.promo_slots}개 · D-{day.d_day}</div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 2: 슬롯 생애주기
// ═══════════════════════════════════════════════════
const Tab2 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tabData = (RAW_DATA.tab1 || {})[context.anchorDate] || null;
  const consumption = tabData?.consumption;

  if (!consumption || consumption.length === 0) return <NoData msg="소비 데이터가 없습니다." />;

  // 데이터 품질 확인 (첫 수집일 등 비교 불가 케이스)
  const dataQuality = consumption[0]?.data_quality;
  const dataNoteMsg = consumption[0]?.data_note;
  const isUnavailable = dataQuality === 'unavailable';

  const totals = useMemo(() => {
    const sum = (key) => consumption.reduce((s, r) => s + (r[key] || 0), 0);
    return { consumed: sum('consumed'), new_open: sum('new_open'), cancel_reopen: sum('cancel_reopen'), unsold: sum('unsold'), stayed: sum('stayed') };
  }, [consumption]);

  const chartData = useMemo(() =>
    consumption.map(r => ({
      name: r.course_name,
      stayed: r.stayed || 0,
      consumed: r.consumed || 0,
      new_open: r.new_open || 0,
      cancel_reopen: r.cancel_reopen || 0,
      consume_rate: r.consume_rate,
      today_slots: r.today_slots,
    })).sort((a, b) => (b.today_slots || 0) - (a.today_slots || 0))
  , [consumption]);

  return (
    <div>
      <InfoBanner text={"🔄 어제 대비 판매 현황을 추적합니다.\n소진율 = 소진 티 ÷ 전일 티 × 100 · 증감 = (신규오픈 + 티취소) - (소진 + 미판매)"} />
      <DateNavigator context={context} metadata={metadata} />
      {isUnavailable && dataNoteMsg && (
        <InfoBanner text={dataNoteMsg} level="warning" />
      )}

      {/* KPI 3열 — 비교 불가 시 오늘 티만 */}
      {!isUnavailable && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 28 }}>
          <KpiCard title="소진(예약)" value={fmt(totals.consumed)} unit="건" color={SEVERITY_COLORS.error} subtext="어제 있다 오늘 없는 티"
            tooltip="전일에 존재했으나 오늘 사라진 티타임. 예약으로 판매된 것으로 추정합니다." />
          <KpiCard title="미판매" value={fmt(totals.unsold)} unit="건" color={COLORS.textMuted} subtext="팔리지 않고 경기일 지난 티"
            tooltip="판매되지 않은 채 경기일이 지나 자동 소멸된 티타임 수." />
          <KpiCard title="신규오픈" value={fmt(totals.new_open)} unit="건" color={SEVERITY_COLORS.ok} subtext="새 경기일 티"
            tooltip="오늘 새로 등장한 경기일의 티타임. 골프장이 새 날짜를 오픈한 것입니다." />
          <KpiCard title="티취소(재오픈)" value={fmt(totals.cancel_reopen)} unit="건" color="#3B82F6" subtext="예약취소로 재등장"
            tooltip="이전에 소진(예약)되었다가 취소되어 다시 판매 가능해진 티타임." />
        </div>
      )}

      {/* Bar Chart */}
      <SectionTitle title="코스별 티 현황" icon="📊" />
      <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28 }}>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 80, right: 20, top: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
            <XAxis type="number" tick={{ fill: COLORS.textSecondary, fontSize: 12 }} />
            <YAxis dataKey="name" type="category" tick={{ fill: COLORS.textMain, fontSize: 12 }} width={75} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ ...FONT.small, color: COLORS.textSecondary }} />
            {isUnavailable ? (
              <Bar dataKey="today_slots" name="오늘 티" fill="#4F46E5" />
            ) : (
              <>
                <Bar dataKey="stayed" name="유지" stackId="a" fill="#475569" />
                <Bar dataKey="consumed" name="소진" stackId="a" fill="#EF4444" />
                <Bar dataKey="new_open" name="신규오픈" stackId="b" fill="#10B981" />
                <Bar dataKey="cancel_reopen" name="티취소" stackId="b" fill="#3B82F6" />
              </>
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 상세 테이블 */}
      <SectionTitle title="상세 테이블" icon="📋" />
      <div style={{ overflowX: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {isUnavailable
                ? ['골프장', '오늘 티'].map(h => (
                    <th key={h} style={{ padding: '14px 16px', textAlign: h === '골프장' ? 'left' : 'right', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
                  ))
                : ['골프장', '전일', '오늘', '소진', '티취소', '신규', '소진율'].map(h => {
                    const tips = { '전일': '어제 기준 잔여 티타임 수', '오늘': '오늘 기준 잔여 티타임 수', '소진': '어제→오늘 사이 사라진(예약된) 티', '티취소': '예약 취소로 재등장한 티', '신규': '새 경기일이 오픈되어 추가된 티', '소진율': '소진 ÷ 전일 잔여 × 100%' };
                    return <th key={h} title={tips[h]} style={{ padding: '14px 16px', textAlign: h === '골프장' ? 'left' : 'right', color: COLORS.textSecondary, ...FONT.tableHeader, cursor: tips[h] ? 'help' : 'default' }}>{h}</th>;
                  })
              }
            </tr>
          </thead>
          <tbody>
            {consumption.sort((a, b) => (b.today_slots || 0) - (a.today_slots || 0)).map((row, idx) => {
              if (isUnavailable) {
                return (
                  <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                    <td style={{ padding: '14px 16px' }}><CourseBadge name={row.course_name} small /></td>
                    <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textBright, fontWeight: 600 }}>{fmt(row.today_slots)}</td>
                  </tr>
                );
              }
              const rateColor = row.consume_rate >= 25 ? SEVERITY_COLORS.error : row.consume_rate >= 15 ? SEVERITY_COLORS.warning : SEVERITY_COLORS.ok;
              return (
                <tr key={idx} className="table-hover-row" style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                  <td style={{ padding: '14px 16px' }}><CourseBadge name={row.course_name} small /></td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textSecondary }}>{fmt(row.prev_slots)}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textBright, fontWeight: 600 }}>{fmt(row.today_slots)}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: SEVERITY_COLORS.error }}>-{row.consumed}{row.weather_note ? (row.weather_note === '우천예보' ? ' 🌧️' : ' ☀️') : ''}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: '#3B82F6' }}>+{row.cancel_reopen || 0}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: SEVERITY_COLORS.ok }}>+{row.new_open || 0}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
                      <span style={{ color: rateColor, fontWeight: 600 }}>{fmtPct(row.consume_rate)}</span>
                      <div style={{ width: 60, height: 6, background: COLORS.secondary, borderRadius: 3, overflow: 'hidden' }}>
                        <div className="bar-fill" style={{ width: `${Math.min(row.consume_rate, 100)}%`, height: '100%', background: rateColor, borderRadius: 3 }} />
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 3: 소진 패턴
// ═══════════════════════════════════════════════════
const Tab3 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tabData = (RAW_DATA.tab3 || {})[context.anchorDate] || null;

  if (!tabData) return <NoData />;

  const { heatmap, course_patterns, today_distribution } = tabData;

  const pivotedHeatmap = useMemo(() => {
    if (!heatmap || !heatmap.length) return [];
    const map = {};
    heatmap.forEach(row => {
      if (!map[row.weekday]) map[row.weekday] = { weekday: row.weekday };
      map[row.weekday][row.part] = row;
    });
    return Object.values(map);
  }, [heatmap]);

  const parts = useMemo(() => [...new Set((heatmap || []).map(h => h.part))], [heatmap]);

  return (
    <div>
      <InfoBanner text={"🔥 전일 대비 예약으로 사라진 티의 비율을 요일×시간대로 분석합니다.\n소진율 = 소진 건수 ÷ 전일 잔여 × 100\n미판매(경기일 지남)·신규오픈·티취소는 제외한 순수 예약 소진입니다."} />
      <DateNavigator context={context} metadata={metadata} />

      {/* A. 히트맵 */}
      <SectionTitle title="요일 × 시간대 소진율 히트맵" icon="🔥" />
      <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28, overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 400 }}>
          <thead>
            <tr>
              <th style={{ padding: 12, color: COLORS.textSecondary, ...FONT.tableHeader, textAlign: 'left', borderRight: `1px solid ${COLORS.secondary}` }}>요일</th>
              {parts.map(p => (
                <th key={p} style={{ padding: 12, color: COLORS.textSecondary, ...FONT.tableHeader, textAlign: 'center' }}>{p}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pivotedHeatmap.map((row, idx) => (
              <tr key={idx} style={{ borderTop: `1px solid ${COLORS.secondary}` }}>
                <td style={{ padding: 12, color: COLORS.textBright, ...FONT.body, fontWeight: 600, borderRight: `1px solid ${COLORS.secondary}` }}>
                  {row.weekday}
                </td>
                {parts.map(part => {
                  const cell = row[part];
                  const rate = cell?.consume_rate || 0;
                  const bgColor = rate >= 20 ? '#EF4444' : rate >= 15 ? '#F59E0B' : rate >= 10 ? '#3B82F6' : '#10B981';
                  return (
                    <td key={part} style={{
                      padding: 12, background: `${bgColor}25`, borderLeft: `1px solid ${COLORS.secondary}`,
                      textAlign: 'center', minWidth: 80, minHeight: 60
                    }}>
                      <div style={{ fontSize: 18, fontWeight: 700, color: bgColor }}>{fmtPct(rate)}</div>
                      <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 2 }}>{cell?.consumed || 0}/{cell?.total || 0}</div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* B. 코스별 소진율 카드 */}
      <SectionTitle title="코스별 소진율" icon="📊" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 28 }}>
        {(course_patterns || []).sort((a, b) => b.consume_rate - a.consume_rate).map((item, idx) => {
          const rateColor = item.consume_rate >= 20 ? SEVERITY_COLORS.error : item.consume_rate >= 10 ? SEVERITY_COLORS.warning : SEVERITY_COLORS.ok;
          return (
            <div key={idx} className="card-hover" style={{ background: COLORS.cardBg, border: `1px solid ${COLORS.secondary}`, borderRadius: 10, padding: 16 }}>
              <CourseBadge name={item.course_name} small />
              <div style={{ fontSize: 24, fontWeight: 700, color: rateColor, marginTop: 10 }}>{fmtPct(item.consume_rate)}</div>
              <div style={{ color: COLORS.textMuted, ...FONT.small, marginTop: 4 }}>{item.consumed}/{item.total} 소진</div>
              <div style={{ height: 6, background: COLORS.secondary, borderRadius: 3, marginTop: 10, overflow: 'hidden' }}>
                <div className="bar-fill" style={{ width: `${Math.min(item.consume_rate, 100)}%`, height: '100%', background: rateColor, borderRadius: 3 }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* C. 분포 차트 */}
      <SectionTitle title="시간대별 티 분포" icon="📈" />
      <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20 }}>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={(today_distribution || []).map(r => ({ name: `${r.weekday_type} ${r.part_type}`, slots: r.slots, promo: r.promo_slots }))}
                    margin={{ left: 10, right: 10, top: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
            <XAxis dataKey="name" tick={{ fill: COLORS.textSecondary, fontSize: 11 }} angle={-30} textAnchor="end" />
            <YAxis tick={{ fill: COLORS.textSecondary, fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ ...FONT.small }} />
            <Bar dataKey="slots" name="전체 티" fill="#3B82F6" stackId="a" />
            <Bar dataKey="promo" name="특가 티" fill="#F59E0B" stackId="b" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 4: 가격 흐름
// ═══════════════════════════════════════════════════
const Tab4 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tab4 = (RAW_DATA.tab4 || {})[context.anchorDate] || {};
  const [subTab, setSubTab] = useState(0);
  const [ddayFilter, setDdayFilter] = useState([1, 30]);
  const [screenWidth] = useState(window.innerWidth);
  const isMobile = screenWidth < 768;

  // D-day 범위 상태 (산점도용)
  const allDdays = useMemo(() => {
    const days = [...new Set((tab4.scatter || []).map(r => r.d_day))].sort((a, b) => a - b);
    return days.length ? days : [0, 30];
  }, [tab4.scatter]);
  const [ddayRange, setDdayRange] = useState([Math.max(1, allDdays[0] || 1), allDdays[allDdays.length - 1] || 30]);

  // ddayFilter 변경 시 ddayRange도 연동
  useEffect(() => {
    setDdayRange(ddayFilter);
  }, [ddayFilter]);

  // 기준일 변경 시 D-day 범위 리셋
  useEffect(() => {
    setDdayRange([Math.max(1, allDdays[0] || 1), allDdays[allDdays.length - 1] || 30]);
  }, [context.anchorDate]);

  // dday_trend pivot: flat array → d_day keyed with course columns
  const trendData = useMemo(() => {
    const raw = tab4.dday_trend || [];
    const map = {};
    raw.forEach(r => {
      if (!map[r.d_day]) map[r.d_day] = { d_day: r.d_day };
      map[r.d_day][r.course_name] = Math.round(r.avg_price / 10000);
    });
    return Object.values(map).sort((a, b) => b.d_day - a.d_day);
  }, [tab4.dday_trend]);

  const courses = useMemo(() => [...new Set((tab4.dday_trend || []).map(r => r.course_name))], [tab4.dday_trend]);

  // 주말 D-day 집합 (산점도/추세 차트 배경 밴드용)
  const weekendDdays = useMemo(() => {
    const set = new Set();
    (tab4.scatter || []).forEach(r => {
      if (r.weekday_type === '토요일' || r.weekday_type === '일요일') set.add(r.d_day);
    });
    (tab4.dday_trend || []).forEach(r => {
      if (r.weekday_type === '토요일' || r.weekday_type === '일요일') set.add(r.d_day);
    });
    return set;
  }, [tab4.scatter, tab4.dday_trend]);

  // 기상 악화 D-day 목록 (세로 참조선용)
  const forecastChangeDdays = useMemo(() => {
    const tab1Data = (RAW_DATA.tab1 || {})[context.anchorDate];
    const forecasts = tab1Data?.weather?.forecasts || [];
    const result = [];
    forecasts.forEach(f => {
      if (f.forecast_changed === '악화' && f.play_date) {
        // play_date에서 d_day 역산 (scatter 데이터에서 매칭)
        const matchDdays = (tab4.scatter || []).filter(r => r.play_date === f.play_date).map(r => r.d_day);
        if (matchDdays.length > 0) {
          result.push(matchDdays[0]);
        }
      }
    });
    return [...new Set(result)];
  }, [RAW_DATA, context.anchorDate, tab4.scatter]);

  // 골프장 토글 (산점도용)
  const [visibleCourses, setVisibleCourses] = useState(() => {
    const init = {};
    courses.forEach(c => { init[c] = true; });
    return init;
  });
  const [courseOrder, setCourseOrder] = useState(() => {
    // Default order: 베르힐 outermost
    return ['광주CC', '르오네뜨', '어등산', '푸른솔장성', '해피니스', '골드레이크', '무등산', '베르힐'];
  });
  const toggleCourse = (c) => {
    setVisibleCourses(prev => {
      const next = { ...prev, [c]: !prev[c] };
      if (next[c]) {
        // Re-selected: move to end (outermost)
        setCourseOrder(order => [...order.filter(x => x !== c), c]);
      }
      return next;
    });
  };
  const toggleAll = () => {
    const allOn = Object.values(visibleCourses).every(v => v);
    const next = {};
    courses.forEach(c => { next[c] = !allOn; });
    setVisibleCourses(next);
  };

  // 범위 + 골프장 필터된 산점도 데이터
  const filteredScatter = useMemo(() => {
    const lo = ddayFilter[0], hi = ddayFilter[1];
    const live = (tab4.scatter || []).filter(r =>
      r.d_day >= lo && r.d_day <= hi && visibleCourses[r.course_name] !== false
    );
    const ghosts = (tab4.ghost_events || []).filter(r =>
      r.d_day >= lo && r.d_day <= hi && visibleCourses[r.course_name] !== false
    );
    return [...live, ...ghosts];
  }, [tab4.scatter, tab4.ghost_events, ddayFilter, visibleCourses]);

  // 산점도 가격 범위
  const scatterPriceRange = useMemo(() => {
    if (!filteredScatter.length) return [0, 300000];
    const prices = filteredScatter.map(r => r.price_krw);
    const prevPrices = filteredScatter.filter(r => r.previous_price_krw).map(r => r.previous_price_krw);
    const all = [...prices, ...prevPrices];
    return [Math.min(...all) * 0.9, Math.max(...all) * 1.05];
  }, [filteredScatter]);

  // 버블 집계 (5000원 버킷) — 컴포넌트 레벨에서 useMemo
  const BUCKET = 10000;
  const bubbleData = useMemo(() => {
    const map = {};
    filteredScatter.forEach(r => {
      const bucket = Math.round(r.price_krw / BUCKET) * BUCKET;
      const key = `${r.course_name}|${r.d_day}|${bucket}`;
      if (!map[key]) map[key] = { course_name: r.course_name, d_day: r.d_day, price: bucket, count: 0, promo: 0, changed: 0, ghost: 0, drop_sum: 0, rise_sum: 0, tee_times: [] };
      map[key].count++;
      if (r.ghost) map[key].ghost++;
      if (r.promo_flag) map[key].promo++;
      if (r.weekday_type === '토요일' || r.weekday_type === '일요일') { if (!map[key].weekend) map[key].weekend = 0; map[key].weekend++; }
      if (r.price_changed_flag && r.previous_price_krw) {
        map[key].changed++;
        const diff = r.previous_price_krw - r.price_krw;
        if (diff > 0) map[key].drop_sum += diff;
        else map[key].rise_sum += Math.abs(diff);
        if (r.tee_time) map[key].tee_times.push({ time: r.tee_time, prev: r.previous_price_krw, curr: r.price_krw, ghost: !!r.ghost });
      } else if (r.price_changed_flag) {
        map[key].changed++;
        if (r.tee_time) map[key].tee_times.push({ time: r.tee_time, curr: r.price_krw, ghost: !!r.ghost });
      }
    });
    return Object.values(map);
  }, [filteredScatter]);

  const maxBubbleCount = Math.max(...bubbleData.map(b => b.count), 1);

  // Concentric grouping: group bubbles by d_day × price bucket, keep course info
  const concentricData = useMemo(() => {
    const posMap = {};
    bubbleData.forEach(b => {
      const posKey = `${b.d_day}|${b.price}`;
      if (!posMap[posKey]) posMap[posKey] = [];
      posMap[posKey].push(b);
    });
    return posMap;
  }, [bubbleData]);

  // 시간대 모드 토글
  const [scatterMode, setScatterMode] = useState('price'); // 'price' | 'time'
  const priceScroll = useChartScroll();
  const timeScroll = useChartScroll();
  const [showDrop, setShowDrop] = useState(true);
  const [showRise, setShowRise] = useState(true);
  const [showGhost, setShowGhost] = useState(true);
  const [showWeekend, setShowWeekend] = useState(true);
  const [showTuner, setShowTuner] = useState(false);
  const _timeKey = isMobile ? '__vr_timeTuner_m__' : '__vr_timeTuner__';
  const _priceKey = isMobile ? '__vr_priceTuner_m__' : '__vr_priceTuner__';
  const _timeDef = isMobile
    ? { chartH: 400, chartW: 100, bgBright: 48, opacityMin: 4, opacityMax: 48, neonBlur: 2, strokeW: 25, strokeOpacity: 100, sizeMin: 0, sizeMax: 12, ringGap: 20, clampMax: 8 }
    : { chartH: 680, chartW: 100, bgBright: 48, opacityMin: 4, opacityMax: 48, neonBlur: 3, strokeW: 38, strokeOpacity: 100, sizeMin: 0, sizeMax: 19, ringGap: 30, clampMax: 8 };
  const [tuner, setTuner] = useState(() => {
    try { const s = localStorage.getItem(_timeKey); return s ? { ..._timeDef, ...JSON.parse(s) } : _timeDef; } catch(e) { return _timeDef; }
  });
  // 가격 모드 튜닝
  const [showPriceTuner, setShowPriceTuner] = useState(false);
  const [raiseOpen, setRaiseOpen] = useState(false);
  const _priceDef = isMobile
    ? { chartH: 350, chartW: 100, bgBright: 0, trailOpacity: 53, glowBlur: 40, bubbleMax: 4 }
    : { chartH: 570, chartW: 100, bgBright: 0, trailOpacity: 53, glowBlur: 58, bubbleMax: 6 };
  const [priceTuner, setPriceTuner] = useState(() => {
    try { const s = localStorage.getItem(_priceKey); return s ? { ..._priceDef, ...JSON.parse(s) } : _priceDef; } catch(e) { return _priceDef; }
  });
  const setPT = (key, val) => setPriceTuner(prev => ({ ...prev, [key]: Number(val) }));
  const setT = (key, val) => setTuner(prev => ({ ...prev, [key]: Number(val) }));
  const [trendMode, setTrendMode] = useState('price'); // 'price' | 'time'

  // 시간대 모드 버블 데이터 (Y축=시간, 버블크기=가격)
  const timeBubbleData = useMemo(() => {
    if (scatterMode !== 'time') return [];
    const map = {};
    filteredScatter.filter(r => !r.ghost).forEach(r => {
      const hour = r.tee_time ? parseInt(r.tee_time.split(':')[0]) : null;
      if (hour === null) return;
      const key = `${r.course_name}|${r.d_day}|${hour}`;
      if (!map[key]) map[key] = { course_name: r.course_name, d_day: r.d_day, hour, count: 0, total_price: 0, min_price: Infinity, max_price: 0, promo: 0, weekend: 0 };
      map[key].count++;
      map[key].total_price += r.price_krw;
      map[key].min_price = Math.min(map[key].min_price, r.price_krw);
      map[key].max_price = Math.max(map[key].max_price, r.price_krw);
      if (r.promo_flag) map[key].promo++;
      if (r.weekday_type === '토요일' || r.weekday_type === '일요일') map[key].weekend++;
      if (r.price_changed_flag && r.previous_price_krw) {
        const delta = r.price_krw - r.previous_price_krw;
        if (delta > 0) { map[key].has_rise = true; map[key].rise_amt = (map[key].rise_amt || 0) + delta; map[key].rise_cnt = (map[key].rise_cnt || 0) + 1; }
        else if (delta < 0) { map[key].has_drop = true; map[key].drop_amt = (map[key].drop_amt || 0) + Math.abs(delta); map[key].drop_cnt = (map[key].drop_cnt || 0) + 1; }
      }
    });
    return Object.values(map).map(b => ({
      ...b,
      avg_price: Math.round(b.total_price / b.count),
    }));
  }, [filteredScatter, scatterMode]);

  const maxTimePrice = Math.max(...timeBubbleData.map(b => b.avg_price), 200000);
  const maxTimeCount = Math.max(...timeBubbleData.map(b => b.count), 1);

  const heatmapData = useMemo(() => {
    if (trendMode !== 'time') return [];
    const map = {};
    (tab4.scatter || []).forEach(r => {
      if (r.ghost) return;
      const hour = r.tee_time ? parseInt(r.tee_time.split(':')[0]) : null;
      if (hour === null) return;
      const part = hour < 11 ? '1부' : hour < 14 ? '2부' : '오후';
      const key = `${r.course_name}|${part}|${r.d_day}`;
      if (!map[key]) map[key] = { course_name: r.course_name, part, d_day: r.d_day, count: 0, total_price: 0, promo: 0 };
      map[key].count++;
      map[key].total_price += r.price_krw;
      if (r.promo_flag) map[key].promo++;
    });
    return Object.values(map);
  }, [tab4.scatter, trendMode]);

  // Heatmap: build grid data for courses × parts × d_days
  const heatmapGrid = useMemo(() => {
    if (!heatmapData.length) return { courses: [], ddays: [], cells: {} };
    const courseSet = [...new Set(heatmapData.map(h => h.course_name))].sort();
    const ddaySet = [...new Set(heatmapData.map(h => h.d_day))].sort((a, b) => a - b);
    const cells = {};
    // Find max count per course+part for density calculation
    const maxByCoursePart = {};
    heatmapData.forEach(h => {
      const cpKey = `${h.course_name}|${h.part}`;
      maxByCoursePart[cpKey] = Math.max(maxByCoursePart[cpKey] || 0, h.count);
    });
    heatmapData.forEach(h => {
      const cpKey = `${h.course_name}|${h.part}`;
      const maxCount = maxByCoursePart[cpKey] || 1;
      const density = Math.round((1 - h.count / maxCount) * 100); // inverse: fewer remaining = more consumed
      cells[`${h.course_name}|${h.part}|${h.d_day}`] = {
        ...h,
        density,
        avg_price: Math.round(h.total_price / h.count),
      };
    });
    return { courses: courseSet, ddays: ddaySet, cells };
  }, [heatmapData]);

  const subTabs = ['D-day 추세', '산점도', '가격 분포'];

  return (
    <div>
      <InfoBanner text={"💰 경기일(D-day)이 다가올수록 가격이 어떻게 변하는지 보여줍니다.\n정가 = 티 최초 포착 가격 · 할인 강도 = (정가 - 현재가) ÷ 정가 × 100"} />
      <DateNavigator context={context} metadata={metadata} />

      {/* 경기일 필터 */}
      <DdayFilter value={ddayFilter} onChange={setDdayFilter} />

      {/* 가격 인상 경보 배너 */}
      {(() => {
        const raises = (tab4.price_events || []).filter(e => e.event_type === '인상' && e.detected_at === context.anchorDate)
          .sort((a, b) => (b.delta_pct || 0) - (a.delta_pct || 0));
        if (raises.length === 0) return null;
        return (
          <div style={{ background: '#EF444415', border: '1px solid #EF444440', borderRadius: 10, padding: '14px 18px', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: raises.length > 5 ? 'pointer' : 'default' }}
              onClick={() => raises.length > 5 && setRaiseOpen(!raiseOpen)}>
              <span style={{ fontSize: 18 }}>🚨</span>
              <span style={{ color: '#EF4444', fontWeight: 700, ...FONT.body }}>가격 인상 감지 ({raises.length}건)</span>
              {raises.length > 5 && <span style={{ color: '#EF4444', marginLeft: 'auto', fontSize: 12 }}>{raiseOpen ? '▲ 접기' : '▼ 더보기'}</span>}
            </div>
            <div style={{ marginTop: 8 }}>
              {(raiseOpen ? raises : raises.slice(0, 5)).map((ev, idx) => (
                <div key={idx} style={{ ...FONT.small, color: COLORS.textSecondary, marginLeft: 26, marginBottom: 2 }}>
                  <span style={{ color: COLORS.textBright, fontWeight: 600 }}>{ev.course_name}</span> {ev.course_sub} {ev.play_date} {ev.tee_time}: {fmtMan(ev.old_price_krw)}→<span style={{ color: '#EF4444', fontWeight: 700 }}>{fmtMan(ev.new_price_krw)}</span> (+{ev.delta_pct > 0 ? ev.delta_pct : ''}%)
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* 서브탭 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {subTabs.map((name, idx) => (
          <button key={idx} className="btn-hover" onClick={() => setSubTab(idx)} style={{
            padding: '10px 20px', borderRadius: 8,
            border: `1px solid ${subTab === idx ? COLORS.accent : COLORS.secondary}`,
            background: subTab === idx ? COLORS.accent : 'transparent',
            color: subTab === idx ? '#fff' : COLORS.textSecondary,
            cursor: 'pointer', ...FONT.tab, fontWeight: 500
          }}>{name}</button>
        ))}
      </div>

      {/* A. D-day 추세 */}
      {subTab === 0 && (
        <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28 }}>
          {/* 추세 모드 토글 */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button onClick={() => setTrendMode('price')} style={{
              padding: '8px 18px', borderRadius: 8,
              border: `1px solid ${trendMode === 'price' ? COLORS.accent : COLORS.secondary}`,
              background: trendMode === 'price' ? COLORS.accent : 'transparent',
              color: trendMode === 'price' ? '#fff' : COLORS.textSecondary,
              cursor: 'pointer', ...FONT.small, fontWeight: 600,
            }}>💰 가격 추세</button>
            <button onClick={() => setTrendMode('time')} style={{
              padding: '8px 18px', borderRadius: 8,
              border: `1px solid ${trendMode === 'time' ? COLORS.accent : COLORS.secondary}`,
              background: trendMode === 'time' ? COLORS.accent : 'transparent',
              color: trendMode === 'time' ? '#fff' : COLORS.textSecondary,
              cursor: 'pointer', ...FONT.small, fontWeight: 600,
            }}>🕐 시간대 소진</button>
          </div>

          {/* 가격 추세 (기존 라인차트) */}
          {trendMode === 'price' && (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={trendData} margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
              {[...weekendDdays].map(d => (
                <ReferenceArea key={`we_trend_${d}`} x1={d - 0.4} x2={d + 0.4} fill="#F59E0B" fillOpacity={0.05} />
              ))}
              <XAxis dataKey="d_day" reversed={true} tick={{ fill: COLORS.textSecondary, fontSize: 12 }} label={{ value: 'D-day', position: 'insideBottomRight', fill: COLORS.textMuted }} />
              <YAxis tick={{ fill: COLORS.textSecondary, fontSize: 12 }} label={{ value: '만원', angle: -90, position: 'insideLeft', fill: COLORS.textMuted }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ ...FONT.small }} />
              {courses.map(c => (
                <Line key={c} type="monotone" dataKey={c} stroke={COURSE_COLORS[c]} strokeWidth={2} dot={false} name={c} />
              ))}
            </LineChart>
          </ResponsiveContainer>
          )}

          {/* 시간대 소진 히트맵 */}
          {trendMode === 'time' && heatmapGrid.courses.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.tiny }}>
                <thead>
                  <tr>
                    <th style={{ padding: '6px 10px', textAlign: 'left', color: COLORS.textSecondary, position: 'sticky', left: 0, background: COLORS.cardBg, zIndex: 1, minWidth: 90 }}>골프장</th>
                    <th style={{ padding: '6px 6px', textAlign: 'left', color: COLORS.textSecondary, minWidth: 30 }}>시간</th>
                    {heatmapGrid.ddays.filter((d, i) => i % Math.max(1, Math.floor(heatmapGrid.ddays.length / 15)) === 0 || d <= 7).map(d => (
                      <th key={d} style={{ padding: '6px 4px', textAlign: 'center', color: COLORS.textMuted, minWidth: 28 }}>D-{d}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {heatmapGrid.courses.map((cn, ci) => (
                    ['1부', '2부'].map((part, pi) => (
                      <tr key={`${cn}|${part}`} style={{ borderBottom: pi === 1 ? `2px solid ${COLORS.secondary}44` : 'none' }}>
                        {pi === 0 ? (
                          <td rowSpan={2} style={{ padding: '4px 10px', position: 'sticky', left: 0, background: COLORS.cardBg, zIndex: 1 }}>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                              <span style={{ width: 8, height: 8, borderRadius: '50%', background: COURSE_COLORS[cn] || COLORS.accent, display: 'inline-block' }} />
                              <span style={{ color: COLORS.textMain, fontSize: 11 }}>{cn}</span>
                            </span>
                          </td>
                        ) : null}
                        <td style={{ padding: '2px 6px', color: COLORS.textMuted, fontSize: 10 }}>{part}</td>
                        {heatmapGrid.ddays.filter((d, i) => i % Math.max(1, Math.floor(heatmapGrid.ddays.length / 15)) === 0 || d <= 7).map(d => {
                          const cell = heatmapGrid.cells[`${cn}|${part}|${d}`];
                          if (!cell) return <td key={d} style={{ padding: '2px 3px', textAlign: 'center' }}><div style={{ width: 28, height: 20, background: COLORS.secondary, borderRadius: 4, opacity: 0.2 }} /></td>;
                          const pct = cell.density;
                          const heatBg = pct >= 80 ? '#DC2626' : pct >= 60 ? '#EA580C' : pct >= 40 ? '#D97706' : pct >= 20 ? '#65A30D' : '#059669';
                          const heatOpacity = 0.25 + (pct / 100) * 0.7;
                          return (
                            <td key={d} style={{ padding: '2px 3px', textAlign: 'center', cursor: 'pointer' }}
                              title={`${cn} ${part} D-${d}: 잔여${cell.count}티 소진${cell.density}% 평균${parseFloat((cell.avg_price/10000).toFixed(1))}만`}>
                              <div className="heat-hover" style={{
                                width: 28, height: 20, background: heatBg, opacity: heatOpacity,
                                borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                boxShadow: pct >= 80 ? `0 0 6px ${heatBg}60` : 'none',
                              }}>
                                {pct >= 80 && <span style={{ fontSize: 9, color: '#fff', fontWeight: 700, lineHeight: 1 }}>{pct}</span>}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))
                  ))}
                </tbody>
              </table>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center', marginTop: 12, ...FONT.tiny, color: COLORS.textMuted }}>
                <span>잔여 많음</span>
                <div style={{ display: 'flex', gap: 2 }}>
                  {[
                    { color: '#059669', label: '0-20%' },
                    { color: '#65A30D', label: '20-40%' },
                    { color: '#D97706', label: '40-60%' },
                    { color: '#EA580C', label: '60-80%' },
                    { color: '#DC2626', label: '80%+' },
                  ].map((s, i) => (
                    <div key={i} title={s.label} style={{ width: 24, height: 12, background: s.color, borderRadius: 3, opacity: 0.3 + i * 0.175 }} />
                  ))}
                </div>
                <span>거의 소진</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* B. 버블 산점도 */}
      {subTab === 1 && (
        <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28 }}>
          {/* Y축 모드 토글 */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <button onClick={() => setScatterMode('price')} style={{
              padding: '8px 18px', borderRadius: 8,
              border: `1px solid ${scatterMode === 'price' ? COLORS.accent : COLORS.secondary}`,
              background: scatterMode === 'price' ? COLORS.accent : 'transparent',
              color: scatterMode === 'price' ? '#fff' : COLORS.textSecondary,
              cursor: 'pointer', ...FONT.small, fontWeight: 600,
            }}>💰 가격 모드</button>
            <button onClick={() => setScatterMode('time')} style={{
              padding: '8px 18px', borderRadius: 8,
              border: `1px solid ${scatterMode === 'time' ? COLORS.accent : COLORS.secondary}`,
              background: scatterMode === 'time' ? COLORS.accent : 'transparent',
              color: scatterMode === 'time' ? '#fff' : COLORS.textSecondary,
              cursor: 'pointer', ...FONT.small, fontWeight: 600,
            }}>🕐 시간대 모드</button>
          </div>
          {/* 골프장 토글 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            <button onClick={toggleAll} style={{
              padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
              border: `1px solid ${COLORS.secondary}`, background: COLORS.secondary,
              color: COLORS.textSecondary, ...FONT.small, fontWeight: 600,
            }}>{Object.values(visibleCourses).every(v => v) ? '전체 해제' : '전체 선택'}</button>
            {courses.map(c => (
              <button key={c} onClick={() => toggleCourse(c)} style={{
                padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                border: `1px solid ${visibleCourses[c] !== false ? COURSE_COLORS[c] : COLORS.secondary}`,
                background: visibleCourses[c] !== false ? COURSE_COLORS[c] + '25' : 'transparent',
                color: visibleCourses[c] !== false ? COURSE_COLORS[c] : COLORS.textMuted,
                ...FONT.small, fontWeight: 500,
                opacity: visibleCourses[c] !== false ? 1 : 0.4,
              }}>{c}</button>
            ))}
          </div>
          {/* === 가격 모드 === */}
          {scatterMode === 'price' && <>
          {/* D-day 범위 드래그 슬라이더 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
              <span style={{ ...FONT.small, color: COLORS.textSecondary }}>D-day 범위:</span>
              <span style={{ ...FONT.body, fontWeight: 600, color: COLORS.accentLight }}>D-{ddayRange[0]} ~ D-{ddayRange[1]}</span>
              {[
                {label: '3일', r: [1, 3]},
                {label: '7일', r: [1, 7]},
                {label: '14일', r: [1, 14]},
                {label: '전체', r: [1, allDdays[allDdays.length-1]||30]},
              ].map(p => (
                <button key={p.label} onClick={() => { setDdayFilter(p.r); setDdayRange(p.r); }} style={{
                  padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                  border: `1px solid ${ddayRange[0] === p.r[0] && ddayRange[1] === p.r[1] ? COLORS.accent : COLORS.secondary}`,
                  background: ddayRange[0] === p.r[0] && ddayRange[1] === p.r[1] ? COLORS.accent + '20' : 'transparent',
                  color: ddayRange[0] === p.r[0] && ddayRange[1] === p.r[1] ? COLORS.accentLight : COLORS.textSecondary,
                  ...FONT.small,
                }}>{p.label}</button>
              ))}
              <span style={{ ...FONT.small, color: COLORS.textMuted, marginLeft: 4 }}>
                {filteredScatter.length}건{filteredScatter.filter(r => r.ghost).length > 0 && ` (소진 ${filteredScatter.filter(r => r.ghost).length})`}
              </span>
            </div>
            {/* Dual-thumb range slider */}
            {(() => {
              const sliderMin = Math.max(0, allDdays[0] || 0);
              const sliderMax = allDdays[allDdays.length - 1] || 30;
              const range = sliderMax - sliderMin || 1;
              const leftPct = ((ddayRange[0] - sliderMin) / range) * 100;
              const rightPct = ((ddayRange[1] - sliderMin) / range) * 100;
              return (
                <div style={{ position: 'relative', height: 36, padding: '0 8px' }}>
                  {/* Track background */}
                  <div style={{ position: 'absolute', top: 14, left: 8, right: 8, height: 8, background: COLORS.secondary, borderRadius: 4 }} />
                  {/* Active range */}
                  <div style={{ position: 'absolute', top: 14, left: `calc(8px + ${leftPct}% * (100% - 16px) / 100%)`, width: `${rightPct - leftPct}%`, height: 8, background: COLORS.accent, borderRadius: 4, pointerEvents: 'none',
                    left: `calc(8px + (100% - 16px) * ${leftPct / 100})`,
                    width: `calc((100% - 16px) * ${(rightPct - leftPct) / 100})`,
                  }} />
                  {/* Min slider */}
                  <input type="range" min={sliderMin} max={sliderMax} value={ddayRange[0]}
                    onChange={e => { const v = Number(e.target.value); setDdayRange([Math.min(v, ddayRange[1]), ddayRange[1]]); setDdayFilter([Math.min(v, ddayRange[1]), ddayRange[1]]); }}
                    style={{ position: 'absolute', top: 4, left: 0, width: '100%', height: 28, appearance: 'none', WebkitAppearance: 'none', background: 'transparent', pointerEvents: 'none', zIndex: 3,
                      '--thumb': `${COLORS.accentLight}`,
                    }}
                    className="range-thumb"
                  />
                  {/* Max slider */}
                  <input type="range" min={sliderMin} max={sliderMax} value={ddayRange[1]}
                    onChange={e => { const v = Number(e.target.value); setDdayRange([ddayRange[0], Math.max(v, ddayRange[0])]); setDdayFilter([ddayRange[0], Math.max(v, ddayRange[0])]); }}
                    style={{ position: 'absolute', top: 4, left: 0, width: '100%', height: 28, appearance: 'none', WebkitAppearance: 'none', background: 'transparent', pointerEvents: 'none', zIndex: 4 }}
                    className="range-thumb"
                  />
                  {/* Tick labels */}
                  <div style={{ position: 'absolute', top: 24, left: 8, right: 8, display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>{sliderMin}</span>
                    <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>{sliderMax}</span>
                  </div>
                </div>
              );
            })()}
          </div>

          <div style={{ overflowX: 'auto', overflowY: 'hidden', WebkitOverflowScrolling: 'touch' }}
            className="chart-scroll" {...priceScroll.bind}>
          <div style={{ width: `${Math.max(30, Math.round((ddayFilter[1] - ddayFilter[0] + 1) / 30 * priceTuner.chartW))}%` }}>
          <ResponsiveContainer width="100%" height={priceTuner.chartH}>
            <ScatterChart margin={{ left: 50, right: 50, top: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} strokeOpacity={0.4} />
              {[...weekendDdays].filter(d => d >= ddayRange[0] && d <= ddayRange[1]).map(d => (
                <ReferenceArea key={`we_sc_${d}`} x1={d - 0.4} x2={d + 0.4} fill="#F59E0B" fillOpacity={0.05} />
              ))}
              {forecastChangeDdays.filter(d => d >= ddayRange[0] && d <= ddayRange[1]).map(d => (
                <ReferenceLine key={`fc_${d}`} x={d} stroke="#EF4444" strokeDasharray="5 3" strokeOpacity={0.5}
                  label={{ value: '⚠️예보악화', position: 'top', fontSize: 10 }} />
              ))}
              <XAxis dataKey="d_day" name="D-day" type="number"
                domain={[ddayFilter[0] - 1.5, ddayFilter[1] + 0.5]}
                allowDecimals={false}
                tickCount={ddayFilter[1] - ddayFilter[0] + 1}
                tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
                tickFormatter={v => `D-${v}`} />
              <YAxis dataKey="price" name="가격" type="number"
                tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
                tickFormatter={v => `${Math.round(v/10000)}만`} />
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload;
                const posKey = `${d.d_day}|${d.price}`;
                const allAtPos = concentricData[posKey] || [d];
                return (
                  <div style={{ background: COLORS.bg, border: `1px solid ${COLORS.secondary}`, borderRadius: 8, padding: 12, ...FONT.small, color: COLORS.textMain, minWidth: 200 }}>
                    <div style={{ fontWeight: 700, marginBottom: 8, color: COLORS.textBright }}>D-{d.d_day} / {parseFloat((d.price/10000).toFixed(1))}만원대</div>
                    {allAtPos.sort((a, b) => courseOrder.indexOf(a.course_name) - courseOrder.indexOf(b.course_name)).map((b, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0', borderBottom: i < allAtPos.length - 1 ? `1px solid ${COLORS.secondary}22` : 'none' }}>
                        <span style={{ color: COURSE_COLORS[b.course_name], fontWeight: 600 }}>{b.course_name}</span>
                        <span style={{ color: COLORS.textSecondary }}>
                          {parseFloat((b.price/10000).toFixed(1))}만
                          {b.rise_sum > 0 && <span style={{ color: '#EF4444', marginLeft: 4 }}>▲+{parseFloat((b.rise_sum / (b.changed || 1) / 10000).toFixed(1))}만</span>}
                          {b.drop_sum > 0 && <span style={{ color: '#7DD3FC', marginLeft: 4 }}>▼-{parseFloat((b.drop_sum / (b.changed || 1) / 10000).toFixed(1))}만</span>}
                          {b.promo > 0 && <span style={{ color: '#F59E0B', marginLeft: 4 }}>특가</span>}
                          <span style={{ color: COLORS.textMuted, marginLeft: 4 }}>{b.count}개</span>
                        </span>
                      </div>
                    ))}
                    <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 6, borderTop: `1px solid ${COLORS.secondary}`, paddingTop: 4 }}>
                      합계: {allAtPos.reduce((s, b) => s + b.count, 0)}티 / 특가 {allAtPos.reduce((s, b) => s + b.promo, 0)}건
                    </div>
                  </div>
                );
              }} />
              {courses.map(c => (
                <Scatter key={c} name={c}
                  data={bubbleData.filter(b => b.course_name === c)}
                  fill={COURSE_COLORS[c]} fillOpacity={0.65}
                  isAnimationActive={false}
                  shape={({ cx, cy, payload }) => {
                    const rangeSpan = ddayRange[1] - ddayRange[0] + 1;
                    const _bMax = priceTuner.bubbleMax;
                    const r = Math.max(3, Math.min(_bMax, 3 + (payload.count / maxBubbleCount) * (_bMax - 3)));
                    const orderIdx = courseOrder.indexOf(payload.course_name);
                    const layerOffset = orderIdx * (isMobile ? 0.5 : 1);
                    const rFinal = r + layerOffset;
                    const color = COURSE_COLORS[payload.course_name] || '#888';
                    const isPromo = payload.promo > payload.count * 0.5;
                    const baseOpacity = isPromo ? (0.15 + 0.55 * (payload.count / maxBubbleCount)) * 0.5 : 0.15 + 0.55 * (payload.count / maxBubbleCount);
                    const hasDrop = payload.drop_sum > 0;
                    const hasRise = payload.rise_sum > 0;

                    // ── 혜성 꼬리: 그라데이션 빔 + 글로우 필터 ──
                    const priceRange = scatterPriceRange[1] - scatterPriceRange[0];
                    const pxPerWon = priceRange > 0 ? 440 / priceRange : 0;
                    const avgDrop = hasDrop ? payload.drop_sum / payload.changed : 0;
                    const _mobileScale = isMobile ? 0.5 : 1;
                    const _opacity = priceTuner.trailOpacity / 100 * 2; // 혜성 투명도 (튜닝)
                    const trailLen = hasDrop ? Math.max(20, avgDrop * pxPerWon) * _mobileScale : 0;
                    // 꼬리 폭
                    const trailW = Math.max(10, r * 2);
                    // 고유 ID (gradient/filter용)
                    const uid = `t_${payload.course_name}_${payload.d_day}_${payload.price}`.replace(/[^a-zA-Z0-9]/g, '_');

                    return (
                      <g>
                        {/* SVG defs: 글로우 필터 + 그라데이션 */}
                        <defs>
                          {/* 이중 글로우: 넓은 후광 + 선명한 코어 */}
                          <filter id={`glow_${uid}`} x="-80%" y="-80%" width="260%" height="260%">
                            <feGaussianBlur in="SourceGraphic" stdDeviation={priceTuner.glowBlur / 10} result="blur1" />
                            <feGaussianBlur in="SourceGraphic" stdDeviation={priceTuner.glowBlur / 30} result="blur2" />
                            <feMerge>
                              <feMergeNode in="blur1" />
                              <feMergeNode in="blur2" />
                              <feMergeNode in="SourceGraphic" />
                            </feMerge>
                          </filter>
                          {hasDrop && (
                            <linearGradient id={`dropG_${uid}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#7DD3FC" stopOpacity="0" />
                              <stop offset="30%" stopColor="#BAE6FD" stopOpacity="0.4" />
                              <stop offset="70%" stopColor="#E0F2FE" stopOpacity="0.8" />
                              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="1.0" />
                            </linearGradient>
                          )}
                          {hasRise && (
                            <linearGradient id={`riseG_${uid}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#EF4444" stopOpacity="0" />
                              <stop offset="30%" stopColor="#EF4444" stopOpacity="0.2" />
                              <stop offset="70%" stopColor="#FCA5A5" stopOpacity="0.6" />
                              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.9" />
                            </linearGradient>
                          )}
                        </defs>

                        {/* 변동 버블 */}
                        {(hasDrop || hasRise) ? (
                          <>
                            {/* 투명 히트 영역 */}
                            <circle cx={cx} cy={cy} r={rFinal + 10} fill="transparent" stroke="none" />
                            {/* 하락 빔 (50% 수준) */}
                            {hasDrop && showDrop && (
                              <rect
                                x={cx - trailW / 2} y={cy - trailLen}
                                width={trailW} height={trailLen}
                                rx={trailW / 2}
                                fill={`url(#dropG_${uid})`}
                                filter={`url(#glow_${uid})`}
                                opacity={_opacity * 0.5}
                              />
                            )}
                            {/* 인상 빔 (50% 수준) */}
                            {hasRise && showRise && (() => {
                              const avgRise = payload.rise_sum / payload.changed;
                              const riseLen = Math.max(20, avgRise * pxPerWon) * _mobileScale;
                              return (
                                <rect
                                  x={cx - trailW / 2} y={cy}
                                  width={trailW} height={riseLen}
                                  rx={trailW / 2}
                                  fill={`url(#riseG_${uid})`}
                                  filter={`url(#glow_${uid})`}
                                  opacity={_opacity * 0.5}
                                />
                              );
                            })()}
                            {/* 메인 버블 */}
                            <circle cx={cx} cy={cy} r={rFinal}
                              fill={color} fillOpacity={baseOpacity + 0.15}
                              stroke={hasRise && showRise ? "#EF4444" : hasDrop && showDrop ? "#7DD3FC" : color} strokeWidth={1.5} strokeOpacity={0.7} />
                            {/* ▲▼ 마커 */}
                            {hasRise && showRise && (
                              <polygon points={`${cx-3},${cy-rFinal-2} ${cx+3},${cy-rFinal-2} ${cx},${cy-rFinal-6}`} fill="#EF4444" fillOpacity={0.5} />
                            )}
                            {hasDrop && showDrop && (
                              <polygon points={`${cx-3},${cy+rFinal+2} ${cx+3},${cy+rFinal+2} ${cx},${cy+rFinal+6}`} fill="#7DD3FC" fillOpacity={0.5} />
                            )}
                            {/* 인상 텍스트 라벨 */}
                            {hasRise && showRise && (
                              <text x={cx + rFinal + 4} y={cy - rFinal - 4} textAnchor="start" fill="#EF4444" fontSize={isMobile ? 7 : 9} fontWeight="700">
                                +{parseFloat((payload.rise_sum / payload.changed / 10000).toFixed(1))}만↑
                              </text>
                            )}
                            {/* 소진 표시 */}
                            {payload.ghost > 0 && showGhost && (
                              <>
                                <circle cx={cx} cy={cy} r={rFinal + 6} fill="none"
                                  stroke="#FBBF24" strokeWidth={1.2} strokeDasharray="3 2"
                                  strokeOpacity={0.7} />
                                <text x={cx} y={cy - rFinal - (hasRise ? 22 : 8)} textAnchor="middle"
                                  fill="#FBBF24" fontSize={8} fontWeight="600" fillOpacity={0.9}>소진{payload.ghost}</text>
                              </>
                            )}
                          </>
                        ) : (
                          /* 일반 버블 — 변동 없음 */
                          <>
                          {/* 투명 히트 영역 (툴팁 감지용) */}
                          <circle cx={cx} cy={cy} r={rFinal + 8} fill="transparent" stroke="none" />
                          <circle cx={cx} cy={cy} r={rFinal}
                            fill={color} fillOpacity={baseOpacity}
                            stroke={color} strokeWidth={1.2} strokeOpacity={0.8} />
                          {payload.weekend > 0 && showWeekend && <circle cx={cx} cy={cy} r={rFinal + 2} fill="none" stroke="#F59E0B" strokeWidth={1} strokeDasharray="3 2" strokeOpacity={0.5} />}
                          </>
                        )}
                        {/* ▲▼ 가격 변동 마커 */}
                        {payload.rise_sum > 0 && (
                          <polygon points={`${cx-4},${cy-rFinal-4} ${cx+4},${cy-rFinal-4} ${cx},${cy-rFinal-10}`} fill="#EF4444" />
                        )}
                        {payload.drop_sum > 0 && (
                          <polygon points={`${cx-4},${cy+rFinal+4} ${cx+4},${cy+rFinal+4} ${cx},${cy+rFinal+10}`} fill="#7DD3FC" />
                        )}
                        {/* 카운트 라벨 */}
                        {payload.count >= 5 && (
                          <text x={cx} y={cy + 3.5} textAnchor="middle" fill="#fff" fontSize={9} fontWeight="600">{payload.count}</text>
                        )}
                        {rangeSpan <= 7 && payload.count >= 1 && (
                          <text x={cx} y={cy - rFinal - 6} textAnchor="middle" fill={COLORS.textSecondary} fontSize={8} fontWeight="500">{parseFloat((payload.price/10000).toFixed(1))}만</text>
                        )}
                      </g>
                    );
                  }}
                />
              ))}
              <Legend wrapperStyle={{ ...FONT.small }} />
            </ScatterChart>
          </ResponsiveContainer>
          </div>
          </div>
          <ScrollIndicator scrollPct={priceScroll.scrollPct} scrollRef={priceScroll.scrollRef} visible={priceTuner.chartW > 100} />

          {/* 범례 토글 */}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 12, flexWrap: 'wrap' }}>
            {[
              { key: 'drop', label: '가격 인하', color: '#7DD3FC', state: showDrop, set: setShowDrop },
              { key: 'rise', label: '가격 인상', color: '#EF4444', state: showRise, set: setShowRise },
              { key: 'ghost', label: '소진 표시', color: '#FBBF24', state: showGhost, set: setShowGhost },
              { key: 'weekend', label: '◌ 주말 점선', color: '#F59E0B', state: showWeekend, set: setShowWeekend },
            ].map(t => (
              <button key={t.key} onClick={() => t.set(!t.state)} style={{
                padding: '5px 14px', borderRadius: 16, cursor: 'pointer',
                border: `1px solid ${t.state ? t.color : COLORS.secondary}`,
                background: t.state ? t.color + '20' : 'transparent',
                color: t.state ? t.color : COLORS.textMuted,
                ...FONT.tiny, fontWeight: 600, opacity: t.state ? 1 : 0.5,
              }}>{t.state ? '✓ ' : ''}{t.label}</button>
            ))}
          </div>

          {/* 가격 모드 튜닝 */}
          <div style={{ borderTop: `1px solid ${COLORS.secondary}33`, marginTop: 16, paddingTop: 12 }}>
            <div style={{ textAlign: 'center' }}>
              <button onClick={() => setShowPriceTuner(!showPriceTuner)} style={{
                background: showPriceTuner ? COLORS.secondary : 'none',
                border: `1px solid ${COLORS.secondary}`, borderRadius: 6,
                color: showPriceTuner ? COLORS.textBright : COLORS.textMuted,
                ...FONT.tiny, padding: '6px 16px', cursor: 'pointer',
              }}>{showPriceTuner ? '⚙️ 튜닝 닫기' : '⚙️ 시각 튜닝'}</button>
            </div>
            {showPriceTuner && (
              <div style={{ background: COLORS.bg, border: `1px solid ${COLORS.secondary}`, borderRadius: 10, padding: 20, marginTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <span style={{ ...FONT.small, color: COLORS.textBright, fontWeight: 600 }}>가격 모드 튜닝</span>
                  <button onClick={() => {
                    try { const s = localStorage.getItem(_priceKey); setPriceTuner(s ? { ..._priceDef, ...JSON.parse(s) } : _priceDef); } catch(e) { setPriceTuner(_priceDef); }
                  }} style={{
                    background: 'none', border: `1px solid ${COLORS.accent}`, borderRadius: 6,
                    color: COLORS.accent, ...FONT.tiny, padding: '4px 12px', cursor: 'pointer',
                  }}>기본값 복원</button>
                  {window.__USER_ROLE__ === 'admin' && (
                    <button onClick={() => { localStorage.setItem(_priceKey, JSON.stringify(priceTuner)); alert(`가격 모드 ${isMobile ? '모바일' : 'PC'} 기본값 저장 완료`); }} style={{
                      background: 'none', border: `1px solid ${SEVERITY_COLORS.ok}`, borderRadius: 6,
                      color: SEVERITY_COLORS.ok, ...FONT.tiny, padding: '4px 12px', cursor: 'pointer',
                    }}>💾 {isMobile ? '모바일' : 'PC'} 기본값 저장</button>
                  )}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
                  {[
                    { key: 'chartH', label: '차트 높이', min: 200, max: 800, step: 10 },
                    { key: 'chartW', label: '가로 비율 (%)', min: 80, max: 300, step: 5 },
                    { key: 'trailOpacity', label: '혜성 빔 강도 (%)', min: 0, max: 100, step: 1 },
                    { key: 'glowBlur', label: '글로우 강도 (×0.1)', min: 0, max: 60, step: 1 },
                    { key: 'bubbleMax', label: '버블 최대 크기', min: 5, max: 30, step: 1 },
                  ].map(s => (
                    <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ ...FONT.tiny, color: COLORS.textSecondary, minWidth: 120, flexShrink: 0 }}>{s.label}</span>
                      <input type="range" min={s.min} max={s.max} step={s.step} value={priceTuner[s.key]}
                        onChange={e => setPT(s.key, e.target.value)}
                        style={{ flex: 1, height: 6, accentColor: COLORS.accent }} />
                      <span style={{ ...FONT.tiny, color: COLORS.textBright, minWidth: 36, textAlign: 'right', fontWeight: 600 }}>{priceTuner[s.key]}</span>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 16, padding: 10, background: COLORS.cardBg, borderRadius: 6, ...FONT.tiny, color: COLORS.textMuted, wordBreak: 'break-all' }}>
                  <strong style={{ color: COLORS.textBright }}>현재 값: </strong>
                  <span style={{ color: COLORS.textSecondary }}>{JSON.stringify(priceTuner)}</span>
                </div>
              </div>
            )}
          </div>
          </>}

          {/* === 시간대 모드 === */}
          {scatterMode === 'time' && (
            <>
              <div style={{ overflowX: tuner.chartW > 100 ? 'auto' : 'visible', overflowY: 'hidden', WebkitOverflowScrolling: 'touch' }}
                className="chart-scroll" {...timeScroll.bind}>
              <div style={{ width: `${Math.max(30, Math.round((ddayFilter[1] - ddayFilter[0] + 1) / 30 * tuner.chartW))}%` }}>
              <ResponsiveContainer width="100%" height={tuner.chartH}>
                <ScatterChart margin={{ left: 50, right: 30, top: 10, bottom: 20 }} style={{ background: `rgb(${Math.max(0, 15 + tuner.bgBright - 30)}, ${Math.max(0, 23 + tuner.bgBright - 30)}, ${Math.max(0, 42 + tuner.bgBright - 30)})`, borderRadius: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} strokeOpacity={0.3} />
                  <XAxis dataKey="d_day" name="D-day" type="number"
                    domain={[ddayFilter[0] - 1.5, ddayFilter[1] + 0.5]}
                    allowDecimals={false}
                    tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
                    tickFormatter={v => `D-${v}`} />
                  <YAxis dataKey="hour" name="시간" type="number"
                    domain={[5, 17]}
                    tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
                    tickFormatter={v => `${v}시`} />
                  <Tooltip content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const d = payload[0].payload;
                      const allAtPos = timeBubbleData.filter(b => b.d_day === d.d_day && b.hour === d.hour);
                      return (
                        <div style={{ background: COLORS.bg, border: `1px solid ${COLORS.secondary}`, borderRadius: 8, padding: 12, ...FONT.small, color: COLORS.textMain, minWidth: 200 }}>
                          <div style={{ fontWeight: 700, marginBottom: 8, color: COLORS.textBright }}>D-{d.d_day} · {d.hour}:00~{d.hour+1}:00</div>
                          {allAtPos.sort((a, b) => b.avg_price - a.avg_price).map((b, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '3px 0', borderBottom: i < allAtPos.length - 1 ? `1px solid ${COLORS.secondary}22` : 'none' }}>
                              <span style={{ color: COURSE_COLORS[b.course_name], fontWeight: 600 }}>{b.course_name}</span>
                              <span style={{ color: COLORS.textSecondary }}>
                                {parseFloat((b.avg_price/10000).toFixed(1))}만
                                {b.has_rise && <span style={{ color: '#EF4444', marginLeft: 4 }}>▲+{parseFloat(((b.rise_amt||0)/(b.rise_cnt||1)/10000).toFixed(1))}만</span>}
                                {b.has_drop && <span style={{ color: '#7DD3FC', marginLeft: 4 }}>▼-{parseFloat(((b.drop_amt||0)/(b.drop_cnt||1)/10000).toFixed(1))}만</span>}
                                {b.promo > 0 && <span style={{ color: '#F59E0B', marginLeft: 4 }}>특가{b.promo}</span>}
                                <span style={{ color: COLORS.textMuted, marginLeft: 4 }}>{b.count}개</span>
                              </span>
                            </div>
                          ))}
                          <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 6, borderTop: `1px solid ${COLORS.secondary}`, paddingTop: 4 }}>
                            합계: {allAtPos.reduce((s, b) => s + b.count, 0)}티
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }} />
                  {[...weekendDdays].map(d => (
                    <ReferenceArea key={`twe${d}`} x1={d - 0.4} x2={d + 0.4} fill="#F59E0B" fillOpacity={0.05} />
                  ))}
                  {(() => {
                    // 위치별 그룹핑 (d_day × hour)
                    const timeGroups = {};
                    timeBubbleData.filter(b => visibleCourses[b.course_name] !== false).forEach(b => {
                      const key = `${b.d_day}|${b.hour}`;
                      if (!timeGroups[key]) timeGroups[key] = [];
                      timeGroups[key].push(b);
                    });
                    // 각 그룹을 가격 내림차순 정렬 (비싼 게 먼저 = 큰 원이 뒤에)
                    Object.values(timeGroups).forEach(g => g.sort((a, b) => b.avg_price - a.avg_price));
                    // 대표 데이터 (첫번째 = 가장 비싼 것, Scatter 위치용)
                    const uniquePositions = Object.values(timeGroups).map(g => ({ ...g[0], _group: g }));
                    return (
                      <Scatter name="시간대"
                        data={uniquePositions}
                        fill={COLORS.accent}
                        isAnimationActive={false}
                        shape={({ cx, cy, payload }) => {
                          const group = payload._group || [payload];
                          const minR = tuner.sizeMin;
                          const maxR = tuner.sizeMax;
                          const transition = 'opacity 0.3s ease';
                          // 네온 필터 ID
                          const neonId = `neon_${payload.d_day}_${payload.hour}`.replace(/[^a-zA-Z0-9]/g, '_');
                          // 비싼 것부터 그림 (큰 원 → 작은 원 순서로 덮기)
                          return (
                            <g>
                              {/* 네온 글로우 필터 */}
                              <defs>
                                {group.map((b, i) => {
                                  const c = COURSE_COLORS[b.course_name] || '#888';
                                  return (
                                    <filter key={i} id={`${neonId}_${i}`} x="-50%" y="-50%" width="200%" height="200%">
                                      <feDropShadow dx="0" dy="0" stdDeviation={tuner.neonBlur / 10} floodColor={c} floodOpacity="0.7" />
                                    </filter>
                                  );
                                })}
                              </defs>
                              {/* 투명 히트 영역 */}
                              <circle cx={cx} cy={cy} r={isMobile ? 16 : 24} fill="transparent" stroke="none" />
                              {(() => {
                                // 로그 스케일 + 최소 간격 2px 보장
                                // 전체 기준 정규화 (그룹 내가 아닌 전체 데이터 기준)

                                const radii = [];
                                let lastR = maxR + 3;
                                group.forEach((b, i) => {
                                  // 로그 스케일: 저가 작게, 고가 확 크게
                                  const logPrice = Math.log(Math.max(b.avg_price, 30000) / 30000 + 1);
                                  const logMax = Math.log(250000 / 30000 + 1);
                                  const priceR = minR + (logPrice / logMax) * (maxR - minR);
                                  // 최소 2px 간격 보장
                                  const r = Math.max(minR, Math.min(priceR, lastR - tuner.ringGap / 10));
                                  lastR = r;
                                  const clamped = Math.min(b.count, tuner.clampMax);
                                  const opacity = tuner.opacityMin / 100 + (clamped / tuner.clampMax) * ((tuner.opacityMax - tuner.opacityMin) / 100);
                                  const isOverflow = b.count > tuner.clampMax;
                                  radii.push({ ...b, r, opacity, isOverflow });
                                });
                                const outerR = radii.length > 0 ? radii[0].r : maxR;
                                return (
                                  <>
                                    {radii.map((b, i) => {
                                      const color = COURSE_COLORS[b.course_name] || '#888';
                                      const isInnermost = i === radii.length - 1;
                                      return (
                                        <React.Fragment key={i}>
                                          {isInnermost ? (
                                            <circle cx={cx} cy={cy} r={b.r}
                                              fill={color} fillOpacity={b.opacity}
                                              stroke={color} strokeWidth={1} strokeOpacity={b.opacity * (tuner.strokeOpacity / 100)}
                                              filter={`url(#${neonId}_${i})`}
                                              style={{ transition }} />
                                          ) : (
                                            <circle cx={cx} cy={cy} r={b.r}
                                              fill="none"
                                              stroke={color} strokeWidth={tuner.strokeW / 10} strokeOpacity={b.opacity * (tuner.strokeOpacity / 100)}
                                              filter={`url(#${neonId}_${i})`}
                                              style={{ transition }} />
                                          )}
                                          {b.isOverflow && (
                                            <circle cx={cx} cy={cy} r={b.r + 2}
                                              fill="none" stroke={color} strokeWidth={1} strokeOpacity={0.5} strokeDasharray="2 2" />
                                          )}
                                        </React.Fragment>
                                      );
                                    })}
                                    {group.some(b => b.has_rise) && (
                                      <polygon points={`${cx-4},${cy-outerR-3} ${cx+4},${cy-outerR-3} ${cx},${cy-outerR-9}`} fill="#EF4444" fillOpacity={0.5} />
                                    )}
                                    {group.some(b => b.has_drop) && (
                                      <polygon points={`${cx-4},${cy+outerR+3} ${cx+4},${cy+outerR+3} ${cx},${cy+outerR+9}`} fill="#7DD3FC" fillOpacity={0.5} />
                                    )}
                                  </>
                                );
                              })()}
                            </g>
                          );
                        }}
                      />
                    );
                  })()}
                </ScatterChart>
              </ResponsiveContainer>
              </div>
              </div>
              <ScrollIndicator scrollPct={timeScroll.scrollPct} scrollRef={timeScroll.scrollRef} visible={tuner.chartW > 100} />
              <div style={{ display: 'flex', gap: 20, justifyContent: 'center', marginTop: 8, ...FONT.small, color: COLORS.textMuted }}>
                <span>● 크기 = 가격 (클수록 비쌈)</span>
                <span>● 진하기 = 잔여 수 (진할수록 많이 남음)</span>
                <span style={{ color: '#EF4444' }}>▲ 인상</span>
                <span style={{ color: '#7DD3FC' }}>▼ 인하</span>
                <span>◌ 점선 = 15개+ 과잉잔여</span>
              </div>

              {/* 튜닝 패널 (토글과 분리) */}
              <div style={{ borderTop: `1px solid ${COLORS.secondary}33`, marginTop: 16, paddingTop: 12 }}>
                <div style={{ textAlign: 'center' }}>
                  <button onClick={() => setShowTuner(!showTuner)} style={{
                    background: showTuner ? COLORS.secondary : 'none',
                    border: `1px solid ${COLORS.secondary}`, borderRadius: 6,
                    color: showTuner ? COLORS.textBright : COLORS.textMuted,
                    ...FONT.tiny, padding: '6px 16px', cursor: 'pointer',
                  }}>{showTuner ? '⚙️ 튜닝 닫기' : '⚙️ 시각 튜닝'}</button>
                </div>
                {showTuner && (
                  <div style={{ background: COLORS.bg, border: `1px solid ${COLORS.secondary}`, borderRadius: 10, padding: 20, marginTop: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                      <span style={{ ...FONT.small, color: COLORS.textBright, fontWeight: 600 }}>시각 튜닝</span>
                      <button onClick={() => {
                        try { const s = localStorage.getItem(_timeKey); setTuner(s ? { ..._timeDef, ...JSON.parse(s) } : _timeDef); } catch(e) { setTuner(_timeDef); }
                      }} style={{
                        background: 'none', border: `1px solid ${COLORS.accent}`, borderRadius: 6,
                        color: COLORS.accent, ...FONT.tiny, padding: '4px 12px', cursor: 'pointer',
                      }}>기본값 복원</button>
                      {window.__USER_ROLE__ === 'admin' && (
                        <button onClick={() => { localStorage.setItem(_timeKey, JSON.stringify(tuner)); alert(`시간대 모드 ${isMobile ? '모바일' : 'PC'} 기본값 저장 완료`); }} style={{
                          background: 'none', border: `1px solid ${SEVERITY_COLORS.ok}`, borderRadius: 6,
                          color: SEVERITY_COLORS.ok, ...FONT.tiny, padding: '4px 12px', cursor: 'pointer',
                        }}>💾 {isMobile ? '모바일' : 'PC'} 기본값 저장</button>
                      )}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
                      {[
                        { key: 'chartH', label: '차트 높이', min: 200, max: 1000, step: 10 },
                        { key: 'chartW', label: '가로 비율 (%)', min: 80, max: 300, step: 5 },
                        { key: 'bgBright', label: '배경 밝기', min: -30, max: 100, step: 1 },
                        { key: 'opacityMin', label: '투명도 최소 (%)', min: 0, max: 80, step: 1 },
                        { key: 'opacityMax', label: '투명도 최대 (%)', min: 20, max: 100, step: 1 },
                        { key: 'neonBlur', label: '네온 강도 (×0.1)', min: 0, max: 100, step: 1 },
                        { key: 'strokeW', label: '테두리 두께 (×0.1)', min: 0, max: 80, step: 1 },
                        { key: 'strokeOpacity', label: '테두리 진하기 (%)', min: 10, max: 100, step: 1 },
                        { key: 'sizeMin', label: '버블 최소 크기', min: 0, max: 15, step: 1 },
                        { key: 'sizeMax', label: '버블 최대 크기', min: 5, max: 50, step: 1 },
                        { key: 'ringGap', label: '동심원 간격 (×0.1)', min: 0, max: 60, step: 1 },
                        { key: 'clampMax', label: '잔여 수 클램핑', min: 1, max: 50, step: 1 },
                      ].map(s => (
                        <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span style={{ ...FONT.tiny, color: COLORS.textSecondary, minWidth: 120, flexShrink: 0 }}>{s.label}</span>
                          <input type="range" min={s.min} max={s.max} step={s.step} value={tuner[s.key]}
                            onChange={e => setT(s.key, e.target.value)}
                            style={{ flex: 1, height: 6, accentColor: COLORS.accent }} />
                          <span style={{ ...FONT.tiny, color: COLORS.textBright, minWidth: 36, textAlign: 'right', fontWeight: 600 }}>{tuner[s.key]}</span>
                        </div>
                      ))}
                    </div>
                    <div style={{ marginTop: 16, padding: 10, background: COLORS.cardBg, borderRadius: 6, ...FONT.tiny, color: COLORS.textMuted, wordBreak: 'break-all' }}>
                      <strong style={{ color: COLORS.textBright }}>현재 값: </strong>
                      <span style={{ color: COLORS.textSecondary }}>{JSON.stringify(tuner)}</span>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* C. 가격 분포 */}
      {subTab === 2 && (
        <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28 }}>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={tab4.histogram || []} margin={{ left: 10, right: 10, top: 10, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
              <XAxis dataKey="price_bucket" tick={{ fill: COLORS.textSecondary, fontSize: 11 }} angle={-45} textAnchor="end" />
              <YAxis tick={{ fill: COLORS.textSecondary, fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ ...FONT.small }} />
              <Bar dataKey="non_promo" name="정가" fill="#3B82F6" stackId="a" />
              <Bar dataKey="promo" name="특가" fill="#F59E0B" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* D. 가격 변동 이벤트 테이블 */}
      <SectionTitle title={`가격 변동 이벤트 (${(tab4.price_events || []).length}건)`} icon="📋" />
      <div style={{ overflowX: 'auto', maxHeight: 500, overflowY: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead style={{ position: 'sticky', top: 0, background: COLORS.cardBg, zIndex: 1 }}>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {['골프장', '코스', '이벤트', '변동', '경기일', '시간'].map(h => (
                <th key={h} style={{ padding: '12px 14px', textAlign: 'left', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(tab4.price_events || []).map((evt, idx) => (
              <tr key={idx} className="table-hover-row" style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                <td style={{ padding: '12px 14px' }}><CourseBadge name={evt.course_name} small /></td>
                <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{evt.course_sub}</td>
                <td style={{ padding: '12px 14px' }}>
                  <span className="badge-hover" title={evt.event_type === '인하' ? '시장 가격 인하 — 수요 부족으로 가격이 내려감' : evt.event_type === '인상' ? '시장 가격 인상 — 수요 증가로 가격이 올라감' : evt.event_type === '특가부착' ? '골프장이 할인 라벨을 붙여 프로모션 시작' : evt.event_type === '특가해제' ? '골프장이 할인 라벨을 제거하여 프로모션 종료' : ''}
                    style={{
                    padding: '3px 10px', borderRadius: 12, ...FONT.tiny, fontWeight: 600, cursor: 'help',
                    background: `${EVENT_COLORS[evt.event_type] || COLORS.secondary}25`,
                    color: EVENT_COLORS[evt.event_type] || COLORS.textSecondary
                  }}>{evt.event_type}</span>
                </td>
                <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{fmtMan(evt.old_price_krw)}→{fmtMan(evt.new_price_krw)} ({evt.delta_pct > 0 ? '+' : ''}{evt.delta_pct}%)</td>
                <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{evt.play_date}</td>
                <td style={{ padding: '12px 14px', color: COLORS.textMuted }}>{evt.tee_time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 5: 할인 반응
// ═══════════════════════════════════════════════════
const Tab5 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tab5a = (RAW_DATA.tab5a || {})[context.anchorDate] || {};
  const [discountView, setDiscountView] = useState('all'); // 'all' | 'market' | 'promo'
  const [ddayFilter5, setDdayFilter5] = useState([1, 30]);

  // Tab5 주말 D-day 집합
  const weekendDdays5 = useMemo(() => {
    const set = new Set();
    (tab5a.discount_events || []).forEach(e => {
      if (e.play_date) {
        const dow = new Date(e.play_date).getDay();
        if (dow === 0 || dow === 6) set.add(e.d_day);
      }
    });
    return set;
  }, [tab5a.discount_events]);

  // 할인 이벤트를 시장 반응 vs 특가 프로모션으로 분리
  const allEvents = (tab5a.discount_events || []).filter(e => e.d_day >= ddayFilter5[0] && e.d_day <= ddayFilter5[1]);
  const marketEvents = allEvents.filter(e => e.event_type === '인하' || e.event_type === '인상');
  const promoEvents = allEvents.filter(e => e.event_type === '특가부착' || e.event_type === '특가해제');
  const displayEvents = discountView === 'market' ? marketEvents : discountView === 'promo' ? promoEvents : allEvents;
  const eff = tab5a.effectiveness || {};

  const OUTCOME_STYLE = {
    consumed: { label: '소진', color: '#10B981', bg: '#10B98120', icon: '✅', tip: '할인/특가 후 예약되어 판매 완료된 티타임' },
    waiting:  { label: '대기', color: '#3B82F6', bg: '#3B82F620', icon: '⏳', tip: '할인/특가 적용 후 아직 판매되지 않고 대기 중인 티타임' },
    expired:  { label: '미판매', color: '#64748B', bg: '#64748B20', icon: '⏱️', tip: '할인/특가에도 불구하고 판매되지 않은 채 경기일이 지난 티타임' },
  };

  return (
    <div>
      <InfoBanner text="🔻 시장 반응 = 수요에 의해 실제 가격이 변동된 것 | 🏷️ 특가 프로모션 = 골프장이 처음부터 할인 라벨을 붙인 것" />
      <DateNavigator context={context} metadata={metadata} />
      <DdayFilter value={ddayFilter5} onChange={setDdayFilter5} />

      {/* A. 인하 효과 요약 */}
      <SectionTitle title="인하 효과 분석" icon="📊" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 28 }}>
        <div className="kpi-hover" title="가격 인하 또는 특가 라벨이 붙은 전체 이벤트 수" style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: `1px solid ${COLORS.secondary}` }}>
          <div style={{ ...FONT.small, color: COLORS.textMuted }}>전체 인하/특가</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: COLORS.textBright, marginTop: 6 }}>{eff.total_events || 0}<span style={{ ...FONT.small, color: COLORS.textMuted, marginLeft: 4 }}>건</span></div>
        </div>
        <div className="kpi-hover" title="인하/특가 후 실제로 예약(판매)된 티타임 수" style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: '1px solid #10B98140' }}>
          <div style={{ ...FONT.small, color: '#10B981' }}>✅ 소진 (인하→판매)</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#10B981', marginTop: 6 }}>{eff.consumed || 0}<span style={{ ...FONT.small, color: COLORS.textMuted, marginLeft: 4 }}>건</span></div>
        </div>
        <div className="kpi-hover" title="인하/특가 적용 후 아직 판매되지 않고 경기일을 기다리는 중" style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: '1px solid #3B82F640' }}>
          <div style={{ ...FONT.small, color: '#3B82F6' }}>⏳ 대기 (아직 미판매)</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#3B82F6', marginTop: 6 }}>{eff.waiting || 0}<span style={{ ...FONT.small, color: COLORS.textMuted, marginLeft: 4 }}>건</span></div>
        </div>
        <div className="kpi-hover" title="인하/특가 이벤트 중 실제 판매로 이어진 비율. 미판매(경기일 지남) 건은 제외하고 계산." style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: '1px solid #F59E0B40' }}>
          <div style={{ ...FONT.small, color: '#F59E0B' }}>인하 후 소진율</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#F59E0B', marginTop: 6 }}>{eff.consumption_rate != null ? eff.consumption_rate + '%' : '-'}</div>
          <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 4 }}>미판매 {eff.expired || 0}건 제외</div>
        </div>
      </div>

      {/* B. 골프장별 할인 현황 카드 (소진율 포함) */}
      <SectionTitle title="골프장별 인하 효과" icon="🏷️" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14, marginBottom: 28 }}>
        {(tab5a.course_summary || []).map((cs, idx) => {
          const act = (cs.consumed || 0) + (cs.waiting || 0);
          return (
            <div key={idx} className="card-hover" style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: `1px solid ${COLORS.secondary}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <CourseBadge name={cs.course_name} small />
                {cs.consumption_rate != null && (
                  <span style={{ ...FONT.small, fontWeight: 700, color: cs.consumption_rate > 50 ? '#10B981' : cs.consumption_rate > 0 ? '#F59E0B' : '#64748B' }}>
                    소진 {cs.consumption_rate}%
                  </span>
                )}
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: COLORS.textBright, marginTop: 10 }}>
                {cs.event_count}<span style={{ ...FONT.small, color: COLORS.textMuted, marginLeft: 4 }}>건</span>
              </div>
              <div style={{ color: COLORS.textSecondary, ...FONT.small, marginTop: 6 }}>
                평균 할인 {fmtPct(cs.avg_discount_pct)} · 최대 {fmtPct(cs.max_discount_pct)}
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8, ...FONT.tiny }}>
                <span style={{ color: '#10B981' }}>✅{cs.consumed || 0}</span>
                <span style={{ color: '#3B82F6' }}>⏳{cs.waiting || 0}</span>
                <span style={{ color: '#64748B' }}>⏱️{cs.expired || 0}미판매</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* C. D-day별 특가 vs 정가 */}
      {tab5a.dday_comparison && tab5a.dday_comparison.length > 0 && (
        <>
          <SectionTitle title="D-day별 특가 vs 정가" icon="📈" />
          <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28 }}>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={(tab5a.dday_comparison || []).sort((a, b) => b.d_day - a.d_day)}
                margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
                {[...weekendDdays5].map(d => (
                  <ReferenceArea key={`we5_${d}`} x1={d - 0.4} x2={d + 0.4} fill="#F59E0B" fillOpacity={0.05} />
                ))}
                <XAxis dataKey="d_day" reversed tick={{ fill: COLORS.textSecondary, fontSize: 12 }} />
                <YAxis tick={{ fill: COLORS.textSecondary, fontSize: 12 }} tickFormatter={v => `${Math.round(v/10000)}만`} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ ...FONT.small }} />
                <Line type="monotone" dataKey="avg_promo" name="특가 평균" stroke="#F59E0B" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="avg_non_promo" name="정가 평균" stroke="#94A3B8" strokeWidth={2} strokeDasharray="5 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* D. 할인 이벤트 테이블 — 시장 반응 vs 특가 분리 필터 */}
      <SectionTitle title="할인 이벤트 상세" icon="📋" />
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {[
          { key: 'all', label: '전체', count: allEvents.length, color: COLORS.textSecondary },
          { key: 'market', label: '🔻 시장 반응 (인하/인상)', count: marketEvents.length, color: '#EF4444' },
          { key: 'promo', label: '🏷️ 특가 전환', count: promoEvents.length, color: '#F59E0B' },
        ].map(opt => (
          <button key={opt.key} className="btn-hover" onClick={() => setDiscountView(opt.key)} style={{
            padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
            border: `1px solid ${discountView === opt.key ? opt.color : COLORS.secondary}`,
            background: discountView === opt.key ? opt.color + '20' : 'transparent',
            color: discountView === opt.key ? opt.color : COLORS.textMuted,
            ...FONT.small, fontWeight: discountView === opt.key ? 600 : 400,
          }}>{opt.label} ({opt.count})</button>
        ))}
      </div>
      <div style={{ overflowX: 'auto', maxHeight: 500, overflowY: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead style={{ position: 'sticky', top: 0, background: COLORS.cardBg, zIndex: 1 }}>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {['골프장', '코스', '유형', '이벤트', '할인율', '할인액', '경기일', '시간', '상태', '원인'].map(h => (
                <th key={h} style={{ padding: '12px 14px', textAlign: 'left', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayEvents.map((evt, idx) => {
              const isMarket = evt.event_type === '인하' || evt.event_type === '인상';
              const _isWeekend5 = evt.play_date && (new Date(evt.play_date).getDay() === 0 || new Date(evt.play_date).getDay() === 6);
              return (
                <tr key={idx} className="table-hover-row" style={{ borderBottom: `1px solid ${COLORS.secondary}22`, background: _isWeekend5 ? 'rgba(249,158,11,0.05)' : 'transparent' }}>
                  <td style={{ padding: '12px 14px' }}><CourseBadge name={evt.course_name} small /></td>
                  <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{evt.course_sub}</td>
                  <td style={{ padding: '12px 14px' }}>
                    <span className="badge-hover" title={isMarket ? '시장반응: 수요에 따라 가격이 자연스럽게 변동 (인하/인상)' : '특가전환: 골프장이 할인 라벨을 붙이거나 해제한 프로모션 활동'}
                      style={{ padding: '2px 8px', borderRadius: 10, ...FONT.tiny, fontWeight: 600, cursor: 'help',
                      background: isMarket ? '#EF444420' : '#F59E0B20',
                      color: isMarket ? '#EF4444' : '#F59E0B',
                    }}>{isMarket ? '시장반응' : '특가전환'}</span>
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <span title={evt.event_type === '인하' ? '시장 가격 인하 — 수요 부족으로 가격이 내려감' : evt.event_type === '인상' ? '시장 가격 인상 — 수요 증가로 가격이 올라감' : evt.event_type === '특가부착' ? '골프장이 할인 라벨을 붙여 프로모션 시작' : evt.event_type === '특가해제' ? '골프장이 할인 라벨을 제거하여 프로모션 종료' : ''}
                      style={{ padding: '3px 10px', borderRadius: 12, ...FONT.tiny, fontWeight: 600, cursor: 'help',
                      background: `${EVENT_COLORS[evt.event_type] || '#F59E0B'}25`, color: EVENT_COLORS[evt.event_type] || '#F59E0B'
                    }}>{evt.event_type}</span>
                  </td>
                  <td style={{ padding: '12px 14px', color: SEVERITY_COLORS.error }}>{fmtPct(evt.discount_pct)}</td>
                  <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{fmt(evt.discount_amt)}원</td>
                  <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{evt.play_date}</td>
                  <td style={{ padding: '12px 14px', color: COLORS.textMuted }}>{evt.tee_time}</td>
                  <td style={{ padding: '12px 14px' }}>
                    {evt.outcome && (() => {
                      const s = OUTCOME_STYLE[evt.outcome];
                      return s ? (
                        <span title={s.tip} style={{ padding: '2px 8px', borderRadius: 10, ...FONT.tiny, fontWeight: 600, background: s.bg, color: s.color, cursor: 'help' }}>
                          {s.icon} {s.label}
                        </span>
                      ) : <span style={{ color: COLORS.textMuted }}>-</span>;
                    })()}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    {evt.weather_cause ? (
                      <span style={{ ...FONT.tiny, color: evt.weather_cause === '우천예보' ? '#3B82F6' : '#10B981' }}>
                        {evt.weather_cause === '우천예보' ? '🌧️' : '☀️'} {evt.weather_cause}
                      </span>
                    ) : <span style={{ color: COLORS.textMuted }}>-</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 6: 수익 구조
// ═══════════════════════════════════════════════════
const Tab6 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tabData = (RAW_DATA.tab5b || {})[context.anchorDate] || null;
  const [ddayFilter6, setDdayFilter6] = useState([1, 30]);

  if (!tabData) return <NoData />;

  // yield_slots를 D-day 필터로 필터링하여 course_summary 재계산
  const filteredYieldSlots = useMemo(() => {
    return (tabData.yield_slots || []).filter(yd => yd.d_day >= ddayFilter6[0] && yd.d_day <= ddayFilter6[1]);
  }, [tabData.yield_slots, ddayFilter6]);

  const course_summary = useMemo(() => {
    if (ddayFilter6[0] === 1 && ddayFilter6[1] === 30) return tabData.course_summary || [];
    // D-day 필터가 적용된 경우 재계산
    const courseYield = {};
    filteredYieldSlots.forEach(yd => {
      const cn = yd.course_name;
      if (!courseYield[cn]) courseYield[cn] = { weekday: [], weekend: [] };
      if (yd.weekday_type === '토요일' || yd.weekday_type === '일요일' || yd.weekday_type === '금요일') {
        courseYield[cn].weekend.push(yd.yield);
      } else {
        courseYield[cn].weekday.push(yd.yield);
      }
    });
    return Object.entries(courseYield).map(([cn, data]) => {
      const wdAvg = data.weekday.length ? data.weekday.reduce((a, b) => a + b, 0) / data.weekday.length : null;
      const weAvg = data.weekend.length ? data.weekend.reduce((a, b) => a + b, 0) / data.weekend.length : null;
      return {
        course_name: cn,
        weekday_avg_yield: wdAvg ? parseFloat(wdAvg.toFixed(3)) : null,
        weekend_avg_yield: weAvg ? parseFloat(weAvg.toFixed(3)) : null,
        weekday_discount_pct: wdAvg ? parseFloat(((1 - wdAvg) * 100).toFixed(1)) : null,
        weekend_discount_pct: weAvg ? parseFloat(((1 - weAvg) * 100).toFixed(1)) : null,
        weekday_count: data.weekday.length,
        weekend_count: data.weekend.length,
        promo_ratio_weekday: 0,
      };
    }).sort((a, b) => a.course_name.localeCompare(b.course_name));
  }, [filteredYieldSlots, ddayFilter6, tabData.course_summary]);

  const yield_histogram = tabData.yield_histogram;

  return (
    <div>
      <InfoBanner text={"📈 정가(최초 포착가) 대비 실제 판매가 비율입니다.\n양수(+) = 할인 중, 음수(-) = 프리미엄 판매 · 전량 특가 코스는 기준가 없어 '-' 표시"} />
      <DateNavigator context={context} metadata={metadata} />
      <DdayFilter value={ddayFilter6} onChange={setDdayFilter6} />

      {/* A. 할인 강도 카드 */}
      <SectionTitle title="코스별 할인 강도" icon="⚖️" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14, marginBottom: 28 }}>
        {(course_summary || []).map((cs, idx) => {
          const wdDisc = cs.weekday_discount_pct;
          const weDisc = cs.weekend_discount_pct;
          const discColor = (v) => v == null ? COLORS.textMuted : v > 0 ? SEVERITY_COLORS.warning : SEVERITY_COLORS.ok;
          const discLabel = (v) => v == null ? '-' : v > 0 ? `할인 ${v}%` : `프리미엄 ${Math.abs(v)}%`;
          return (
            <div key={idx} style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: `1px solid ${COLORS.secondary}` }}>
              <CourseBadge name={cs.course_name} small />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
                <div>
                  <div style={{ ...FONT.small, color: COLORS.textMuted }}>평일 할인강도</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: discColor(wdDisc) }}>
                    {discLabel(wdDisc)}
                  </div>
                  <div style={{ ...FONT.tiny, color: COLORS.textMuted }}>{cs.weekday_count}티</div>
                </div>
                <div>
                  <div style={{ ...FONT.small, color: COLORS.textMuted }}>주말 할인강도</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: discColor(weDisc) }}>
                    {discLabel(weDisc)}
                  </div>
                  <div style={{ ...FONT.tiny, color: COLORS.textMuted }}>{cs.weekend_count}티</div>
                </div>
              </div>
              <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 8 }}>평일 특가비율: {fmtPct(cs.promo_ratio_weekday)}</div>
            </div>
          );
        })}
      </div>

      {/* B. Yield 분포 히스토그램 */}
      <SectionTitle title="Yield 분포" icon="📊" />
      <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20 }}>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={yield_histogram || []} margin={{ left: 10, right: 10, top: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
            <XAxis dataKey="yield_bucket" tick={{ fill: COLORS.textSecondary, fontSize: 11 }} angle={-30} textAnchor="end"
              tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
            <YAxis tick={{ fill: COLORS.textSecondary, fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ ...FONT.small }} />
            <Bar dataKey="non_promo" name="정가" fill="#3B82F6" stackId="a" />
            <Bar dataKey="promo" name="특가" fill="#F59E0B" stackId="a" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 7: 코스 비교
// ═══════════════════════════════════════════════════
const Tab7 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tabData = (RAW_DATA.tab6 || {})[context.anchorDate] || null;

  if (!tabData) return <NoData />;

  const { subcourse_rows, member_opens_latest } = tabData;

  return (
    <div>
      <InfoBanner text="⛳ 같은 골프장 안에서도 코스(서브코스)마다 가격과 남은 자리가 다를 수 있어요. 회원 전용 오픈도 여기서 확인!" />
      <DateNavigator context={context} metadata={metadata} />

      {/* A. 세부 코스 테이블 */}
      <SectionTitle title="세부 코스 현황" icon="⛳" />
      <div style={{ overflowX: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}`, marginBottom: 28 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {['골프장', '코스', '타입', '티', '평균가', '가격범위', '특가', '전일대비'].map(h => (
                <th key={h} style={{ padding: '12px 14px', textAlign: h === '골프장' || h === '코스' || h === '타입' ? 'left' : 'right', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(subcourse_rows || []).map((row, idx) => (
              <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                <td style={{ padding: '12px 14px' }}><CourseBadge name={row.course_name} small /></td>
                <td style={{ padding: '12px 14px', color: COLORS.textMain }}>{row.sub_display || row.course_sub}</td>
                <td style={{ padding: '12px 14px' }}>
                  <span style={{
                    padding: '2px 8px', borderRadius: 10, ...FONT.tiny,
                    background: row.membership_type === '회원제' ? `${COLORS.accentLight}30` : `${COLORS.secondary}`,
                    color: row.membership_type === '회원제' ? COLORS.accentLight : COLORS.textSecondary
                  }}>{row.member_label || row.membership_type}</span>
                </td>
                <td style={{ padding: '12px 14px', textAlign: 'right', color: COLORS.textBright, fontWeight: 600 }}>{row.slots}</td>
                <td style={{ padding: '12px 14px', textAlign: 'right', color: COLORS.textSecondary }}>{fmtMan(row.avg_price)}</td>
                <td style={{ padding: '12px 14px', textAlign: 'right', color: COLORS.textMuted, ...FONT.tiny }}>
                  {fmtMan(row.min_price)}~{fmtMan(row.max_price)}
                </td>
                <td style={{ padding: '12px 14px', textAlign: 'right', color: row.promo_slots > 0 ? EVENT_COLORS['특가부착'] : COLORS.textMuted }}>{row.promo_slots}</td>
                <td style={{ padding: '12px 14px', textAlign: 'right',
                  color: row.slot_delta > 0 ? SEVERITY_COLORS.ok : row.slot_delta < 0 ? SEVERITY_COLORS.error : COLORS.textMuted }}>
                  {row.slot_delta != null ? `${row.slot_delta > 0 ? '+' : ''}${row.slot_delta}` : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* B. 회원제 오픈 이벤트 */}
      {member_opens_latest && member_opens_latest.length > 0 && (
        <>
          <SectionTitle title="회원제 오픈 이벤트" icon="🔑" />
          <div style={{ display: 'grid', gap: 12 }}>
            {member_opens_latest.map((evt, idx) => (
              <div key={idx} style={{
                background: COLORS.cardBg, borderLeft: `4px solid ${COLORS.accent}`,
                borderRadius: 8, padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12
              }}>
                <div>
                  <CourseBadge name={evt.course_name} />
                  <div style={{ color: COLORS.textSecondary, ...FONT.small, marginTop: 6 }}>
                    경기일 {evt.play_date} · {evt.member_slot_count}티
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ color: COLORS.textBright, ...FONT.body, fontWeight: 600 }}>
                    {fmtMan(evt.min_price_krw)}~{fmtMan(evt.max_price_krw)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 8: AI 진단
// ═══════════════════════════════════════════════════
const DIAG_RANGE_OPTIONS = [
  { key: '1d', label: '1일', days: 1 },
  { key: '3d', label: '3일', days: 3 },
  { key: '7d', label: '7일', days: 7 },
  { key: '30d', label: '30일', days: 30 },
  { key: '1y', label: '1년', days: 365 },
];

const Tab8 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tabData = (RAW_DATA.tab7 || {})[context.anchorDate] || null;
  const [expandedDiag, setExpandedDiag] = useState({});
  const [diagRange, setDiagRange] = useState('1d');

  if (!tabData) return <NoData />;

  const { diagnostics, data_note, data_days, rules_applicable, rules_pending } = tabData;
  const selectedRange = DIAG_RANGE_OPTIONS.find(o => o.key === diagRange);
  const rangeAvailable = data_days >= (selectedRange?.days || 1);

  return (
    <div>
      {data_note && <InfoBanner text={data_note} />}
      <DateNavigator context={context} metadata={metadata} />

      {/* 분석 범위 선택 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, alignItems: 'center' }}>
        <span style={{ color: COLORS.textSecondary, ...FONT.small }}>📅 분석 범위</span>
        {DIAG_RANGE_OPTIONS.map(o => {
          const available = data_days >= o.days;
          return (
            <button key={o.key} onClick={() => available && setDiagRange(o.key)} style={{
              padding: '8px 16px', borderRadius: 20,
              border: `1px solid ${diagRange === o.key ? COLORS.accent : COLORS.secondary}`,
              background: diagRange === o.key ? COLORS.accent : 'transparent',
              color: diagRange === o.key ? '#fff' : available ? COLORS.textSecondary : COLORS.textMuted,
              cursor: available ? 'pointer' : 'default',
              opacity: available ? 1 : 0.4,
              ...FONT.small, fontWeight: 500, minHeight: 36,
            }}>{o.label}{!available && ` (${o.days - data_days}일 후)`}</button>
          );
        })}
      </div>
      {!rangeAvailable && (
        <InfoBanner text={`⚠️ 현재 ${data_days}일 데이터 기준 분석입니다. ${selectedRange.label} 분석은 데이터 ${selectedRange.days - data_days}일 추가 축적 후 활성화됩니다.`} level="warning" />
      )}

      {/* 규칙 레전드 */}
      <SectionTitle title="진단 규칙" icon="🤖" />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        {(rules_applicable || []).map(rule => (
          <span key={rule} style={{
            padding: '6px 14px', borderRadius: 20, ...FONT.small, fontWeight: 600,
            background: `${COLORS.accent}30`, color: COLORS.accent
          }}>{rule}: {RULE_LABELS[rule] || rule}</span>
        ))}
      </div>
      {rules_pending && rules_pending.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 28 }}>
          {rules_pending.map(rule => (
            <span key={rule} style={{
              padding: '6px 14px', borderRadius: 20, ...FONT.small,
              background: COLORS.secondary, color: COLORS.textMuted
            }}>{rule}: {RULE_LABELS[rule] || rule} (대기)</span>
          ))}
        </div>
      )}

      {/* 골프장별 진단 카드 */}
      <SectionTitle title="골프장별 진단" icon="📋" />
      <div style={{ display: 'grid', gap: 16 }}>
        {(diagnostics || []).sort((a, b) => (b.severity_max || 0) - (a.severity_max || 0)).map((diag, idx) => {
          const severityLabel = diag.severity_max >= 3 ? '심각' : diag.severity_max >= 2 ? '주의' : '양호';
          const severityColor = diag.severity_max >= 3 ? SEVERITY_COLORS.error : diag.severity_max >= 2 ? SEVERITY_COLORS.warning : SEVERITY_COLORS.ok;
          return (
            <div key={idx} style={{ background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}`, overflow: 'hidden' }}>
              {/* 카드 헤더 */}
              <div style={{ padding: '14px 18px', borderBottom: `1px solid ${COLORS.secondary}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <CourseBadge name={diag.course_name} />
                  <span style={{ padding: '4px 12px', borderRadius: 12, ...FONT.tiny, fontWeight: 600, background: `${severityColor}25`, color: severityColor }}>
                    {severityLabel}
                  </span>
                </div>
                <span style={{ color: COLORS.textMuted, ...FONT.small }}>{diag.finding_count}건</span>
              </div>
              {/* 종합 해설 */}
              {diag.narrative && (
                <div style={{ padding: '14px 18px', borderBottom: `1px solid ${COLORS.secondary}`, background: `${COLORS.accent}08` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <span style={{ fontSize: 14 }}>📝</span>
                    <span style={{ ...FONT.small, color: COLORS.accent, fontWeight: 600 }}>종합 분석</span>
                  </div>
                  <div style={{ ...FONT.small, color: COLORS.textSecondary, lineHeight: 1.6 }}>{diag.narrative}</div>
                </div>
              )}
              {/* Findings */}
              <div style={{ padding: '12px 18px' }}>
                {((expandedDiag[diag.course_name] ? diag.findings : (diag.findings || []).slice(0, 8)) || []).map((f, fi) => {
                  const fColor = f.severity === 'error' ? SEVERITY_COLORS.error : f.severity === 'warning' ? SEVERITY_COLORS.warning : SEVERITY_COLORS.info;
                  return (
                    <div key={fi} style={{ borderLeft: `3px solid ${fColor}`, padding: '8px 12px', marginBottom: 8, borderRadius: '0 6px 6px 0', background: `${fColor}08` }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <span style={{ padding: '2px 8px', borderRadius: 8, ...FONT.tiny, fontWeight: 700, background: `${COLORS.accent}30`, color: COLORS.accent }}>{f.rule}</span>
                        <span style={{ ...FONT.small, fontWeight: 600, color: COLORS.textBright }}>{f.title}</span>
                      </div>
                      <div style={{ ...FONT.tiny, color: COLORS.textSecondary, marginBottom: 2 }}>{f.desc}</div>
                      {f.action && <div style={{ ...FONT.tiny, color: COLORS.accent, fontStyle: 'italic' }}>→ {f.action}</div>}
                    </div>
                  );
                })}
                {diag.finding_count > 8 && (
                  <button onClick={() => setExpandedDiag(prev => ({ ...prev, [diag.course_name]: !prev[diag.course_name] }))}
                    style={{ ...FONT.tiny, color: COLORS.accent, background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0' }}>
                    {expandedDiag[diag.course_name] ? '접기 ▲' : `나머지 ${diag.finding_count - 8}건 더보기 ▼`}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Tab 9: 티타임 상세
// ═══════════════════════════════════════════════════
const Tab9 = ({ context, metadata }) => {
  const rawSlots = useMemo(() => (window.__GOLF_TAB8_TODAY__?.slots || []), []);
  const [ddayFilter9, setDdayFilter9] = useState([1, 30]);
  const allSlots = useMemo(() => rawSlots.filter(r => r.d_day >= ddayFilter9[0] && r.d_day <= ddayFilter9[1]), [rawSlots, ddayFilter9]);

  const [filters, setFilters] = useState({ course: '', promo: '', weekday: '', part: '', search: '', status: '' });
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  const filtered = useMemo(() => {
    let data = allSlots;
    if (filters.course) data = data.filter(r => r.course_name === filters.course);
    if (filters.promo === '있음') data = data.filter(r => r.promo_flag);
    if (filters.promo === '없음') data = data.filter(r => !r.promo_flag);
    if (filters.weekday === '평일') data = data.filter(r => r.weekday_type === '평일');
    if (filters.weekday === '주말') data = data.filter(r => r.weekday_type === '토요일' || r.weekday_type === '일요일');
    if (filters.part) data = data.filter(r => r.part_type === filters.part);
    if (filters.status) data = data.filter(r => r.slot_status === filters.status);
    if (filters.search) {
      const s = filters.search.toLowerCase();
      data = data.filter(r => (r.course_name + r.course_sub + r.play_date + r.tee_time + (r.promo_text || '')).toLowerCase().includes(s));
    }
    return data;
  }, [allSlots, filters]);

  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  useEffect(() => { setPage(0); }, [filters]);

  const courses = useMemo(() => [...new Set(allSlots.map(r => r.course_name))].sort(), [allSlots]);

  const selectStyle = {
    background: COLORS.cardBg, border: `1px solid ${COLORS.secondary}`, borderRadius: 8,
    color: COLORS.textMain, padding: '10px 14px', ...FONT.small, minHeight: 40, cursor: 'pointer'
  };

  return (
    <div>
      <InfoBanner text={`🔍 총 ${fmt(allSlots.length)}개 티타임이 있어요. 아래 필터로 골프장·날짜·가격 등 원하는 조건을 골라보세요!`} />
      <DdayFilter value={ddayFilter9} onChange={setDdayFilter9} />

      {/* 필터 바 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10, marginBottom: 24 }}>
        <select value={filters.course} onChange={e => setFilters(p => ({ ...p, course: e.target.value }))} style={selectStyle}>
          <option value="">전체 골프장</option>
          {courses.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filters.promo} onChange={e => setFilters(p => ({ ...p, promo: e.target.value }))} style={selectStyle}>
          <option value="">특가: 전체</option>
          <option value="있음">특가 있음</option>
          <option value="없음">특가 없음</option>
        </select>
        <select value={filters.weekday} onChange={e => setFilters(p => ({ ...p, weekday: e.target.value }))} style={selectStyle}>
          <option value="">요일: 전체</option>
          <option value="평일">평일</option>
          <option value="주말">주말</option>
        </select>
        <select value={filters.part} onChange={e => setFilters(p => ({ ...p, part: e.target.value }))} style={selectStyle}>
          <option value="">시간대: 전체</option>
          <option value="1부">1부</option>
          <option value="2부">2부</option>
          <option value="오후">오후</option>
        </select>
        <select value={filters.status} onChange={e => setFilters(p => ({ ...p, status: e.target.value }))} style={selectStyle}>
          <option value="">상태: 전체</option>
          <option value="new_open">신규오픈</option>
          <option value="cancel_reopen">티취소(재오픈)</option>
        </select>
        <div style={{ position: 'relative' }}>
          <input value={filters.search} onChange={e => setFilters(p => ({ ...p, search: e.target.value }))}
            placeholder="검색..." style={{ ...selectStyle, width: '100%', paddingRight: 36 }} />
          <Search size={16} color={COLORS.textMuted} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)' }} />
        </div>
      </div>

      {/* 결과 카운트 */}
      <div style={{ ...FONT.small, color: COLORS.textSecondary, marginBottom: 12 }}>
        {fmt(filtered.length)}건 / 전체 {fmt(allSlots.length)}건 · 페이지 {page + 1}/{totalPages || 1}
      </div>

      {/* 데이터 테이블 */}
      <div style={{ overflowX: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}`, marginBottom: 20 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {['골프장', '코스', '경기일', '시간', '가격', 'D-day', '특가'].map(h => (
                <th key={h} style={{ padding: '12px 14px', textAlign: 'left', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((row, idx) => {
              const _isWeekend9 = row.weekday_type === '토요일' || row.weekday_type === '일요일';
              return (
              <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22`, background: _isWeekend9 ? 'rgba(249,158,11,0.05)' : 'transparent' }}>
                <td style={{ padding: '10px 14px' }}><CourseBadge name={row.course_name} small /></td>
                <td style={{ padding: '10px 14px', color: COLORS.textSecondary }}>{row.sub_display || row.course_sub}</td>
                <td style={{ padding: '10px 14px', color: COLORS.textMain }}>{row.play_date}</td>
                <td style={{ padding: '10px 14px', color: COLORS.textSecondary }}>{row.tee_time}</td>
                <td style={{ padding: '10px 14px', color: COLORS.textBright, fontWeight: 600 }}>{fmtMan(row.price_krw)}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{
                    padding: '3px 10px', borderRadius: 12, ...FONT.tiny, fontWeight: 600,
                    background: row.d_day <= 3 ? `${SEVERITY_COLORS.error}25` : row.d_day <= 7 ? `${SEVERITY_COLORS.warning}25` : `${SEVERITY_COLORS.ok}25`,
                    color: row.d_day <= 3 ? SEVERITY_COLORS.error : row.d_day <= 7 ? SEVERITY_COLORS.warning : SEVERITY_COLORS.ok
                  }}>D-{row.d_day}</span>
                </td>
                <td style={{ padding: '10px 14px' }}>
                  {row.promo_flag ? (
                    <span style={{ padding: '3px 10px', borderRadius: 12, ...FONT.tiny, fontWeight: 600, background: '#F59E0B25', color: '#F59E0B' }}>
                      {row.promo_text || '특가'}
                    </span>
                  ) : null}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
            style={{ ...selectStyle, opacity: page === 0 ? 0.3 : 1 }}>← 이전</button>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
            style={{ ...selectStyle, opacity: page >= totalPages - 1 ? 0.3 : 1 }}>다음 →</button>
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════
// Main App
// ═══════════════════════════════════════════════════
// ═══════════════════════════════════════════════════
// 관리자 패널
// ═══════════════════════════════════════════════════
const ROLE_LABELS = { admin: '관리자', manager: '매니저', viewer: '뷰어', guest: '게스트' };
const ROLE_OPTIONS = ['admin', 'manager', 'viewer', 'guest'];

const AdminPanel = ({ onClose }) => {
  const [tab, setTab] = useState('pending');
  const [pending, setPending] = useState([]);
  const [users, setUsers] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editUser, setEditUser] = useState(null);
  const admin = window.__vrAdmin__;

  const refresh = async () => {
    setLoading(true);
    setError('');
    try {
      if (tab === 'pending') setPending(await admin.getPendingRequests());
      if (tab === 'users') setUsers(await admin.getApprovedUsers());
      if (tab === 'logs') {
        setLogs(await admin.getAccessLogs());
        if (users.length === 0) setUsers(await admin.getApprovedUsers());
      }
    } catch(e) {
      console.error(e);
      setError(e.message || '관리자 데이터를 불러오지 못했습니다.');
    }
    setLoading(false);
  };

  useEffect(() => { refresh(); }, [tab]);
  useEffect(() => {
    if (tab !== 'pending') return;
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [tab]);

  const handleApprove = async (req, role) => {
    const adminName = prompt('표시 이름 (워터마크용):', req.self_name || '');
    if (adminName === null) return;
    await admin.approveUser(req.email || req.id, req.self_name, role, adminName || req.self_name);
    alert(`${req.self_name || req.id} → ${ROLE_LABELS[role]}로 승인`);
    refresh();
  };

  const handleDeny = async (req) => {
    if (!confirm(`${req.self_name || req.id} 거부하시겠습니까?`)) return;
    await admin.denyUser(req.email || req.id);
    refresh();
  };

  const handleToggle = async (u) => {
    await admin.toggleUser(u.email || u.id, !u.active);
    refresh();
  };

  const handleRemove = async (u) => {
    if (!confirm(`${u.admin_name || u.self_name || u.id} 완전 삭제?`)) return;
    await admin.removeUser(u.email || u.id);
    refresh();
  };

  const handleSaveEdit = async () => {
    if (!editUser) return;
    const fields = {
      role: editUser.role,
      admin_name: editUser.admin_name || editUser.self_name,
    };
    if (editUser.expires_at) fields.expires_at = editUser.expires_at;
    else fields.expires_at = null;
    if (editUser.max_logins) fields.max_logins = parseInt(editUser.max_logins);
    else fields.max_logins = null;
    if (editUser.session_hours) fields.session_hours = parseInt(editUser.session_hours);
    else fields.session_hours = null;
    if (editUser.allowed_hours_start != null && editUser.allowed_hours_end != null) {
      fields.allowed_hours = [parseInt(editUser.allowed_hours_start), parseInt(editUser.allowed_hours_end)];
    } else {
      fields.allowed_hours = null;
    }
    await admin.updateUser(editUser.email || editUser.id, fields);
    setEditUser(null);
    refresh();
  };

  const modalBg = { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.7)', zIndex: 100000, display: 'flex', alignItems: 'center', justifyContent: 'center' };
  const modalBox = { background: COLORS.bg, borderRadius: 16, border: `1px solid ${COLORS.secondary}`, width: '90%', maxWidth: 800, maxHeight: '85vh', overflow: 'auto', padding: '24px 28px' };
  const btnStyle = (active) => ({ padding: '8px 18px', borderRadius: 8, border: `1px solid ${active ? COLORS.accent : COLORS.secondary}`, background: active ? COLORS.accent : 'transparent', color: active ? '#fff' : COLORS.textSecondary, cursor: 'pointer', ...FONT.small, fontWeight: 600 });
  const inputStyle = { padding: '8px 12px', borderRadius: 6, border: `1px solid ${COLORS.secondary}`, background: COLORS.cardBg, color: COLORS.textMain, ...FONT.small, width: '100%', boxSizing: 'border-box' };
  const selectStyle2 = { ...inputStyle, appearance: 'auto' };

  return (
    <div style={modalBg} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={modalBox}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ color: COLORS.textBright, margin: 0, fontSize: 22 }}>관리자 패널</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: COLORS.textMuted, fontSize: 24, cursor: 'pointer' }}>✕</button>
        </div>

        {/* 탭 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          {[['pending','승인 대기'], ['users','사용자 관리'], ['logs','접속 로그']].map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)} style={btnStyle(tab === k)}>{label}</button>
          ))}
        </div>

        {loading && <div style={{ color: COLORS.textMuted, padding: 20, textAlign: 'center' }}>로드 중...</div>}
        {!loading && error && <div style={{ color: '#EF4444', padding: 12, marginBottom: 12, border: '1px solid #EF444455', borderRadius: 8 }}>{error}</div>}

        {/* 승인 대기 */}
        {tab === 'pending' && !loading && (
          <div>
            {pending.length === 0 && <div style={{ color: COLORS.textMuted, padding: 20, textAlign: 'center' }}>대기 중인 요청이 없습니다</div>}
            {pending.filter(r => r.status !== 'denied').map((req, idx) => (
              <div key={idx} style={{ background: COLORS.cardBg, borderRadius: 10, padding: 16, marginBottom: 10, border: `1px solid ${COLORS.secondary}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div>
                    <span style={{ color: COLORS.textBright, fontWeight: 600 }}>{req.self_name || '-'}</span>
                    <span style={{ color: COLORS.textMuted, ...FONT.small, marginLeft: 8 }}>{req.email || req.id}</span>
                  </div>
                  <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>{req.requested_at?.toDate?.()?.toLocaleString?.() || ''}</span>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {ROLE_OPTIONS.filter(r => r !== 'admin').map(role => (
                    <button key={role} onClick={() => handleApprove(req, role)} style={{ padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.accent}`, background: `${COLORS.accent}20`, color: COLORS.accent, cursor: 'pointer', ...FONT.small }}>
                      {ROLE_LABELS[role]}로 승인
                    </button>
                  ))}
                  <button onClick={() => handleDeny(req)} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #EF4444', background: '#EF444420', color: '#EF4444', cursor: 'pointer', ...FONT.small }}>
                    거부
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 사용자 관리 */}
        {tab === 'users' && !loading && (
          <div>
            {/* 수정 모달 */}
            {editUser && (
              <div style={{ background: COLORS.cardBg, borderRadius: 12, padding: 20, marginBottom: 16, border: `2px solid ${COLORS.accent}` }}>
                <h3 style={{ color: COLORS.textBright, margin: '0 0 16px 0', fontSize: 16 }}>
                  {editUser.admin_name || editUser.self_name} 설정
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 4, display: 'block' }}>표시 이름</label>
                    <input style={inputStyle} value={editUser.admin_name || ''} onChange={e => setEditUser({...editUser, admin_name: e.target.value})} />
                  </div>
                  <div>
                    <label style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 4, display: 'block' }}>등급</label>
                    <select style={selectStyle2} value={editUser.role} onChange={e => setEditUser({...editUser, role: e.target.value})}>
                      {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 4, display: 'block' }}>만료일 (비우면 무제한)</label>
                    <input style={inputStyle} type="date" value={editUser.expires_at || ''} onChange={e => setEditUser({...editUser, expires_at: e.target.value})} />
                  </div>
                  <div>
                    <label style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 4, display: 'block' }}>최대 접속 횟수 (비우면 무제한)</label>
                    <input style={inputStyle} type="number" value={editUser.max_logins || ''} onChange={e => setEditUser({...editUser, max_logins: e.target.value})} />
                  </div>
                  <div>
                    <label style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 4, display: 'block' }}>세션 시간(시) (비우면 등급 기본값)</label>
                    <input style={inputStyle} type="number" value={editUser.session_hours || ''} onChange={e => setEditUser({...editUser, session_hours: e.target.value})} />
                  </div>
                  <div>
                    <label style={{ ...FONT.tiny, color: COLORS.textMuted, marginBottom: 4, display: 'block' }}>접속 허용 시간대 (비우면 24시간)</label>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <input style={{ ...inputStyle, width: 60 }} type="number" min="0" max="23" placeholder="시작" value={editUser.allowed_hours_start ?? ''} onChange={e => setEditUser({...editUser, allowed_hours_start: e.target.value})} />
                      <span style={{ color: COLORS.textMuted }}>~</span>
                      <input style={{ ...inputStyle, width: 60 }} type="number" min="0" max="23" placeholder="종료" value={editUser.allowed_hours_end ?? ''} onChange={e => setEditUser({...editUser, allowed_hours_end: e.target.value})} />
                      <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>시</span>
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                  <button onClick={handleSaveEdit} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: COLORS.accent, color: '#fff', cursor: 'pointer', fontWeight: 600 }}>저장</button>
                  <button onClick={() => setEditUser(null)} style={{ padding: '8px 20px', borderRadius: 8, border: `1px solid ${COLORS.secondary}`, background: 'transparent', color: COLORS.textMuted, cursor: 'pointer' }}>취소</button>
                </div>
              </div>
            )}

            {/* 사용자 목록 */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.small }}>
                <thead>
                  <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
                    {['이름', '이메일', '등급', '상태', '접속', '만료일', ''].map(h => (
                      <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: COLORS.textSecondary }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, idx) => (
                    <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                      <td style={{ padding: '10px 12px', color: COLORS.textBright, fontWeight: 600 }}>{u.admin_name || u.self_name || '-'}</td>
                      <td style={{ padding: '10px 12px', color: COLORS.textMuted }}>{u.email || u.id}</td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{ padding: '2px 10px', borderRadius: 10, background: u.role === 'admin' ? '#6366F120' : '#33415520', color: u.role === 'admin' ? '#6366F1' : COLORS.textSecondary, ...FONT.tiny, fontWeight: 600 }}>
                          {ROLE_LABELS[u.role] || u.role}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{ color: u.active ? '#10B981' : '#EF4444', fontWeight: 600 }}>{u.active ? '활성' : '차단'}</span>
                      </td>
                      <td style={{ padding: '10px 12px', color: COLORS.textMuted }}>{u.login_count || 0}회</td>
                      <td style={{ padding: '10px 12px', color: COLORS.textMuted }}>{u.expires_at || '-'}</td>
                      <td style={{ padding: '10px 12px' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button onClick={() => setEditUser({ ...u, allowed_hours_start: u.allowed_hours?.[0] ?? '', allowed_hours_end: u.allowed_hours?.[1] ?? '' })} style={{ padding: '4px 10px', borderRadius: 4, border: `1px solid ${COLORS.secondary}`, background: 'transparent', color: COLORS.accent, cursor: 'pointer', ...FONT.tiny }}>설정</button>
                          {u.role !== 'admin' && <button onClick={() => handleToggle(u)} style={{ padding: '4px 10px', borderRadius: 4, border: `1px solid ${u.active ? '#EF4444' : '#10B981'}`, background: 'transparent', color: u.active ? '#EF4444' : '#10B981', cursor: 'pointer', ...FONT.tiny }}>{u.active ? '차단' : '활성'}</button>}
                          {u.role !== 'admin' && <button onClick={() => handleRemove(u)} style={{ padding: '4px 10px', borderRadius: 4, border: '1px solid #EF4444', background: '#EF444410', color: '#EF4444', cursor: 'pointer', ...FONT.tiny }}>삭제</button>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 접속 로그 */}
        {tab === 'logs' && !loading && (
          <div style={{ overflowX: 'auto', maxHeight: 400, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.tiny }}>
              <thead style={{ position: 'sticky', top: 0, background: COLORS.bg }}>
                <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
                  {['시간', '이름', '이메일', '등급', '행동'].map(h => (
                    <th key={h} style={{ padding: '8px 10px', textAlign: 'left', color: COLORS.textSecondary }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log, idx) => {
                  const u = users.find(u => (u.email || u.id) === log.email);
                  const name = u ? (u.admin_name || u.self_name) : '-';
                  return (
                    <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                      <td style={{ padding: '6px 10px', color: COLORS.textMuted }}>{log.timestamp?.toDate?.()?.toLocaleString?.() || '-'}</td>
                      <td style={{ padding: '6px 10px', color: COLORS.textBright, fontWeight: 600 }}>{name}</td>
                      <td style={{ padding: '6px 10px', color: COLORS.textSecondary }}>{log.email}</td>
                      <td style={{ padding: '6px 10px', color: COLORS.textMuted }}>{ROLE_LABELS[log.role] || log.role}</td>
                      <td style={{ padding: '6px 10px', color: log.action === 'login' ? '#10B981' : log.action === 'logout' ? COLORS.textMuted : '#EF4444' }}>{log.action}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════
// AI 토론 채팅 컴포넌트
// ═══════════════════════════════════════════════════
const TAB_CONTEXT_KEYS = {
  '브리핑':     d => ({ kpi: d.tab1?.[Object.keys(d.tab1||{})[0]]?.kpi, consumption: d.tab1?.[Object.keys(d.tab1||{})[0]]?.consumption?.map(c => ({ name: c.course_name, slots: c.today_slots, consumed: c.consumed, unsold: c.unsold, consume_rate: c.consume_rate, revenue: c.revenue })), alerts: d.tab1?.[Object.keys(d.tab1||{})[0]]?.alerts }),
  '판매내역':   d => ({ consumption: d.tab1?.[Object.keys(d.tab1||{})[0]]?.consumption?.map(c => ({ name: c.course_name, prev: c.prev_slots, today: c.today_slots, consumed: c.consumed, new_open: c.new_open, cancel_reopen: c.cancel_reopen })) }),
  '소진 패턴':  d => d.tab3?.[Object.keys(d.tab3||{})[0]] || {},
  '가격 흐름':  d => { const t = d.tab4?.[Object.keys(d.tab4||{})[0]] || {}; return { scatter_sample: (t.scatter||[]).slice(0,50), dday_trend: t.dday_trend }; },
  '할인 반응':  d => { const t = d.tab5a?.[Object.keys(d.tab5a||{})[0]] || {}; return { effectiveness: t.effectiveness, course_summary: t.course_summary }; },
  '수익 구조':  d => d.tab5b?.[Object.keys(d.tab5b||{})[0]] || {},
  '코스 비교':  d => d.tab6?.[Object.keys(d.tab6||{})[0]] || {},
  'AI 진단':    d => d.tab7?.[Object.keys(d.tab7||{})[0]] || {},
  '티타임 상세': d => ({ note: '티타임 상세 데이터는 별도 JSON 참조' }),
};

const AI_MODELS = [
  { id: 'gpt-5.4', label: 'GPT-5.4', inputPer1M: 2.50, outputPer1M: 15.00 },
  { id: 'gpt-5', label: 'GPT-5', inputPer1M: 1.25, outputPer1M: 10.00 },
  { id: 'gpt-5-mini', label: 'GPT-5 Mini', inputPer1M: 0.25, outputPer1M: 2.00 },
];

const REASONING_EFFORTS = [
  { id: 'none', label: 'None' },
  { id: 'low', label: 'Low' },
  { id: 'medium', label: 'Medium' },
  { id: 'high', label: 'High' },
  { id: 'xhigh', label: 'XHigh' },
];

const AIChatModal = ({ tabName, onClose }) => {
  const [messages, setMessages] = React.useState([]);
  const [input, setInput] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [model, setModel] = React.useState('gpt-5.4');
  const [effort, setEffort] = React.useState('none');
  const [tokenStats, setTokenStats] = React.useState({ input: 0, output: 0, cost: 0 });
  const [view, setView] = React.useState('list'); // 'list' | 'chat'
  const [histories, setHistories] = React.useState([]);
  const [historyId, setHistoryId] = React.useState(null);
  const [histLoading, setHistLoading] = React.useState(true);
  const chatEndRef = React.useRef(null);
  const inputRef = React.useRef(null);

  React.useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  React.useEffect(() => {
    if (view === 'chat') inputRef.current?.focus();
  }, [view]);

  // 내역 목록 로드
  React.useEffect(() => {
    const admin = window.__vrAdmin__;
    if (!admin?.getChatHistories) { setHistLoading(false); setView('chat'); return; }
    admin.getChatHistories().then(list => {
      setHistories(list);
      setHistLoading(false);
    }).catch(() => { setHistLoading(false); setView('chat'); });
  }, []);

  // 자동 저장 (assistant 응답 후)
  const autoSave = async (msgs, stats) => {
    const admin = window.__vrAdmin__;
    if (!admin?.saveChatHistory || msgs.length === 0) return;
    const firstUser = msgs.find(m => m.role === 'user');
    const title = firstUser ? firstUser.content.slice(0, 40) : '새 대화';
    try {
      const savedId = await admin.saveChatHistory({
        id: historyId, tabName, title, messages: msgs, tokenStats: stats, model,
      });
      if (!historyId) setHistoryId(savedId);
    } catch (e) { console.warn('채팅 저장 실패:', e.message); }
  };

  // 새 대화 시작
  const startNewChat = () => {
    setMessages([]); setTokenStats({ input: 0, output: 0, cost: 0 });
    setHistoryId(null); setView('chat');
  };

  // 내역 불러오기
  const loadHistory = (h) => {
    setMessages(h.messages || []);
    setTokenStats(h.tokenStats || { input: 0, output: 0, cost: 0 });
    setModel(h.model || 'gpt-5.4');
    setHistoryId(h.id);
    setView('chat');
  };

  // 내역 삭제
  const deleteHistory = async (e, id) => {
    e.stopPropagation();
    const admin = window.__vrAdmin__;
    if (!admin?.deleteChatHistory) return;
    try {
      await admin.deleteChatHistory(id);
      setHistories(prev => prev.filter(h => h.id !== id));
    } catch (err) { console.warn('삭제 실패:', err.message); }
  };

  const getTabContext = () => {
    const RAW = window.__GOLF_DATA__ || {};
    const extractor = TAB_CONTEXT_KEYS[tabName];
    if (!extractor) return {};
    try {
      const ctx = extractor(RAW);
      // 크기 제한 (토큰 절약)
      const str = JSON.stringify(ctx);
      return str.length > 15000 ? JSON.parse(str.slice(0, 15000) + '..."}}') : ctx;
    } catch { return {}; }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);

    try {
      const tabContext = getTabContext();
      const systemPrompt = `당신은 골프장 운영 분석 전문가입니다. 현재 "${tabName}" 탭의 데이터를 기반으로 토론합니다.
아래는 현재 탭의 데이터입니다:
${JSON.stringify(tabContext, null, 1)}

사용자의 질문에 데이터 근거를 들어 답변하세요. 한국어로 답변합니다. 간결하게.`;

      const chatHistory = messages.map(m => ({ role: m.role, content: m.content }));
      chatHistory.push({ role: 'user', content: text });

      // localhost에서는 함수 에뮬레이터로 연결한다.
      const isLocalDev = ['localhost', '127.0.0.1'].includes(window.location.hostname);
      const fnUrl = window.__FIREBASE_FUNCTIONS_URL__ || (isLocalDev
        ? 'http://127.0.0.1:5001/verhill-radar/us-central1'
        : 'https://us-central1-verhill-radar.cloudfunctions.net');
      const idToken = window.__FIREBASE_ID_TOKEN__ || '';
      const localAdminEmail = window.__LOCAL_DEV_ADMIN_EMAIL__ || '';
      const headers = { 'Content-Type': 'application/json' };
      if (idToken) headers.Authorization = `Bearer ${idToken}`;
      if (isLocalDev && localAdminEmail) headers['X-Local-Admin-Email'] = localAdminEmail;
      if (isLocalDev) headers['X-Local-Mock-Response'] = '1';
      const resp = await fetch(`${fnUrl}/aiChat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ system: systemPrompt, messages: chatHistory, model, reasoning_effort: effort }),
      });

      if (!resp.ok) {
        let err = '';
        try {
          const data = await resp.json();
          err = data.error || JSON.stringify(data);
        } catch (_) {
          err = await resp.text();
        }
        throw new Error(err || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      const reply = data.reply || data.content || '응답을 받지 못했습니다.';
      const newMessages = [...messages, { role: 'user', content: text }, { role: 'assistant', content: reply }];
      setMessages(newMessages);
      // 토큰 사용량 누적
      let newStats = tokenStats;
      if (data.usage) {
        const modelInfo = AI_MODELS.find(m => m.id === model) || AI_MODELS[0];
        const addInput = data.usage.input_tokens || 0;
        const addOutput = data.usage.output_tokens || 0;
        const addCost = (addInput / 1000000) * modelInfo.inputPer1M + (addOutput / 1000000) * modelInfo.outputPer1M;
        newStats = {
          input: tokenStats.input + addInput,
          output: tokenStats.output + addOutput,
          cost: tokenStats.cost + addCost,
        };
        setTokenStats(newStats);
      }
      // 자동 저장
      autoSave(newMessages, newStats);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `오류: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
      zIndex: 10000, display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: COLORS.bg, borderRadius: 16, width: '90%', maxWidth: 600,
        height: '80vh', maxHeight: 700, display: 'flex', flexDirection: 'column',
        border: `1px solid ${COLORS.secondary}`, boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        {/* 헤더 */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '14px 20px', borderBottom: `1px solid ${COLORS.secondary}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {view === 'chat' && (
              <button onClick={() => { setView('list'); window.__vrAdmin__?.getChatHistories().then(setHistories).catch(() => {}); }} style={{
                background: 'none', border: 'none', color: COLORS.textMuted,
                cursor: 'pointer', fontSize: 16, padding: 0,
              }}>{'◀'}</button>
            )}
            <span style={{ ...FONT.body, color: COLORS.textBright, fontWeight: 700 }}>
              {view === 'list' ? '💬 대화 내역' : `💬 AI 토론 — ${tabName}`}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {view === 'chat' && (
              <>
              <select value={model} onChange={e => setModel(e.target.value)} style={{
                padding: '4px 6px', borderRadius: 6, border: `1px solid ${COLORS.secondary}`,
                background: COLORS.cardBg, color: COLORS.textSecondary, ...FONT.tiny,
                cursor: 'pointer', outline: 'none', fontSize: 10,
              }}>
                {AI_MODELS.map(m => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
              <select value={effort} onChange={e => setEffort(e.target.value)} style={{
                padding: '4px 6px', borderRadius: 6, border: `1px solid ${COLORS.secondary}`,
                background: COLORS.cardBg, color: COLORS.textSecondary, ...FONT.tiny,
                cursor: 'pointer', outline: 'none', fontSize: 10,
              }}>
                {REASONING_EFFORTS.map(r => (
                  <option key={r.id} value={r.id}>{r.label}</option>
                ))}
              </select>
              </>
            )}
          <button onClick={onClose} style={{
            background: COLORS.secondary, border: 'none', borderRadius: 6,
            width: 28, height: 28, color: COLORS.textMuted, cursor: 'pointer',
            fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>{'✕'}</button>
          </div>
        </div>

        {/* 내역 목록 */}
        {view === 'list' && (
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button onClick={startNewChat} style={{
              padding: '14px 16px', borderRadius: 10, border: `1px dashed ${COLORS.accent}`,
              background: 'transparent', color: COLORS.accent, ...FONT.small, fontWeight: 600,
              cursor: 'pointer', textAlign: 'center',
            }}>{'+ 새 대화 시작'}</button>
            {histLoading && (
              <div style={{ ...FONT.small, color: COLORS.textMuted, textAlign: 'center', marginTop: 20 }}>{'불러오는 중...'}</div>
            )}
            {!histLoading && histories.length === 0 && (
              <div style={{ ...FONT.small, color: COLORS.textMuted, textAlign: 'center', marginTop: 20 }}>{'저장된 대화가 없습니다'}</div>
            )}
            {histories.map(h => (
              <div key={h.id} onClick={() => loadHistory(h)} style={{
                padding: '12px 16px', borderRadius: 10, border: `1px solid ${COLORS.secondary}`,
                background: COLORS.cardBg, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ ...FONT.small, color: COLORS.textBright, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {h.title || '제목 없음'}
                  </div>
                  <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 4 }}>
                    {h.tabName || ''}{' · '}{h.messages?.length || 0}{'개 메시지'}
                    {h.tokenStats?.cost > 0 && ` · $${h.tokenStats.cost.toFixed(4)} · ₩${Math.round(h.tokenStats.cost * 1500).toLocaleString()}`}
                  </div>
                </div>
                <button onClick={(e) => deleteHistory(e, h.id)} style={{
                  background: 'none', border: 'none', color: COLORS.textMuted,
                  cursor: 'pointer', fontSize: 14, padding: '4px 8px', flexShrink: 0,
                }}>{'🗑'}</button>
              </div>
            ))}
          </div>
        )}

        {/* 메시지 영역 */}
        {view === 'chat' && (<React.Fragment>
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {messages.length === 0 && (
            <div style={{ ...FONT.small, color: COLORS.textMuted, textAlign: 'center', marginTop: 40 }}>
              {tabName} 데이터를 기반으로 자유롭게 질문하세요
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              background: m.role === 'user' ? COLORS.accent + '22' : COLORS.cardBg,
              border: `1px solid ${m.role === 'user' ? COLORS.accent + '44' : COLORS.secondary}`,
              borderRadius: m.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              padding: '10px 14px',
            }}>
              <div style={{ ...FONT.small, color: COLORS.textBright, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ alignSelf: 'flex-start', ...FONT.small, color: COLORS.textMuted }}>
              {'⏳ 분석 중...'}
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* 토큰 통계 패널 */}
        <div style={{
          padding: '8px 20px', borderTop: `1px solid ${COLORS.secondary}`,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: COLORS.cardBg,
        }}>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>
              {'📥 입력 '}<span style={{ color: COLORS.textSecondary }}>{tokenStats.input.toLocaleString()}</span>{' tk'}
            </span>
            <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>
              {'📤 출력 '}<span style={{ color: COLORS.textSecondary }}>{tokenStats.output.toLocaleString()}</span>{' tk'}
            </span>
          </div>
          <span style={{ ...FONT.tiny, color: COLORS.accent, fontWeight: 700 }}>
            {'💰 $'}{tokenStats.cost.toFixed(4)}{' · ₩'}{Math.round(tokenStats.cost * 1500).toLocaleString()}
          </span>
        </div>

        {/* 입력 영역 */}
        <div style={{
          padding: '12px 20px', borderTop: `1px solid ${COLORS.secondary}`,
          display: 'flex', gap: 8,
        }}>
          <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown}
            placeholder="메시지 입력..." disabled={loading}
            style={{
              flex: 1, padding: '10px 14px', borderRadius: 10,
              border: `1px solid ${COLORS.secondary}`, background: COLORS.cardBg,
              color: COLORS.textBright, ...FONT.small, outline: 'none',
            }} />
          <button onClick={sendMessage} disabled={loading || !input.trim()}
            style={{
              padding: '10px 18px', borderRadius: 10, border: 'none',
              background: COLORS.accent, color: '#fff', ...FONT.small, fontWeight: 600,
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              opacity: loading || !input.trim() ? 0.5 : 1,
            }}>전송</button>
        </div>
        </React.Fragment>)}
      </div>
    </div>
  );
};

const TAB_CONFIG = [
  { name: '브리핑', icon: '📋', component: Tab1 },
  { name: '판매내역', icon: '🔄', component: Tab2 },
  { name: '소진 패턴', icon: '🔥', component: Tab3 },
  { name: '가격 흐름', icon: '📈', component: Tab4 },
  { name: '할인 반응', icon: '🏷️', component: Tab5 },
  { name: '수익 구조', icon: '⚖️', component: Tab6 },
  { name: '코스 비교', icon: '⛳', component: Tab7 },
  { name: 'AI 진단', icon: '🤖', component: Tab8 },
  { name: '티타임 상세', icon: '📊', component: Tab9 },
];

// 내부 앱 컴포넌트 (SettingsContext 소비)
function AppInner() {
  const [activeTab, setActiveTab] = useState(0);
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const metadata = RAW_DATA.metadata || {};
  const todayKst = useMemo(() => new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Seoul'
  }).format(new Date()), []);
  const lastCrawlDate = metadata.last_crawl?.finished_at?.slice(0, 10);
  const todayUpdateCount = metadata.last_crawl?.today_update_count;
  const todayUpdateLabel = lastCrawlDate === todayKst && todayUpdateCount
    ? ` · 오늘 업데이트 ${todayUpdateCount}번째`
    : '';
  const [userInfo, setUserInfo] = useState({ name: '', role: '', photo: '', email: '' });
  const [showAdmin, setShowAdmin] = useState(false);
  const [watermarkOn, setWatermarkOn] = useState(false); // admin 기본 off
  const [adminAlerts, setAdminAlerts] = useState(0);

  // 관리자: 승인 대기 건수 체크
  useEffect(() => {
    if (userInfo.role === 'admin' && window.__vrAdmin__) {
      const loadPendingCount = () => window.__vrAdmin__.getPendingRequests().then(list => {
        const pending = list.filter(r => r.status !== 'denied').length;
        setAdminAlerts(pending);
      }).catch(() => {});

      loadPendingCount();
      const timer = setInterval(loadPendingCount, 15000);
      return () => clearInterval(timer);
    }
  }, [userInfo.role]);

  // 워터마크 토글
  useEffect(() => {
    const el = document.getElementById('__watermark__');
    if (el) el.style.display = watermarkOn ? 'block' : 'none';
  }, [watermarkOn]);

  useEffect(() => {
    // auth_gate.js가 window에 세팅한 값을 읽어옴
    const check = () => {
      if (window.__DISPLAY_NAME__) {
        setUserInfo({
          name: window.__DISPLAY_NAME__ || '',
          role: window.__USER_ROLE__ || '',
          photo: window.__USER_PHOTO__ || '',
          email: window.__USER_EMAIL__ || '',
        });
      } else {
        setTimeout(check, 300);
      }
    };
    check();
  }, []);

  const context = useContext(SettingsContext);
  const ActiveComponent = TAB_CONFIG[activeTab].component;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '20px 24px', minHeight: '100vh' }}>
      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: COLORS.textBright, margin: 0 }}>
              VERHILL RADAR
            </h1>
            <span style={{ fontSize: 13, color: COLORS.textSecondary, fontWeight: 500, borderLeft: `2px solid ${COLORS.secondary}`, paddingLeft: 12 }}>
              베르힐 기획실
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div onClick={() => userInfo.role === 'admin' && setShowAdmin(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: userInfo.role === 'admin' ? 'pointer' : 'default' }}>
              {userInfo.photo && (
                <img src={userInfo.photo} alt="" referrerPolicy="no-referrer"
                  style={{ width: 32, height: 32, borderRadius: '50%', border: `2px solid ${COLORS.secondary}` }} />
              )}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', position: 'relative' }}>
                <span style={{ ...FONT.small, color: COLORS.textBright, fontWeight: 600 }}>
                  {userInfo.name}
                </span>
                <span style={{ ...FONT.tiny, color: COLORS.textMuted }}>
                  {userInfo.role === 'admin' ? '관리자' : userInfo.role === 'manager' ? '매니저' : userInfo.role === 'viewer' ? '뷰어' : userInfo.role === 'guest' ? '게스트' : ''}
                </span>
                {adminAlerts > 0 && (
                  <span style={{
                    position: 'absolute', top: -4, right: -12,
                    background: '#EF4444', color: '#fff', borderRadius: '50%',
                    width: 18, height: 18, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 700,
                  }}>{adminAlerts}</span>
                )}
              </div>
            </div>
            {userInfo.role === 'admin' && (
              <button onClick={() => setWatermarkOn(!watermarkOn)} style={{
                background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, padding: '4px',
                opacity: watermarkOn ? 1 : 0.4,
              }} title={watermarkOn ? '워터마크 끄기' : '워터마크 켜기'}>{watermarkOn ? '🔒' : '🔓'}</button>
            )}
            <button onClick={() => window.__vrLogout__ && window.__vrLogout__()} style={{
              padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.secondary}`,
              background: 'transparent', color: COLORS.textMuted, ...FONT.small,
              cursor: 'pointer', marginLeft: 4,
            }}>로그아웃</button>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
          <span style={{ ...FONT.small, color: COLORS.textMuted }}>
            {metadata.courses?.length || 0}개 골프장 · {metadata.all_dates?.length || 0}일 데이터 · 최종 수집: {metadata.last_crawl?.finished_at ? metadata.last_crawl.finished_at.replace('T',' ').slice(0,16) : metadata.latest_date || '-'}{todayUpdateLabel} ({metadata.last_crawl?.status === 'success' ? '성공' : metadata.last_crawl?.status || '-'} · {(metadata.last_crawl?.total_rows || 0).toLocaleString()}건)
          </span>
        </div>
      </div>

      {/* 탭 바 */}
      <div style={{
        display: 'flex', gap: 6, overflowX: 'auto', WebkitOverflowScrolling: 'touch',
        paddingBottom: 8, marginBottom: 28, borderBottom: `2px solid ${COLORS.secondary}`,
        scrollbarWidth: 'thin', minHeight: 56,
      }}>
        {TAB_CONFIG.map((tab, idx) => (
          <button key={idx} onClick={() => setActiveTab(idx)} style={{
            padding: '14px 20px', border: 'none', cursor: 'pointer',
            borderBottom: activeTab === idx ? `3px solid ${COLORS.accent}` : '3px solid transparent',
            borderRadius: '8px 8px 0 0',
            background: activeTab === idx ? COLORS.secondary : 'transparent',
            color: activeTab === idx ? COLORS.textBright : COLORS.textMuted,
            ...FONT.tab, fontWeight: activeTab === idx ? 700 : 400,
            whiteSpace: 'nowrap', minHeight: 52, minWidth: 80,
            transition: 'all 0.15s ease',
            flexShrink: 0,
          }}>
            {tab.icon} {tab.name}
          </button>
        ))}
      </div>

      {/* 탭 컨텐츠 + AI 토론 버튼 */}
      {(() => {
        const [aiChatOpen, setAiChatOpen] = React.useState(false);
        const tabName = TAB_CONFIG[activeTab].name;
        return <>
          {/* AI 토론 버튼 (관리자만) */}
          {userInfo.role === 'admin' && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
              <button onClick={() => setAiChatOpen(true)} style={{
                padding: '8px 16px', borderRadius: 20, border: `1px solid ${COLORS.accent}44`,
                background: COLORS.accent + '15', color: COLORS.accent,
                ...FONT.small, fontWeight: 600, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => { e.target.style.background = COLORS.accent + '30'; }}
              onMouseLeave={e => { e.target.style.background = COLORS.accent + '15'; }}
              >{'💬'} AI 토론</button>
            </div>
          )}
          <div key={activeTab} className="tab-fade-in">
            <ActiveComponent context={context} metadata={metadata} />
          </div>
          {aiChatOpen && <AIChatModal tabName={tabName} onClose={() => setAiChatOpen(false)} />}
        </>;
      })()}

      {/* 관리자 패널 모달 */}
      {showAdmin && userInfo.role === 'admin' && (
        <AdminPanel onClose={() => setShowAdmin(false)} />
      )}
    </div>
  );
}

// 루트 App = SettingsProvider 래퍼
const RangeSliderStyles = () => (
  <style dangerouslySetInnerHTML={{ __html: `
    .range-thumb::-webkit-slider-thumb {
      -webkit-appearance: none; appearance: none;
      width: 20px; height: 20px; border-radius: 50%;
      background: #60A5FA; border: 2px solid #fff;
      cursor: pointer; pointer-events: auto;
      box-shadow: 0 0 6px rgba(96,165,250,0.5);
    }
    .range-thumb::-moz-range-thumb {
      width: 18px; height: 18px; border-radius: 50%;
      background: #60A5FA; border: 2px solid #fff;
      cursor: pointer; pointer-events: auto;
      box-shadow: 0 0 6px rgba(96,165,250,0.5);
    }

    /* ── 호버/애니메이션 시스템 ── */
    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fillBar {
      from { transform: scaleX(0); }
      to { transform: scaleX(1); }
    }

    .tab-fade-in { animation: fadeInUp 0.3s ease-out; }

    .bar-fill { transform-origin: left; animation: fillBar 0.8s ease-out; }

    .kpi-hover {
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-hover:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }

    .card-hover {
      transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .card-hover:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(0,0,0,0.25);
      border-color: #4F46E5 !important;
    }

    .table-hover-row {
      transition: background 0.15s ease;
    }
    .table-hover-row:hover {
      background: rgba(255,255,255,0.04) !important;
    }

    .alert-hover {
      transition: filter 0.2s ease, border-left-width 0.2s ease;
    }
    .alert-hover:hover {
      filter: brightness(1.15);
    }

    .btn-hover {
      transition: all 0.2s ease;
    }
    .btn-hover:hover {
      transform: translateY(-1px);
      box-shadow: 0 3px 10px rgba(0,0,0,0.2);
    }

    .badge-hover {
      transition: transform 0.15s ease;
      display: inline-block;
    }
    .badge-hover:hover {
      transform: scale(1.08);
    }

    .heat-hover {
      transition: all 0.15s ease;
      position: relative;
    }
    .heat-hover:hover {
      transform: scale(1.2);
      z-index: 10;
      box-shadow: 0 0 12px rgba(255,255,255,0.15);
    }
  `}} />
);

export default function App() {
  return (
    <SettingsProvider>
      <RangeSliderStyles />
      <AppInner />
    </SettingsProvider>
  );
}
