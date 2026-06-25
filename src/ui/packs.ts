// ============================================================
// Pack management — CRUD + view + import/export
// ============================================================

import { state } from '../state'
import { esc, escJs, showToast } from '../utils'
import { loadPacks, addPackItem, removePackItem, batchLoadItems, createPack } from '../api'
import type { ConfigItem } from '../types'
import { renderList, applyLocalFilter } from './items'
import { renderSidebar } from './sidebar'

export async function createPackFlow(name: string): Promise<void> {
  const ok = await createPack(name)
  if (ok) { state.pack = name; loadPacks().then(() => renderSidebar()) }
}

export async function addToPack(item: ConfigItem): Promise<void> {
  if (!state.packs || !Object.keys(state.packs).length) { showToast('请先在侧边栏创建配置包', 'error'); return }
  const names = Object.keys(state.packs)
  let target: string | null = names.length === 1 ? names[0] : null
  if (!target) {
    target = prompt(`添加到哪个包？\n${names.join(', ')}`, names[0])
    if (!target || !state.packs[target]) return
  }
  const ok = await addPackItem(target, item.type, item.name)
  if (ok) loadPacks().then(() => renderSidebar())
}

export async function removeFromPack(item: ConfigItem): Promise<void> {
  if (!state.pack) return
  const ok = await removePackItem(state.pack, item.type, item.name)
  if (ok) loadPackItems()
}

export function exportPack(name: string): void {
  window.open(`/api/packs/${encodeURIComponent(name)}/export`, '_blank')
}

export async function loadPackItems(): Promise<void> {
  if (!state.pack) return
  const pack = state.packs[state.pack]
  if (!pack) { state.items = []; renderList(); return }

  const listPanel = document.getElementById('listPanel')
  if (listPanel) listPanel.innerHTML = '<div class="loading"><div class="spinner"></div>加载中...</div>'

  const reqItems: { type: string; name: string }[] = []
  for (const typeKey of ['skills', 'agents', 'commands', 'rules', 'mcps', 'tools', 'workflows']) {
    for (const name of (pack as any)[typeKey] || []) {
      reqItems.push({ type: typeKey.replace(/s$/, ''), name })
    }
  }
  const allItems = reqItems.length ? await batchLoadItems(reqItems) : []
  state._allItems = allItems
  state.search = '';
  (document.getElementById('search') as HTMLInputElement).value = ''
  applyLocalFilter()
  renderPackStats()
}

export function renderPackStats(): void {
  const pack = state.pack ? state.packs[state.pack] : null
  if (!pack) return
  const total = (pack.skills || []).length + (pack.agents || []).length + (pack.commands || []).length + (pack.rules || []).length + (pack.mcps || []).length + (pack.tools || []).length + (pack.workflows || []).length
  const statusbar = document.getElementById('statusbar')
  if (statusbar) {
    statusbar.innerHTML = `📦 ${esc(state.pack)} &middot; ${total} 项 &middot; Skills:${(pack.skills || []).length} Agents:${(pack.agents || []).length} Commands:${(pack.commands || []).length} Rules:${(pack.rules || []).length} &middot; <button class="btn" style="font-size:10px;padding:1px 6px" id="btnExportPack">📤 导出</button> <button class="btn primary" style="font-size:10px;padding:1px 6px" id="btnInstallPackToProject">📥 安装到项目</button>`
    document.getElementById('btnExportPack')?.addEventListener('click', () => exportPack(state.pack))
    document.getElementById('btnInstallPackToProject')?.addEventListener('click', () => showInstallPackDialog())
  }
}

export function showInstallPackDialog(): void {
  if (!state.pack) return
  const projectNames = Object.keys(state.projects)
  if (!projectNames.length) { showToast('请先在侧边栏创建项目', 'error'); return }

  const pack = state.packs[state.pack]
  const total = (pack.skills || []).length + (pack.agents || []).length + (pack.commands || []).length + (pack.rules || []).length + (pack.mcps || []).length + (pack.tools || []).length + (pack.workflows || []).length

  let target: string | null = projectNames.length === 1 ? projectNames[0] : null
  if (!target) {
    target = prompt(`安装 "${state.pack}" (${total} 项) 到哪个项目？\n${projectNames.join(', ')}`, projectNames[0])
    if (!target || !state.projects[target]) return
  }

  const btn = document.getElementById('btnInstallPackToProject') as HTMLButtonElement | null
  if (btn) { btn.disabled = true; btn.textContent = '安装中...' }
  import('../api').then(m => m.importPackToProject(target!, state.pack!)).then(result => {
    if (btn) { btn.disabled = false; btn.textContent = '📥 安装到项目' }
    if (result.success) {
      import('../api').then(m => m.loadProjects()).then(() => renderSidebar())
    }
  })
}
