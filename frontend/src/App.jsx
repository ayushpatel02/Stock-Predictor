import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import Disclaimer from './components/Disclaimer.jsx'
import Backtest from './pages/Backtest.jsx'
import Dashboard from './pages/Dashboard.jsx'
import StockDetail from './pages/StockDetail.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-slate-900 text-slate-200">
        {/* Top nav */}
        <header className="border-b border-slate-700 px-6 py-3 flex items-center gap-4">
          <a href="/" className="text-xl font-bold text-indigo-400 hover:text-indigo-300">
            Nifty50 Predictor
          </a>
          <span className="text-xs text-slate-400 hidden sm:block">
            Decision-support tool · Not financial advice
          </span>
        </header>

        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/stock/:symbol" element={<StockDetail />} />
            <Route path="/backtest/:symbol" element={<Backtest />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        <Disclaimer />
      </div>
    </BrowserRouter>
  )
}
