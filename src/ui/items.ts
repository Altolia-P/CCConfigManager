// ============================================================
// List panel, item detail, selection, search filtering
// ============================================================

import { state, API } from '../state'
import { $, esc, escAttr, escJs, applySourceStyles, showToast } from '../utils'
import { loadItem, saveItem, moveItem, loadStats } from '../api'
import type { ConfigItem } from '../types'
import { addToProject } from './projects'
import { addToPack, removeFromPack } from './packs'
import { initWorkflowEditor } from '../workflow/integration'
import { WF } from '../workflow/engine'

// --- List ---
export function renderList(): void {
  const panel = document.getElementById('listPanel')
  if (!panel) return

  if (!state.items.length) {
    if (state.project) {
      panel.innerHTML = `<div class="empty"><div class="empty-icon">📁</div><div><strong>${esc(state.project)}</strong> 中暂无关联配置</div><div style="font-size:12px;color:var(--text-muted);margin-top:4px">在全局类型列表点击详情，选择 <strong>📁 关联到项目</strong> 即可添加</div></div>`
    } else if (state.pack) {
      panel.innerHTML = `<div class="empty"><div class="empty-icon">📦</div><div>配置包 <strong>${esc(state.pack)}</strong> 中暂无配置</div><div style="font-size:12px;color:var(--text-muted);margin-top:4px">在全局类型列表点击详情，选择 <strong>📦 加到包</strong> 即可添加</div></div>`
    } else if (!state.search && !state.type && !state.source && !state.status) {
      // First-time user: no items at all, no filters active
      panel.innerHTML = `<div class="empty">
        <div class="empty-icon">👋</div>
        <div style="font-size:14px;font-weight:600;margin:8px 0">欢迎使用 CCConfigManager</div>
        <div style="font-size:12px;color:var(--text-muted);line-height:1.6;max-width:360px;text-align:center">
          你的 <code style="background:var(--bg-secondary);padding:1px 4px;border-radius:2px">~/.claude/</code> 目录中还没有配置文件。
        </div>
        <div style="margin-top:16px;text-align:left;font-size:12px;color:var(--text-secondary);line-height:1.8">
          <strong>快速开始：</strong><br>
          1. 在 Claude Code 中运行 <strong>/init</strong> 生成项目配置<br>
          2. 手动在 <code style="background:var(--bg-secondary);padding:1px 4px;border-radius:2px">~/.claude/</code> 下创建 Skills/Agents<br>
          3. 或安装 ECC/Gstack/Superpowers 等配置集
        </div>
        <div style="margin-top:12px;font-size:11px;color:var(--text-muted)">
          配置就绪后，刷新页面即可自动发现
        </div>
      </div>`
    } else {
      panel.innerHTML = `<div class="empty"><div class="empty-icon">🔍</div>没有找到匹配项<div style="font-size:12px;color:var(--text-muted);margin-top:4px">试试其他搜索词或清除筛选</div></div>`
    }
    return
  }

  panel.innerHTML = state.items.map(item => {
    const sel = state.selected && state.selected.type === item.type && state.selected.name === item.name
    return `<div class="list-item${sel ? ' selected' : ''}" data-type="${item.type}" data-name="${escAttr(item.name)}" role="option" aria-selected="${sel}" onclick="window._selectItem('${item.type}','${escJs(item.name)}')">
      <div class="item-header">
        <span class="status-dot ${item.status}" title="${item.status === 'active' ? '活跃' : '隔离'}"></span>
        <span class="item-name">${esc(item.name)}</span>
        <span class="source-tag ${item.source}">${item.source}</span>
      </div>
      ${item.description ? `<div class="item-desc">${esc(item.description.substring(0, 80))}</div>` : ''}
    </div>`
  }).join('')
  applySourceStyles(panel)

  const selEl = panel.querySelector('.list-item.selected')
  if (selEl) selEl.scrollIntoView({ block: 'nearest' })
}

// --- Local filter (project/pack search) ---
export function applyLocalFilter(): void {
  if (!state._allItems) return
  const q = state.search.toLowerCase()
  state.items = state._allItems.filter(i => {
    if (q && !i.name.toLowerCase().includes(q) && !(i.description || '').toLowerCase().includes(q)) return false
    if (state.source && i.source !== state.source) return false
    if (state.status && i.status !== state.status) return false
    return true
  })
  renderList()
}

// --- Item selection ---
export function selectItemSafe(type: string, name: string): void {
  if (WF.isDirty() && WF.canvasWrap?.innerHTML && state.selected?.type === 'workflow') {
    if (!confirm('当前工作流有未保存的修改。\n确定=放弃修改并继续\n取消=留在此页')) return
  }
  selectItem(type, name)
}

function refreshList(): void {
  if (state.project) {
    import('./projects').then(m => m.renderProjectSections())
  } else {
    renderList()
  }
}

export async function selectItem(type: string, name: string): Promise<void> {
  const cached = state.items.find(i => i.type === type && i.name === name)
  if (cached) { state.selected = cached; renderDetail(cached); refreshList(); return }

  const detailPanel = document.getElementById('detailPanel')
  if (detailPanel) detailPanel.innerHTML = '<div class="loading"><div class="spinner"></div>加载详情...</div>'

  const item = await loadItem(type, name)
  if (item) { state.selected = item; renderDetail(item); refreshList() }
  else if (detailPanel) detailPanel.innerHTML = '<div class="empty">未找到该项目</div>'
}

// --- Detail panel ---
export function renderDetail(item: ConfigItem): void {
  const detailPanel = document.getElementById('detailPanel')
  if (!detailPanel) return

  if (item.type !== 'workflow') detailPanel.classList.remove('wf-active')

  const toLabel = item.status === 'active' ? '隔离区' : '活跃区'
  const toStatus = item.status === 'active' ? 'archived' : 'active'
  const content = item.content_preview || ''
  const isReadOnly = item.type === 'mcp' || item.type === 'tool' || item.type === 'hook'
  const isWorkflow = item.type === 'workflow'

  detailPanel.innerHTML = `
    <div class="detail-section"><h3>详情</h3>
      <div class="detail-row"><span class="detail-label">名称</span>${esc(item.name)}</div>
      <div class="detail-row"><span class="detail-label">类型</span>${item.type}</div>
      <div class="detail-row"><span class="detail-label">来源</span><span class="source-tag ${item.source}">${item.source}</span></div>
      ${!isReadOnly ? `<div class="detail-row"><span class="detail-label">状态</span><span class="status-dot ${item.status}" style="display:inline-block"></span> ${item.status === 'active' ? '活跃' : '隔离'}</div>` : ''}
      ${item.type === 'agent' ? '<div class="detail-row" id="agentModelInfo"><span class="detail-label">模型</span><span style="font-size:12px;color:var(--text-muted)">加载中...</span></div>' : ''}
    </div>
    <div class="detail-section"><h3>${isReadOnly ? '配置文件' : '路径'}</h3><div class="detail-path">${esc(item.path)}</div></div>
    <div class="detail-section"><h3>描述</h3>
      <textarea id="editDesc" style="width:100%;min-height:48px;font-size:13px;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg-secondary);color:var(--text);resize:vertical;font-family:inherit;line-height:1.5">${esc(item.description || '')}</textarea>
    </div>
    ${isWorkflow ? `<div class="detail-section"><h3>工作流编辑器</h3><div class="wf-canvas-wrap" id="wfCanvasWrap"><div class="loading"><div class="spinner"></div>加载画布...</div></div></div>
    <div class="detail-section" id="wfRunStatus"><h3>执行状态</h3><span style="font-size:12px;color:var(--text-muted)">加载中...</span></div>`
    : item.type === 'mcp' ? `<div class="detail-section"><h3>Server 配置</h3><pre class="preview-box">${esc(content)}</pre></div>`
    : isReadOnly ? `<div class="detail-section"><h3>详情</h3><pre class="preview-box">${esc(content)}</pre></div>`
    : `<div class="detail-section"><h3>内容编辑</h3><textarea id="editContent" style="width:100%;min-height:300px;font-family:'Cascadia Code','Fira Code',monospace;font-size:12px;padding:12px;border:1px solid var(--border);border-radius:4px;resize:vertical;background:var(--bg-secondary);color:var(--text);line-height:1.5;tab-size:2">${esc(content)}</textarea></div>`}
    <div class="actions">
      ${!isWorkflow && item.type !== 'tool' && item.type !== 'hook' ? '<button class="btn primary" id="btnSaveDesc">💾 保存描述</button>' : ''}
      ${isWorkflow ? '<button class="btn primary" id="btnWfSave">💾 保存</button><button class="btn" id="btnFitView">⊡ 适应画布</button><button class="btn" id="btnWfFullscreen">⛶ 展开全屏</button><button class="btn" id="btnWfDelete" style="color:var(--color-archived)">🗑 删除</button>' : ''}
      ${!isReadOnly && !isWorkflow ? '<button class="btn primary" id="btnSave">💾 保存</button>' : ''}
      ${!isReadOnly && !isWorkflow ? `<button class="btn primary" id="btnMove">↗ 移到${toLabel}</button>` : ''}
      ${!isReadOnly && !isWorkflow && state.pack ? '<button class="btn" id="btnRemoveFromPack" style="color:var(--color-archived)">📤 从包中移除</button>' : ''}
      ${!isReadOnly && !isWorkflow && !state.pack ? '<button class="btn" id="btnAddToProject">📁 关联到项目</button><button class="btn" id="btnAddToPack">📦 加到包</button>' : ''}
      <button class="btn" id="btnCopy">📋 复制路径</button>
    </div>`
  applySourceStyles(detailPanel)

  // Bind actions
  const editDesc = document.getElementById('editDesc') as HTMLTextAreaElement | null
  const btnSaveDesc = document.getElementById('btnSaveDesc') as HTMLButtonElement | null
  if (editDesc && btnSaveDesc) {
    btnSaveDesc.onclick = async () => {
      btnSaveDesc.disabled = true; btnSaveDesc.textContent = '保存中...'
      const ok = await saveItem(item.type, item.name, undefined, editDesc.value)
      showToast(ok ? '已保存' : '保存失败', ok ? 'success' : 'error')
      if (ok) { item.description = editDesc.value; state.selected = item }
      btnSaveDesc.disabled = false; btnSaveDesc.textContent = '💾 保存描述'
    }
  }

  const editEl = document.getElementById('editContent') as HTMLTextAreaElement | null
  const btnSave = document.getElementById('btnSave') as HTMLButtonElement | null
  if (editEl && btnSave) {
    btnSave.onclick = async () => {
      btnSave.disabled = true; btnSave.textContent = '保存中...'
      const ok = await saveItem(item.type, item.name, editEl.value)
      showToast(ok ? '已保存' : '保存失败', ok ? 'success' : 'error')
      if (ok) { item.content_preview = editEl.value; state.selected = item }
      btnSave.disabled = false; btnSave.textContent = '💾 保存'
    }
    editEl.addEventListener('keydown', (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); btnSave.click() }
    })
  }

  document.getElementById('btnMove')?.addEventListener('click', () => showConfirm(item, toStatus))
  document.getElementById('btnAddToProject')?.addEventListener('click', () => addToProject(item))
  document.getElementById('btnAddToPack')?.addEventListener('click', () => addToPack(item))
  document.getElementById('btnRemoveFromPack')?.addEventListener('click', () => removeFromPack(item))
  document.getElementById('btnCopy')?.addEventListener('click', () => {
    navigator.clipboard.writeText(item.path)
    showToast('已复制路径', 'success')
  })

  // Agent model info — async load
  if (item.type === 'agent') {
    fetch(`/api/agent-config/${encodeURIComponent(item.name)}`)
      .then(r => r.json()).then(d => {
        const el = document.getElementById('agentModelInfo')
        if (el && d.success && d.data?.model) {
          const cfg = d.data
          let info = `<span style="font-size:12px;font-weight:500;color:var(--color-superpowers)">${esc(cfg.model)}</span>`
          if (cfg.base_url) info += ` <span style="font-size:10px;color:var(--text-muted)">via ${esc(cfg.base_url)}</span>`
          el.innerHTML = `<span class="detail-label">模型</span>${info}`
        } else if (el) {
          el.innerHTML = '<span class="detail-label">模型</span><span style="font-size:11px;color:var(--text-muted)">默认 (ANTHROPIC_API_KEY)</span>'
        }
      }).catch(() => {})
  }

  // Workflow canvas init
  if (isWorkflow) {
    const init = () => {
      if (item.raw_content) {
        initWorkflowEditor(item)
      } else {
        // Fallback: fetch full detail to get raw_content
        import('../api').then(m => m.loadItem(item.type, item.name)).then(full => {
          if (full?.raw_content) { item.raw_content = full.raw_content; initWorkflowEditor(item) }
          else if (detailPanel) detailPanel.innerHTML = '<div class="empty">工作流数据加载失败</div>'
        })
      }
    }
    init()
    // Load last run status asynchronously
    loadWfRunStatus(item.name)
  }
}

// --- Workflow run status ---
async function loadWfRunStatus(slug: string): Promise<void> {
  const el = document.getElementById('wfRunStatus')
  if (!el) return
  try {
    const r = await fetch('/api/runs')
    const runs: any[] = await r.json()
    const wfRuns = runs.filter((run: any) => run.workflow_slug === slug)
    if (wfRuns.length === 0) {
      el.innerHTML = '<h3>执行状态</h3><span style="font-size:12px;color:var(--text-muted)">暂无执行记录</span>'
      return
    }
    const last = wfRuns[0]
    const statusIcon = last.status === 'completed' ? '✅' : last.status === 'failed' ? '❌' : last.status === 'running' ? '🔄' : '⏸'
    const statusLabel = last.status === 'completed' ? '成功' : last.status === 'failed' ? '失败' : last.status === 'running' ? '运行中' : '已暂停'
    let durStr = ''
    if (last.started_at && last.finished_at) {
      const dur = Math.round((new Date(last.finished_at).getTime() - new Date(last.started_at).getTime()) / 1000)
      durStr = dur >= 60 ? `${Math.floor(dur / 60)}分${dur % 60}秒` : `${dur}秒`
    } else if (last.started_at && last.status === 'running') {
      durStr = '进行中'
    }
    const msg = last.error ? `<br><span style="font-size:10px;color:var(--color-archived)">${esc(last.error)}</span>` : ''
    const initMsg = last.initial_message ? `<br><span style="font-size:10px;color:var(--text-muted)">触发: ${esc((last.initial_message || '').substring(0, 80))}${last.initial_message.length > 80 ? '...' : ''}</span>` : ''
    el.innerHTML = `<h3>执行状态</h3>
      <div style="font-size:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        ${statusIcon} <strong>${statusLabel}</strong>
        <span style="color:var(--text-muted)">${new Date(last.started_at).toLocaleString()}</span>
        ${durStr ? `<span style="color:var(--text-muted)">⏱ ${durStr}</span>` : ''}
        ${msg}${initMsg}
      </div>`
  } catch (_) {
    el.innerHTML = '<h3>执行状态</h3><span style="font-size:12px;color:var(--text-muted)">加载失败</span>'
  }
}

// --- Confirm dialog ---
function showConfirm(item: ConfigItem, toStatus: string): void {
  const label = toStatus === 'archived' ? '隔离区' : '活跃区'
  const ov = document.createElement('div')
  ov.className = 'overlay'
  ov.innerHTML = `<div class="dialog"><p>将 <strong>${esc(item.name)}</strong> 移到${label}？</p><div class="dialog-actions"><button class="btn" id="btnCancel">取消</button><button class="btn primary" id="btnConfirm">确认</button></div></div>`
  document.body.appendChild(ov)
  ov.querySelector('#btnCancel')!.addEventListener('click', () => ov.remove())
  ov.querySelector('#btnConfirm')!.addEventListener('click', async () => { ov.remove(); await doMove(item, toStatus) })
}

async function doMove(item: ConfigItem, toStatus: string): Promise<void> {
  const btn = document.getElementById('btnMove') as HTMLButtonElement | null
  if (btn) btn.disabled = true
  const ok = await moveItem(item.type, item.name, toStatus)
  showToast(ok ? '已移动' : '移动失败', ok ? 'success' : 'error')
  if (ok) { state.selected = null; await Promise.all([import('../api').then(m => m.loadItems()), import('../api').then(m => m.loadStats())]); renderList(); renderStats() }
  if (btn) btn.disabled = false
}

// --- Stats bar ---
export function renderStats(): void {
  const statusbar = document.getElementById('statusbar')
  if (!statusbar) return
  if (state.project) { import('./projects').then(m => m.renderProjectStats()); return }
  if (!state.stats) return
  let total = 0, ac = 0, ar = 0
  Object.values(state.stats).forEach(st => { ac += st.active || 0; ar += st.archived || 0; total += (st.active || 0) + (st.archived || 0) })
  const unk = state.items.filter(i => i.source === 'unknown').length
  statusbar.innerHTML = `共 ${total} 项 &middot; 活跃 ${ac} &middot; 隔离 ${ar}${unk ? ` &middot; <span class="warn">未知来源 ${unk}</span>` : ''}`
}
