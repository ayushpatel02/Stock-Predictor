/**
 * StockPriceAnalysis — key metrics grid for the company overview tab.
 *
 * Shows current price + day change, 52W range bar, and a grid of fundamental
 * metrics (market cap, P/E, EPS, book value, dividend yield, beta, margins).
 *
 * Props:
 *   data — price_analysis object from GET /stocks/{symbol}/overview
 */

function fmtNum(v, digits = 2) {
  if (v == null) return '—'
  return Number(v).toFixed(digits)
}

function fmtPct(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(2)}%`
}

function fmtCap(v) {
  if (v == null) return '—'
  if (v >= 1e12) return `₹${(v / 1e12).toFixed(2)}T`
  if (v >= 1e9) return `₹${(v / 1e9).toFixed(2)}B`
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)}Cr`
  return `₹${v.toLocaleString('en-IN')}`
}

function MetricRow({ label, value }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-slate-700/50">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="text-sm font-mono text-slate-100 font-medium">{value}</span>
    </div>
  )
}

export default function StockPriceAnalysis({ data }) {
  if (!data) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-slate-500 text-sm text-center">
        Price analysis data unavailable
      </div>
    )
  }

  const {
    current_price,
    day_change,
    day_change_pct,
    week_52_high,
    week_52_low,
    market_cap,
    pe_ratio,
    eps,
    book_value,
    dividend_yield,
    beta,
    price_to_book,
    profit_margins,
    revenue_growth,
    roe,
  } = data

  const isUp = (day_change ?? 0) >= 0
  const dayPct = (day_change_pct ?? 0) * 100

  // 52W range position (0-100%)
  const rangePos =
    week_52_high && week_52_low && current_price
      ? ((current_price - week_52_low) / (week_52_high - week_52_low)) * 100
      : null

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 space-y-4">
      {/* Price header */}
      <div className="flex items-end gap-4 flex-wrap">
        <div>
          <div className="text-3xl font-bold text-slate-100">
            ₹{fmtNum(current_price)}
          </div>
          <div className={`flex items-center gap-1 text-sm font-semibold mt-0.5 ${isUp ? 'text-green-400' : 'text-red-400'}`}>
            <span>{isUp ? '▲' : '▼'}</span>
            <span>{isUp ? '+' : ''}{fmtNum(day_change)} ({isUp ? '+' : ''}{dayPct.toFixed(2)}%)</span>
            <span className="text-slate-500 font-normal text-xs ml-1">today</span>
          </div>
        </div>
      </div>

      {/* 52W range bar */}
      {rangePos != null && (
        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>52W Low ₹{fmtNum(week_52_low)}</span>
            <span>52W High ₹{fmtNum(week_52_high)}</span>
          </div>
          <div className="relative h-2 bg-slate-700 rounded-full">
            <div
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-indigo-400 border-2 border-slate-800 -translate-x-1/2"
              style={{ left: `${Math.min(98, Math.max(2, rangePos))}%` }}
              title={`Current: ₹${fmtNum(current_price)} (${rangePos.toFixed(0)}% of 52W range)`}
            />
            <div
              className="h-full bg-indigo-600/30 rounded-full"
              style={{ width: `${Math.min(100, rangePos)}%` }}
            />
          </div>
          <div className="text-center text-xs text-slate-500 mt-1">
            {rangePos.toFixed(0)}% of 52-week range
          </div>
        </div>
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
        <div>
          <MetricRow label="Market Cap" value={fmtCap(market_cap)} />
          <MetricRow label="P/E Ratio" value={fmtNum(pe_ratio)} />
          <MetricRow label="EPS (TTM)" value={pe_ratio != null && eps != null ? `₹${fmtNum(eps)}` : '—'} />
          <MetricRow label="Book Value" value={book_value != null ? `₹${fmtNum(book_value)}` : '—'} />
          <MetricRow label="Price / Book" value={fmtNum(price_to_book)} />
          <MetricRow label="Dividend Yield" value={fmtPct(dividend_yield)} />
          <MetricRow label="Beta" value={fmtNum(beta)} />
        </div>
        <div>
          <MetricRow label="Profit Margin" value={fmtPct(profit_margins)} />
          <MetricRow label="Revenue Growth" value={fmtPct(revenue_growth)} />
          <MetricRow label="Return on Equity" value={fmtPct(roe)} />
          {week_52_high && <MetricRow label="52W High" value={`₹${fmtNum(week_52_high)}`} />}
          {week_52_low && <MetricRow label="52W Low" value={`₹${fmtNum(week_52_low)}`} />}
        </div>
      </div>
    </div>
  )
}
