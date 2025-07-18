import { useEffect, useMemo, useState } from 'react'
import './App.css'

function api(path) {
  const base = import.meta.env.VITE_SUPABASE_URL
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY
  return fetch(`${base}${path}`, {
    headers: { apikey: key, Authorization: `Bearer ${key}` }
  }).then(async res => {
    if (!res.ok) throw new Error(`Supabase ${res.status}`)
    return res.json()
  })
}

function formatPrice(p) {
  return p == null ? '—' : `${(p * 100).toFixed(2)}%`
}

function formatChange(p) {
  if (p == null) return '—'
  const arrow = p < 0 ? '↓' : '↑'
  return `${arrow} ${Math.abs(p).toFixed(2)}%`
}

function formatDate(d) {
  if (!d) return '—'
  const dt = new Date(d)
  return dt.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

export default function App() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [sourceFilter, setSourceFilter] = useState('all')
  const [catFilter, setCatFilter] = useState('all')
  const [sortKey, setSortKey] = useState('volume')
  const [sortDir, setSortDir] = useState('desc')

  useEffect(() => {
    async function load() {
      try {
        setLoading(true)
        let data = await api(
          '/rest/v1/latest_snapshots' +
            '?select=market_id,source,price,volume,timestamp,market_name,event_name,expiration,summary,tags' +
            '&limit=1000'
        )
        data = data.filter(r => (r.volume ?? 0) > 0)
        const idList = data.map(r => `'${r.market_id}'`).join(',')
        const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
        const prevRows = await api(
          `/rest/v1/market_snapshots?select=market_id,price&market_id=in.(${idList})&timestamp=gt.${since}&order=timestamp.desc`
        )
        const prevPrice = {}
        prevRows.forEach(p => {
          if (prevPrice[p.market_id] == null) prevPrice[p.market_id] = p.price
        })
        const deduped = Object.values(
          data.reduce((acc, r) => {
            acc[r.market_id] = r
            return acc
          }, {})
        )
        deduped.forEach(r => {
          const p24 = prevPrice[r.market_id]
          r.price24h = p24
          r.changePct =
            r.price != null && p24 != null && p24 !== 0
              ? ((r.price - p24) / p24) * 100
              : null
          r.dollarVolumeCalc =
            r.price != null && p24 != null && r.volume != null
              ? Math.abs(r.price - p24) * r.volume
              : null
        })
        setRows(deduped.slice(0, 100))
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const categories = useMemo(() => {
    const setC = new Set()
    rows.forEach(r => {
      if (Array.isArray(r.tags) && r.tags.length) {
        r.tags.forEach(t => setC.add(t))
      } else {
        setC.add('General')
      }
    })
    return Array.from(setC)
  }, [rows])

  const sources = useMemo(() => Array.from(new Set(rows.map(r => r.source))), [rows])

  const filtered = useMemo(
    () =>
      rows.filter(r => {
        const matchSource = sourceFilter === 'all' || r.source === sourceFilter
        const tags = Array.isArray(r.tags) && r.tags.length ? r.tags : ['General']
        const matchCat = catFilter === 'all' || tags.includes(catFilter)
        return matchSource && matchCat
      }),
    [rows, sourceFilter, catFilter]
  )

  const sorted = useMemo(() => {
    const list = [...filtered]
    list.sort((a, b) => {
      const va = a[sortKey] ?? (typeof a[sortKey] === 'string' ? '' : -Infinity)
      const vb = b[sortKey] ?? (typeof b[sortKey] === 'string' ? '' : -Infinity)
      if (typeof va === 'string' || typeof vb === 'string') {
        const cmp = String(va).localeCompare(String(vb))
        return sortDir === 'desc' ? -cmp : cmp
      }
      return sortDir === 'desc' ? vb - va : va - vb
    })
    return list
  }, [filtered, sortKey, sortDir])

  const toggleSort = key => {
    setSortDir(prev => (sortKey === key && prev === 'desc' ? 'asc' : 'desc'))
    setSortKey(key)
  }

  return (
    <div id="rootInner">
      <h1>Prediction Markets</h1>
      <div className="filters">
        <label>
          Source:
          <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}>
            <option value="all">All</option>
            {sources.map(s => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Category:
          <select value={catFilter} onChange={e => setCatFilter(e.target.value)}>
            <option value="all">All</option>
            {categories.map(c => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <table className="market-table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Market</th>
              <th>Source</th>
              <th>Category</th>
              <th onClick={() => toggleSort('price')}>Last Price</th>
              <th>24hr Price</th>
              <th onClick={() => toggleSort('changePct')}>% Change (24h)</th>
              <th onClick={() => toggleSort('volume')}>Volume (Contracts)</th>
              <th onClick={() => toggleSort('dollarVolumeCalc')}>Dollar Volume (24h)</th>
              <th>Expiration</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(r => (
              <tr key={r.market_id}>
                <td>{r.event_name}</td>
                <td>{r.market_name}</td>
                <td>{r.source}</td>
                <td>{(Array.isArray(r.tags) && r.tags[0]) || 'General'}</td>
                <td>{formatPrice(r.price)}</td>
                <td>{formatPrice(r.price24h)}</td>
                <td>{formatChange(r.changePct)}</td>
                <td>{r.volume != null ? r.volume.toLocaleString() : '—'}</td>
                <td>
                  {r.dollarVolumeCalc != null
                    ? r.dollarVolumeCalc.toLocaleString()
                    : '—'}
                </td>
                <td>{formatDate(r.expiration)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

