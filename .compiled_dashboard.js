const {
  useState,
  useMemo,
  createContext,
  useContext
} = React;
const {
  LineChart,
  Line,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  BarChart,
  ReferenceLine
} = Recharts;

// ─────────────────────────────────────────────────────────
// 데이터 로드 (window.__GOLF_DATA__ 또는 FALLBACK_DATA)
// ─────────────────────────────────────────────────────────
const FALLBACK_DATA = {
  metadata: {
    generated_at: "2026-03-14 23:46",
    latest_date: "2026-03-14",
    prev_date: "2026-03-13",
    courses: ["골드레이크", "광주CC", "르오네뜨", "무등산", "베르힐", "어등산", "푸른솔장성", "해피니스"],
    member_courses: ["골드레이크", "해피니스"]
  },
  tab1: {
    kpi: {
      total_slots_today: 8015,
      total_slots_prev: 3950,
      slot_delta: 4065,
      total_price_changes: 143,
      changes_by_type: {
        인상: 2,
        인하: 125,
        특가부착: 11,
        특가해제: 5
      },
      total_promo_slots: 2012,
      promo_ratio: 25.1
    },
    course_kpi: [{
      course_name: "골드레이크",
      slots: 679,
      avg_price: 137732,
      promo_slots: 3
    }, {
      course_name: "광주CC",
      slots: 565,
      avg_price: 119159,
      promo_slots: 219
    }, {
      course_name: "르오네뜨",
      slots: 559,
      avg_price: 111306,
      promo_slots: 42
    }, {
      course_name: "무등산",
      slots: 621,
      avg_price: 108500,
      promo_slots: 55
    }, {
      course_name: "베르힐",
      slots: 1200,
      avg_price: 95000,
      promo_slots: 80
    }, {
      course_name: "어등산",
      slots: 580,
      avg_price: 112000,
      promo_slots: 30
    }, {
      course_name: "푸른솔장성",
      slots: 490,
      avg_price: 98000,
      promo_slots: 20
    }, {
      course_name: "해피니스",
      slots: 620,
      avg_price: 125000,
      promo_slots: 15
    }],
    prev_course_kpi: {
      골드레이크: {
        course_name: "골드레이크",
        slots: 422,
        avg_price: 134147
      }
    },
    price_changes: {
      인상: [{
        course_name: "무등산",
        play_date: "2026-03-20",
        tee_time: "08:08",
        course_sub: "인왕봉",
        old_price_krw: 115000,
        new_price_krw: 120000,
        delta_price_krw: 5000,
        delta_pct: 4.35,
        competitor_same_day_raises: 1,
        note: "경쟁사 1곳도 동일 시점 인상"
      }],
      인하: [{
        course_name: "광주CC",
        play_date: "2026-03-15",
        tee_time: "08:11",
        course_sub: "섬진",
        old_price_krw: 140000,
        new_price_krw: 135000,
        delta_price_krw: -5000,
        delta_pct: -3.57
      }],
      특가부착: [],
      특가해제: []
    },
    consumption: [{
      course_name: "골드레이크",
      prev_slots: 422,
      today_slots: 679,
      consumed: 420,
      new_open: 17,
      member_open: 330,
      stayed: 2,
      consume_rate: 99.5
    }, {
      course_name: "광주CC",
      prev_slots: 316,
      today_slots: 565,
      consumed: 41,
      new_open: 290,
      member_open: 0,
      stayed: 275,
      consume_rate: 13.0
    }],
    alerts: [{
      level: "warning",
      type: "mass_discount",
      course: "광주CC",
      msg: "대량 인하 감지 — 23건"
    }, {
      level: "warning",
      type: "mass_discount",
      course: "무등산",
      msg: "대량 인하 감지 — 22건"
    }],
    calendar: [{
      play_date: "2026-03-15",
      weekday_type: "일요일",
      slots: 133,
      avg_price: 134981,
      promo_slots: 50,
      d_day: 1
    }, {
      play_date: "2026-03-16",
      weekday_type: "평일",
      slots: 279,
      avg_price: 102659,
      promo_slots: 85,
      d_day: 2
    }, {
      play_date: "2026-03-17",
      weekday_type: "평일",
      slots: 310,
      avg_price: 98000,
      promo_slots: 70,
      d_day: 3
    }, {
      play_date: "2026-03-18",
      weekday_type: "평일",
      slots: 295,
      avg_price: 99000,
      promo_slots: 60,
      d_day: 4
    }, {
      play_date: "2026-03-19",
      weekday_type: "평일",
      slots: 280,
      avg_price: 100000,
      promo_slots: 55,
      d_day: 5
    }, {
      play_date: "2026-03-20",
      weekday_type: "금요일",
      slots: 350,
      avg_price: 118000,
      promo_slots: 40,
      d_day: 6
    }, {
      play_date: "2026-03-21",
      weekday_type: "토요일",
      slots: 420,
      avg_price: 145000,
      promo_slots: 20,
      d_day: 7
    }]
  },
  tab4: {
    dday_trend: [{
      course_name: "골드레이크",
      d_day: 1,
      avg_price: 137143,
      slot_count: 7,
      promo_count: 0,
      weekday_type: "일요일"
    }, {
      course_name: "골드레이크",
      d_day: 3,
      avg_price: 110000,
      slot_count: 20,
      promo_count: 2,
      weekday_type: "평일"
    }],
    scatter: [{
      course_name: "골드레이크",
      price_krw: 120000,
      d_day: 1,
      promo_flag: 0,
      weekday_type: "일요일"
    }],
    histogram: [{
      price_bucket: 80000,
      total: 50,
      promo: 5,
      non_promo: 45
    }],
    price_events: []
  },
  tab6: {
    subcourse_rows: [{
      course_name: "골드레이크",
      course_sub: "밸리(대중제)",
      membership_type: "대중제",
      member_label: "대중제",
      slots: 178,
      avg_price: 125084,
      promo_slots: 1,
      part1: 113,
      part2: 65,
      promo_ratio: 0.6,
      sub_display: "밸리",
      slot_delta: null,
      price_delta: null
    }],
    course_summary: {},
    member_opens_latest: []
  },
  tab8: {
    slots: [{
      course_name: "골드레이크",
      course_sub: "밸리(대중제)",
      sub_display: "밸리",
      membership_type: "대중제",
      play_date: "2026-03-15",
      tee_time: "07:00",
      price_krw: 120000,
      promo_flag: 0,
      promo_text: null,
      pax_condition: "4인 필수",
      part_type: "1부",
      weekday_type: "일요일",
      d_day: 1,
      season: "봄"
    }]
  }
};
const RAW_DATA = typeof window !== 'undefined' && window.__GOLF_DATA__ ? window.__GOLF_DATA__ : FALLBACK_DATA;

// ─────────────────────────────────────────────────────────
// 유틸리티
// ─────────────────────────────────────────────────────────
const COLORS = {
  primary: '#2563EB',
  competitor: '#94A3B8',
  positive: '#16A34A',
  negative: '#DC2626',
  member: '#7C3AED',
  public: '#0891B2',
  warning: '#D97706',
  bg: '#F8FAFC',
  card: '#FFFFFF',
  amber: '#F59E0B'
};
const COURSE_PALETTE = ['#2563EB', '#DC2626', '#16A34A', '#7C3AED', '#D97706', '#0891B2', '#9333EA', '#EA580C'];
function groupBy(arr, keyFn) {
  return (arr || []).reduce((acc, item) => {
    const key = keyFn(item);
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});
}
function formatPrice(price) {
  if (price == null || price === 0) return '-';
  return `${Math.round(price / 1000)}k`;
}
function formatCurrency(value) {
  if (value == null) return '-';
  return `₩${value.toLocaleString('ko-KR')}`;
}
function isWeekend(weekday_type) {
  return weekday_type === '토요일' || weekday_type === '일요일' || weekday_type === '금요일';
}

// ─────────────────────────────────────────────────────────
// Settings Context
// ─────────────────────────────────────────────────────────
const SettingsContext = createContext({
  baseCourse: '',
  competitors: []
});

// ─────────────────────────────────────────────────────────
// Settings Modal
// ─────────────────────────────────────────────────────────
function SettingsModal({
  isOpen,
  onClose,
  onSave
}) {
  const {
    baseCourse,
    competitors
  } = useContext(SettingsContext);
  const [localBase, setLocalBase] = useState(baseCourse);
  const [localComp, setLocalComp] = useState(competitors);
  const allCourses = RAW_DATA.metadata.courses;
  if (!isOpen) return null;
  const toggleCompetitor = course => {
    if (localComp.includes(course)) {
      setLocalComp(localComp.filter(c => c !== course));
    } else {
      setLocalComp([...localComp, course]);
    }
  };
  const handleBaseChange = val => {
    setLocalBase(val);
    setLocalComp(allCourses.filter(c => c !== val));
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl shadow-2xl max-w-md w-full p-6"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-xl font-bold mb-6 text-gray-900"
  }, "\u2699 \uB300\uC2DC\uBCF4\uB4DC \uC124\uC815"), /*#__PURE__*/React.createElement("div", {
    className: "space-y-5"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    className: "block text-sm font-semibold text-gray-700 mb-2"
  }, "\uAE30\uC900 \uACE8\uD504\uC7A5"), /*#__PURE__*/React.createElement("select", {
    value: localBase,
    onChange: e => handleBaseChange(e.target.value),
    className: "w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
  }, allCourses.map(c => /*#__PURE__*/React.createElement("option", {
    key: c,
    value: c
  }, c))), /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mt-1"
  }, "\uC120\uD0DD\uB41C \uACE8\uD504\uC7A5\uC774 \uBAA8\uB4E0 \uBD84\uC11D\uC758 \uAE30\uC900\uC810\uC774 \uB429\uB2C8\uB2E4")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    className: "block text-sm font-semibold text-gray-700 mb-2"
  }, "\uACBD\uC7C1 \uADF8\uB8F9"), /*#__PURE__*/React.createElement("div", {
    className: "space-y-2 max-h-48 overflow-y-auto border border-gray-200 p-3 rounded-lg bg-gray-50"
  }, allCourses.filter(c => c !== localBase).map(course => /*#__PURE__*/React.createElement("label", {
    key: course,
    className: "flex items-center cursor-pointer hover:bg-white p-1 rounded"
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: localComp.includes(course),
    onChange: () => toggleCompetitor(course),
    className: "w-4 h-4 text-blue-600 rounded"
  }), /*#__PURE__*/React.createElement("span", {
    className: "ml-2 text-sm text-gray-700"
  }, course)))))), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-3 mt-7"
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    className: "flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition"
  }, "\uCDE8\uC18C"), /*#__PURE__*/React.createElement("button", {
    onClick: () => {
      onSave(localBase, localComp);
      onClose();
    },
    className: "flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition"
  }, "\uC800\uC7A5"))));
}

// ─────────────────────────────────────────────────────────
// Tab 1: 오늘의 브리핑
// ─────────────────────────────────────────────────────────
function Tab1() {
  const {
    baseCourse,
    competitors
  } = useContext(SettingsContext);
  const data = RAW_DATA.tab1;
  const baseKpi = data.course_kpi.find(k => k.course_name === baseCourse);
  const basePrev = data.prev_course_kpi?.[baseCourse];
  const slotDelta = baseKpi && basePrev ? baseKpi.slots - basePrev.slots : null;
  const priceDelta = baseKpi && basePrev ? baseKpi.avg_price - basePrev.avg_price : null;
  const competitorKpis = useMemo(() => {
    return data.course_kpi.filter(k => competitors.includes(k.course_name));
  }, [competitors]);
  const competitorAvg = useMemo(() => {
    if (competitorKpis.length === 0) return {
      slots: 0,
      avg_price: 0
    };
    return {
      slots: Math.round(competitorKpis.reduce((s, k) => s + k.slots, 0) / competitorKpis.length),
      avg_price: competitorKpis.reduce((s, k) => s + k.avg_price, 0) / competitorKpis.length
    };
  }, [competitorKpis]);
  const raiseChanges = data.price_changes['인상'] || [];
  const dropChanges = data.price_changes['인하'] || [];
  return /*#__PURE__*/React.createElement("div", {
    className: "space-y-6"
  }, raiseChanges.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg flex items-start gap-3"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-2xl"
  }, "\u26A0\uFE0F"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "font-bold text-red-900"
  }, "\uAC00\uACA9 \uC778\uC0C1 \uAC10\uC9C0"), /*#__PURE__*/React.createElement("p", {
    className: "text-sm text-red-800"
  }, raiseChanges.length, "\uAC74\uC758 \uC778\uC0C1 \u2014 \uACBD\uC7C1 \uB3D9\uD5A5 \uD655\uC778 \uD544\uC694"))), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-2 gap-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border-2 border-blue-200 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-blue-600 font-semibold uppercase mb-2"
  }, "\uAE30\uC900 \xB7 ", baseCourse), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-2 gap-3"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500"
  }, "\uC794\uC5EC\uC2AC\uB86F"), /*#__PURE__*/React.createElement("p", {
    className: "text-xl font-bold text-gray-900"
  }, baseKpi?.slots ?? '-'), slotDelta != null && /*#__PURE__*/React.createElement("p", {
    className: `text-xs font-semibold ${slotDelta >= 0 ? 'text-green-600' : 'text-red-600'}`
  }, slotDelta >= 0 ? '+' : '', slotDelta, " \uC804\uC77C\uB300\uBE44")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500"
  }, "\uD3C9\uADE0\uAC00"), /*#__PURE__*/React.createElement("p", {
    className: "text-xl font-bold text-gray-900"
  }, formatPrice(baseKpi?.avg_price)), priceDelta != null && /*#__PURE__*/React.createElement("p", {
    className: `text-xs font-semibold ${priceDelta > 0 ? 'text-red-600' : priceDelta < 0 ? 'text-green-600' : 'text-gray-500'}`
  }, priceDelta > 0 ? '+' : '', formatPrice(priceDelta))))), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-gray-500 font-semibold uppercase mb-2"
  }, "\uACBD\uC7C1 \uD3C9\uADE0 (", competitorKpis.length, "\uACF3)"), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-2 gap-3"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500"
  }, "\uC794\uC5EC\uC2AC\uB86F"), /*#__PURE__*/React.createElement("p", {
    className: "text-xl font-bold text-gray-900"
  }, competitorAvg.slots)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500"
  }, "\uD3C9\uADE0\uAC00"), /*#__PURE__*/React.createElement("p", {
    className: "text-xl font-bold text-gray-900"
  }, formatPrice(competitorAvg.avg_price))))), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-gray-500 font-semibold uppercase mb-2"
  }, "\uAC00\uACA9 \uBCC0\uACBD"), /*#__PURE__*/React.createElement("div", {
    className: "text-2xl font-bold text-gray-900"
  }, data.kpi.total_price_changes), /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-gray-500 mt-1"
  }, "\uC778\uC0C1 ", data.kpi.changes_by_type.인상 ?? 0, " \xB7 \uC778\uD558 ", data.kpi.changes_by_type.인하 ?? 0, " \xB7 \uD2B9\uAC00\uBD80\uCC29 ", data.kpi.changes_by_type.특가부착 ?? 0)), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-gray-500 font-semibold uppercase mb-2"
  }, "\uD2B9\uAC00\uC728"), /*#__PURE__*/React.createElement("div", {
    className: "text-2xl font-bold text-gray-900"
  }, data.kpi.promo_ratio?.toFixed(1), "%"), /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-gray-500 mt-1"
  }, data.kpi.total_promo_slots, " / ", data.kpi.total_slots_today, " \uC2AC\uB86F"))), data.alerts.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "font-bold text-base mb-3 text-gray-900"
  }, "\uD83D\uDEA8 \uACBD\uBCF4"), /*#__PURE__*/React.createElement("div", {
    className: "space-y-2"
  }, data.alerts.slice(0, 5).map((alert, idx) => /*#__PURE__*/React.createElement("div", {
    key: idx,
    className: `flex items-start gap-3 p-3 rounded-lg border ${alert.level === 'error' ? 'bg-red-50 border-red-200' : alert.level === 'warning' ? 'bg-yellow-50 border-yellow-200' : 'bg-blue-50 border-blue-200'}`
  }, /*#__PURE__*/React.createElement("span", {
    className: `text-xs font-bold px-2 py-1 rounded whitespace-nowrap ${alert.level === 'error' ? 'bg-red-200 text-red-800' : alert.level === 'warning' ? 'bg-yellow-200 text-yellow-800' : 'bg-blue-200 text-blue-800'}`
  }, alert.level === 'error' ? '오류' : alert.level === 'warning' ? '경고' : '정보'), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-sm font-semibold text-gray-900"
  }, alert.course), /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-700"
  }, alert.msg)))))), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "font-bold text-base mb-3 text-gray-900"
  }, "\uAC00\uACA9 \uBCC0\uACBD \uC774\uBCA4\uD2B8"), /*#__PURE__*/React.createElement("div", {
    className: "space-y-3"
  }, raiseChanges.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "border-2 border-red-300 rounded-lg p-3 bg-red-50"
  }, /*#__PURE__*/React.createElement("h4", {
    className: "font-semibold text-red-900 text-sm mb-2"
  }, "\uD83D\uDCC8 \uC778\uC0C1 (", raiseChanges.length, "\uAC74)"), /*#__PURE__*/React.createElement("div", {
    className: "overflow-x-auto"
  }, /*#__PURE__*/React.createElement("table", {
    className: "text-xs w-full"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    className: "text-gray-500 border-b border-red-200"
  }, /*#__PURE__*/React.createElement("th", {
    className: "text-left py-1 px-2"
  }, "\uACE8\uD504\uC7A5"), /*#__PURE__*/React.createElement("th", {
    className: "text-left py-1 px-2"
  }, "\uCF54\uC2A4"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-1 px-2"
  }, "\uACBD\uAE30\uC77C"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-1 px-2"
  }, "\uBCC0\uACBD\uC804"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-1 px-2"
  }, "\uBCC0\uACBD\uD6C4"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-1 px-2"
  }, "\uBCC0\uB3D9"), /*#__PURE__*/React.createElement("th", {
    className: "text-left py-1 px-2"
  }, "\uBE44\uACE0"))), /*#__PURE__*/React.createElement("tbody", null, raiseChanges.map((item, idx) => /*#__PURE__*/React.createElement("tr", {
    key: idx,
    className: "border-b border-red-100"
  }, /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 font-semibold text-gray-900"
  }, item.course_name), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-gray-600"
  }, item.course_sub), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-right text-gray-600"
  }, item.play_date), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-right"
  }, formatCurrency(item.old_price_krw)), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-right font-bold text-red-600"
  }, formatCurrency(item.new_price_krw)), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-right font-bold text-red-600"
  }, "+", formatPrice(item.delta_price_krw)), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-gray-500 text-xs"
  }, item.note))))))), dropChanges.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "border border-green-300 rounded-lg p-3 bg-green-50"
  }, /*#__PURE__*/React.createElement("h4", {
    className: "font-semibold text-green-900 text-sm mb-2"
  }, "\uD83D\uDCC9 \uC778\uD558 (", dropChanges.length, "\uAC74)"), /*#__PURE__*/React.createElement("div", {
    className: "overflow-x-auto"
  }, /*#__PURE__*/React.createElement("table", {
    className: "text-xs w-full"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    className: "text-gray-500 border-b border-green-200"
  }, /*#__PURE__*/React.createElement("th", {
    className: "text-left py-1 px-2"
  }, "\uACE8\uD504\uC7A5"), /*#__PURE__*/React.createElement("th", {
    className: "text-left py-1 px-2"
  }, "\uCF54\uC2A4"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-1 px-2"
  }, "\uBCC0\uACBD\uC804"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-1 px-2"
  }, "\uBCC0\uACBD\uD6C4"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-1 px-2"
  }, "\uBCC0\uB3D9"))), /*#__PURE__*/React.createElement("tbody", null, dropChanges.slice(0, 10).map((item, idx) => /*#__PURE__*/React.createElement("tr", {
    key: idx,
    className: "border-b border-green-100"
  }, /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 font-semibold text-gray-900"
  }, item.course_name), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-gray-600"
  }, item.course_sub), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-right"
  }, formatCurrency(item.old_price_krw)), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-right font-bold text-green-600"
  }, formatCurrency(item.new_price_krw)), /*#__PURE__*/React.createElement("td", {
    className: "py-1.5 px-2 text-right font-bold text-green-600"
  }, formatPrice(item.delta_price_krw))))))), dropChanges.length > 10 && /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mt-2 pl-2"
  }, "\uC678 ", dropChanges.length - 10, "\uAC74")))), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "font-bold text-base mb-3 text-gray-900"
  }, "\uC18C\uC9C4 \uD604\uD669"), /*#__PURE__*/React.createElement("div", {
    className: "overflow-x-auto"
  }, /*#__PURE__*/React.createElement("table", {
    className: "w-full text-sm"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    className: "border-b-2 border-gray-200 bg-gray-50"
  }, /*#__PURE__*/React.createElement("th", {
    className: "text-left py-2 px-3 text-gray-600 font-semibold"
  }, "\uACE8\uD504\uC7A5"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uC804\uC77C\uC794\uC5EC"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uAE08\uC77C\uC794\uC5EC"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uC18C\uC9C4"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uC2E0\uADDC"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uD68C\uC6D0\uC624\uD508"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uC18C\uC9C4\uC728"))), /*#__PURE__*/React.createElement("tbody", null, (data.consumption || []).sort((a, b) => (b.consume_rate ?? 0) - (a.consume_rate ?? 0)).map((item, idx) => /*#__PURE__*/React.createElement("tr", {
    key: idx,
    className: `border-b border-gray-100 hover:bg-blue-50 transition ${item.course_name === baseCourse ? 'bg-blue-50 font-semibold' : ''}`
  }, /*#__PURE__*/React.createElement("td", {
    className: "py-2 px-3 text-gray-900"
  }, item.course_name === baseCourse ? '⭐ ' : '', item.course_name), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 text-gray-600"
  }, item.prev_slots ?? '-'), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 text-gray-600"
  }, item.today_slots ?? '-'), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 text-gray-600"
  }, item.consumed ?? '-'), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 text-green-600"
  }, item.new_open != null ? `+${item.new_open}` : '-'), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 text-purple-600"
  }, item.member_open != null ? `+${item.member_open}` : '-'), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3"
  }, item.consume_rate != null ? /*#__PURE__*/React.createElement("span", {
    className: `font-bold ${item.consume_rate > 80 ? 'text-red-600' : item.consume_rate > 40 ? 'text-amber-600' : 'text-gray-700'}`
  }, item.consume_rate.toFixed(1), "%") : '-'))))))), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "font-bold text-base mb-3 text-gray-900"
  }, "\uD5A5\uD6C4 7\uC77C \uACBD\uAE30\uC77C \uCE98\uB9B0\uB354"), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-2 overflow-x-auto pb-2"
  }, (data.calendar || []).slice(0, 7).map((day, idx) => {
    const we = isWeekend(day.weekday_type);
    return /*#__PURE__*/React.createElement("div", {
      key: idx,
      className: `flex-shrink-0 rounded-xl border p-3 text-center min-w-[110px] ${we ? 'bg-amber-50 border-amber-300' : 'bg-gray-50 border-gray-200'}`
    }, /*#__PURE__*/React.createElement("p", {
      className: "text-xs text-gray-500"
    }, day.play_date), /*#__PURE__*/React.createElement("p", {
      className: `font-bold text-sm mt-0.5 ${we ? 'text-amber-700' : 'text-gray-700'}`
    }, day.weekday_type), /*#__PURE__*/React.createElement("div", {
      className: "mt-2 border-t border-gray-200 pt-2"
    }, /*#__PURE__*/React.createElement("p", {
      className: "text-xs text-gray-600"
    }, day.slots, " \uC2AC\uB86F"), /*#__PURE__*/React.createElement("p", {
      className: "text-sm font-bold text-blue-600"
    }, formatPrice(day.avg_price)), day.promo_slots > 0 && /*#__PURE__*/React.createElement("p", {
      className: "text-xs text-green-600"
    }, "\uD2B9\uAC00 ", day.promo_slots)), /*#__PURE__*/React.createElement("p", {
      className: "text-xs text-gray-400 mt-1"
    }, "D-", day.d_day));
  }))));
}

// ─────────────────────────────────────────────────────────
// Tab 4: 가격 흐름 분석
// ─────────────────────────────────────────────────────────
function Tab4() {
  const {
    baseCourse,
    competitors
  } = useContext(SettingsContext);
  const data = RAW_DATA.tab4;
  const [dayType, setDayType] = useState('전체');
  const [selectedCourses, setSelectedCourses] = useState([baseCourse, ...(competitors || [])].slice(0, 6));
  const allCourses = RAW_DATA.metadata.courses;
  const filteredTrend = useMemo(() => {
    return (data.dday_trend || []).filter(item => {
      const courseMatch = selectedCourses.includes(item.course_name);
      const dayMatch = dayType === '전체' ? true : dayType === '주말' ? isWeekend(item.weekday_type) : item.weekday_type === '평일';
      return courseMatch && dayMatch;
    });
  }, [dayType, selectedCourses]);

  // D-day별 코스 라인 데이터 피봇
  const trendByDday = useMemo(() => {
    const map = {};
    filteredTrend.forEach(item => {
      if (!map[item.d_day]) map[item.d_day] = {
        d_day: item.d_day
      };
      map[item.d_day][item.course_name] = item.avg_price;
    });
    return Object.values(map).sort((a, b) => a.d_day - b.d_day);
  }, [filteredTrend]);

  // scatter: 기준 골프장 vs 경쟁 분류
  const scatterByCourse = useMemo(() => {
    return groupBy((data.scatter || []).filter(r => selectedCourses.includes(r.course_name)), r => r.course_name);
  }, [selectedCourses]);

  // histogram: 숫자 bucket → label 변환
  const histogramData = useMemo(() => {
    return (data.histogram || []).map(r => ({
      ...r,
      label: `${Math.round(r.price_bucket / 1000)}k`
    }));
  }, []);
  const toggleCourse = course => {
    if (selectedCourses.includes(course)) {
      setSelectedCourses(selectedCourses.filter(c => c !== course));
    } else {
      setSelectedCourses([...selectedCourses, course]);
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "space-y-6"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex flex-wrap gap-3 items-start"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mb-2 font-semibold"
  }, "\uC694\uC77C \uAD6C\uBD84"), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-2"
  }, ['전체', '평일', '주말'].map(d => /*#__PURE__*/React.createElement("button", {
    key: d,
    onClick: () => setDayType(d),
    className: `px-4 py-1.5 rounded-lg text-sm font-semibold transition ${dayType === d ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`
  }, d)))), /*#__PURE__*/React.createElement("div", {
    className: "flex-1"
  }, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mb-2 font-semibold"
  }, "\uACE8\uD504\uC7A5 \uC120\uD0DD"), /*#__PURE__*/React.createElement("div", {
    className: "flex flex-wrap gap-1.5"
  }, allCourses.map((c, idx) => /*#__PURE__*/React.createElement("button", {
    key: c,
    onClick: () => toggleCourse(c),
    className: `px-3 py-1 rounded-full text-xs font-semibold transition border ${selectedCourses.includes(c) ? c === baseCourse ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-700 text-white border-gray-700' : 'bg-white text-gray-500 border-gray-300'}`
  }, c === baseCourse ? `⭐ ${c}` : c)))))), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "font-bold text-base mb-4 text-gray-900"
  }, "D-day \uAC00\uACA9 \uCD94\uC138 (\uB300\uC911\uC81C \uAE30\uC900)"), trendByDday.length > 0 ? /*#__PURE__*/React.createElement(ResponsiveContainer, {
    width: "100%",
    height: 300
  }, /*#__PURE__*/React.createElement(LineChart, {
    data: trendByDday,
    margin: {
      top: 5,
      right: 20,
      left: 10,
      bottom: 5
    }
  }, /*#__PURE__*/React.createElement(CartesianGrid, {
    strokeDasharray: "3 3",
    stroke: "#f0f0f0"
  }), /*#__PURE__*/React.createElement(XAxis, {
    dataKey: "d_day",
    label: {
      value: 'D-day',
      position: 'insideBottom',
      offset: -3,
      fontSize: 12
    }
  }), /*#__PURE__*/React.createElement(YAxis, {
    tickFormatter: v => `${Math.round(v / 1000)}k`
  }), /*#__PURE__*/React.createElement(Tooltip, {
    formatter: (v, name) => [formatCurrency(v), name]
  }), /*#__PURE__*/React.createElement(Legend, null), selectedCourses.map((course, idx) => /*#__PURE__*/React.createElement(Line, {
    key: course,
    type: "monotone",
    dataKey: course,
    stroke: course === baseCourse ? COLORS.primary : COURSE_PALETTE[idx % COURSE_PALETTE.length],
    strokeWidth: course === baseCourse ? 3 : 1.5,
    dot: false,
    isAnimationActive: false
  })), /*#__PURE__*/React.createElement(ReferenceLine, {
    x: 1,
    stroke: COLORS.warning,
    strokeDasharray: "4 4"
  }))) : /*#__PURE__*/React.createElement("p", {
    className: "text-gray-400 text-sm text-center py-10"
  }, "\uC120\uD0DD\uB41C \uACE8\uD504\uC7A5\uC758 \uCD94\uC138 \uB370\uC774\uD130\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4")), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "font-bold text-base mb-4 text-gray-900"
  }, "\uAC00\uACA9\uB300 \uBD84\uD3EC (D-day \xD7 \uAC00\uACA9)"), /*#__PURE__*/React.createElement(ResponsiveContainer, {
    width: "100%",
    height: 300
  }, /*#__PURE__*/React.createElement(ScatterChart, {
    margin: {
      top: 10,
      right: 20,
      bottom: 20,
      left: 20
    }
  }, /*#__PURE__*/React.createElement(CartesianGrid, {
    strokeDasharray: "3 3",
    stroke: "#f0f0f0"
  }), /*#__PURE__*/React.createElement(XAxis, {
    type: "number",
    dataKey: "price_krw",
    name: "\uAC00\uACA9",
    tickFormatter: v => `${Math.round(v / 1000)}k`
  }), /*#__PURE__*/React.createElement(YAxis, {
    type: "number",
    dataKey: "d_day",
    name: "D-day",
    label: {
      value: 'D-day',
      angle: -90,
      position: 'insideLeft',
      fontSize: 11
    }
  }), /*#__PURE__*/React.createElement(Tooltip, {
    cursor: {
      strokeDasharray: '3 3'
    },
    formatter: (v, name) => [name === 'price_krw' ? formatCurrency(v) : v, name === 'price_krw' ? '가격' : 'D-day']
  }), /*#__PURE__*/React.createElement(Legend, null), Object.entries(scatterByCourse).slice(0, 6).map(([course, items], idx) => /*#__PURE__*/React.createElement(Scatter, {
    key: course,
    name: course,
    data: items,
    fill: course === baseCourse ? COLORS.primary : COURSE_PALETTE[idx % COURSE_PALETTE.length],
    fillOpacity: 0.5,
    r: 3
  }))))), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "font-bold text-base mb-4 text-gray-900"
  }, "\uAC00\uACA9\uB300\uBCC4 \uC2AC\uB86F \uBD84\uD3EC (\uC804\uCCB4 \uACE8\uD504\uC7A5)"), /*#__PURE__*/React.createElement(ResponsiveContainer, {
    width: "100%",
    height: 250
  }, /*#__PURE__*/React.createElement(BarChart, {
    data: histogramData,
    margin: {
      top: 5,
      right: 20,
      left: 10,
      bottom: 5
    }
  }, /*#__PURE__*/React.createElement(CartesianGrid, {
    strokeDasharray: "3 3",
    stroke: "#f0f0f0"
  }), /*#__PURE__*/React.createElement(XAxis, {
    dataKey: "label"
  }), /*#__PURE__*/React.createElement(YAxis, null), /*#__PURE__*/React.createElement(Tooltip, null), /*#__PURE__*/React.createElement(Legend, null), /*#__PURE__*/React.createElement(Bar, {
    dataKey: "non_promo",
    stackId: "a",
    fill: COLORS.primary,
    name: "\uC77C\uBC18\uAC00"
  }), /*#__PURE__*/React.createElement(Bar, {
    dataKey: "promo",
    stackId: "a",
    fill: COLORS.positive,
    name: "\uD2B9\uAC00"
  })))));
}

// ─────────────────────────────────────────────────────────
// Tab 6: 코스 × 서브코스 현황
// ─────────────────────────────────────────────────────────
function Tab6() {
  const {
    baseCourse
  } = useContext(SettingsContext);
  const rows = RAW_DATA.tab6.subcourse_rows || [];
  const groupedByCourse = useMemo(() => groupBy(rows, r => r.course_name), []);
  return /*#__PURE__*/React.createElement("div", {
    className: "space-y-5"
  }, Object.entries(groupedByCourse).map(([course, subcourses]) => {
    const isBase = course === baseCourse;
    const totalSlots = subcourses.reduce((s, sc) => s + sc.slots, 0);
    const maxSlots = Math.max(...subcourses.map(s => s.slots), 1);
    return /*#__PURE__*/React.createElement("div", {
      key: course,
      className: `bg-white rounded-xl border-2 p-4 ${isBase ? 'border-blue-500 shadow-md' : 'border-gray-200'}`
    }, /*#__PURE__*/React.createElement("div", {
      className: "flex justify-between items-center mb-3"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", {
      className: "font-bold text-base text-gray-900"
    }, isBase && /*#__PURE__*/React.createElement("span", {
      className: "text-blue-500 mr-1"
    }, "\u2B50"), course), /*#__PURE__*/React.createElement("p", {
      className: "text-xs text-gray-500"
    }, "\uCD1D ", totalSlots, " \uC2AC\uB86F \xB7 ", subcourses.length, "\uAC1C \uC11C\uBE0C\uCF54\uC2A4")), isBase && /*#__PURE__*/React.createElement("span", {
      className: "text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-semibold"
    }, "\uAE30\uC900 \uACE8\uD504\uC7A5")), /*#__PURE__*/React.createElement("div", {
      className: "space-y-2"
    }, subcourses.map((sub, idx) => {
      const memberLabel = sub.member_label;
      const isMember = memberLabel === '회원제';
      return /*#__PURE__*/React.createElement("div", {
        key: idx,
        className: `p-3 rounded-lg border ${isMember ? 'bg-purple-50 border-purple-200' : 'bg-slate-50 border-slate-200'}`
      }, /*#__PURE__*/React.createElement("div", {
        className: "flex justify-between items-start mb-1.5"
      }, /*#__PURE__*/React.createElement("div", {
        className: "flex items-center gap-2"
      }, /*#__PURE__*/React.createElement("p", {
        className: "font-semibold text-sm text-gray-900"
      }, sub.sub_display || sub.course_sub), memberLabel && /*#__PURE__*/React.createElement("span", {
        className: `text-xs px-1.5 py-0.5 rounded font-medium ${isMember ? 'bg-purple-200 text-purple-800' : 'bg-cyan-200 text-cyan-800'}`
      }, memberLabel)), /*#__PURE__*/React.createElement("div", {
        className: "text-right"
      }, /*#__PURE__*/React.createElement("p", {
        className: "font-bold text-gray-900 text-sm"
      }, sub.slots, " \uC2AC\uB86F"), sub.slot_delta != null && /*#__PURE__*/React.createElement("p", {
        className: `text-xs ${sub.slot_delta >= 0 ? 'text-green-600' : 'text-red-600'}`
      }, sub.slot_delta >= 0 ? '+' : '', sub.slot_delta))), /*#__PURE__*/React.createElement("div", {
        className: "h-2 bg-gray-200 rounded-full overflow-hidden mb-1.5"
      }, /*#__PURE__*/React.createElement("div", {
        className: `h-full rounded-full transition-all ${isMember ? 'bg-purple-500' : 'bg-blue-500'}`,
        style: {
          width: `${sub.slots / maxSlots * 100}%`
        }
      })), /*#__PURE__*/React.createElement("div", {
        className: "flex justify-between text-xs text-gray-500"
      }, /*#__PURE__*/React.createElement("span", null, "1\uBD80 ", sub.part1, " \xB7 2\uBD80 ", sub.part2), /*#__PURE__*/React.createElement("span", null, formatPrice(sub.avg_price)), sub.promo_ratio > 0 && /*#__PURE__*/React.createElement("span", {
        className: "text-green-600"
      }, "\uD2B9\uAC00 ", sub.promo_ratio, "%"), sub.price_delta != null && /*#__PURE__*/React.createElement("span", {
        className: sub.price_delta > 0 ? 'text-red-600' : 'text-green-600'
      }, "\uAC00\uACA9 ", sub.price_delta > 0 ? '+' : '', formatPrice(sub.price_delta))));
    })));
  }));
}

// ─────────────────────────────────────────────────────────
// Tab 8: 티타임 상세
// ─────────────────────────────────────────────────────────
function Tab8() {
  const {
    baseCourse
  } = useContext(SettingsContext);
  const allSlots = RAW_DATA.tab8?.slots || [];
  const [filterCourse, setFilterCourse] = useState('전체');
  const [filterPromo, setFilterPromo] = useState('전체');
  const [filterMembership, setFilterMembership] = useState('전체');
  const [filterPart, setFilterPart] = useState('전체');
  const [page, setPage] = useState(0);
  const ITEMS_PER_PAGE = 50;
  const courseOptions = useMemo(() => ['전체', ...new Set(allSlots.map(r => r.course_name))], []);
  const membershipTypes = useMemo(() => ['전체', ...new Set(allSlots.map(r => r.membership_type).filter(Boolean))], []);
  const filtered = useMemo(() => {
    return allSlots.filter(r => {
      if (filterCourse !== '전체' && r.course_name !== filterCourse) return false;
      if (filterPromo === '특가' && !r.promo_flag) return false;
      if (filterPromo === '일반' && r.promo_flag) return false;
      if (filterMembership !== '전체' && r.membership_type !== filterMembership) return false;
      if (filterPart !== '전체' && r.part_type !== filterPart) return false;
      return true;
    });
  }, [filterCourse, filterPromo, filterMembership, filterPart]);
  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE);
  const pageData = filtered.slice(page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE);
  const handleFilterChange = setter => val => {
    setter(val);
    setPage(0);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "space-y-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex flex-wrap gap-4"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mb-1 font-semibold"
  }, "\uACE8\uD504\uC7A5"), /*#__PURE__*/React.createElement("select", {
    value: filterCourse,
    onChange: e => handleFilterChange(setFilterCourse)(e.target.value),
    className: "text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-400 outline-none"
  }, courseOptions.map(c => /*#__PURE__*/React.createElement("option", {
    key: c,
    value: c
  }, c === baseCourse ? `⭐ ${c}` : c)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mb-1 font-semibold"
  }, "\uD2B9\uAC00\uC5EC\uBD80"), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-1.5"
  }, ['전체', '특가', '일반'].map(v => /*#__PURE__*/React.createElement("button", {
    key: v,
    onClick: () => handleFilterChange(setFilterPromo)(v),
    className: `text-xs px-3 py-1.5 rounded-lg font-semibold transition ${filterPromo === v ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`
  }, v)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mb-1 font-semibold"
  }, "\uD68C\uC6D0\uAD6C\uBD84"), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-1.5"
  }, membershipTypes.map(v => /*#__PURE__*/React.createElement("button", {
    key: v,
    onClick: () => handleFilterChange(setFilterMembership)(v),
    className: `text-xs px-3 py-1.5 rounded-lg font-semibold transition ${filterMembership === v ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`
  }, v)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-500 mb-1 font-semibold"
  }, "\uBD80"), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-1.5"
  }, ['전체', '1부', '2부'].map(v => /*#__PURE__*/React.createElement("button", {
    key: v,
    onClick: () => handleFilterChange(setFilterPart)(v),
    className: `text-xs px-3 py-1.5 rounded-lg font-semibold transition ${filterPart === v ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`
  }, v))))), /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-400 mt-2"
  }, filtered.length.toLocaleString(), "\uAC74 (\uC804\uCCB4 ", allSlots.length.toLocaleString(), "\uAC74)")), /*#__PURE__*/React.createElement("div", {
    className: "bg-white rounded-xl border border-gray-200 p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "overflow-x-auto"
  }, /*#__PURE__*/React.createElement("table", {
    className: "w-full text-sm"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    className: "border-b-2 border-gray-200 bg-gray-50"
  }, /*#__PURE__*/React.createElement("th", {
    className: "text-left py-2 px-3 text-gray-600 font-semibold"
  }, "\uACE8\uD504\uC7A5"), /*#__PURE__*/React.createElement("th", {
    className: "text-left py-2 px-3 text-gray-600 font-semibold"
  }, "\uCF54\uC2A4"), /*#__PURE__*/React.createElement("th", {
    className: "text-left py-2 px-3 text-gray-600 font-semibold"
  }, "\uAD6C\uBD84"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uACBD\uAE30\uC77C"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uD2F0\uD0C0\uC784"), /*#__PURE__*/React.createElement("th", {
    className: "text-left py-2 px-3 text-gray-600 font-semibold"
  }, "\uBD80"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "D-day"), /*#__PURE__*/React.createElement("th", {
    className: "text-right py-2 px-3 text-gray-600 font-semibold"
  }, "\uAC00\uACA9"), /*#__PURE__*/React.createElement("th", {
    className: "text-center py-2 px-3 text-gray-600 font-semibold"
  }, "\uD2B9\uAC00"), /*#__PURE__*/React.createElement("th", {
    className: "text-left py-2 px-3 text-gray-600 font-semibold"
  }, "\uC870\uAC74"))), /*#__PURE__*/React.createElement("tbody", null, pageData.map((item, idx) => /*#__PURE__*/React.createElement("tr", {
    key: idx,
    className: `border-b border-gray-100 transition text-xs ${item.course_name === baseCourse ? 'bg-blue-50' : item.promo_flag ? 'bg-green-50' : 'hover:bg-gray-50'}`
  }, /*#__PURE__*/React.createElement("td", {
    className: "py-2 px-3 font-semibold text-gray-900"
  }, item.course_name), /*#__PURE__*/React.createElement("td", {
    className: "py-2 px-3 text-gray-600"
  }, item.sub_display || item.course_sub), /*#__PURE__*/React.createElement("td", {
    className: "py-2 px-3"
  }, item.membership_type && item.membership_type !== '단일' && /*#__PURE__*/React.createElement("span", {
    className: `text-xs px-1.5 py-0.5 rounded font-medium ${item.membership_type === '회원제' ? 'bg-purple-100 text-purple-700' : 'bg-cyan-100 text-cyan-700'}`
  }, item.membership_type)), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 text-gray-600"
  }, item.play_date), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 font-mono text-gray-700"
  }, item.tee_time), /*#__PURE__*/React.createElement("td", {
    className: "py-2 px-3 text-gray-500"
  }, item.part_type), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 font-semibold text-gray-700"
  }, item.d_day), /*#__PURE__*/React.createElement("td", {
    className: "text-right py-2 px-3 font-bold text-gray-900"
  }, formatCurrency(item.price_krw)), /*#__PURE__*/React.createElement("td", {
    className: "text-center py-2 px-3"
  }, item.promo_flag ? /*#__PURE__*/React.createElement("span", {
    className: "bg-green-200 text-green-800 text-xs px-2 py-0.5 rounded font-semibold"
  }, "\uD2B9\uAC00") : /*#__PURE__*/React.createElement("span", {
    className: "text-gray-300"
  }, "\u2014")), /*#__PURE__*/React.createElement("td", {
    className: "py-2 px-3 text-gray-400 text-xs"
  }, item.pax_condition || '')))))), totalPages > 1 && /*#__PURE__*/React.createElement("div", {
    className: "mt-4 flex justify-center items-center gap-2"
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setPage(0),
    disabled: page === 0,
    className: "px-3 py-1 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-40"
  }, "\uCC98\uC74C"), /*#__PURE__*/React.createElement("button", {
    onClick: () => setPage(Math.max(0, page - 1)),
    disabled: page === 0,
    className: "px-3 py-1 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-40"
  }, "\uC774\uC804"), /*#__PURE__*/React.createElement("span", {
    className: "text-sm text-gray-600 font-semibold"
  }, page + 1, " / ", totalPages), /*#__PURE__*/React.createElement("button", {
    onClick: () => setPage(Math.min(totalPages - 1, page + 1)),
    disabled: page === totalPages - 1,
    className: "px-3 py-1 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-40"
  }, "\uB2E4\uC74C"), /*#__PURE__*/React.createElement("button", {
    onClick: () => setPage(totalPages - 1),
    disabled: page === totalPages - 1,
    className: "px-3 py-1 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-40"
  }, "\uB05D"))));
}

// ─────────────────────────────────────────────────────────
// Main App
// ─────────────────────────────────────────────────────────
function App() {
  const allCourses = RAW_DATA.metadata.courses;
  const defaultBase = allCourses[0] || '골드레이크';
  const [baseCourse, setBaseCourse] = useState(defaultBase);
  const [competitors, setCompetitors] = useState(allCourses.filter(c => c !== defaultBase));
  const [currentTab, setCurrentTab] = useState('tab1');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const handleSaveSettings = (newBase, newComp) => {
    setBaseCourse(newBase);
    setCompetitors(newComp);
  };
  const tabs = [{
    id: 'tab1',
    label: '📋 오늘의 브리핑',
    component: Tab1
  }, {
    id: 'tab4',
    label: '📊 가격 흐름 분석',
    component: Tab4
  }, {
    id: 'tab6',
    label: '🏌️ 코스별 현황',
    component: Tab6
  }, {
    id: 'tab8',
    label: '🕐 티타임 상세',
    component: Tab8
  }];
  const CurrentComponent = tabs.find(t => t.id === currentTab)?.component || Tab1;
  return /*#__PURE__*/React.createElement(SettingsContext.Provider, {
    value: {
      baseCourse,
      competitors
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "min-h-screen",
    style: {
      backgroundColor: COLORS.bg
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "sticky top-0 z-40 bg-white border-b border-gray-200 shadow-sm"
  }, /*#__PURE__*/React.createElement("div", {
    className: "max-w-7xl mx-auto px-4 sm:px-6 py-3"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex justify-between items-center"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    className: "text-xl font-bold text-gray-900"
  }, "\u26F3 \uACE8\uD504 \uAC00\uACA9 \uBAA8\uB2C8\uD130\uB9C1 \uB300\uC2DC\uBCF4\uB4DC"), /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-gray-400"
  }, "\uC5C5\uB370\uC774\uD2B8: ", RAW_DATA.metadata.generated_at, " \xA0\xB7\xA0 \uAE30\uC900: ", /*#__PURE__*/React.createElement("span", {
    className: "font-semibold text-blue-600"
  }, baseCourse))), /*#__PURE__*/React.createElement("button", {
    onClick: () => setSettingsOpen(true),
    className: "px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition flex items-center gap-1"
  }, "\u2699 \uC124\uC815"))), /*#__PURE__*/React.createElement("div", {
    className: "max-w-7xl mx-auto px-4 sm:px-6"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex gap-0 overflow-x-auto"
  }, tabs.map(tab => /*#__PURE__*/React.createElement("button", {
    key: tab.id,
    onClick: () => setCurrentTab(tab.id),
    className: `px-4 py-2.5 text-sm font-semibold transition border-b-2 whitespace-nowrap ${currentTab === tab.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'}`
  }, tab.label))))), /*#__PURE__*/React.createElement("div", {
    className: "max-w-7xl mx-auto px-4 sm:px-6 py-6"
  }, /*#__PURE__*/React.createElement(CurrentComponent, null)), /*#__PURE__*/React.createElement(SettingsModal, {
    isOpen: settingsOpen,
    onClose: () => setSettingsOpen(false),
    onSave: handleSaveSettings
  })));
}

// ── 마운트 ──
const rootEl = document.getElementById('root');
ReactDOM.createRoot(rootEl).render(React.createElement(App, null));