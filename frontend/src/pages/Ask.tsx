import { ArrowUp, Info, Mic, Square, Volume2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnnouncementCard } from '../components/AnnouncementCard'
import { CitedText } from '../components/Cited'
import { Delta } from '../components/ui'
import { api, type ChatReply, type Digest } from '../services/api'
import { crore, multiple } from '../utils/format'

type Turn = { role: 'user'; text: string } | { role: 'finn'; reply?: ChatReply; error?: string; pending?: boolean }

const SUGGESTIONS = (sym: string | null) => [
  'What are the most important developments in my portfolio today?',
  sym ? `Why did ${sym}'s volume increase?` : 'Why did RELIANCE volume spike?',
  `Compare the last four quarters of revenue${sym ? '' : ' for SUZLON'}`,
  'What did management promise in the last earnings call?',
  'Did the company achieve its guided growth?',
  'What are the biggest risks disclosed in the annual report?',
]

// Minimal typing for the Web Speech API (not in TypeScript's DOM lib).
type Recognition = { lang: string; interimResults: boolean; onresult: (e: { results: { 0: { transcript: string } }[] }) => void; onend: () => void; onerror: () => void; start: () => void; stop: () => void }
const SpeechRec: (new () => Recognition) | undefined =
  (window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition }).SpeechRecognition
  ?? (window as unknown as { webkitSpeechRecognition?: new () => Recognition }).webkitSpeechRecognition

export function AskPage() {
  const [params, setParams] = useSearchParams()
  const symbol = params.get('symbol')
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [listening, setListening] = useState(false)
  const rec = useRef<Recognition | null>(null)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns])

  async function send(text: string) {
    const msg = text.trim()
    if (!msg) return
    setInput('')
    setTurns((t) => [...t, { role: 'user', text: msg }, { role: 'finn', pending: true }])
    try {
      const reply = await api.post<ChatReply>('/api/research/chat', { message: msg, symbol })
      if (reply.symbol && reply.symbol !== symbol) setParams({ symbol: reply.symbol }, { replace: true })
      setTurns((t) => [...t.slice(0, -1), { role: 'finn', reply }])
    } catch (e) {
      setTurns((t) => [...t.slice(0, -1), { role: 'finn', error: (e as Error).message }])
    }
  }

  function toggleMic() {
    if (!SpeechRec) return
    if (listening) {
      rec.current?.stop()
      return
    }
    const r = new SpeechRec()
    r.lang = 'en-IN'
    r.interimResults = false
    r.onresult = (e) => void send(e.results[0][0].transcript)
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    rec.current = r
    setListening(true)
    r.start()
  }

  return (
    <div className="flex min-h-[calc(100dvh-9rem)] flex-col">
      <div className="mb-3 flex items-start gap-2">
        <div className="flex-1">
          <h1 className="text-xl font-bold tracking-tight">Ask FINN</h1>
          <p className="text-xs text-ink-3">
            {symbol ? <>Talking about <span className="font-semibold text-ink-2">{symbol}</span> · <button onClick={() => setParams({})} className="underline underline-offset-2">clear</button></> : 'About your portfolio, or any company by name'}
          </p>
        </div>
        <BriefAloud />
      </div>

      <div className="flex-1 space-y-4">
        {turns.length === 0 && (
          <div className="space-y-2">
            {SUGGESTIONS(symbol).map((s) => (
              <button key={s} onClick={() => void send(s)} className="block w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-left text-sm text-ink-2 hover:text-ink">{s}</button>
            ))}
          </div>
        )}
        {turns.map((t, i) => t.role === 'user'
          ? <p key={i} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-ink px-3.5 py-2 text-sm text-page">{t.text}</p>
          : <Answer key={i} turn={t} />)}
        <div ref={end} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); void send(input) }}
        className="sticky bottom-[4.5rem] mt-4 flex items-center gap-2 rounded-2xl border border-line bg-surface p-1.5 shadow-sm">
        {SpeechRec && (
          <button type="button" onClick={toggleMic} aria-label={listening ? 'Stop listening' : 'Ask by voice'} aria-pressed={listening}
            className={`grid size-9 shrink-0 place-items-center rounded-xl ${listening ? 'bg-accent-fill text-[#0b0b0b]' : 'text-ink-2 hover:bg-surface-2'}`}>
            {listening ? <Square size={14} aria-hidden /> : <Mic size={17} aria-hidden />}
          </button>
        )}
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={listening ? 'Listening…' : 'Ask about a company or your portfolio'}
          aria-label="Your question" className="h-9 min-w-0 flex-1 bg-transparent px-1 text-[15px] outline-none" maxLength={600} />
        <button disabled={!input.trim()} aria-label="Send" className="grid size-9 shrink-0 place-items-center rounded-xl bg-ink text-page disabled:opacity-30">
          <ArrowUp size={17} aria-hidden />
        </button>
      </form>
    </div>
  )
}

function Answer({ turn }: { turn: Extract<Turn, { role: 'finn' }> }) {
  if (turn.pending) return <div className="skeleton h-16 w-3/4" aria-label="FINN is answering" />
  if (turn.error) return <p className="text-sm text-down">{turn.error}</p>
  const r = turn.reply!
  return (
    <div className="space-y-2.5">
      <CitedText segments={r.segments} className="text-[15px]" />
      {r.table && (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="num w-full text-xs">
            <thead className="bg-surface-2 text-ink-3"><tr>{r.table.columns.map((c) => <th key={c} className="px-2.5 py-2 text-right font-medium first:text-left">{c}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {r.table.rows.map((row, i) => (
                <tr key={i}>{row.map((v, j) => (
                  <td key={j} className="px-2.5 py-2 text-right first:text-left">
                    {j === 0 ? v : v == null ? '—' : j === 4 ? `${v}%` : crore(v as number)}
                  </td>))}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {r.moves && r.moves.length > 0 && (
        <ul className="space-y-1.5">
          {r.moves.map((m) => (
            <li key={m.id} className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs">
              <span className="font-semibold">{m.symbol}</span>
              <span className="text-ink-3">{m.kind === 'volume' ? 'volume' : 'price'}</span>
              <span className="ml-auto">{m.kind === 'volume' ? multiple(m.value) : <Delta value={m.value} />}</span>
            </li>
          ))}
        </ul>
      )}
      {r.cards.length > 0 && <div className="space-y-2">{r.cards.map((a) => <AnnouncementCard key={a.id} a={a} compact />)}</div>}
      {r.basis && <p className="flex items-start gap-1.5 text-[11px] text-ink-3"><Info size={12} className="mt-px shrink-0" aria-hidden />{r.basis}{r.model ? ` · ${r.model}` : ''}</p>}
    </div>
  )
}

/** Reads today's must-reads aloud: a 60-second brief while you commute. Uses the browser's own voice. */
function BriefAloud() {
  const [speaking, setSpeaking] = useState(false)
  if (!('speechSynthesis' in window)) return null
  async function play() {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const d = await api.get<Digest>('/api/intelligence/digest?hours=24').catch(() => null)
    if (!d) return
    const items = [...d.must_read, ...d.worth_a_look].slice(0, 5)
    const lines = [
      `Good ${new Date().getHours() < 12 ? 'morning' : 'day'}. ${d.counts.filings} filings in the last day; ${d.counts.high} must read.`,
      ...items.map((a) => `${a.company_name}. ${a.summary?.what_happened ?? a.title.replace(/Announcement under Regulation 30 \(LODR\)-/i, '')}.`),
      items.length ? 'That is everything that matters. The rest is routine.' : 'Nothing material. The rest is routine.',
    ]
    const u = new SpeechSynthesisUtterance(lines.join(' '))
    u.lang = 'en-IN'
    u.rate = 1.05
    u.onend = () => setSpeaking(false)
    setSpeaking(true)
    window.speechSynthesis.speak(u)
  }
  return (
    <button onClick={() => void play()} aria-pressed={speaking}
      className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border border-line px-3 text-xs font-medium text-ink-2">
      {speaking ? <Square size={12} aria-hidden /> : <Volume2 size={13} aria-hidden />} {speaking ? 'Stop' : 'Brief me'}
    </button>
  )
}
