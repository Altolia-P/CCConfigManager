// ============================================================
// CCConfigManager — Entry Point
// ============================================================

import { state } from './state'
import { showToast } from './utils'
import { loadItems, loadStats, loadProjects, loadPacks } from './api'
import { renderSidebar } from './ui/sidebar'
import { renderList, selectItemSafe, renderStats, applyLocalFilter } from './ui/items'
import { loadProjectItems, applyFilterAndRender } from './ui/projects'
import { loadPackItems } from './ui/packs'

// --- Search ---
const searchInput = document.getElementById('search') as HTMLInputElement
searchInput.addEventListener('input', () => {
  if (state.timer) clearTimeout(state.timer)
  state.timer = setTimeout(() => {
    state.search = searchInput.value.trim()
    state.selected = null
    if (state.project) {
      applyFilterAndRender()
    } else if (state.pack) {
      applyLocalFilter()
    } else {
      loadItems().then(() => { renderList(); renderStats() })
    }
  }, 300)
})

// --- Keyboard ---
document.addEventListener('keydown', (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); searchInput.focus() }
  if (e.key === 'Escape' && document.activeElement === searchInput) {
    if (state.timer) { clearTimeout(state.timer); state.timer = null }
    searchInput.value = ''; state.search = ''
    if (state.project) loadProjectItems()
    else if (state.pack) loadPackItems()
    else loadItems().then(() => { renderList(); renderStats() })
  }
})

// --- Theme ---
const STORAGE_KEY = 'ccconfigmanager-theme'
function getTheme(): string {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}
function applyTheme(theme: string): void {
  document.documentElement.setAttribute('data-theme', theme)
  const btn = document.getElementById('themeToggle')
  if (btn) btn.textContent = theme === 'dark' ? '☾' : '☀'
}
const currentTheme = getTheme()
applyTheme(currentTheme)

document.getElementById('themeToggle')!.addEventListener('click', () => {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'
  localStorage.setItem(STORAGE_KEY, next)
  applyTheme(next)
})

// --- Global helpers for inline onclick ---
;(window as any)._selectItem = selectItemSafe
// Expose packs for workflow properties panel
Object.defineProperty(window, '__packs', { get: () => state.packs, enumerable: true })

// --- Boot ---
// Default to skills if no type selected (first visit)
if (!state.type) state.type = 'skill'

Promise.all([loadStats(), loadItems()]).then(() => {
  renderSidebar()
  renderList()
  renderStats()
  // Load projects/packs in background after main data
  loadProjects().then(() => renderSidebar()).catch(() => {})
  loadPacks().then(() => renderSidebar()).catch(() => {})
})
