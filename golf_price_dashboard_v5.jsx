import React, { useState, useContext, createContext, useMemo, useCallback, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Cell, ComposedChart, Area, AreaChart, PieChart, Pie
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
  "골드레이크": "#6366F1", "광주CC": "#0EA5E9", "르오네뜨": "#10B981", "무등산": "#F59E0B",
  "베르힐": "#EF4444", "어등산": "#8B5CF6", "푸른솔장성": "#EC4899", "해피니스": "#14B8A6"
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
const KpiCard = ({ title, value, unit, subtext, color, icon: Icon }) => (
  <div style={{
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
        <span style={{ color: COLORS.textSecondary, ...FONT.small }}>📅 기준일</span>
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
      <div style={{ display: 'flex', gap: 8 }}>
        {['1d', '3d', '7d', 'all'].map(mode => (
          <button key={mode} onClick={() => context.setRangeMode(mode)} style={{
            padding: '8px 16px', borderRadius: 20,
            border: `1px solid ${context.rangeMode === mode ? COLORS.accent : COLORS.secondary}`,
            background: context.rangeMode === mode ? COLORS.accent : 'transparent',
            color: context.rangeMode === mode ? '#fff' : COLORS.textSecondary,
            cursor: 'pointer', ...FONT.small, fontWeight: 500, minHeight: 36
          }}>
            {mode === '1d' ? '당일' : mode === '3d' ? '3일' : mode === '7d' ? '7일' : '전체'}
          </button>
        ))}
      </div>
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

  const { kpi, course_kpi, prev_course_kpi, alerts, price_changes, calendar } = tabData;
  const consumeRate = kpi?.consume_rate;
  const consumedCount = kpi?.consumed_count || 0;
  const newOpenCount = kpi?.new_open_count || 0;

  return (
    <div>
      <InfoBanner text="📊 8개 골프장의 오늘 가격과 남은 티타임, 특가 정보를 한눈에 확인할 수 있어요." />
      <DateNavigator context={context} metadata={metadata} />

      {/* A. KPI Cards (4열) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, marginBottom: 28 }}>
        <KpiCard title="잔여 티타임" value={fmt(kpi?.total_slots_today)} unit="개" icon={TrendingUp} color={COLORS.accent} subtext="전체 8개 골프장" />
        <KpiCard title="전일 소진율" value={consumeRate != null ? `${consumeRate}%` : '-'}
          subtext={`소진 ${fmt(consumedCount)}건 · 신규 ${fmt(newOpenCount)}건`}
          color={consumeRate > 5 ? SEVERITY_COLORS.warning : SEVERITY_COLORS.ok} icon={consumeRate > 5 ? TrendingDown : TrendingUp} />
        <KpiCard title="시장 반응 변동" value={fmt((kpi?.changes_by_type?.['인하'] || 0) + (kpi?.changes_by_type?.['인상'] || 0))} unit="건"
          subtext={`인하 ${kpi?.changes_by_type?.['인하'] || 0} / 인상 ${kpi?.changes_by_type?.['인상'] || 0}`} color="#EF4444" icon={TrendingDown} />
        <KpiCard title="특가 프로모션" value={fmtPct(kpi?.promo_ratio)} unit=""
          subtext={`원조특가 ${fmt(kpi?.total_promo_slots || 0)}슬롯 · 신규부착 ${kpi?.changes_by_type?.['특가부착'] || 0}건`} color="#F59E0B" />
      </div>

      {/* B. 알림 배너 */}
      {alerts && alerts.length > 0 && (
        <>
          <SectionTitle title="주의사항" icon="⚠️" />
          <div style={{ display: 'grid', gap: 10, marginBottom: 28 }}>
            {alerts.slice(0, 5).map((alert, idx) => (
              <div key={idx} style={{
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

      {/* C. 골프장 현황 테이블 */}
      <SectionTitle title="골프장 현황" icon="⛳" />
      <div style={{ overflowX: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}`, marginBottom: 28 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {['골프장', '잔여', '전일비교', '평균가', '특가', '회원/대중'].map(h => (
                <th key={h} style={{ padding: '14px 16px', textAlign: h === '골프장' ? 'left' : 'right', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(course_kpi || []).map((row, idx) => {
              const prev = prev_course_kpi?.[row.course_name];
              const slotDelta = prev ? row.slots - prev.slots : null;
              return (
                <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                  <td style={{ padding: '14px 16px' }}><CourseBadge name={row.course_name} small /></td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textBright, fontWeight: 600 }}>{fmt(row.slots)}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: slotDelta > 0 ? SEVERITY_COLORS.ok : slotDelta < 0 ? SEVERITY_COLORS.error : COLORS.textMuted }}>
                    {slotDelta != null ? `${slotDelta > 0 ? '+' : ''}${slotDelta}` : '-'}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textSecondary }}>{fmtMan(row.avg_price)}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: row.promo_slots > 0 ? EVENT_COLORS['특가부착'] : COLORS.textMuted }}>{row.promo_slots || 0}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textSecondary }}>{row.member_slots || 0} / {row.public_slots || 0}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

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
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {(price_changes[type] || []).slice(0, 5).map((evt, idx) => (
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

      {/* E. 향후 7일 캘린더 */}
      {calendar && calendar.length > 0 && (
        <>
          <SectionTitle title="향후 7일 요약" icon="📅" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, marginBottom: 28 }}>
            {calendar.map((day, idx) => {
              const isWeekend = day.weekday_type === '토요일' || day.weekday_type === '일요일';
              return (
                <div key={idx} style={{
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
    return { consumed: sum('consumed'), new_open: sum('new_open'), member_open: sum('member_open'), stayed: sum('stayed') };
  }, [consumption]);

  const chartData = useMemo(() =>
    consumption.map(r => ({
      name: r.course_name,
      stayed: r.stayed || 0,
      consumed: r.consumed || 0,
      new_open: r.new_open || 0,
      member_open: r.member_open || 0,
      consume_rate: r.consume_rate,
      today_slots: r.today_slots,
    })).sort((a, b) => (b.today_slots || 0) - (a.today_slots || 0))
  , [consumption]);

  return (
    <div>
      <InfoBanner text="🔄 어제 있던 티타임 중 오늘 사라진 것(=예약됨), 새로 열린 것, 회원 전용으로 풀린 것을 비교해요." />
      <DateNavigator context={context} metadata={metadata} />
      {isUnavailable && dataNoteMsg && (
        <InfoBanner text={dataNoteMsg} level="warning" />
      )}

      {/* KPI 3열 — 비교 불가 시 오늘 슬롯만 */}
      {!isUnavailable && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 28 }}>
          <KpiCard title="총 소진" value={fmt(totals.consumed)} unit="슬롯" color={SEVERITY_COLORS.error} subtext="전일 대비 사라진 슬롯" />
          <KpiCard title="신규 오픈" value={fmt(totals.new_open)} unit="슬롯" color={SEVERITY_COLORS.ok} subtext="새로 등장한 슬롯" />
          <KpiCard title="회원제 오픈" value={fmt(totals.member_open)} unit="슬롯" color={COLORS.accentLight} subtext="회원제 전환 슬롯" />
        </div>
      )}

      {/* Bar Chart */}
      <SectionTitle title="코스별 슬롯 현황" icon="📊" />
      <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28 }}>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 80, right: 20, top: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
            <XAxis type="number" tick={{ fill: COLORS.textSecondary, fontSize: 12 }} />
            <YAxis dataKey="name" type="category" tick={{ fill: COLORS.textMain, fontSize: 12 }} width={75} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ ...FONT.small, color: COLORS.textSecondary }} />
            {isUnavailable ? (
              <Bar dataKey="today_slots" name="오늘 슬롯" fill="#4F46E5" />
            ) : (
              <>
                <Bar dataKey="stayed" name="유지" stackId="a" fill="#475569" />
                <Bar dataKey="consumed" name="소진" stackId="a" fill="#EF4444" />
                <Bar dataKey="new_open" name="신규" stackId="b" fill="#10B981" />
                <Bar dataKey="member_open" name="회원제" stackId="b" fill="#8B5CF6" />
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
                ? ['골프장', '오늘 슬롯'].map(h => (
                    <th key={h} style={{ padding: '14px 16px', textAlign: h === '골프장' ? 'left' : 'right', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
                  ))
                : ['골프장', '전일', '오늘', '소진', '신규', '회원제', '소진율'].map(h => (
                    <th key={h} style={{ padding: '14px 16px', textAlign: h === '골프장' ? 'left' : 'right', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
                  ))
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
                <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                  <td style={{ padding: '14px 16px' }}><CourseBadge name={row.course_name} small /></td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textSecondary }}>{fmt(row.prev_slots)}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.textBright, fontWeight: 600 }}>{fmt(row.today_slots)}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: SEVERITY_COLORS.error }}>-{row.consumed}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: SEVERITY_COLORS.ok }}>+{row.new_open}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right', color: COLORS.accentLight }}>+{row.member_open}</td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
                      <span style={{ color: rateColor, fontWeight: 600 }}>{fmtPct(row.consume_rate)}</span>
                      <div style={{ width: 60, height: 6, background: COLORS.secondary, borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.min(row.consume_rate, 100)}%`, height: '100%', background: rateColor, borderRadius: 3 }} />
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
      <InfoBanner text="🔥 어떤 요일, 어떤 시간대 티타임이 가장 인기 있는지(=빨리 마감되는지) 색상으로 한눈에 볼 수 있어요." />
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
            <div key={idx} style={{ background: COLORS.cardBg, border: `1px solid ${COLORS.secondary}`, borderRadius: 10, padding: 16 }}>
              <CourseBadge name={item.course_name} small />
              <div style={{ fontSize: 24, fontWeight: 700, color: rateColor, marginTop: 10 }}>{fmtPct(item.consume_rate)}</div>
              <div style={{ color: COLORS.textMuted, ...FONT.small, marginTop: 4 }}>{item.consumed}/{item.total} 소진</div>
              <div style={{ height: 6, background: COLORS.secondary, borderRadius: 3, marginTop: 10, overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(item.consume_rate, 100)}%`, height: '100%', background: rateColor, borderRadius: 3 }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* C. 분포 차트 */}
      <SectionTitle title="시간대별 슬롯 분포" icon="📈" />
      <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20 }}>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={(today_distribution || []).map(r => ({ name: `${r.weekday_type} ${r.part_type}`, slots: r.slots, promo: r.promo_slots }))}
                    margin={{ left: 10, right: 10, top: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
            <XAxis dataKey="name" tick={{ fill: COLORS.textSecondary, fontSize: 11 }} angle={-30} textAnchor="end" />
            <YAxis tick={{ fill: COLORS.textSecondary, fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ ...FONT.small }} />
            <Bar dataKey="slots" name="전체 슬롯" fill="#3B82F6" stackId="a" />
            <Bar dataKey="promo" name="특가 슬롯" fill="#F59E0B" stackId="b" />
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
  const tab4 = RAW_DATA.tab4 || {};
  const [subTab, setSubTab] = useState(0);

  // D-day 범위 상태 (산점도용)
  const allDdays = useMemo(() => {
    const days = [...new Set((tab4.scatter || []).map(r => r.d_day))].sort((a, b) => a - b);
    return days.length ? days : [0, 30];
  }, [tab4.scatter]);
  const [ddayRange, setDdayRange] = useState([allDdays[0] || 0, allDdays[allDdays.length - 1] || 30]);

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

  // 골프장 토글 (산점도용)
  const [visibleCourses, setVisibleCourses] = useState(() => {
    const init = {};
    courses.forEach(c => { init[c] = true; });
    return init;
  });
  const toggleCourse = (c) => setVisibleCourses(prev => ({ ...prev, [c]: !prev[c] }));
  const toggleAll = () => {
    const allOn = Object.values(visibleCourses).every(v => v);
    const next = {};
    courses.forEach(c => { next[c] = !allOn; });
    setVisibleCourses(next);
  };

  // 범위 + 골프장 필터된 산점도 데이터
  const filteredScatter = useMemo(() =>
    (tab4.scatter || []).filter(r =>
      r.d_day >= ddayRange[0] && r.d_day <= ddayRange[1] && visibleCourses[r.course_name] !== false
    ),
    [tab4.scatter, ddayRange, visibleCourses]);

  // 산점도 가격 범위
  const scatterPriceRange = useMemo(() => {
    if (!filteredScatter.length) return [0, 300000];
    const prices = filteredScatter.map(r => r.price_krw);
    const prevPrices = filteredScatter.filter(r => r.previous_price_krw).map(r => r.previous_price_krw);
    const all = [...prices, ...prevPrices];
    return [Math.min(...all) * 0.9, Math.max(...all) * 1.05];
  }, [filteredScatter]);

  // 버블 집계 (5000원 버킷) — 컴포넌트 레벨에서 useMemo
  const BUCKET = 5000;
  const bubbleData = useMemo(() => {
    const map = {};
    filteredScatter.forEach(r => {
      const bucket = Math.round(r.price_krw / BUCKET) * BUCKET;
      const key = `${r.course_name}|${r.d_day}|${bucket}`;
      if (!map[key]) map[key] = { course_name: r.course_name, d_day: r.d_day, price: bucket, count: 0, promo: 0, changed: 0, drop_sum: 0, rise_sum: 0 };
      map[key].count++;
      if (r.promo_flag) map[key].promo++;
      if (r.price_changed_flag && r.previous_price_krw) {
        map[key].changed++;
        const diff = r.previous_price_krw - r.price_krw;
        if (diff > 0) map[key].drop_sum += diff;
        else map[key].rise_sum += Math.abs(diff);
      } else if (r.price_changed_flag) {
        map[key].changed++;
      }
    });
    return Object.values(map);
  }, [filteredScatter]);

  const maxBubbleCount = Math.max(...bubbleData.map(b => b.count), 1);

  const subTabs = ['D-day 추세', '산점도', '가격 분포'];

  return (
    <div>
      <InfoBanner text="💰 라운드 날짜가 다가올수록 가격이 어떻게 변하는지, 어느 가격대에 티타임이 몰려 있는지 확인해요." />

      {/* 서브탭 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {subTabs.map((name, idx) => (
          <button key={idx} onClick={() => setSubTab(idx)} style={{
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
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={trendData} margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} />
              <XAxis dataKey="d_day" reversed tick={{ fill: COLORS.textSecondary, fontSize: 12 }} label={{ value: 'D-day', position: 'insideBottomRight', fill: COLORS.textMuted }} />
              <YAxis tick={{ fill: COLORS.textSecondary, fontSize: 12 }} label={{ value: '만원', angle: -90, position: 'insideLeft', fill: COLORS.textMuted }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ ...FONT.small }} />
              {courses.map(c => (
                <Line key={c} type="monotone" dataKey={c} stroke={COURSE_COLORS[c]} strokeWidth={2} dot={false} name={c} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* B. 버블 산점도 (가격대별 집계) */}
      {subTab === 1 && (
        <div style={{ background: COLORS.cardBg, borderRadius: 10, padding: 20, marginBottom: 28 }}>
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
          {/* 범위 조절 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <span style={{ ...FONT.small, color: COLORS.textSecondary }}>D-day:</span>
            <input type="range" min={allDdays[0] || 0} max={allDdays[allDdays.length - 1] || 30}
              value={ddayRange[0]}
              onChange={e => { const v = Number(e.target.value); setDdayRange([Math.min(v, ddayRange[1] - 1), ddayRange[1]]); }}
              style={{ width: 100, accentColor: COLORS.accent }} />
            <span style={{ ...FONT.body, color: COLORS.textBright, fontWeight: 600 }}>D-{ddayRange[0]} ~ D-{ddayRange[1]}</span>
            <input type="range" min={allDdays[0] || 0} max={allDdays[allDdays.length - 1] || 30}
              value={ddayRange[1]}
              onChange={e => { const v = Number(e.target.value); setDdayRange([ddayRange[0], Math.max(v, ddayRange[0] + 1)]); }}
              style={{ width: 100, accentColor: COLORS.accent }} />
            {[{label: '7일', r: [0, 7]}, {label: '14일', r: [0, 14]}, {label: '전체', r: [allDdays[0]||0, allDdays[allDdays.length-1]||30]}].map(p => (
              <button key={p.label} onClick={() => setDdayRange(p.r)} style={{
                padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                border: `1px solid ${COLORS.secondary}`, background: 'transparent',
                color: COLORS.textSecondary, ...FONT.small,
              }}>{p.label}</button>
            ))}
            <span style={{ ...FONT.small, color: COLORS.textMuted }}>({filteredScatter.length}건)</span>
          </div>

          <ResponsiveContainer width="100%" height={480}>
            <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.secondary} strokeOpacity={0.4} />
              <XAxis dataKey="d_day" name="D-day" type="number"
                domain={[ddayRange[0], ddayRange[1]]}
                tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
                tickFormatter={v => `D-${v}`} />
              <YAxis dataKey="price" name="가격" type="number"
                tick={{ fill: COLORS.textSecondary, fontSize: 12 }}
                tickFormatter={v => `${Math.round(v/10000)}만`} />
              <Tooltip content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload;
                  return (
                    <div style={{ background: COLORS.bg, border: `1px solid ${COLORS.secondary}`, borderRadius: 8, padding: 12, ...FONT.small, color: COLORS.textMain }}>
                      <div style={{ fontWeight: 600, color: COURSE_COLORS[d.course_name] }}>{d.course_name}</div>
                      <div>D-{d.d_day} · {fmtMan(d.price)}</div>
                      <div style={{ marginTop: 4 }}>
                        슬롯 <strong>{d.count}</strong>건
                        {d.promo > 0 && <span style={{ color: EVENT_COLORS['특가부착'] }}> · 특가 {d.promo}</span>}
                        {d.changed > 0 && <span style={{ color: SEVERITY_COLORS.warning }}> · 변동 {d.changed}</span>}
                      </div>
                    </div>
                  );
                }
                return null;
              }} />
              {courses.map(c => (
                <Scatter key={c} name={c}
                  data={bubbleData.filter(b => b.course_name === c)}
                  fill={COURSE_COLORS[c]} fillOpacity={0.65}
                  shape={({ cx, cy, payload }) => {
                    const r = Math.max(3, Math.min(14, 3 + (payload.count / maxBubbleCount) * 11));
                    const color = COURSE_COLORS[payload.course_name] || '#888';
                    const baseOpacity = 0.15 + 0.55 * (payload.count / maxBubbleCount);
                    const hasDrop = payload.drop_sum > 0;
                    const hasRise = payload.rise_sum > 0;

                    // ── 혜성 꼬리 V3: 그라데이션 빔 + 글로우 필터 ──
                    const priceRange = scatterPriceRange[1] - scatterPriceRange[0];
                    const pxPerWon = priceRange > 0 ? 440 / priceRange : 0;
                    const avgDrop = hasDrop ? payload.drop_sum / payload.changed : 0;
                    const trailLen = hasDrop ? Math.max(25, Math.min(80, avgDrop * pxPerWon)) : 0;
                    // 꼬리 폭: 버블 지름과 비슷하되 최소 8px
                    const trailW = Math.max(8, r * 1.6);
                    // 고유 ID (gradient/filter용)
                    const uid = `t_${payload.course_name}_${payload.d_day}_${payload.price}`.replace(/[^a-zA-Z0-9]/g, '_');

                    return (
                      <g>
                        {/* SVG defs: 글로우 필터 + 그라데이션 */}
                        <defs>
                          {/* 이중 글로우: 넓은 후광 + 선명한 코어 */}
                          <filter id={`glow_${uid}`} x="-80%" y="-80%" width="260%" height="260%">
                            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur1" />
                            <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur2" />
                            <feMerge>
                              <feMergeNode in="blur1" />
                              <feMergeNode in="blur2" />
                              <feMergeNode in="SourceGraphic" />
                            </feMerge>
                          </filter>
                          {hasDrop && (
                            <linearGradient id={`dropG_${uid}`} x1="0" y1="1" x2="0" y2="0">
                              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.9" />
                              <stop offset="30%" stopColor="#E0F2FE" stopOpacity="0.6" />
                              <stop offset="70%" stopColor="#BAE6FD" stopOpacity="0.2" />
                              <stop offset="100%" stopColor="#7DD3FC" stopOpacity="0" />
                            </linearGradient>
                          )}
                          {hasRise && (
                            <linearGradient id={`riseG_${uid}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.8" />
                              <stop offset="30%" stopColor="#D1FAE5" stopOpacity="0.5" />
                              <stop offset="70%" stopColor="#6EE7B7" stopOpacity="0.15" />
                              <stop offset="100%" stopColor="#6EE7B7" stopOpacity="0" />
                            </linearGradient>
                          )}
                        </defs>

                        {/* 하락 혜성빔: 흰색→하늘색 발광 (위쪽) */}
                        {hasDrop && (
                          <rect
                            x={cx - trailW / 2} y={cy - trailLen}
                            width={trailW} height={trailLen}
                            rx={trailW / 2}
                            fill={`url(#dropG_${uid})`}
                            filter={`url(#glow_${uid})`}
                          />
                        )}
                        {/* 인상 혜성빔: 흰색→연초록 발광 (아래쪽) */}
                        {hasRise && (() => {
                          const avgRise = payload.rise_sum / payload.changed;
                          const riseLen = Math.max(20, Math.min(60, avgRise * pxPerWon));
                          return (
                            <rect
                              x={cx - trailW / 2} y={cy}
                              width={trailW} height={riseLen}
                              rx={trailW / 2}
                              fill={`url(#riseG_${uid})`}
                              filter={`url(#glow_${uid})`}
                            />
                          );
                        })()}
                        {/* 변동 버블: 별똥별 스타일 */}
                        {(hasDrop || hasRise) ? (
                          <>
                            {/* 외곽 발광 링 — 부드러운 흰색 후광 */}
                            <circle cx={cx} cy={cy} r={r + 4} fill="none"
                              stroke="#FFFFFF" strokeWidth={1.5}
                              strokeOpacity={0.4} filter={`url(#glow_${uid})`} />
                            {/* 내곽 발광 링 — 밝고 선명한 흰색 */}
                            <circle cx={cx} cy={cy} r={r + 2} fill="none"
                              stroke="#FFFFFF" strokeWidth={2}
                              strokeOpacity={0.9} filter={`url(#glow_${uid})`} />
                            {/* 메인 버블 — 글로우 적용 */}
                            <circle cx={cx} cy={cy} r={r}
                              fill={color} fillOpacity={baseOpacity + 0.15}
                              stroke="#FFFFFF" strokeWidth={1.5} strokeOpacity={0.7}
                              filter={`url(#glow_${uid})`} />
                            {/* ✦ 스파클 포인트 — 별똥별 반짝임 */}
                            {[[-1, -1], [1, -1], [0.8, 0.6], [-0.7, 0.8]].map(([dx, dy], si) => (
                              <circle key={`sp${si}`}
                                cx={cx + dx * (r + 5)} cy={cy + dy * (r + 5)}
                                r={1.2} fill="#FFFFFF" fillOpacity={0.7 - si * 0.12}
                                filter={`url(#glow_${uid})`} />
                            ))}
                          </>
                        ) : (
                          /* 일반 버블 — 변동 없음 */
                          <circle cx={cx} cy={cy} r={r}
                            fill={color} fillOpacity={baseOpacity}
                            stroke={color} strokeWidth={1.2} strokeOpacity={0.8} />
                        )}
                        {/* 카운트 라벨 */}
                        {payload.count >= 5 && (
                          <text x={cx} y={cy + 3.5} textAnchor="middle" fill="#fff" fontSize={9} fontWeight="600">{payload.count}</text>
                        )}
                      </g>
                    );
                  }}
                />
              ))}
              <Legend wrapperStyle={{ ...FONT.small }} />
            </ScatterChart>
          </ResponsiveContainer>

          {/* 범례 보조 */}
          <div style={{ display: 'flex', gap: 20, justifyContent: 'center', marginTop: 8, ...FONT.small, color: COLORS.textMuted }}>
            <span>● 크기 = 슬롯 수</span>
            <span style={{ color: '#E0F2FE' }}>✦ 흰색 빔↑ = 가격 하락</span>
            <span style={{ color: '#D1FAE5' }}>✦ 연초록 빔↓ = 가격 인상</span>
            <span style={{ color: '#FFFFFF' }}>◎ 발광 = 가격 변동</span>
          </div>
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
      <SectionTitle title="가격 변동 이벤트" icon="📋" />
      <div style={{ overflowX: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {['골프장', '코스', '이벤트', '변동', '경기일', '시간'].map(h => (
                <th key={h} style={{ padding: '12px 14px', textAlign: 'left', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(tab4.price_events || []).slice(0, 15).map((evt, idx) => (
              <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                <td style={{ padding: '12px 14px' }}><CourseBadge name={evt.course_name} small /></td>
                <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{evt.course_sub}</td>
                <td style={{ padding: '12px 14px' }}>
                  <span style={{
                    padding: '3px 10px', borderRadius: 12, ...FONT.tiny, fontWeight: 600,
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
  const tab5a = RAW_DATA.tab5a || {};
  const [discountView, setDiscountView] = useState('all'); // 'all' | 'market' | 'promo'

  // 할인 이벤트를 시장 반응 vs 특가 프로모션으로 분리
  const allEvents = tab5a.discount_events || [];
  const marketEvents = allEvents.filter(e => e.event_type === '인하' || e.event_type === '인상');
  const promoEvents = allEvents.filter(e => e.event_type === '특가부착' || e.event_type === '특가해제');
  const displayEvents = discountView === 'market' ? marketEvents : discountView === 'promo' ? promoEvents : allEvents;

  return (
    <div>
      {tab5a.data_limitation && <InfoBanner text={tab5a.data_limitation} level="warning" />}
      <InfoBanner text="🔻 시장 반응 = 수요에 의해 실제 가격이 변동된 것 | 🏷️ 특가 프로모션 = 골프장이 처음부터 할인 라벨을 붙인 것. 이 둘은 의미가 완전히 다릅니다." />

      {/* B. 골프장별 할인 현황 카드 */}
      <SectionTitle title="골프장별 할인 현황" icon="🏷️" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 28 }}>
        {(tab5a.course_summary || []).map((cs, idx) => (
          <div key={idx} style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: `1px solid ${COLORS.secondary}` }}>
            <CourseBadge name={cs.course_name} small />
            <div style={{ fontSize: 28, fontWeight: 700, color: COLORS.textBright, marginTop: 10 }}>{cs.event_count}<span style={{ ...FONT.small, color: COLORS.textMuted, marginLeft: 4 }}>건</span></div>
            <div style={{ color: COLORS.textSecondary, ...FONT.small, marginTop: 6 }}>평균 할인 {fmtPct(cs.avg_discount_pct)} · 최대 {fmtPct(cs.max_discount_pct)}</div>
          </div>
        ))}
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
          <button key={opt.key} onClick={() => setDiscountView(opt.key)} style={{
            padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
            border: `1px solid ${discountView === opt.key ? opt.color : COLORS.secondary}`,
            background: discountView === opt.key ? opt.color + '20' : 'transparent',
            color: discountView === opt.key ? opt.color : COLORS.textMuted,
            ...FONT.small, fontWeight: discountView === opt.key ? 600 : 400,
          }}>{opt.label} ({opt.count})</button>
        ))}
      </div>
      <div style={{ overflowX: 'auto', background: COLORS.cardBg, borderRadius: 10, border: `1px solid ${COLORS.secondary}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', ...FONT.table }}>
          <thead>
            <tr style={{ borderBottom: `2px solid ${COLORS.secondary}` }}>
              {['골프장', '코스', '유형', '이벤트', '할인율', '할인액', '경기일', '시간'].map(h => (
                <th key={h} style={{ padding: '12px 14px', textAlign: 'left', color: COLORS.textSecondary, ...FONT.tableHeader }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayEvents.slice(0, 20).map((evt, idx) => {
              const isMarket = evt.event_type === '인하' || evt.event_type === '인상';
              return (
                <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
                  <td style={{ padding: '12px 14px' }}><CourseBadge name={evt.course_name} small /></td>
                  <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{evt.course_sub}</td>
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{ padding: '2px 8px', borderRadius: 10, ...FONT.tiny, fontWeight: 600,
                      background: isMarket ? '#EF444420' : '#F59E0B20',
                      color: isMarket ? '#EF4444' : '#F59E0B',
                    }}>{isMarket ? '시장반응' : '특가전환'}</span>
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <span style={{ padding: '3px 10px', borderRadius: 12, ...FONT.tiny, fontWeight: 600,
                      background: `${EVENT_COLORS[evt.event_type] || '#F59E0B'}25`, color: EVENT_COLORS[evt.event_type] || '#F59E0B'
                    }}>{evt.event_type}</span>
                  </td>
                  <td style={{ padding: '12px 14px', color: SEVERITY_COLORS.error }}>{fmtPct(evt.discount_pct)}</td>
                  <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{fmt(evt.discount_amt)}원</td>
                  <td style={{ padding: '12px 14px', color: COLORS.textSecondary }}>{evt.play_date}</td>
                  <td style={{ padding: '12px 14px', color: COLORS.textMuted }}>{evt.tee_time}</td>
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

  if (!tabData) return <NoData />;

  const { course_summary, yield_histogram } = tabData;

  return (
    <div>
      <InfoBanner text="📈 정가 대비 실제로 얼마에 팔리고 있는지 비율을 보여줘요. 100%보다 낮으면 할인 중, 높으면 프리미엄이에요." />
      <DateNavigator context={context} metadata={metadata} />

      {/* A. Yield 카드 */}
      <SectionTitle title="코스별 Yield" icon="⚖️" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14, marginBottom: 28 }}>
        {(course_summary || []).map((cs, idx) => (
          <div key={idx} style={{ background: COLORS.cardBg, borderRadius: 10, padding: 18, border: `1px solid ${COLORS.secondary}` }}>
            <CourseBadge name={cs.course_name} small />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
              <div>
                <div style={{ ...FONT.small, color: COLORS.textMuted }}>평일 Yield</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: cs.weekday_avg_yield >= 1 ? SEVERITY_COLORS.ok : SEVERITY_COLORS.warning }}>
                  {(cs.weekday_avg_yield * 100).toFixed(1)}%
                </div>
                <div style={{ ...FONT.tiny, color: COLORS.textMuted }}>{cs.weekday_count}슬롯</div>
              </div>
              <div>
                <div style={{ ...FONT.small, color: COLORS.textMuted }}>주말 Yield</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: cs.weekend_avg_yield >= 1 ? SEVERITY_COLORS.ok : SEVERITY_COLORS.warning }}>
                  {(cs.weekend_avg_yield * 100).toFixed(1)}%
                </div>
                <div style={{ ...FONT.tiny, color: COLORS.textMuted }}>{cs.weekend_count}슬롯</div>
              </div>
            </div>
            <div style={{ ...FONT.tiny, color: COLORS.textMuted, marginTop: 8 }}>평일 특가비율: {fmtPct(cs.promo_ratio_weekday)}</div>
          </div>
        ))}
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
              {['골프장', '코스', '타입', '슬롯', '평균가', '가격범위', '특가', '전일대비'].map(h => (
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
                    경기일 {evt.play_date} · {evt.member_slot_count}슬롯
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
const Tab8 = ({ context, metadata }) => {
  const RAW_DATA = window.__GOLF_DATA__ || {};
  const tabData = (RAW_DATA.tab7 || {})[context.anchorDate] || null;

  if (!tabData) return <NoData />;

  const { diagnostics, data_note, data_days, rules_applicable, rules_pending } = tabData;

  return (
    <div>
      {data_note && <InfoBanner text={data_note} />}
      <DateNavigator context={context} metadata={metadata} />

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
              {/* Findings */}
              <div style={{ padding: '12px 18px' }}>
                {(diag.findings || []).slice(0, 8).map((f, fi) => {
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
                  <div style={{ ...FONT.tiny, color: COLORS.textMuted, padding: 4 }}>... 외 {diag.finding_count - 8}건</div>
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
  const allSlots = useMemo(() => (window.__GOLF_TAB8_TODAY__?.slots || []), []);

  const [filters, setFilters] = useState({ course: '', promo: '', weekday: '', part: '', search: '' });
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
            {paged.map((row, idx) => (
              <tr key={idx} style={{ borderBottom: `1px solid ${COLORS.secondary}22` }}>
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
            ))}
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
const TAB_CONFIG = [
  { name: '브리핑', icon: '📋', component: Tab1 },
  { name: '생애주기', icon: '🔄', component: Tab2 },
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

  const context = useContext(SettingsContext);
  const ActiveComponent = TAB_CONFIG[activeTab].component;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '20px 24px', minHeight: '100vh' }}>
      {/* 헤더 */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: COLORS.textBright, margin: 0 }}>
            ⛳ 전라도 골프 가격 변동 예측
          </h1>
          <span style={{ fontSize: 13, color: COLORS.textSecondary, fontWeight: 500, borderLeft: `2px solid ${COLORS.secondary}`, paddingLeft: 12 }}>
            대성베르힐건설 AI기획실
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
          <span style={{ ...FONT.small, color: COLORS.textMuted }}>
            {metadata.courses?.length || 0}개 골프장 · {metadata.all_dates?.length || 0}일 데이터 · 최종 수집: {metadata.latest_date || '-'}
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

      {/* 탭 컨텐츠 */}
      <ActiveComponent context={context} metadata={metadata} />
    </div>
  );
}

// 루트 App = SettingsProvider 래퍼
export default function App() {
  return (
    <SettingsProvider>
      <AppInner />
    </SettingsProvider>
  );
}
