// ============================================================
// Sidebar rendering and filter bindings
// ============================================================

import { state, TYPES, WORKFLOW_MODES, SOURCES, API } from '../state'
import { esc, escAttr, escJs, applySourceStyles } from '../utils'
import { loadItems, loadStats } from '../api'
import { loadProjectItems } from './projects'
import { loadPackItems } from './packs'
import { maybeLeaveWorkflow, newWorkflow } from '../workflow/integration'
import { deleteProject, deletePack, loadPacks } from '../api'

function newProjectDialog(): void {
  const name = prompt('项目名称：')
  if (!name?.trim()) return
  const path = prompt('项目路径（如 D:/Desktop/my-project）：')
  if (!path?.trim()) return
  import('./projects').then(m => m.createProjectFlow(name.trim(), path.trim()))
}

function newPackDialog(): void {
  const name = prompt('配置包名称（如：前端开发、Python工具集）：')
  if (!name?.trim()) return
  import('./packs').then(m => m.createPackFlow(name.trim()))
}

function doDeleteProject(name: string): void {
  if (!confirm(`确定删除项目 "${name}"？\n仅删除记录，不影响项目目录中的实际文件。`)) return
  deleteProject(name).then(ok => {
    if (ok) {
      if (state.project === name) { state.project = ''; state.items = []; import('./items').then(m => m.renderList()) }
      import('../api').then(m => m.loadProjects()).then(() => renderSidebar())
    }
  })
}

function doDeletePack(name: string): void {
  if (!confirm(`确定删除配置包 "${name}"？`)) return
  deletePack(name).then(ok => {
    if (ok) {
      if (state.pack === name) { state.pack = ''; state.items = []; import('./items').then(m => m.renderList()) }
      import('../api').then(m => m.loadPacks()).then(() => renderSidebar())
    }
  })
}

export function renderSidebar(): void {
  if (!state.stats) return
  const sidebar = document.getElementById('sidebar')
  if (!sidebar) return

  const TYPE_ICONS: Record<string, string> = { skill: '✨', agent: '🤖', command: '⌨', rule: '📜', mcp: '🔌', tool: '🔧', hook: '🪝' }
  let h = '<h3>配置类型</h3><div class="type-list">'
  TYPES.forEach(([k, label]) => {
    const st: any = state.stats![k] || {}
    const ac = st.active || 0, ar = st.archived || 0
    const icon = TYPE_ICONS[k] || '•'
    h += `<button class="type-item${state.type === k ? ' active' : ''}" data-type="${k}">${icon} ${label}<span class="count"><span class="ac">${ac}</span>${ar ? `<span class="ar">/${ar}</span>` : ''}</span></button>`
  })
  const wf: any = state.stats['workflow'] || {}
  const wfTotal = (wf.active || 0) + (wf.archived || 0)
  h += `<button class="type-item${state.type === 'workflow' && !state.wfMode ? ' active' : ''}" data-type="workflow">⚙ Workflows<span class="count">${wfTotal}</span></button>`
  h += '<button class="type-item" style="color:var(--color-superpowers);font-size:12px;padding-left:16px" id="btnNewWorkflow">+ 新建工作流</button>'
  WORKFLOW_MODES.forEach(([mode, label]) => {
    h += `<button class="type-item${state.type === 'workflow' && state.wfMode === mode ? ' active' : ''}" data-wfmode="${mode}" style="padding-left:28px;font-size:12px">${label}</button>`
  })
  h += '</div><h3>来源筛选</h3><div class="filters"><div class="filter-group">'
  SOURCES.forEach(([k, label]) => {
    h += `<label><input type="radio" name="sourceFilter" class="source-filter" value="${k}"${state.source === k ? ' checked' : ''}> <span class="source-tag ${k}">${label}</span></label>`
  })
  h += '</div></div><h3>状态筛选</h3><div class="filters"><div class="filter-group">'
  ;[['active', '活跃'], ['archived', '隔离']].forEach(([k, label]) => {
    h += `<label><input type="checkbox" class="status-filter" value="${k}"${state.status === k ? ' checked' : ''}> ${label}</label>`
  })
  h += '</div></div>'
  // Projects
  h += '<h3 style="margin-top:4px">项目</h3><div class="type-list" id="projectList">'
  Object.entries(state.projects).forEach(([name, proj]) => {
    const total = (proj.skills || []).length + (proj.agents || []).length + (proj.commands || []).length + (proj.rules || []).length + (proj.mcps || []).length + (proj.tools || []).length + (proj.workflows || []).length + (proj.hooks || []).length
    h += `<button class="type-item${state.project === name ? ' active' : ''}" data-project="${escAttr(name)}">${esc(name)}<span class="count">${total}</span><span class="sidebar-del" data-del-project="${escAttr(name)}" title="删除项目">×</span></button>`
  })
  h += '</div><button class="type-item" style="color:var(--color-superpowers);font-size:12px" id="btnNewProject">+ 新建项目</button>'
  // Packs
  h += '<h3 style="margin-top:8px">配置包</h3><div class="type-list">'
  Object.entries(state.packs).forEach(([name, pack]) => {
    const total = (pack.skills || []).length + (pack.agents || []).length + (pack.commands || []).length + (pack.rules || []).length + (pack.mcps || []).length + (pack.tools || []).length + (pack.workflows || []).length
    h += `<button class="type-item${state.pack === name ? ' active' : ''}" data-pack="${escAttr(name)}">📦 ${esc(name)}<span class="count">${total}</span><span class="sidebar-del" data-del-pack="${escAttr(name)}" title="删除包">×</span></button>`
  })
  h += '</div><button class="type-item" style="color:var(--color-superpowers);font-size:12px" id="btnNewPack">+ 新建配置包</button>'
  h += '<button class="type-item" style="color:var(--color-superpowers);font-size:12px" id="btnImport">📥 导入工作流/配置包</button>'
  h += '<button class="type-item sidebar-agent-config" style="color:var(--text-secondary);font-size:11px" id="btnAgentConfig">⚙ Agent 配置 (模型/Key)</button>'
  h += '<button class="type-item" style="color:var(--text-secondary);font-size:11px" id="btnRefreshMcp">🔄 刷新 MCP 工具</button>'
  h += '<input type="file" id="importFileInput" accept=".json" style="display:none">'

  sidebar.innerHTML = h
  applySourceStyles(sidebar)

  // Bind item clicks
  sidebar.querySelectorAll<HTMLElement>('.type-item').forEach(b => {
    if (b.dataset.wfmode) {
      b.onclick = () => {
        maybeLeaveWorkflow(() => {
          state.type = 'workflow'; state.wfMode = b.dataset.wfmode!; state.source = ''; state.project = ''; state.pack = ''; state.selected = null
          renderSidebar(); loadItems().then(() => { import('./items').then(m => { m.renderList(); m.renderStats() }) })
        })
      }
    } else if (b.dataset.type) {
      b.onclick = () => {
        maybeLeaveWorkflow(() => {
          state.type = b.dataset.type!; state.wfMode = ''; state.project = ''; state.pack = ''; state.selected = null
          renderSidebar(); loadItems().then(() => { import('./items').then(m => { m.renderList(); m.renderStats() }) })
        })
      }
    } else if (b.dataset.project) {
      b.onclick = () => {
        maybeLeaveWorkflow(() => {
          state.project = b.dataset.project!; state.type = ''; state.pack = ''; state.selected = null
          renderSidebar(); loadProjectItems()
        })
      }
    } else if (b.dataset.pack) {
      b.onclick = () => {
        maybeLeaveWorkflow(() => {
          state.pack = b.dataset.pack!; state.type = ''; state.project = ''; state.selected = null
          renderSidebar(); loadPackItems()
        })
      }
    }
  })

  // Specific button IDs
  document.getElementById('btnNewWorkflow')!.onclick = () => newWorkflow()
  document.getElementById('btnNewProject')!.onclick = () => newProjectDialog()
  document.getElementById('btnNewPack')!.onclick = () => newPackDialog()
  document.getElementById('btnImport')!.onclick = () => document.getElementById('importFileInput')!.click()
  document.getElementById('btnAgentConfig')!.onclick = () => showAgentConfigDialog()
  document.getElementById('btnRefreshMcp')!.onclick = async () => {
    await fetch('/api/mcp/refresh-tools', { method: 'POST' })
    import('../utils').then(u => u.showToast('MCP 工具刷新已启动', 'success'))
  }

  // Sidebar delete buttons
  sidebar.querySelectorAll<HTMLElement>('.sidebar-del').forEach(el => {
    el.onclick = (e: Event) => {
      e.stopPropagation()
      if (el.dataset.delProject) doDeleteProject(el.dataset.delProject)
      else if (el.dataset.delPack) doDeletePack(el.dataset.delPack!)
    }
  })

  // Source filter
  sidebar.querySelectorAll<HTMLInputElement>('.source-filter').forEach(cb => {
    cb.onchange = () => {
      state.source = cb.checked ? cb.value : ''
      sidebar.querySelectorAll<HTMLInputElement>('.source-filter').forEach((c: HTMLInputElement) => { if (c !== cb) c.checked = false })
      if (!cb.checked) state.source = ''
      if (state.project) {
        import('./projects').then(m => m.applyFilterAndRender())
      } else if (state.pack) {
        import('./items').then(m => m.applyLocalFilter())
      } else {
        loadItems().then(() => { import('./items').then(m => { m.renderList(); m.renderStats() }) })
      }
    }
  })

  // Status filter
  sidebar.querySelectorAll<HTMLInputElement>('.status-filter').forEach(cb => {
    cb.onchange = () => {
      if (!cb.checked) { cb.checked = true; state.status = cb.value; return }
      state.status = cb.value
      sidebar.querySelectorAll<HTMLInputElement>('.status-filter').forEach((c: HTMLInputElement) => { if (c !== cb) c.checked = false })
      if (state.project) {
        import('./projects').then(m => m.applyFilterAndRender())
      } else if (state.pack) {
        import('./items').then(m => m.applyLocalFilter())
      } else {
        loadItems().then(() => { import('./items').then(m => { m.renderList(); m.renderStats() }) })
      }
    }
  })

  // Import handler
  const importInput = document.getElementById('importFileInput') as HTMLInputElement
  if (importInput) {
    importInput.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      import('../api').then(m => m.importFile(file)).then(data => {
        import('../utils').then(util => util.showToast(data.message, data.success ? 'success' : 'error'))
        if (data.success) {
          if (data.type === 'workflow') { state.type = 'workflow'; loadItems(); loadStats() }
          else { loadPacks().then(() => renderSidebar()) }
        }
      })
      importInput.value = ''
    }
  }
}

async function showAgentConfigDialog(): Promise<void> {
  let agentOptions = '<option value="">选择 Agent...</option>'
  try {
    const r = await fetch(`${API}/api/items?type=agents&status=active`)
    const agents = await r.json()
    agentOptions += agents.map((a: any) => `<option value="${a.name}">${a.name}</option>`).join('')
  } catch (_) { /* empty list ok */ }

  const ov = document.createElement('div')
  ov.className = 'overlay'
  ov.innerHTML = `<div class="dialog" style="max-width:480px">
    <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)">
      <strong>⚙ Agent 配置</strong>
      <button class="btn" id="btnAgentCfgClose" style="font-size:18px;padding:0 6px">✕</button>
    </div>
    <div style="padding:12px 16px">
      <div style="font-size:12px;color:var(--text-secondary);margin-bottom:10px">为 Agent 单独指定模型、API Base URL 和 Key。</div>
      <div class="wf-field" style="margin-bottom:10px">
        <label>Agent</label>
        <select id="agentCfgName" style="padding:6px 8px;font-size:12px;border:1px solid var(--border);border-radius:6px;width:100%">${agentOptions}</select>
      </div>
      <div class="wf-field" style="margin-bottom:10px">
        <label>模型名称</label>
        <input id="agentCfgModel" placeholder="如 deepseek-v4-pro, claude-opus-4-7" style="padding:6px 8px;font-size:12px;border:1px solid var(--border);border-radius:6px;width:100%">
      </div>
      <div class="wf-field" style="margin-bottom:10px">
        <label>API Base URL（CCswitch 地址）</label>
        <input id="agentCfgBaseUrl" placeholder="如 http://localhost:3456/v1" style="padding:6px 8px;font-size:12px;border:1px solid var(--border);border-radius:6px;width:100%">
      </div>
      <div class="wf-field" style="margin-bottom:12px">
        <label>API Key</label>
        <input id="agentCfgKey" type="password" placeholder="留空则使用环境变量 ANTHROPIC_API_KEY" style="padding:6px 8px;font-size:12px;border:1px solid var(--border);border-radius:6px;width:100%">
      </div>
      <button class="btn primary" id="btnAgentCfgSave" style="width:100%">💾 保存</button>
    </div>
  </div>`
  document.body.appendChild(ov)

  const close = () => ov.remove()
  ov.querySelector('#btnAgentCfgClose')!.addEventListener('click', close)
  ov.addEventListener('click', (e: Event) => { if (e.target === ov) close() })

  // Load existing config when agent selected
  const nameSel = document.getElementById('agentCfgName') as HTMLSelectElement
  nameSel.addEventListener('change', async () => {
    const name = nameSel.value
    if (!name) return
    try {
      const r = await fetch(`/api/agent-config/${encodeURIComponent(name)}`)
      const data = await r.json()
      if (data.success && data.data) {
        const m = document.getElementById("agentCfgModel") as HTMLInputElement
        const u = document.getElementById("agentCfgBaseUrl") as HTMLInputElement
        m.value = (data.data as any).model || ""
        u.value = (data.data as any).base_url || ""
      }
    } catch (_) { /* no saved config */ }
  })
  document.getElementById('btnAgentCfgSave')!.addEventListener('click', async () => {
    const name = nameSel.value
    const model = (document.getElementById('agentCfgModel') as HTMLInputElement).value.trim()
    const baseUrl = (document.getElementById('agentCfgBaseUrl') as HTMLInputElement).value.trim()
    const key = (document.getElementById('agentCfgKey') as HTMLInputElement).value.trim()
    if (!name) { import('../utils').then(u => u.showToast('请选择 Agent', 'error')); return }
    if (!model) { import('../utils').then(u => u.showToast('请填写模型名称', 'error')); return }
    try {
      const body: Record<string, string> = { model }
      if (baseUrl) body.base_url = baseUrl
      if (key) body.api_key = key
      const r = await fetch(`/api/agent-config/${encodeURIComponent(name)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const data = await r.json()
      import('../utils').then(u => u.showToast(data.message || (data.success ? '已保存' : '保存失败'), data.success ? 'success' : 'error'))
      if (data.success) close()
    } catch (_) { import('../utils').then(u => u.showToast('保存失败', 'error')) }
  })
}
