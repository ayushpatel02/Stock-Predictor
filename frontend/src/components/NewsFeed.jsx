import { useEffect, useState } from 'react'
import { fetchNews } from '../api/client'

const SENTIMENT_STYLES = {
  positive: { tag: 'bg-green-900/60 text-green-300', dot: 'bg-green-400' },
  negative: { tag: 'bg-red-900/60 text-red-300', dot: 'bg-red-400' },
  neutral: { tag: 'bg-slate-700 text-slate-400', dot: 'bg-slate-400' },
}

function timeAgo(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  const diff = Math.floor((Date.now() - date.getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

/**
 * NewsFeed — Latest news headlines for a stock with sentiment tags.
 *
 * Props:
 *   symbol — stock symbol
 *   limit  — max number of items (default 8)
 */
export default function NewsFeed({ symbol, limit = 8 }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchNews(symbol, limit)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [symbol, limit])

  if (loading) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          News
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-14 bg-slate-900/50 rounded animate-pulse mb-2" />
        ))}
      </div>
    )
  }

  const items = data?.items ?? []
  const agg = data?.aggregate ?? {}

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          News
        </div>
        {items.length > 0 && (
          <div className="flex gap-2 text-xs">
            <span className="text-green-400">▲ {agg.bullish_count ?? 0}</span>
            <span className="text-slate-500">— {agg.neutral_count ?? 0}</span>
            <span className="text-red-400">▼ {agg.bearish_count ?? 0}</span>
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div className="text-sm text-slate-500 py-6 text-center">
          No recent news for {symbol}
        </div>
      ) : (
        <ul className="divide-y divide-slate-700">
          {items.map((item, i) => {
            const s = SENTIMENT_STYLES[item.sentiment] ?? SENTIMENT_STYLES.neutral
            return (
              <li key={i} className="py-2">
                <a
                  href={item.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block hover:bg-slate-900/30 rounded p-2 -m-2 transition-colors"
                >
                  <div className="flex items-start gap-2">
                    <span className={`inline-block w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${s.dot}`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-slate-200 leading-snug">
                        {item.title}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                        <span>{item.publisher}</span>
                        <span>·</span>
                        <span>{timeAgo(item.published)}</span>
                        <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] ${s.tag}`}>
                          {item.sentiment}
                        </span>
                      </div>
                    </div>
                  </div>
                </a>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
