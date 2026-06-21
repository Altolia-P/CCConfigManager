// ============================================================
// Project management — CRUD + view + auto-discovery
// ============================================================

import { state, TYPES } from '../state'
import { esc, escAttr, escJs, showToast, sourceStyle } from '../utils'
import { loadProjects, addProjectItem, discoverProject, batchLoadItems, createProject, loadItem } from '../api'
import type { ConfigItem } from '../types'
import { selectItemSafe } from './items'
import { renderSidebar } from './sidebar'

const TYPE_LABELS: Record<string, string> = { skill: 'Skills', agent: 'Agents', command: 'Commands', rule: 'Rules', mcp: 'MCPs', tool: 'Tools', workflow: 'Workflows', hook: 'Hooks' }
const TYPE_ICONS: Record<string, string> = { skill: '✨', agent: '🤖', command: '⌨', rule: '📜', mcp: '🔌', tool: '🔧', workflow: '⚙', hook: '🪝' }
const TYPE_ORDER = ['skill', 'agent', 'command', 'rule', 'mcp', 'tool', 'workflow', 'hook']

export async function createProjectFlow(name: string, path: string): Promise<void> {
  const ok = await createProject(name, path)
  if (ok) {
    await loadProjects()
    state.project = name; state.type = ''
    renderSidebar()
    loadProjectItems()
  }
}

export async function addToProject(item: ConfigItem): Promise<void> {
  if (!state.projects || !Object.keys(state.projects).length) {
    showToast('请先在侧边栏底部创建项目', 'error'); return
  }
  const projNames = Object.keys(state.projects)
  let targetName: string | null = projNames.length === 1 ? projNames[0] : null
  if (!targetName) {
    targetName = prompt(`关联到哪个项目？\n${projNames.join(', ')}`, projNames[0])
    if (!targetName || !state.projects[targetName]) return
  }
  const ok = await addProjectItem(targetName, item.type, item.name)
  if (ok) loadProjects().then(() => renderSidebar())
}

export async function loadProjectItems(): Promise<void> {
  if (!state.project) return
  const proj = state.projects[state.project]
  if (!proj) { state.items = []; renderProjectSections(); return }

  const listPanel = document.getElementById('listPanel')
  if (listPanel) listPanel.innerHTML = '<div class="loading"><div class="spinner"></div>加载项目配置...</div>'

  try {
    const reqItems: { type: string; name: string }[] = []
    for (const typeKey of ['skills', 'agents', 'commands', 'rules', 'mcps', 'tools', 'workflows', 'hooks']) {
      for (const name of (proj as any)[typeKey] || []) {
        reqItems.push({ type: typeKey.replace(/s$/, ''), name })
      }
    }
    const allItems = reqItems.length ? await batchLoadItems(reqItems) : []
    state._allItems = allItems
    state.search = '';
    (document.getElementById('search') as HTMLInputElement).value = ''
    applyFilterAndRender()

    // Auto-discover new references
    const d = await discoverProject(state.project)
    if (d.added > 0) {
      showToast(d.message, 'success')
      loadProjects().then(() => { loadProjectItems() })
    }
  } catch (_) {
    if (listPanel) listPanel.innerHTML = '<div class="error-state">加载失败</div>'
  }
}

export function applyFilterAndRender(): void {
  if (!state._allItems) return
  const q = state.search.toLowerCase()
  state.items = state._allItems.filter(i => {
    if (q && !i.name.toLowerCase().includes(q) && !(i.description || '').toLowerCase().includes(q)) return false
    if (state.source && i.source !== state.source) return false
    if (state.status && i.status !== state.status) return false
    return true
  })
  renderProjectSections()
}

export function renderProjectSections(): void {
  const panel = document.getElementById('listPanel')
  if (!panel) return

  if (!state.items.length && !(state as any)._allItems?.length) {
    panel.innerHTML = `<div class="empty">
      <div class="empty-icon">📁</div>项目 <strong>${esc(state.project)}</strong> 中暂无关联配置
      <div style="font-size:12px;color:var(--text-secondary);margin-top:8px">
        点击下方按钮批量添加，或在全局类型列表中点击详情页的 <strong>📁 关联到项目</strong>
      </div>
    </div>
    <div style="display:flex;justify-content:center;padding:12px">
      <button class="btn primary" id="btnProjectAddConfigs">📥 添加配置</button>
    </div>`
  } else {
    // Group items by type
    const grouped: Record<string, ConfigItem[]> = {}
    for (const item of state.items) {
      (grouped[item.type] ||= []).push(item)
    }

    let h = `<div class="project-toolbar">
      <span class="project-toolbar-title">📁 ${esc(state.project)}</span>
      <span class="project-toolbar-count">${(state as any)._allItems?.length ?? state.items.length} 项</span>
      <span style="flex:1"></span>
      <button class="btn primary" id="btnProjectAddConfigs" style="font-size:11px;padding:4px 12px">📥 添加配置</button>
    </div>`

    for (const typeKey of TYPE_ORDER) {
      const items = grouped[typeKey] || []
      const proj = state.projects[state.project]
      const totalInProj = proj ? ((proj as any)[typeKey + 's'] || []).length : 0
      // Show section even if no items match current filter (but project HAS items of this type)
      const sectionEmpty = items.length === 0 && totalInProj === 0
      if (sectionEmpty) continue
      const collapsed = false
      const label = TYPE_LABELS[typeKey] || typeKey
      const icon = TYPE_ICONS[typeKey] || '•'

      h += `<div class="proj-section" data-section="${typeKey}">
        <div class="proj-section-header" data-toggle="${typeKey}">
          <span class="proj-section-toggle">▼</span>
          <span>${icon} ${label}</span>
          <span class="proj-section-count">${totalInProj}</span>
          ${items.length === 0 && totalInProj > 0 ? '<span style="font-size:10px;color:var(--text-secondary);margin-left:4px">(搜索无匹配)</span>' : ''}
        </div>
        <div class="proj-section-body">`

      if (items.length === 0) {
        h += `<div style="padding:8px 16px;font-size:12px;color:var(--text-secondary)">搜索无匹配项</div>`
      } else {
        for (const item of items) {
          const sel = state.selected && state.selected.type === item.type && state.selected.name === item.name
          h += `<div class="list-item${sel ? ' selected' : ''}" data-type="${item.type}" data-name="${escAttr(item.name)}" role="option" onclick="window._selectItem('${item.type}','${escJs(item.name)}')">
            <div class="item-header">
              <span class="status-dot ${item.status}" title="${item.status === 'active' ? '活跃' : '隔离'}"></span>
              <span class="item-name">${esc(item.name)}</span>
              <span class="source-tag ${item.source}">${item.source}</span>
            </div>
            ${item.description ? `<div class="item-desc">${esc(item.description.substring(0, 80))}</div>` : ''}
          </div>`
        }
      }
      h += `</div></div>`
    }
    panel.innerHTML = h

    // Bind collapse toggle
    panel.querySelectorAll<HTMLElement>('.proj-section-header').forEach(header => {
      header.onclick = () => {
        const body = header.nextElementSibling as HTMLElement
        const toggle = header.querySelector('.proj-section-toggle')!
        if (body) {
          body.style.display = body.style.display === 'none' ? '' : 'none'
          toggle.textContent = body.style.display === 'none' ? '▶' : '▼'
        }
      }
    })

    // Apply source tag colors
    panel.querySelectorAll<HTMLElement>('.source-tag').forEach(el => {
      const src = el.className.replace('source-tag', '').trim()
      el.setAttribute('style', sourceStyle(src))
    })
  }

  // Bind add-configs button
  document.getElementById('btnProjectAddConfigs')?.addEventListener('click', () => showAddConfigDialog())

  renderProjectStats()

  // Scroll selected into view
  const selEl = panel.querySelector('.list-item.selected')
  if (selEl) selEl.scrollIntoView({ block: 'nearest' })
}

export function renderProjectStats(): void {
  const proj = state.project && state.projects ? state.projects[state.project] : null
  if (!proj) return
  const byType: Record<string, number> = {}
  const all = (state as any)._allItems || state.items
  all.forEach((i: any) => { byType[i.type] = (byType[i.type] || 0) + 1 })
  const parts = [`路径: ${esc(proj.path)}`]
  for (const t of TYPE_ORDER) {
    const c = byType[t] || 0
    if (c) parts.push(`${TYPE_LABELS[t]}:${c}`)
  }
  const mc = (proj.mcps || []).length, wf = (proj.workflows || []).length, hk = (proj.hooks || []).length
  if (mc && !byType['mcp']) parts.push(`MCPs:${mc}`)
  if (wf && !byType['workflow']) parts.push(`Workflows:${wf}`)
  if (hk && !byType['hook']) parts.push(`Hooks:${hk}`)
  const statusbar = document.getElementById('statusbar')
  if (statusbar) statusbar.innerHTML = parts.join(' &middot; ')
}

export async function showAddConfigDialog(): Promise<void> {
  if (!state.project) return

  // Build current project's item set
  const proj = state.projects[state.project]
  const existing: Record<string, Set<string>> = {}
  for (const tk of ['skills', 'agents', 'commands', 'rules', 'mcps', 'tools', 'workflows', 'hooks']) {
    existing[tk] = new Set((proj as any)[tk] || [])
  }

  // Show modal with loading state
  const ov = document.createElement('div')
  ov.className = 'overlay'
  ov.innerHTML = `<div class="dialog" style="max-width:640px;max-height:80vh;display:flex;flex-direction:column">
    <div class="dialog-header" style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)">
      <strong>添加配置到 ${esc(state.project)}</strong>
      <button class="btn" id="btnAddConfigClose" style="font-size:18px;padding:0 6px">✕</button>
    </div>
    <div style="display:flex;gap:1px;padding:8px 12px;background:var(--bg-secondary)" id="addConfigTabs"></div>
    <div style="flex:1;overflow-y:auto;padding:12px;min-height:200px" id="addConfigList">
      <div class="loading"><div class="spinner"></div>加载中...</div>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:8px;padding:12px 16px;border-top:1px solid var(--border)">
      <span style="font-size:11px;color:var(--text-secondary);margin-right:auto" id="addConfigSelected">已选 0 项</span>
      <button class="btn" id="btnAddConfigCancel">取消</button>
      <button class="btn primary" id="btnAddConfigConfirm">批量添加</button>
    </div>
  </div>`
  document.body.appendChild(ov)

  // Close handlers
  const close = () => ov.remove()
  ov.querySelector('#btnAddConfigClose')!.addEventListener('click', close)
  ov.querySelector('#btnAddConfigCancel')!.addEventListener('click', close)
  ov.addEventListener('click', (e: Event) => { if (e.target === ov) close() })

  // Load all items from API
  let allItems: ConfigItem[] = []
  try {
    const resp = await fetch('/api/items?type=skills&status=active&limit=500')
    const skills = await resp.json()
    allItems = [...skills]
    for (const cat of ['agents', 'commands', 'rules', 'mcps', 'tools', 'workflows', 'hooks']) {
      const r = await fetch(`/api/items?type=${cat}&status=active&limit=500`)
      const items = await r.json()
      allItems = allItems.concat(items)
    }
  } catch (_) {
    ov.querySelector('#addConfigList')!.innerHTML = '<div class="error-state">加载失败</div>'
    return
  }

  // Group by type, filter out already-in-project
  const grouped: Record<string, ConfigItem[]> = {}
  for (const item of allItems) {
    const ek = item.type + 's'
    if (existing[ek]?.has(item.name)) continue
    (grouped[item.type] ||= []).push(item)
  }

  const typeKeys = TYPE_ORDER.filter(k => (grouped[k] || []).length > 0)
  if (!typeKeys.length) {
    ov.querySelector('#addConfigList')!.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-secondary)">所有配置已添加到此项目 ✅</div>'
    return
  }

  let activeTab = typeKeys[0]
  const renderTabList = () => {
    const tabsEl = ov.querySelector('#addConfigTabs')!
    tabsEl.innerHTML = typeKeys.map(k => {
      const count = (grouped[k] || []).length
      const icon = TYPE_ICONS[k] || '•'
      return `<button class="wf-tab${k === activeTab ? ' active' : ''}" data-tab="${k}" style="font-size:11px;border:none;background:transparent;padding:4px 10px;cursor:pointer;border-radius:4px">${icon} ${TYPE_LABELS[k]} (${count})</button>`
    }).join('')
    tabsEl.querySelectorAll<HTMLElement>('[data-tab]').forEach(btn => {
      btn.onclick = () => { activeTab = btn.dataset.tab!; renderTabList(); renderTabItems() }
    })
  }

  const selectedSet = new Set<string>()
  const renderTabItems = () => {
    const listEl = ov.querySelector('#addConfigList')!
    const items = grouped[activeTab] || []
    if (!items.length) {
      listEl.innerHTML = '<div style="text-align:center;padding:16px;color:var(--text-secondary)">无可添加项</div>'
    } else {
      listEl.innerHTML = items.map(item => {
        const key = `${item.type}/${item.name}`
        const checked = selectedSet.has(key)
        return `<label class="add-config-item" style="display:flex;align-items:center;gap:8px;padding:6px 8px;cursor:pointer;border-radius:4px">
          <input type="checkbox" value="${escAttr(item.name)}" data-type="${item.type}"${checked ? ' checked' : ''}>
          <span style="font-size:11px;color:var(--text-secondary)">${TYPE_ICONS[item.type] || '•'}</span>
          <span style="font-size:13px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(item.name)}</span>
          <span class="source-tag ${item.source}" style="font-size:10px;padding:1px 5px;border-radius:3px">${item.source}</span>
        </label>`
      }).join('')

      // Bind checkboxes
      listEl.querySelectorAll<HTMLInputElement>('input[type=checkbox]').forEach(cb => {
        cb.onchange = () => {
          const key = `${cb.dataset.type}/${cb.value}`
          if (cb.checked) selectedSet.add(key)
          else selectedSet.delete(key)
          ov.querySelector('#addConfigSelected')!.textContent = `已选 ${selectedSet.size} 项`
        }
      })

      // Apply source colors
      listEl.querySelectorAll<HTMLElement>('.source-tag').forEach(el => {
        const src = el.className.replace('source-tag', '').trim()
        el.setAttribute('style', sourceStyle(src))
      })
    }
  }

  // Select all checkbox
  const selectAll = () => {
    const items = grouped[activeTab] || []
    for (const item of items) {
      selectedSet.add(`${item.type}/${item.name}`)
    }
    renderTabItems()
    ov.querySelector('#addConfigSelected')!.textContent = `已选 ${selectedSet.size} 项`
  }

  renderTabList()
  renderTabItems()

  // Confirm
  ov.querySelector('#btnAddConfigConfirm')!.addEventListener('click', async () => {
    if (selectedSet.size === 0) { showToast('未选择任何项', 'error'); return }
    const btn = ov.querySelector('#btnAddConfigConfirm') as HTMLButtonElement
    btn.disabled = true; btn.textContent = '添加中...'

    let added = 0
    for (const key of selectedSet) {
      const [itemType, itemName] = key.split('/', 2)
      const ok = await addProjectItem(state.project, itemType, itemName)
      if (ok) added++
    }
    close()
    showToast(`已添加 ${added}/${selectedSet.size} 项`, added > 0 ? 'success' : 'error')
    loadProjects().then(() => { renderSidebar(); loadProjectItems() })
  })
}
