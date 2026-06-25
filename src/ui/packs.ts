// ============================================================
// Pack management — CRUD + view + import/export
// ============================================================

import { state } from '../state'
import { esc, escAttr, escJs, showToast } from '../utils'
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
    statusbar.innerHTML = `📦 ${esc(state.pack)} &middot; ${total} 项 &middot; Skills:${(pack.skills || []).length} Agents:${(pack.agents || []).length} Commands:${(pack.commands || []).length} Rules:${(pack.rules || []).length} &middot; <button class="btn" style="font-size:10px;padding:1px 6px" id="btnExportPack">📤 导出</button> <button class="btn primary" style="font-size:10px;padding:1px 6px" id="btnInstallPackToProject">📥 安装到项目</button> <button class="btn primary" style="font-size:10px;padding:1px 6px;background:var(--color-superpowers);border-color:var(--color-superpowers)" id="btnApplyPack">🚀 应用到项目</button>`
    document.getElementById('btnExportPack')?.addEventListener('click', () => exportPack(state.pack))
    document.getElementById('btnInstallPackToProject')?.addEventListener('click', () => showInstallPackDialog())
    document.getElementById('btnApplyPack')?.addEventListener('click', () => showApplyPackDialog())
  }
}

export function showApplyPackDialog(): void {
  if (!state.pack) return
  const projectNames = Object.keys(state.projects)
  if (!projectNames.length) { showToast('请先在侧边栏创建项目', 'error'); return }

  const pack = state.packs[state.pack]
  const skillCount = (pack.skills || []).length
  const ruleCount = (pack.rules || []).length
  const cmdCount = (pack.commands || []).length

  let target: string | null = projectNames.length === 1 ? projectNames[0] : null
  const showPicker = !target

  let body = `<div style="padding:12px 16px">
    <div style="margin-bottom:12px">
      <strong>目标项目</strong>
      ${showPicker ? `<select id="applyPackTarget" style="width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:6px;margin-top:4px">${projectNames.map(n => `<option value="${escAttr(n)}">${esc(n)}</option>`).join('')}</select>`
      : `<div style="font-size:13px;padding:6px 8px;background:var(--bg-secondary);border-radius:6px;margin-top:4px">📁 ${esc(target!)}</div>`}
    </div>
    <div style="font-size:13px;color:var(--text-secondary);line-height:1.8">
      <strong>将执行以下操作:</strong><br>
      ${skillCount ? `• 在项目 CLAUDE.md 中写入 ${skillCount} 个 skill 触发路由<br>` : ''}
      ${ruleCount ? `• 复制 ${ruleCount} 个 rule 文件到项目<br>` : ''}
      ${cmdCount ? `• 复制 ${cmdCount} 个 command 文件到项目<br>` : ''}
    </div>
    <div style="font-size:11px;color:var(--text-secondary);margin-top:10px;padding:6px 8px;background:var(--bg-secondary);border-radius:4px">⚠️ 同名文件将被覆盖。CLAUDE.md 已有内容不受影响。</div>
  </div>`

  const ov = document.createElement('div')
  ov.className = 'overlay'
  ov.innerHTML = `<div class="dialog" style="max-width:440px">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)">
      <strong>🚀 应用到项目: ${esc(state.pack!)}</strong>
      <button class="btn" id="btnApplyPackClose" style="font-size:18px;padding:0 6px">✕</button>
    </div>
    ${body}
    <div style="display:flex;justify-content:flex-end;gap:8px;padding:12px 16px;border-top:1px solid var(--border)">
      <button class="btn" id="btnApplyPackCancel">取消</button>
      <button class="btn primary" id="btnApplyPackConfirm" style="background:var(--color-superpowers);border-color:var(--color-superpowers)">确认应用</button>
    </div>
  </div>`
  document.body.appendChild(ov)

  const close = () => ov.remove()
  ov.querySelector('#btnApplyPackClose')!.addEventListener('click', close)
  ov.querySelector('#btnApplyPackCancel')!.addEventListener('click', close)
  ov.addEventListener('click', (e: Event) => { if (e.target === ov) close() })

  ov.querySelector('#btnApplyPackConfirm')!.addEventListener('click', async () => {
    if (showPicker) {
      target = (ov.querySelector('#applyPackTarget') as HTMLSelectElement).value
      if (!target) return
    }
    const btn = ov.querySelector('#btnApplyPackConfirm') as HTMLButtonElement
    btn.disabled = true; btn.textContent = '应用中...'
    const result = await import('../api').then(m => m.applyPackToProject(state.pack!, target!))
    if (result.success) {
      import('../api').then(m => m.loadProjects()).then(() => renderSidebar())
    }
    close()
  })
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
