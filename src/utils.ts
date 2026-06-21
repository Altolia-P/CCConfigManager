// ============================================================
// Utility functions
// ============================================================

export const $ = <T extends HTMLElement>(s: string): T | null => document.querySelector(s) as T | null
export const $$ = <T extends HTMLElement>(s: string): T[] => [...document.querySelectorAll(s)] as T[]

export async function fetchJSON<T = any>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(String(r.status))
  return r.json()
}

export function esc(s: unknown): string {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

export function escAttr(s: unknown): string {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

export function escJs(s: unknown): string {
  return String(s ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n')
}

export function trunc(s: unknown, max: number): string {
  const str = String(s ?? '')
  if (max <= 0) return '…'
  return str.length > max ? str.slice(0, max) + '…' : str
}

// Source tag coloring
const SOURCE_COLORS = ['#7c3aed','#059669','#2563eb','#ea580c','#0891b2','#9333ea','#c2410c','#4f46e5','#0d9488','#b91c1c','#1e40af','#a21caf']
const SOURCE_BG = ['#ede9fe','#d1fae5','#dbeafe','#fff7ed','#cffafe','#f3e8ff','#fff1f2','#eef2ff','#ccfbf1','#fef2f2','#dbeafe','#fae8ff']

export function sourceStyle(source: string): string {
  let h = 0
  for (let i = 0; i < source.length; i++) h = ((h << 5) - h) + source.charCodeAt(i)
  const idx = Math.abs(h) % SOURCE_COLORS.length
  return `background:${SOURCE_BG[idx]};color:${SOURCE_COLORS[idx]}`
}

export function applySourceStyles(root: Document | HTMLElement = document): void {
  root.querySelectorAll('.source-tag').forEach(el => {
    const src = (el as HTMLElement).className.replace('source-tag', '').trim()
    el.setAttribute('style', sourceStyle(src))
  })
}

// Toast notification
let toastTimer: ReturnType<typeof setTimeout>
export function showToast(msg: string, type: 'success' | 'error'): void {
  const t = document.getElementById('toast')
  if (!t) return
  t.textContent = msg
  t.className = `toast ${type} show`
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { t.className = 'toast' }, 2500)
}
