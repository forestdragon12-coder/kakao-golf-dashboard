import React, { useState, useMemo, createContext, useContext, useEffect, useCallback } from 'react';
import {
  LineChart, Line, ComposedChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ScatterChart, Scatter, BarChart, ReferenceLine, Area, AreaChart,
  Cell
} from 'recharts';

// ─────────────────────────────────────────────────────────
// 데이터 로드
// ─────────────────────────────────────────────────────────
const RAW_DATA = (typeof window !== 'undefined' && window.__GOLF_DATA__) ? window.__GOLF_DATA__ : {
  metadata: { generated_at: "2026-03-14 23:46", latest_date: "2026-03-14", prev_date: "2026-03-13",
    courses: ["골드레이크","광주CC","르오네뜨","무등산","베르힐","어등산","푸른솔장성","해피니스"],
    member_courses: ["골드레이크","해피니스"] },
  tab1: { kpi: { total_slots_today: 8015, total_slots_prev: 3950, slot_delta: 4065,
    total_price_changes: 143, changes_by_type: {인상:2,인하:125,특가부착:11,특가해제:5},
    total_promo_slots: 2012, promo_ratio: 25.1 },
    course_kpi: [], prev_course_kpi: {}, price_changes: {}, consumption: [], alerts: [], calendar: [] },
  tab2: { lifecycle_summary: [], play_date_summary: [], data_days: 1 },
  tab3: { heatmap: [], course_patterns: [], today_distribution: [], data_days: 1 },
  tab4: { dday_trend: [], scatter: [], histogram: [], price_events: [] },
  tab5a: { discount_events: [], course_summary: [], promo_distribution: [], dday_comparison: [] },
  tab5b: { yield_slots: [], course_summary: [], yield_histogram: [] },
  tab6: { subcourse_rows: [], course_summary: {}, member_opens_latest: [] },
  tab7: { diagnostics: [], data_days: 1, rules_applicable: [], rules_pending: [], data_note: "" },
};

// ─────────────────────────────────────────────────────────
// 상수 & 유틸리티
// ─────────────────────────────────────────────────────────
const COURSE_COLORS = {
  "골드레이크": "#6366F1",
  "광주CC":     "#0EA5E9",
  "르오네뜨":   "#10B981",
  "무등산":     "#F59E0B",
  "베르힐":     "#EF4444",
  "어등산":     "#8B5CF6",
  "푸른솔장성": "#EC4899",
  "해피니스":   "#14B8A6",
};

const COURSES = ["골드레이크","광주CC","르오네뜨","무등산","베르힐","어등산","푸른솔장성","해피니스"];

const WEEKDAY_ORDER = { "월요일":0,"화요일":1,"수요일":2,"목요일":3,"금요일":4,"토요일":5,"일요일":6 };

function fmt(p) {
  if (p == null) return "—";
  const v = p / 10000;
  const s = v % 1 === 0 ? v.toFixed(0) : v.toFixed(1);
  return s + "만";
}

function fmtK(p) {
  if (p == null) return "—";
  return Math.round(p).toLocaleString() + "원";
}

function pct(n, d) {
  if (!d) return "—";
  return (n / d * 100).toFixed(1) + "%";
}

function delta(v, prev) {
  if (v == null || prev == null) return null;
  return v - prev;
}

function sign(v) {
  if (v == null) return "";
  return v > 0 ? "▲" : v < 0 ? "▼" : "±";
}

function groupBy(arr, keyFn) {
  const map = {};
  for (const item of arr) {
    const k = keyFn(item);
    if (!map[k]) map[k] = [];
    map[k].push(item);
  }
  return map;
}

function isWeekend(wt) {
  return wt === "토요일" || wt === "일요일" || wt === "금요일";
}

const SEVERITY_CONFIG = {
  error:   { color: "text-red-600",    bg: "bg-red-50",    border: "border-red-300",   icon: "🔴", label: "긴급" },
  warning: { color: "text-amber-600",  bg: "bg-amber-50",  border: "border-amber-300", icon: "🟡", label: "주의" },
  info:    { color: "text-blue-600",   bg: "bg-blue-50",   border: "border-blue-300",  icon: "🔵", label: "정보" },
  ok:      { color: "text-green-600",  bg: "bg-green-50",  border: "border-green-300", icon: "🟢", label: "정상" },
};

// ─────────────────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────────────────
const SettingsContext = createContext({
  baseCourse: "", setBaseCourse: () => {},
  weekdayMode: "전체", setWeekdayMode: () => {},
});

// ─────────────────────────────────────────────────────────
// 공통 컴포넌트
// ─────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, delta: d, color, icon }) {
  const pos = d != null && d > 0;
  const neg = d != null && d < 0;
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
      {color && <div className="h-1" style={{ background: color }} />}
      <div className="p-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-500 font-medium uppercase tracking-wide">{label}</span>
          {icon && <span className="text-lg">{icon}</span>}
        </div>
        <div className="text-2xl font-bold text-slate-800">{value}</div>
        {(sub || d != null) && (
          <div className="mt-1 flex items-center gap-2">
            {sub && <span className="text-xs text-slate-400">{sub}</span>}
            {d != null && (
              <span className={`text-xs font-semibold ${pos ? "text-emerald-500" : neg ? "text-red-500" : "text-slate-400"}`}>
                {sign(d)}{Math.abs(d).toLocaleString()}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CourseBadge({ course, size = "sm" }) {
  const color = COURSE_COLORS[course] || "#94a3b8";
  const sz = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";
  return (
    <span className={`inline-block rounded-full font-medium ${sz}`}
      style={{ background: color + "22", color }}>
      {course}
    </span>
  );
}

function SectionHeader({ title, sub }) {
  return (
    <div className="mb-4">
      <h3 className="text-base font-bold text-slate-700">{title}</h3>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function DataNote({ text }) {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700 mb-4">
      ⚠️ {text}
    </div>
  );
}

function WeekdayToggle({ value, onChange }) {
  const opts = ["전체", "평일", "주말"];
  return (
    <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
      {opts.map(o => (
        <button key={o}
          onClick={() => onChange(o)}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${value === o ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
          {o}
        </button>
      ))}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-slate-600">{p.name}:</span>
          <span className="font-medium">{p.value?.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Settings Modal
// ─────────────────────────────────────────────────────────
function SettingsModal({ onClose }) {
  const { baseCourse, setBaseCourse } = useContext(SettingsContext);
  const [selected, setSelected] = useState(baseCourse);
  const meta = RAW_DATA.metadata;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-lg font-bold text-slate-800">⚙️ 대시보드 설정</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">✕</button>
        </div>
        <div className="p-6">
          <p className="text-sm text-slate-600 mb-1 font-medium">우리 골프장 선택</p>
          <p className="text-xs text-slate-400 mb-4">선택한 골프장이 전 탭에서 강조 표시됩니다</p>
          <div className="grid grid-cols-2 gap-2">
            {(meta.courses || COURSES).map(c => {
              const color = COURSE_COLORS[c] || "#94a3b8";
              const isSelected = selected === c;
              return (
                <button key={c} onClick={() => setSelected(c)}
                  className={`flex items-center gap-2 p-3 rounded-xl border-2 transition-all text-sm font-medium
                    ${isSelected ? "border-current" : "border-slate-200 hover:border-slate-300 text-slate-600"}`}
                  style={isSelected ? { borderColor: color, color, background: color + "11" } : {}}>
                  <span className="w-3 h-3 rounded-full" style={{ background: color }} />
                  {c}
                </button>
              );
            })}
          </div>
          {selected && (
            <button onClick={() => setSelected("")}
              className="mt-2 text-xs text-slate-400 underline">선택 해제</button>
          )}
        </div>
        <div className="px-6 pb-6 flex gap-3">
          <button onClick={onClose} className="flex-1 py-2 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50">취소</button>
          <button
            onClick={() => { setBaseCourse(selected); onClose(); }}
            className="flex-1 py-2 rounded-xl text-sm font-semibold text-white"
            style={{ background: "linear-gradient(135deg, #1e293b, #334155)" }}>
            저장
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 1 — 오늘의 브리핑
// ─────────────────────────────────────────────────────────
function Tab1() {
  const { baseCourse, weekdayMode } = useContext(SettingsContext);
  const d = RAW_DATA.tab1;
  const kpi = d.kpi;
  const meta = RAW_DATA.metadata;

  // AI 액션 (Tab7 요약)
  const aiDiags = RAW_DATA.tab7?.diagnostics || [];
  const baseDiag = baseCourse ? aiDiags.find(x => x.course_name === baseCourse) : null;
  const topFindings = baseDiag?.findings?.filter(f => f.rule !== "OK").slice(0, 3) || [];

  return (
    <div className="space-y-6">
      {/* AI 액션 패널 (기준 골프장 설정 시) */}
      {baseCourse && topFindings.length > 0 && (
        <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-xl p-4 text-white">
          <p className="text-xs text-slate-300 font-medium mb-3 uppercase tracking-wide">
            🤖 {baseCourse} AI 진단 요약
          </p>
          <div className="space-y-2">
            {topFindings.map((f, i) => {
              const cfg = SEVERITY_CONFIG[f.severity] || SEVERITY_CONFIG.info;
              return (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span>{cfg.icon}</span>
                  <div>
                    <span className="font-semibold">[{f.title}]</span>{" "}
                    <span className="text-slate-300">{f.desc}</span>{" "}
                    <span className="text-slate-400 text-xs">→ {f.action}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* KPI 카드 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="총 잔여 슬롯" value={kpi.total_slots_today?.toLocaleString()}
          sub={`전일 ${kpi.total_slots_prev?.toLocaleString()}`}
          delta={kpi.slot_delta} color="#6366F1" icon="🏌️" />
        <KpiCard label="가격 변경" value={kpi.total_price_changes}
          sub={`인하 ${kpi.changes_by_type?.인하 || 0} / 인상 ${kpi.changes_by_type?.인상 || 0}`}
          color="#EF4444" icon="💰" />
        <KpiCard label="특가 슬롯" value={kpi.total_promo_slots?.toLocaleString()}
          sub={`전체 ${kpi.promo_ratio}%`} color="#F59E0B" icon="🏷️" />
        <KpiCard label="감지 골프장" value={`${meta.courses?.length || 8}개`}
          sub={meta.latest_date} color="#10B981" icon="📊" />
      </div>

      {/* 경보 섹션 */}
      {d.alerts?.length > 0 && (
        <div>
          <SectionHeader title="⚠️ 경보" />
          <div className="space-y-2">
            {d.alerts.map((a, i) => {
              const cfg = SEVERITY_CONFIG[a.level] || SEVERITY_CONFIG.info;
              return (
                <div key={i} className={`flex items-center gap-3 p-3 rounded-lg border ${cfg.bg} ${cfg.border}`}>
                  <span className="text-base">{cfg.icon}</span>
                  <div className="flex-1 min-w-0">
                    <span className={`text-xs font-semibold ${cfg.color}`}>[{cfg.label}] </span>
                    <span className="text-xs text-slate-700">{a.msg}</span>
                  </div>
                  <CourseBadge course={a.course} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 골프장별 현황 */}
      <div>
        <SectionHeader title="📋 골프장별 현황" sub="오늘 기준 잔여 슬롯 및 소진 현황" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-slate-50">
                <th className="text-left px-4 py-2 text-xs text-slate-500 font-semibold border-b border-slate-200">골프장</th>
                <th className="text-right px-3 py-2 text-xs text-slate-500 font-semibold border-b border-slate-200">잔여</th>
                <th className="text-right px-3 py-2 text-xs text-slate-500 font-semibold border-b border-slate-200">전일</th>
                <th className="text-right px-3 py-2 text-xs text-slate-500 font-semibold border-b border-slate-200">소진</th>
                <th className="text-right px-3 py-2 text-xs text-slate-500 font-semibold border-b border-slate-200">소진율</th>
                <th className="text-right px-3 py-2 text-xs text-slate-500 font-semibold border-b border-slate-200">평균가</th>
                <th className="text-right px-3 py-2 text-xs text-slate-500 font-semibold border-b border-slate-200">특가</th>
              </tr>
            </thead>
            <tbody>
              {d.course_kpi?.map((r, i) => {
                const color = COURSE_COLORS[r.course_name] || "#94a3b8";
                const cons = d.consumption?.find(c => c.course_name === r.course_name);
                const isBase = baseCourse === r.course_name;
                return (
                  <tr key={i}
                    className={`border-b border-slate-100 hover:bg-slate-50 transition-colors
                      ${isBase ? "bg-indigo-50/50" : ""}`}>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                        <span className={`font-medium text-slate-700 ${isBase ? "font-bold" : ""}`}>
                          {r.course_name}
                          {isBase && <span className="ml-1 text-xs text-indigo-500">★</span>}
                        </span>
                      </div>
                    </td>
                    <td className="text-right px-3 py-2.5 font-semibold text-slate-800">
                      {r.slots?.toLocaleString()}
                    </td>
                    <td className="text-right px-3 py-2.5 text-slate-500">
                      {cons?.prev_slots?.toLocaleString() || "—"}
                    </td>
                    <td className="text-right px-3 py-2.5">
                      {cons?.consumed != null ? (
                        <span className="text-emerald-600 font-medium">{cons.consumed}</span>
                      ) : "—"}
                    </td>
                    <td className="text-right px-3 py-2.5">
                      {cons?.consume_rate != null ? (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full
                          ${cons.consume_rate >= 50 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                          {cons.consume_rate}%
                        </span>
                      ) : "—"}
                    </td>
                    <td className="text-right px-3 py-2.5 text-slate-700">{fmt(r.avg_price)}</td>
                    <td className="text-right px-3 py-2.5">
                      {r.promo_slots > 0 ? (
                        <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                          {r.promo_slots}
                        </span>
                      ) : <span className="text-slate-300">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 가격 변경 이벤트 */}
      {(d.price_changes?.인하?.length > 0 || d.price_changes?.인상?.length > 0 || d.price_changes?.특가부착?.length > 0) && (
        <div className="grid sm:grid-cols-2 gap-4">
          {d.price_changes?.인하?.length > 0 && (
            <div>
              <SectionHeader title={`📉 가격 인하 (${d.price_changes.인하.length}건)`} />
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead><tr className="bg-slate-50">
                    {["골프장","서브코스","경기일","변경"].map(h => (
                      <th key={h} className="text-left px-3 py-2 text-slate-500 font-semibold border-b border-slate-200">{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {d.price_changes.인하.slice(0, 15).map((ev, i) => (
                      <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-2"><CourseBadge course={ev.course_name} /></td>
                        <td className="px-3 py-2 text-slate-600">{ev.course_sub?.replace(/\(.*?\)/, "")}</td>
                        <td className="px-3 py-2 text-slate-600">{ev.play_date?.slice(5)}</td>
                        <td className="px-3 py-2">
                          <span className="text-slate-500">{fmt(ev.old_price_krw)}</span>
                          <span className="text-slate-400 mx-1">→</span>
                          <span className="text-blue-600 font-medium">{fmt(ev.new_price_krw)}</span>
                          <span className="text-blue-500 ml-1">{ev.delta_pct?.toFixed(1)}%</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {d.price_changes?.인상?.length > 0 && (
            <div>
              <SectionHeader title={`📈 가격 인상 (${d.price_changes.인상.length}건)`} />
              <div className="space-y-2">
                {d.price_changes.인상.map((ev, i) => (
                  <div key={i} className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <CourseBadge course={ev.course_name} />
                      <span className="text-xs text-red-600 font-bold">+{ev.delta_pct?.toFixed(1)}%</span>
                    </div>
                    <p className="text-xs text-slate-700">
                      {ev.course_sub} {ev.play_date?.slice(5)} {ev.tee_time}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {fmt(ev.old_price_krw)} → {fmt(ev.new_price_krw)}
                    </p>
                    {ev.note && <p className="text-xs text-slate-400 mt-1 italic">{ev.note}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 향후 7일 캘린더 */}
      {d.calendar?.length > 0 && (
        <div>
          <SectionHeader title="📅 향후 7일 경기일" sub="D-7 이내 경기일 잔여 현황" />
          <div className="grid grid-cols-3 sm:grid-cols-7 gap-2">
            {d.calendar.map((c, i) => {
              const isWknd = isWeekend(c.weekday_type);
              return (
                <div key={i} className={`rounded-xl p-3 text-center border
                  ${isWknd ? "bg-indigo-50 border-indigo-200" : "bg-white border-slate-200"}`}>
                  <p className={`text-xs font-semibold mb-1 ${isWknd ? "text-indigo-600" : "text-slate-500"}`}>
                    {c.play_date?.slice(5)} {c.weekday_type?.slice(0,1)}
                  </p>
                  <p className="text-lg font-bold text-slate-800">{c.slots}</p>
                  <p className="text-xs text-slate-500">{fmt(c.avg_price)}</p>
                  {c.promo_slots > 0 && (
                    <p className="text-xs text-amber-600 mt-0.5">특가 {c.promo_slots}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 2 — 슬롯 생애주기
// ─────────────────────────────────────────────────────────
function Tab2() {
  const { baseCourse } = useContext(SettingsContext);
  const d = RAW_DATA.tab2;

  const chartData = useMemo(() => {
    return (d.lifecycle_summary || []).map(r => ({
      name: r.course_name,
      active: r.total,
      consumed: r.consumed || 0,
      new_open: r.new_open || 0,
      consume_rate: r.consume_rate || 0,
    }));
  }, [d]);

  // 경기일별 골프장 슬롯 매트릭스
  const playDateData = useMemo(() => {
    const grouped = groupBy(d.play_date_summary || [], r => r.play_date);
    return Object.entries(grouped).map(([date, rows]) => {
      const entry = { date: date.slice(5), weekday: rows[0]?.weekday_type };
      for (const r of rows) {
        entry[r.course_name] = r.active_slots;
      }
      return entry;
    });
  }, [d]);

  return (
    <div className="space-y-6">
      {d.data_days < 7 && (
        <DataNote text={`현재 ${d.data_days}일 데이터. 슬롯 생애주기 타임라인은 7일+ 축적 후 완전 표시됩니다.`} />
      )}

      {/* 생애주기 집계 */}
      <div>
        <SectionHeader title="🔄 골프장별 슬롯 상태" sub="전일 대비 소진/신규/잔여 현황" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {(d.lifecycle_summary || []).map((r, i) => {
            const color = COURSE_COLORS[r.course_name] || "#94a3b8";
            const isBase = baseCourse === r.course_name;
            return (
              <div key={i} className={`bg-white rounded-xl border p-4 shadow-sm
                ${isBase ? "ring-2" : "border-slate-200"}`}
                style={isBase ? { ringColor: color } : {}}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-3 h-3 rounded-full" style={{ background: color }} />
                  <span className="text-sm font-bold text-slate-700">{r.course_name}</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">잔여</span>
                    <span className="font-bold text-slate-800">{r.total}</span>
                  </div>
                  {r.consumed != null && (
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">소진</span>
                      <span className="font-semibold text-emerald-600">{r.consumed}</span>
                    </div>
                  )}
                  {r.new_open != null && r.new_open > 0 && (
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">신규오픈</span>
                      <span className="font-semibold text-blue-600">{r.new_open}</span>
                    </div>
                  )}
                  {r.consume_rate != null && (
                    <div className="mt-2">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-400">소진율</span>
                        <span className={`font-bold ${r.consume_rate >= 50 ? "text-emerald-600" : "text-amber-600"}`}>
                          {r.consume_rate}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all"
                          style={{ width: `${Math.min(100, r.consume_rate)}%`, background: color }} />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="active" name="잔여" fill="#6366F1" radius={[4,4,0,0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={COURSE_COLORS[entry.name] || "#6366F1"} />
                ))}
              </Bar>
              <Bar dataKey="consumed" name="소진" fill="#10B981" radius={[4,4,0,0]} opacity={0.7} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* 경기일별 슬롯 */}
      {playDateData.length > 0 && (
        <div>
          <SectionHeader title="📅 경기일별 골프장 잔여 (D-14 이내)" />
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50">
                  <th className="text-left px-3 py-2 text-slate-500 font-semibold border-b border-slate-200">경기일</th>
                  {COURSES.map(c => (
                    <th key={c} className="text-right px-2 py-2 font-semibold border-b border-slate-200"
                      style={{ color: COURSE_COLORS[c] || "#94a3b8" }}>
                      {c.slice(0, 3)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {playDateData.map((row, i) => {
                  const isWknd = isWeekend(row.weekday);
                  return (
                    <tr key={i} className={`border-b border-slate-100 ${isWknd ? "bg-indigo-50/30" : ""}`}>
                      <td className="px-3 py-2 font-medium text-slate-700">
                        {row.date} <span className={`${isWknd ? "text-indigo-500" : "text-slate-400"}`}>
                          {row.weekday?.slice(0,1)}
                        </span>
                      </td>
                      {COURSES.map(c => (
                        <td key={c} className="text-right px-2 py-2 text-slate-600">
                          {row[c] ?? "—"}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 3 — 소진 패턴 매트릭스
// ─────────────────────────────────────────────────────────
function Tab3() {
  const { weekdayMode } = useContext(SettingsContext);
  const d = RAW_DATA.tab3;

  const WEEKDAYS = ["월요일","화요일","수요일","목요일","금요일","토요일","일요일"];
  const PARTS = ["1부","2부"];

  // 히트맵 데이터 정리
  const heatmapGrid = useMemo(() => {
    const grid = {};
    for (const row of d.heatmap || []) {
      grid[`${row.weekday}_${row.part}`] = row;
    }
    return grid;
  }, [d]);

  function getCell(weekday, part) {
    return heatmapGrid[`${weekday}_${part}`];
  }

  function heatColor(rate) {
    if (rate == null) return "#f8fafc";
    if (rate >= 70) return "#10B981";
    if (rate >= 50) return "#6EE7B7";
    if (rate >= 30) return "#FCD34D";
    if (rate >= 10) return "#FCA5A5";
    return "#FEE2E2";
  }

  // 현재 잔여 분포
  const distData = useMemo(() => {
    const grouped = groupBy(d.today_distribution || [], r => r.part_type);
    return PARTS.map(part => {
      const rows = grouped[part] || [];
      const entry = { part };
      for (const r of rows) entry[r.weekday_type] = r.slots;
      return entry;
    });
  }, [d]);

  return (
    <div className="space-y-6">
      {d.data_days < 2 && (
        <DataNote text="소진 패턴은 2일+ 데이터가 필요합니다. 현재는 오늘 잔여 분포만 표시됩니다." />
      )}

      {/* 소진 히트맵 */}
      {d.heatmap?.length > 0 && (
        <div>
          <SectionHeader title="🔥 소진율 히트맵 (전일→금일)" sub="요일 × 파트별 슬롯 소진율" />
          <div className="overflow-x-auto">
            <table className="border-collapse">
              <thead>
                <tr>
                  <th className="w-12 text-xs text-slate-400 p-2"></th>
                  {WEEKDAYS.map((w, i) => (
                    <th key={w} className={`text-xs p-2 font-semibold
                      ${i >= 5 ? "text-indigo-500" : "text-slate-500"}
                      ${i === 5 ? "border-l-2 border-indigo-200" : ""}`}>
                      {w.slice(0,1)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PARTS.map(part => (
                  <tr key={part}>
                    <td className="text-xs text-slate-500 p-2 font-medium">{part}</td>
                    {WEEKDAYS.map((wd, i) => {
                      const cell = getCell(wd, part);
                      const rate = cell?.consume_rate;
                      return (
                        <td key={wd} className={`text-center p-1 ${i === 5 ? "border-l-2 border-indigo-200" : ""}`}>
                          <div className="w-14 h-12 rounded-lg flex flex-col items-center justify-center text-xs font-bold"
                            style={{ background: heatColor(rate), color: rate != null && rate >= 50 ? "#fff" : "#374151" }}>
                            {rate != null ? `${rate}%` : "—"}
                            {cell?.total && <span className="text-[10px] opacity-70 mt-0.5">{cell.total}건</span>}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-3 mt-3 text-xs text-slate-500">
            <span>소진율:</span>
            {[["≥70%","#10B981"],["50~69%","#6EE7B7"],["30~49%","#FCD34D"],["10~29%","#FCA5A5"],["<10%","#FEE2E2"]].map(([label,c]) => (
              <div key={label} className="flex items-center gap-1">
                <span className="w-3 h-3 rounded" style={{ background: c }} />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 골프장별 소진율 */}
      {d.course_patterns?.length > 0 && (
        <div>
          <SectionHeader title="🏌️ 골프장별 소진율" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {d.course_patterns.map((cp, i) => {
              const color = COURSE_COLORS[cp.course_name] || "#94a3b8";
              return (
                <div key={i} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                    <span className="text-sm font-bold text-slate-700">{cp.course_name}</span>
                  </div>
                  <div className="text-2xl font-bold mb-1" style={{ color }}>
                    {cp.consume_rate}%
                  </div>
                  <p className="text-xs text-slate-400">{cp.consumed}/{cp.total} 소진</p>
                  <div className="h-1.5 bg-slate-100 rounded-full mt-2 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${cp.consume_rate}%`, background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 오늘 잔여 분포 */}
      <div>
        <SectionHeader title="📊 현재 잔여 슬롯 분포 (오늘 수집)" sub="요일 × 파트별 잔여 슬롯 수" />
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={d.today_distribution || []} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="weekday_type" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="slots" name="잔여슬롯" fill="#6366F1" radius={[4,4,0,0]} />
            <Bar dataKey="promo_slots" name="특가" fill="#F59E0B" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 4 — 가격 흐름 분석
// ─────────────────────────────────────────────────────────
function Tab4() {
  const { baseCourse, weekdayMode } = useContext(SettingsContext);
  const d = RAW_DATA.tab4;
  const [activeView, setActiveView] = useState("trend");

  // D-day 트렌드 데이터
  const trendData = useMemo(() => {
    let rows = d.dday_trend || [];
    if (weekdayMode === "평일") rows = rows.filter(r => !isWeekend(r.weekday_type));
    if (weekdayMode === "주말") rows = rows.filter(r => isWeekend(r.weekday_type));

    const byCourse = groupBy(rows, r => r.course_name);
    const ddays = [...new Set(rows.map(r => r.d_day))].sort((a, b) => a - b);
    return ddays.map(d => {
      const entry = { d_day: d };
      for (const [cn, crows] of Object.entries(byCourse)) {
        const row = crows.find(r => r.d_day === d);
        if (row) entry[cn] = Math.round(row.avg_price);
      }
      return entry;
    });
  }, [d, weekdayMode]);

  // 히스토그램
  const histData = useMemo(() => {
    return (d.histogram || []).map(r => ({
      ...r,
      label: fmt(r.price_bucket),
    }));
  }, [d]);

  return (
    <div className="space-y-6">
      {/* 뷰 토글 */}
      <div className="flex gap-2">
        {["trend","scatter","histogram"].map(v => (
          <button key={v} onClick={() => setActiveView(v)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all border
              ${activeView === v ? "bg-slate-800 text-white border-slate-800" : "text-slate-600 border-slate-200 hover:bg-slate-50"}`}>
            {v === "trend" ? "D-day 트렌드" : v === "scatter" ? "가격 산개도" : "가격 히스토그램"}
          </button>
        ))}
        <WeekdayToggle value={weekdayMode} onChange={v => {}} />
      </div>

      {activeView === "trend" && (
        <div>
          <SectionHeader title="📈 D-day별 평균가 추이" sub="경기일까지 남은 일수에 따른 가격 변화" />
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="d_day" reversed tick={{ fontSize: 11 }} label={{ value: "D-day", position: "insideBottomRight", offset: -10, fontSize: 11 }} />
              <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} formatter={(v, n) => [fmt(v), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {COURSES.map(cn => {
                const color = COURSE_COLORS[cn] || "#94a3b8";
                const isBase = baseCourse === cn;
                return (
                  <Line key={cn} type="monotone" dataKey={cn} stroke={color}
                    strokeWidth={isBase ? 3 : 1.5}
                    strokeOpacity={baseCourse && !isBase ? 0.35 : 1}
                    dot={false} connectNulls />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {activeView === "scatter" && (
        <div>
          <SectionHeader title="⚡ 가격 × D-day 산개도" sub="가격과 잔여 기간의 분포" />
          <ResponsiveContainer width="100%" height={360}>
            <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="price_krw" type="number" name="가격"
                tickFormatter={v => fmt(v)} tick={{ fontSize: 10 }}
                label={{ value: "가격", position: "insideBottomRight", offset: -10, fontSize: 11 }} />
              <YAxis dataKey="d_day" type="number" name="D-day" tick={{ fontSize: 10 }}
                label={{ value: "D-day", angle: -90, position: "insideLeft", fontSize: 11 }} />
              <Tooltip cursor={{ strokeDasharray: "3 3" }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0]?.payload;
                  return (
                    <div className="bg-white border border-slate-200 rounded-lg shadow p-2 text-xs">
                      <p className="font-semibold" style={{ color: COURSE_COLORS[p?.course_name] }}>{p?.course_name}</p>
                      <p>가격: {fmt(p?.price_krw)}</p>
                      <p>D-day: {p?.d_day}</p>
                      <p>{p?.promo_flag ? "🏷️ 특가" : "정가"} | {p?.part_type}</p>
                    </div>
                  );
                }} />
              {COURSES.map(cn => {
                const color = COURSE_COLORS[cn] || "#94a3b8";
                const isBase = baseCourse === cn;
                const dots = (d.scatter || []).filter(r => r.course_name === cn);
                return (
                  <Scatter key={cn} name={cn} data={dots}
                    fill={color} opacity={baseCourse && !isBase ? 0.2 : 0.7} />
                );
              })}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}

      {activeView === "histogram" && (
        <div>
          <SectionHeader title="📊 가격대별 슬롯 분포" sub="현재 활성 슬롯의 가격대" />
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={histData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} angle={-45} textAnchor="end" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="non_promo" name="정가" stackId="a" fill="#6366F1" radius={[0,0,0,0]} />
              <Bar dataKey="promo" name="특가" stackId="a" fill="#F59E0B" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 가격 이벤트 요약 */}
      {d.price_events?.length > 0 && (
        <div>
          <SectionHeader title="📋 가격 변경 이벤트" />
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50">
                  {["골프장","유형","서브코스","경기일","변경전","변경후","변동%"].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-slate-500 font-semibold border-b border-slate-200">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.price_events.slice(0, 20).map((ev, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-3 py-2"><CourseBadge course={ev.course_name} /></td>
                    <td className="px-3 py-2">
                      <span className={`text-xs font-semibold px-1.5 py-0.5 rounded
                        ${ev.event_type === "인하" ? "bg-blue-100 text-blue-700" : ev.event_type === "인상" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{ev.course_sub?.replace(/\(.*?\)/,"")}</td>
                    <td className="px-3 py-2 text-slate-600">{ev.play_date?.slice(5)}</td>
                    <td className="px-3 py-2 text-slate-500">{fmt(ev.old_price_krw)}</td>
                    <td className="px-3 py-2 font-medium text-slate-700">{fmt(ev.new_price_krw)}</td>
                    <td className={`px-3 py-2 font-semibold ${(ev.delta_pct||0) < 0 ? "text-blue-600" : "text-red-600"}`}>
                      {ev.delta_pct?.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 5A — 할인 반응 분석
// ─────────────────────────────────────────────────────────
function Tab5A() {
  const { baseCourse } = useContext(SettingsContext);
  const d = RAW_DATA.tab5a;

  const discountByDepth = useMemo(() => {
    const buckets = [0,5,10,15,20,25,30,40,50];
    return buckets.map((b, i) => {
      const next = buckets[i+1] || 100;
      const events = (d.discount_events || []).filter(ev =>
        ev.discount_pct >= b && ev.discount_pct < next);
      return { range: `${b}~${next}%`, count: events.length, b };
    }).filter(x => x.count > 0);
  }, [d]);

  return (
    <div className="space-y-6">
      <DataNote text={d.data_limitation || "2일 데이터 — Lift/증분 계산은 30일+ 축적 후 가능"} />

      {/* 골프장별 할인 요약 */}
      <div>
        <SectionHeader title="🏷️ 골프장별 할인 현황" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(d.course_summary || []).map((r, i) => {
            const color = COURSE_COLORS[r.course_name] || "#94a3b8";
            const isBase = baseCourse === r.course_name;
            return (
              <div key={i} className={`bg-white rounded-xl border p-4 shadow-sm ${isBase ? "ring-2" : "border-slate-200"}`}
                style={isBase ? { ringColor: color } : {}}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                  <span className="text-sm font-bold text-slate-700">{r.course_name}</span>
                </div>
                <div className="text-2xl font-bold text-slate-800 mb-1">{r.event_count}</div>
                <p className="text-xs text-slate-500">건 (평균 {r.avg_discount_pct?.toFixed(1)}% 인하)</p>
                <p className="text-xs text-slate-400 mt-1">최대 {r.max_discount_pct?.toFixed(1)}% 인하</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* 할인 깊이 분포 */}
      <div>
        <SectionHeader title="📊 할인 깊이 분포" sub="이벤트별 할인율 구간 분포" />
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={discountByDepth} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="range" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="count" name="이벤트 수" radius={[4,4,0,0]}>
              {discountByDepth.map((entry, i) => (
                <Cell key={i} fill={entry.b >= 20 ? "#EF4444" : entry.b >= 10 ? "#F59E0B" : "#6366F1"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* D-day별 할인 vs 정가 비교 */}
      {d.dday_comparison?.length > 0 && (
        <div>
          <SectionHeader title="📈 D-day별 할인/정가 가격 비교" />
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={d.dday_comparison} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="d_day" reversed tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} formatter={(v, n) => [fmt(v), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="avg_non_promo" name="정가 평균" stroke="#6366F1" strokeWidth={2} dot={false} connectNulls />
              <Line type="monotone" dataKey="avg_promo" name="특가 평균" stroke="#F59E0B" strokeWidth={2} strokeDasharray="5 3" dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 할인 이벤트 상세 */}
      <div>
        <SectionHeader title="📋 할인 이벤트 상세" sub={`총 ${d.discount_events?.length || 0}건`} />
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50">
                {["골프장","유형","서브코스","경기일","전","후","할인율","D-day"].map(h => (
                  <th key={h} className="text-left px-3 py-2 text-slate-500 font-semibold border-b border-slate-200">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(d.discount_events || []).slice(0, 20).map((ev, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2"><CourseBadge course={ev.course_name} /></td>
                  <td className="px-3 py-2 text-slate-600">{ev.event_type}</td>
                  <td className="px-3 py-2 text-slate-600">{ev.course_sub?.replace(/\(.*?\)/,"")}</td>
                  <td className="px-3 py-2 text-slate-600">{ev.play_date?.slice(5)}</td>
                  <td className="px-3 py-2 text-slate-500">{fmt(ev.old_price_krw)}</td>
                  <td className="px-3 py-2 font-medium text-blue-700">{fmt(ev.new_price_krw)}</td>
                  <td className="px-3 py-2 font-semibold text-blue-600">
                    -{ev.discount_pct?.toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 text-slate-500">D-{ev.play_date ? "?" : "?"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 5B — 수익 구조 분석
// ─────────────────────────────────────────────────────────
function Tab5B() {
  const { baseCourse, weekdayMode } = useContext(SettingsContext);
  const d = RAW_DATA.tab5b;

  const yieldHistData = useMemo(() => {
    return (d.yield_histogram || []).map(r => ({
      ...r,
      label: r.yield_bucket?.toFixed(1),
    }));
  }, [d]);

  function yieldColor(y) {
    if (y >= 1.05) return "#10B981";
    if (y >= 0.95) return "#6366F1";
    if (y >= 0.80) return "#F59E0B";
    return "#EF4444";
  }

  return (
    <div className="space-y-6">
      <DataNote text="Yield = 실제 잔여 가격 / 세그먼트 기대가격(비할인 중앙값). 1.0 이상 = 프리미엄 잔여, 미만 = 할인 잔여." />

      {/* 골프장별 Yield 요약 */}
      <div>
        <SectionHeader title="⚖️ 골프장별 Yield 요약" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(d.course_summary || []).map((r, i) => {
            const color = COURSE_COLORS[r.course_name] || "#94a3b8";
            const isBase = baseCourse === r.course_name;
            const avgY = r.weekday_avg_yield ?? r.weekend_avg_yield;
            return (
              <div key={i} className={`bg-white rounded-xl border p-4 shadow-sm ${isBase ? "ring-2" : "border-slate-200"}`}
                style={isBase ? { ringColor: color } : {}}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                  <span className="text-xs font-bold text-slate-700">{r.course_name}</span>
                </div>
                {avgY != null && (
                  <div className="text-2xl font-bold mb-1" style={{ color: yieldColor(avgY) }}>
                    {avgY.toFixed(2)}
                  </div>
                )}
                <div className="space-y-1 text-xs text-slate-500">
                  {r.weekday_avg_yield != null && (
                    <div className="flex justify-between">
                      <span>평일</span>
                      <span className="font-semibold" style={{ color: yieldColor(r.weekday_avg_yield) }}>
                        {r.weekday_avg_yield.toFixed(2)}
                      </span>
                    </div>
                  )}
                  {r.weekend_avg_yield != null && (
                    <div className="flex justify-between">
                      <span>주말</span>
                      <span className="font-semibold" style={{ color: yieldColor(r.weekend_avg_yield) }}>
                        {r.weekend_avg_yield.toFixed(2)}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>특가비율</span>
                    <span>{r.promo_ratio_weekday?.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Yield 히스토그램 */}
      {yieldHistData.length > 0 && (
        <div>
          <SectionHeader title="📊 Yield 분포" sub="전체 잔여 슬롯의 Yield 분포" />
          <div className="mb-2 flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" /> Yield≥1.05 (프리미엄)</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-indigo-500" /> 0.95~1.05 (정상)</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-400" /> 0.80~0.95 (할인)</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-400" /> {'<'}0.80 (대폭할인)</span>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={yieldHistData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine x="1.0" stroke="#6366F1" strokeDasharray="4 2" />
              <Bar dataKey="non_promo" name="정가" stackId="a" fill="#6366F1" />
              <Bar dataKey="promo" name="특가" stackId="a" fill="#F59E0B" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 6 — 코스 × 서브코스 현황
// ─────────────────────────────────────────────────────────
function Tab6() {
  const { baseCourse } = useContext(SettingsContext);
  const d = RAW_DATA.tab6;

  const byCourseName = useMemo(() => {
    return groupBy(d.subcourse_rows || [], r => r.course_name);
  }, [d]);

  return (
    <div className="space-y-6">
      {/* 골프장 카드 */}
      <div>
        <SectionHeader title="🏌️ 골프장별 서브코스 현황" />
        <div className="grid sm:grid-cols-2 gap-4">
          {COURSES.map(cn => {
            const rows = byCourseName[cn] || [];
            const color = COURSE_COLORS[cn] || "#94a3b8";
            const isBase = baseCourse === cn;
            const summary = d.course_summary?.[cn];
            if (!rows.length) return null;

            return (
              <div key={cn} className={`bg-white rounded-xl border shadow-sm overflow-hidden
                ${isBase ? "ring-2" : "border-slate-200"}`}
                style={isBase ? { ringColor: color } : {}}>
                <div className="px-4 py-3 flex items-center justify-between"
                  style={{ background: color + "18", borderBottom: `2px solid ${color}` }}>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ background: color }} />
                    <span className="font-bold text-slate-800">{cn}</span>
                    {isBase && <span className="text-xs text-white rounded-full px-2 py-0.5 font-medium" style={{ background: color }}>우리</span>}
                  </div>
                  <div className="text-xs text-slate-500">
                    총 {summary?.total_slots || rows.reduce((s,r) => s+r.slots, 0)}슬롯
                  </div>
                </div>
                <div className="p-4 space-y-2">
                  {rows.map((r, i) => {
                    const barColor = r.member_label === "회원제" ? "#8B5CF6" : color;
                    const maxSlots = Math.max(...rows.map(x => x.slots));
                    const barPct = maxSlots > 0 ? (r.slots / maxSlots) * 100 : 0;
                    return (
                      <div key={i}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-slate-700">{r.sub_display}</span>
                            {r.member_label && (
                              <span className={`text-xs px-1.5 py-0.5 rounded font-medium
                                ${r.member_label === "회원제" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>
                                {r.member_label}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-slate-600">
                            <span className="font-semibold">{r.slots}슬롯</span>
                            <span className="text-slate-400">{fmt(r.avg_price)}</span>
                            {r.promo_ratio > 0 && (
                              <span className="text-amber-600">특가{r.promo_ratio}%</span>
                            )}
                            {r.slot_delta != null && (
                              <span className={r.slot_delta > 0 ? "text-blue-500" : r.slot_delta < 0 ? "text-red-500" : "text-slate-400"}>
                                {sign(r.slot_delta)}{Math.abs(r.slot_delta)}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all"
                            style={{ width: `${barPct}%`, background: barColor }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 서브코스 비교 테이블 */}
      <div>
        <SectionHeader title="📋 서브코스 전체 비교" />
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50">
                {["골프장","서브코스","구분","잔여","평균가","최저가","특가율","전일대비","가격변화"].map(h => (
                  <th key={h} className="text-left px-3 py-2 text-slate-500 font-semibold border-b border-slate-200">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(d.subcourse_rows || []).map((r, i) => {
                const color = COURSE_COLORS[r.course_name] || "#94a3b8";
                const isBase = baseCourse === r.course_name;
                return (
                  <tr key={i} className={`border-b border-slate-100 hover:bg-slate-50 ${isBase ? "bg-indigo-50/30" : ""}`}>
                    <td className="px-3 py-2">
                      <span className="font-medium text-xs" style={{ color }}>
                        {r.course_name}
                        {isBase && " ★"}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-700 font-medium">{r.sub_display}</td>
                    <td className="px-3 py-2">
                      {r.member_label && (
                        <span className={`text-xs px-1.5 py-0.5 rounded
                          ${r.member_label === "회원제" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>
                          {r.member_label}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-semibold text-slate-800">{r.slots}</td>
                    <td className="px-3 py-2 text-slate-700">{fmt(r.avg_price)}</td>
                    <td className="px-3 py-2 text-slate-500">{fmt(r.min_price)}</td>
                    <td className="px-3 py-2">
                      {r.promo_ratio > 0 ? (
                        <span className="text-amber-600 font-medium">{r.promo_ratio}%</span>
                      ) : "—"}
                    </td>
                    <td className="px-3 py-2">
                      {r.slot_delta != null ? (
                        <span className={r.slot_delta > 0 ? "text-blue-600" : r.slot_delta < 0 ? "text-red-600" : "text-slate-400"}>
                          {sign(r.slot_delta)}{Math.abs(r.slot_delta)}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-3 py-2">
                      {r.price_delta != null ? (
                        <span className={r.price_delta > 0 ? "text-red-500" : r.price_delta < 0 ? "text-blue-500" : "text-slate-400"}>
                          {sign(r.price_delta)}{fmt(Math.abs(r.price_delta))}
                        </span>
                      ) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 7 — AI 진단
// ─────────────────────────────────────────────────────────
function Tab7() {
  const { baseCourse } = useContext(SettingsContext);
  const d = RAW_DATA.tab7;

  const RULE_LABELS = {
    A: "가격 유지 여력", B: "할인 의존", C: "할인 효과 확인", D: "할인 무효",
    E: "프리미엄 구간", F: "특가 의존", G: "공정 비교", H: "회원제 오픈",
    I: "날씨 리스크", J: "취소 리스크", OK: "정상",
  };

  const RULE_ICONS = {
    A: "🔒", B: "⚠️", C: "✅", D: "❌", E: "🚀", F: "🏷️",
    G: "⚖️", H: "🔓", I: "⛈", J: "↩️", OK: "✅",
  };

  const sorted = useMemo(() => {
    const diags = d.diagnostics || [];
    // 기준 골프장 최상단
    if (!baseCourse) return diags;
    const base = diags.find(x => x.course_name === baseCourse);
    const others = diags.filter(x => x.course_name !== baseCourse);
    return base ? [base, ...others] : diags;
  }, [d, baseCourse]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <SectionHeader title="🤖 AI 진단 — 룰 엔진" />
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-400">활성 룰: {(d.rules_applicable || []).join(", ")}</p>
          <p className="text-xs text-slate-300">대기 중: {(d.rules_pending || []).join(", ")}</p>
        </div>
      </div>
      {d.data_note && <DataNote text={d.data_note} />}

      <div className="space-y-4">
        {sorted.map((course_diag, ci) => {
          const color = COURSE_COLORS[course_diag.course_name] || "#94a3b8";
          const isBase = baseCourse === course_diag.course_name;
          const findings = course_diag.findings || [];
          const hasIssues = findings.some(f => f.rule !== "OK");

          return (
            <div key={ci} className={`bg-white rounded-xl border shadow-sm overflow-hidden
              ${isBase ? "ring-2" : "border-slate-200"}`}
              style={isBase ? { ringColor: color } : {}}>
              {/* 헤더 */}
              <div className="px-4 py-3 flex items-center justify-between"
                style={{ background: color + "12", borderBottom: `1.5px solid ${color}33` }}>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ background: color }} />
                  <span className="font-bold text-slate-800">{course_diag.course_name}</span>
                  {isBase && (
                    <span className="text-xs px-2 py-0.5 rounded-full text-white font-medium" style={{ background: color }}>
                      우리
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {hasIssues ? (
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                      {course_diag.finding_count}건 감지
                    </span>
                  ) : (
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                      정상
                    </span>
                  )}
                </div>
              </div>

              {/* 진단 결과 */}
              <div className="divide-y divide-slate-100">
                {findings.map((f, fi) => {
                  const cfg = SEVERITY_CONFIG[f.severity] || SEVERITY_CONFIG.info;
                  return (
                    <div key={fi} className={`px-4 py-3 ${cfg.bg}`}>
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 mt-0.5">
                          <span className="text-lg">{RULE_ICONS[f.rule] || "📌"}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                              룰 {f.rule}
                            </span>
                            <span className="text-sm font-semibold text-slate-800">{f.title}</span>
                            <span className={`text-xs font-medium ${cfg.color}`}>[{cfg.label}]</span>
                          </div>
                          <p className="text-xs text-slate-600 mb-1">{f.desc}</p>
                          {f.action !== "—" && (
                            <div className="flex items-center gap-1">
                              <span className="text-xs text-slate-400">→</span>
                              <span className="text-xs font-medium text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
                                {f.action}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* 룰 범례 */}
      <div className="bg-slate-50 rounded-xl p-4">
        <p className="text-xs font-semibold text-slate-600 mb-3">룰 목록</p>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {Object.entries(RULE_LABELS).filter(([k]) => k !== "OK").map(([rule, label]) => {
            const isActive = (d.rules_applicable || []).includes(rule);
            return (
              <div key={rule} className={`flex items-center gap-1.5 text-xs p-2 rounded-lg
                ${isActive ? "bg-white border border-slate-200 text-slate-700" : "text-slate-300"}`}>
                <span>{RULE_ICONS[rule]}</span>
                <span><strong>{rule}</strong>: {label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// TAB 8 — 티타임 상세 (fetch-based)
// ─────────────────────────────────────────────────────────
function Tab8() {
  const { baseCourse } = useContext(SettingsContext);
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);

  const [filterCourse, setFilterCourse] = useState("");
  const [filterPromo, setFilterPromo] = useState("");
  const [filterWeekday, setFilterWeekday] = useState("");
  const [filterPart, setFilterPart] = useState("");
  const [filterSearch, setFilterSearch] = useState("");
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState("play_date");
  const [sortDir, setSortDir] = useState(1);
  const PAGE_SIZE = 50;

  // 데이터 로드
  const loadData = useCallback(() => {
    if (loaded || loading) return;
    setLoading(true);
    fetch("golf_tab8.json")
      .then(r => { if (!r.ok) throw new Error("파일 없음"); return r.json(); })
      .then(data => {
        setSlots(data.slots || []);
        setLoaded(true);
        setLoading(false);
      })
      .catch(() => {
        // fallback: 데이터 없으면 빈 배열
        setSlots([]);
        setLoaded(true);
        setLoading(false);
        setError("golf_tab8.json 파일을 찾을 수 없습니다. build_dashboard.py를 실행하세요.");
      });
  }, [loaded, loading]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filtered = useMemo(() => {
    let data = slots;
    if (filterCourse) data = data.filter(r => r.course_name === filterCourse);
    if (filterPromo === "1") data = data.filter(r => r.promo_flag);
    if (filterPromo === "0") data = data.filter(r => !r.promo_flag);
    if (filterWeekday) data = data.filter(r => r.weekday_type?.includes(filterWeekday));
    if (filterPart) data = data.filter(r => r.part_type === filterPart);
    if (filterSearch) {
      const q = filterSearch.toLowerCase();
      data = data.filter(r =>
        r.course_name?.toLowerCase().includes(q) ||
        r.course_sub?.toLowerCase().includes(q) ||
        r.play_date?.includes(q) ||
        r.tee_time?.includes(q)
      );
    }
    // 정렬
    data = [...data].sort((a, b) => {
      const av = a[sortBy] ?? "";
      const bv = b[sortBy] ?? "";
      return av < bv ? -sortDir : av > bv ? sortDir : 0;
    });
    return data;
  }, [slots, filterCourse, filterPromo, filterWeekday, filterPart, filterSearch, sortBy, sortDir]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const pageData = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function toggleSort(col) {
    if (sortBy === col) setSortDir(d => -d);
    else { setSortBy(col); setSortDir(1); }
    setPage(0);
  }

  function SortTh({ col, children }) {
    const active = sortBy === col;
    return (
      <th className={`text-left px-3 py-2 text-xs font-semibold border-b border-slate-200 cursor-pointer select-none
        ${active ? "text-indigo-600 bg-indigo-50" : "text-slate-500 bg-slate-50"}`}
        onClick={() => toggleSort(col)}>
        {children} {active ? (sortDir > 0 ? "↑" : "↓") : ""}
      </th>
    );
  }

  const courses = [...new Set(slots.map(r => r.course_name))].sort();

  // KPI 요약
  const kpiPromo = filtered.filter(r => r.promo_flag).length;
  const kpiAvgPrice = filtered.length > 0
    ? Math.round(filtered.reduce((s, r) => s + (r.price_krw || 0), 0) / filtered.length) : 0;

  return (
    <div className="space-y-4">
      {/* 로드 버튼 */}
      {!loaded && !loading && (
        <div className="text-center py-12">
          <p className="text-slate-500 mb-4 text-sm">전체 {slots.length ? slots.length.toLocaleString() : "8,015"}개 슬롯 데이터 준비됨</p>
          <button onClick={loadData}
            className="px-6 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors">
            📂 전체 데이터 로드
          </button>
        </div>
      )}
      {loading && (
        <div className="text-center py-12">
          <p className="text-slate-400 text-sm animate-pulse">데이터 로드 중...</p>
        </div>
      )}
      {error && <DataNote text={error} />}

      {loaded && (
        <>
          {/* KPI 요약 */}
          <div className="grid grid-cols-4 gap-3">
            <KpiCard label="전체 슬롯" value={filtered.length.toLocaleString()} color="#6366F1" />
            <KpiCard label="평균가" value={fmt(kpiAvgPrice)} color="#0EA5E9" />
            <KpiCard label="특가 슬롯" value={kpiPromo.toLocaleString()} sub={pct(kpiPromo, filtered.length)} color="#F59E0B" />
            <KpiCard label="골프장" value={courses.length} color="#10B981" />
          </div>

          {/* 필터 */}
          <div className="flex flex-wrap gap-2">
            <select value={filterCourse} onChange={e => { setFilterCourse(e.target.value); setPage(0); }}
              className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700">
              <option value="">전체 골프장</option>
              {courses.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={filterPromo} onChange={e => { setFilterPromo(e.target.value); setPage(0); }}
              className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700">
              <option value="">할인 전체</option>
              <option value="1">특가만</option>
              <option value="0">정가만</option>
            </select>
            <select value={filterWeekday} onChange={e => { setFilterWeekday(e.target.value); setPage(0); }}
              className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700">
              <option value="">요일 전체</option>
              {["월요일","화요일","수요일","목요일","금요일","토요일","일요일"].map(w => (
                <option key={w} value={w.slice(0,1)}>{w}</option>
              ))}
            </select>
            <select value={filterPart} onChange={e => { setFilterPart(e.target.value); setPage(0); }}
              className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700">
              <option value="">파트 전체</option>
              <option value="1부">1부</option>
              <option value="2부">2부</option>
            </select>
            <input value={filterSearch} onChange={e => { setFilterSearch(e.target.value); setPage(0); }}
              placeholder="골프장/날짜/시간 검색..."
              className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 w-48" />
            <button onClick={() => {
              setFilterCourse(""); setFilterPromo(""); setFilterWeekday("");
              setFilterPart(""); setFilterSearch(""); setPage(0);
            }} className="text-xs text-slate-500 px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50">
              초기화
            </button>
          </div>

          {/* 테이블 */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr>
                  <SortTh col="course_name">골프장</SortTh>
                  <SortTh col="course_sub">서브코스</SortTh>
                  <SortTh col="play_date">경기일</SortTh>
                  <SortTh col="tee_time">티타임</SortTh>
                  <SortTh col="price_krw">가격</SortTh>
                  <SortTh col="promo_flag">할인</SortTh>
                  <SortTh col="d_day">D-day</SortTh>
                  <SortTh col="weekday_type">요일</SortTh>
                  <SortTh col="part_type">파트</SortTh>
                  <th className="text-left px-3 py-2 text-xs font-semibold border-b border-slate-200 bg-slate-50 text-slate-500">프로모</th>
                </tr>
              </thead>
              <tbody>
                {pageData.map((r, i) => {
                  const color = COURSE_COLORS[r.course_name] || "#94a3b8";
                  const isBase = baseCourse === r.course_name;
                  const isWknd = isWeekend(r.weekday_type);
                  return (
                    <tr key={i} className={`border-b border-slate-100 hover:bg-slate-50 transition-colors
                      ${isBase ? "bg-indigo-50/30" : ""}`}>
                      <td className="px-3 py-2">
                        <span className="font-medium" style={{ color }}>
                          {r.course_name}{isBase && " ★"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-600">{r.sub_display || r.course_sub?.replace(/\(.*?\)/,"")}</td>
                      <td className="px-3 py-2 text-slate-700 font-medium">{r.play_date}</td>
                      <td className="px-3 py-2 text-slate-600 font-mono">{r.tee_time}</td>
                      <td className="px-3 py-2 font-semibold text-slate-800">{fmt(r.price_krw)}</td>
                      <td className="px-3 py-2">
                        {r.promo_flag ? (
                          <span className="bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium">특가</span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`font-medium ${r.d_day <= 3 ? "text-red-500" : r.d_day <= 7 ? "text-amber-600" : "text-slate-600"}`}>
                          D-{r.d_day}
                        </span>
                      </td>
                      <td className={`px-3 py-2 ${isWknd ? "text-indigo-600 font-medium" : "text-slate-500"}`}>
                        {r.weekday_type?.slice(0,1)}
                      </td>
                      <td className="px-3 py-2 text-slate-500">{r.part_type}</td>
                      <td className="px-3 py-2 text-slate-400">{r.promo_text || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-500">
                {(page * PAGE_SIZE + 1).toLocaleString()}~{Math.min((page+1)*PAGE_SIZE, filtered.length).toLocaleString()} / {filtered.length.toLocaleString()}건
              </p>
              <div className="flex gap-1">
                <button onClick={() => setPage(0)} disabled={page === 0}
                  className="px-2 py-1 text-xs border border-slate-200 rounded disabled:opacity-30 hover:bg-slate-50">«</button>
                <button onClick={() => setPage(p => Math.max(0, p-1))} disabled={page === 0}
                  className="px-2 py-1 text-xs border border-slate-200 rounded disabled:opacity-30 hover:bg-slate-50">‹</button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const p = Math.max(0, Math.min(page - 2, totalPages - 5)) + i;
                  return (
                    <button key={p} onClick={() => setPage(p)}
                      className={`px-2 py-1 text-xs border rounded ${p === page ? "bg-indigo-600 text-white border-indigo-600" : "border-slate-200 hover:bg-slate-50"}`}>
                      {p+1}
                    </button>
                  );
                })}
                <button onClick={() => setPage(p => Math.min(totalPages-1, p+1))} disabled={page === totalPages-1}
                  className="px-2 py-1 text-xs border border-slate-200 rounded disabled:opacity-30 hover:bg-slate-50">›</button>
                <button onClick={() => setPage(totalPages-1)} disabled={page === totalPages-1}
                  className="px-2 py-1 text-xs border border-slate-200 rounded disabled:opacity-30 hover:bg-slate-50">»</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// 메인 앱
// ─────────────────────────────────────────────────────────
const TABS = [
  { id: "tab1", label: "브리핑", icon: "📋" },
  { id: "tab2", label: "생애주기", icon: "🔄" },
  { id: "tab3", label: "소진패턴", icon: "🔥" },
  { id: "tab4", label: "가격흐름", icon: "📈" },
  { id: "tab5a", label: "할인반응", icon: "🏷️" },
  { id: "tab5b", label: "수익구조", icon: "⚖️" },
  { id: "tab6", label: "서브코스", icon: "⛳" },
  { id: "tab7", label: "AI진단", icon: "🤖" },
  { id: "tab8", label: "상세", icon: "📊" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("tab1");
  const [showSettings, setShowSettings] = useState(false);
  const [baseCourse, setBaseCourse] = useState("");
  const [weekdayMode, setWeekdayMode] = useState("전체");

  const meta = RAW_DATA.metadata;

  const TabContent = useMemo(() => {
    switch (activeTab) {
      case "tab1": return <Tab1 />;
      case "tab2": return <Tab2 />;
      case "tab3": return <Tab3 />;
      case "tab4": return <Tab4 />;
      case "tab5a": return <Tab5A />;
      case "tab5b": return <Tab5B />;
      case "tab6": return <Tab6 />;
      case "tab7": return <Tab7 />;
      case "tab8": return <Tab8 />;
      default: return <Tab1 />;
    }
  }, [activeTab]);

  return (
    <SettingsContext.Provider value={{ baseCourse, setBaseCourse, weekdayMode, setWeekdayMode }}>
      <div className="min-h-screen bg-slate-100">
        {/* 헤더 */}
        <header style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f172a 100%)" }}
          className="text-white px-6 py-4 shadow-xl">
          <div className="max-w-screen-xl mx-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center text-xl"
                  style={{ background: "rgba(99,102,241,0.3)" }}>
                  ⛳
                </div>
                <div>
                  <h1 className="text-lg font-bold tracking-tight">골프 가격 모니터링</h1>
                  <p className="text-xs text-slate-400">광주·전남 8개 골프장 실시간 분석</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {/* 기준 골프장 표시 */}
                {baseCourse && (
                  <div className="hidden sm:flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: COURSE_COLORS[baseCourse] }} />
                    <span className="text-xs font-medium text-slate-200">{baseCourse}</span>
                  </div>
                )}
                {/* 데이터 시각 */}
                <div className="hidden sm:block text-right">
                  <p className="text-xs text-slate-300">{meta.latest_date} 기준</p>
                  <p className="text-xs text-slate-500">생성: {meta.generated_at}</p>
                </div>
                {/* 평일/주말 토글 */}
                <div className="flex gap-1 bg-white/10 rounded-lg p-1">
                  {["전체","평일","주말"].map(m => (
                    <button key={m} onClick={() => setWeekdayMode(m)}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all
                        ${weekdayMode === m ? "bg-white text-slate-800" : "text-slate-300 hover:text-white"}`}>
                      {m}
                    </button>
                  ))}
                </div>
                {/* 설정 버튼 */}
                <button onClick={() => setShowSettings(true)}
                  className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 rounded-lg px-3 py-1.5 text-xs font-medium transition-all">
                  ⚙️ 설정
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* 탭 바 */}
        <div className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-40">
          <div className="max-w-screen-xl mx-auto">
            <div className="flex overflow-x-auto scrollbar-hide">
              {TABS.map(tab => {
                const isActive = activeTab === tab.id;
                return (
                  <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-all
                      ${isActive
                        ? "border-indigo-600 text-indigo-600 bg-indigo-50/50"
                        : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50"}`}>
                    <span className="text-base">{tab.icon}</span>
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 컨텐츠 */}
        <main className="max-w-screen-xl mx-auto px-4 sm:px-6 py-6">
          {TabContent}
        </main>

        {/* 설정 모달 */}
        {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      </div>
    </SettingsContext.Provider>
  );
}
