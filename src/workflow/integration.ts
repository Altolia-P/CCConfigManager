// ============================================================
// Workflow Integration — connects WF engine to main app
// ============================================================

import { WF } from './engine'
import type { ConfigItem, WorkflowData } from '../types'
import { showToast } from '../utils'
import { state } from '../state'
import { loadItems, loadStats, deleteWorkflow, copyWorkflow } from '../api'

export function maybeLeaveWorkflow(action: () => void): void {
  if (WF.isDirty() && WF.canvasWrap?.innerHTML) {
    if (confirm('当前工作流有未保存的修改。\n确定=放弃修改并离开\n取消=留在当前页面')) {
      WF.destroy()
      action()
    }
  } else {
    if (WF.canvasWrap) WF.destroy()
    action()
  }
}

export function newWorkflow(): void {
  const name = prompt('工作流名称：')
  if (!name?.trim()) return
  const mode = confirm('使用 Step 阶段门禁模式？\n确定=Step，取消=Auto') ? 'step' : 'auto'
  import('../api').then(m => m.createWorkflow(name.trim(), mode)).then(ok => {
    if (ok) {
      state.type = 'workflow'
      Promise.all([loadItems(), loadStats()])
    }
  })
}

export function initWorkflowEditor(item: ConfigItem): void {
  let data: WorkflowData
  try {
    data = JSON.parse(item.raw_content!)
  } catch (_) {
    showToast('工作流 JSON 解析失败', 'error')
    return
  }

  if (!(data as any).nodes) {
    data = convertV1ToV2(data as any)
  }

  const panel = document.getElementById('detailPanel')!
  panel.classList.add('wf-active')
  WF.init(panel, data)

  // Fullscreen toggle
  const btnFs = document.getElementById('btnWfFullscreen')
  if (btnFs) {
    btnFs.onclick = () => {
      const sidebar = document.getElementById('sidebar')!, list = document.getElementById('listPanel')!, detail = document.getElementById('detailPanel')!
      if (detail.style.position === 'fixed') {
        detail.style.cssText = ''; sidebar.style.display = ''; list.style.display = ''; btnFs.textContent = '⛶ 展开全屏'
      } else {
        sidebar.style.display = 'none'; list.style.display = 'none'
        detail.style.cssText = 'position:fixed;inset:0;z-index:50;background:var(--bg);padding:16px;overflow:auto'
        btnFs.textContent = '⛶ 收起'
        setTimeout(() => WF.fitView(), 100)
      }
    }
  }

  // Shared save helper — validates references before saving
  async function saveWorkflow(btn: HTMLButtonElement, originalLabel: string) {
    btn.disabled = true; btn.textContent = '验证中...'
    try {
      const json = WF.toJSON()
      // Validate references against cached data
      const cachedAgents = WF._cachedAgents || []
      const cachedSkills = WF._cachedSkills || []
      const cachedMcps = WF._cachedMcps || []
      // If all caches are empty (network failure during preloadRefs), warn and skip validation
      if (cachedAgents.length || cachedSkills.length || cachedMcps.length) {
        const agentSet = new Set(cachedAgents.map((a: any) => a.slug))
        const skillSet = new Set(cachedSkills.map((s: any) => s.slug))
        const mcpSet = new Set(cachedMcps.map((m: any) => m.slug))
        const missingAgents: string[] = []
        const missingSkills: string[] = []
        const missingMcps: string[] = []
        for (const node of json.nodes) {
          if (node.agentId && !agentSet.has(node.agentId)) missingAgents.push(node.agentId)
          for (const sid of (node.skillIds || [])) { if (!skillSet.has(sid)) missingSkills.push(sid) }
          for (const mid of (node.mcpIds || [])) { if (!mcpSet.has(mid)) missingMcps.push(mid) }
        }
        const totalIssues = missingAgents.length + missingSkills.length + missingMcps.length
        if (totalIssues > 0) {
        const lines: string[] = []
        if (missingAgents.length) lines.push(`Agent 不存在: ${missingAgents.join(', ')}`)
        if (missingSkills.length) lines.push(`Skill 不存在: ${missingSkills.join(', ')}`)
        if (missingMcps.length) lines.push(`MCP 不存在: ${missingMcps.join(', ')}`)
        const ok = confirm(`⚠ 以下 ${totalIssues} 个引用可能失效:\n\n${lines.join('\n')}\n\n仍然保存吗？执行时可能失败。`)
        if (!ok) { btn.disabled = false; btn.textContent = originalLabel; return }
        }
      } else {
        import('../utils').then(u => u.showToast('无法加载参考数据（后端可能未运行），跳过引用验证', 'error'))
      }
      btn.textContent = '保存中...'
      const r = await fetch(`/api/item/workflows/${encodeURIComponent(item.name)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: JSON.stringify(json, null, 2) })
      })
      const resp = await r.json()
      showToast(resp.message, resp.success ? 'success' : 'error')
      if (resp.success) {
        const jstr = JSON.stringify(json, null, 2)
        item.content_preview = jstr; item.raw_content = jstr; item.description = json.description; state.selected = item
        WF.markClean()
      }
    } catch (_) { showToast('保存失败', 'error') }
    btn.disabled = false; btn.textContent = originalLabel
  }

  // Save button (canvas toolbar)
  const btnSaveCanvas = panel.querySelector('#btnWfSaveCanvas') as HTMLButtonElement
  if (btnSaveCanvas) {
    btnSaveCanvas.onclick = () => saveWorkflow(btnSaveCanvas, '💾 保存')
  }

  // Execute button
  panel.querySelector('#btnWfExecute')?.addEventListener('click', () => {
    promptExecute()
  })

  // Export button
  panel.querySelector('#btnWfExportCanvas')?.addEventListener('click', () => {
    window.open(`/api/workflows/${encodeURIComponent(item.name)}/export`, '_blank')
  })

  // Copy button
  panel.querySelector('#btnWfCopyCanvas')?.addEventListener('click', async () => {
    await copyWorkflow(item.name); loadItems(); loadStats()
  })

  // Delete button (canvas toolbar)
  panel.querySelector('#btnWfDeleteCanvas')?.addEventListener('click', () => {
    if (confirm(`确定删除工作流 "${item.name}"？\n此操作不可恢复。`)) {
      deleteWorkflow(item.name).then(ok => {
        if (ok) {
          panel.innerHTML = '<div class="empty-state"><div class="empty-icon">🗑</div>已删除</div>'
          panel.classList.remove('wf-active'); loadItems(); loadStats()
          showToast('已删除', 'success')
        }
      }).catch(() => showToast('删除失败', 'error'))
    }
  })

  // Detail panel buttons
  document.getElementById('btnFitView')?.addEventListener('click', () => WF.fitView())
  document.getElementById('btnWfDelete')?.addEventListener('click', () => {
    if (confirm(`确定删除工作流 "${item.name}"？\n此操作不可恢复。`)) {
      deleteWorkflow(item.name).then(ok => {
        if (ok) {
          const dp = document.getElementById('detailPanel')!
          dp.innerHTML = '<div class="empty-state"><div class="empty-icon">🗑</div>已删除</div>'
          dp.classList.remove('wf-active'); loadItems(); loadStats()
          showToast('已删除', 'success')
        }
      }).catch(() => showToast('删除失败', 'error'))
    }
  })
  const btnWfSaveEl = document.getElementById('btnWfSave') as HTMLButtonElement | null
  if (btnWfSaveEl) {
    btnWfSaveEl.onclick = () => saveWorkflow(btnWfSaveEl!, '💾 保存')
  }
}

function convertV1ToV2(data: any): WorkflowData {
  const nodes: any[] = [], edges: any[] = []
  const isStep = !!(data.phases && data.phases.length)
  const items = isStep ? data.phases : (data.steps || [])
  items.forEach((item: any, i: number) => {
    const id = (item.id || item.name || 'n' + (i + 1))
    const prev = i > 0 ? items[i - 1] : null
    nodes.push({
      id, type: (isStep && (item.manualAdvance || item.autoDetect)) ? 'gate' : 'agent',
      label: item.label || item.description || item.name || 'Step ' + (i + 1),
      position: { x: i * 280, y: 0 },
      packId: '', agentId: item.agentSlug || null, commandId: null,
      skillIds: item.skillIds || [], mcpIds: item.mcpIds || [], toolIds: item.toolIds || [],
      permissions: isStep ? { allows: item.allows || [], blocks: item.blocks || [] } : { allows: ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob', 'WebFetch', 'WebSearch'], blocks: [] },
      produces: item.produces || [], hooks: item.hooks || [], timeout: item.timeout || 10,
      gateConfig: (isStep && (item.manualAdvance || item.autoDetect)) ? { condition: item.manualAdvance ? 'manual' : 'auto', autoDetect: item.autoDetect || '', manualAdvance: item.manualAdvance || '', expression: '' } : undefined
    })
    if (prev) {
      // Edge condition derives from the PREVIOUS item (source of the edge)
      const isGate = isStep && (item.manualAdvance || item.autoDetect)
      edges.push({
        id: 'e' + i, from: prev.id || prev.name || ('n' + i), to: id,
        condition: isGate ? (item.manualAdvance ? 'manual' : 'auto') : 'auto',
        autoDetect: null, manualAdvance: null
      })
    }
  })
  return { slug: data.slug || '', name: data.name || '', description: data.description || '', mode: isStep ? 'step' : 'auto', nodes, edges } as WorkflowData
}

function promptExecute(): void {
  let overlay = document.getElementById('executePromptOverlay')
  if (!overlay) {
    overlay = document.createElement('div')
    overlay.id = 'executePromptOverlay'
    overlay.className = 'modal-overlay'
    overlay.innerHTML = `
      <div class="modal" style="max-width:480px">
        <div class="modal-header">▶ 执行工作流</div>
        <div class="modal-body">
          <label style="font-size:12px;color:var(--text-secondary)">给 Agent 的初始消息（可选）</label>
          <textarea id="txtInitialMessage" rows="3" placeholder="描述你想让 Agent 完成什么任务..." style="width:100%;margin-top:4px"></textarea>
        </div>
        <div class="modal-footer" style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn" id="btnCancelExecute">取消</button>
          <button class="btn primary" id="btnStartExecute">▶ 开始执行</button>
        </div>
      </div>`
    document.body.appendChild(overlay)
  }

  overlay.style.display = ''

  document.getElementById('btnCancelExecute')!.onclick = () => { overlay!.style.display = 'none' }
  overlay.onclick = (e) => { if (e.target === overlay) overlay!.style.display = 'none' }

  document.getElementById('btnStartExecute')!.onclick = async () => {
    const msg = (document.getElementById('txtInitialMessage') as HTMLTextAreaElement).value.trim()
    overlay!.style.display = 'none'
    const panel = document.querySelector('.detail-panel')
    const btn = panel?.querySelector('#btnWfExecute') as HTMLButtonElement
    if (btn) { btn.disabled = true; btn.textContent = '执行中...' }
    try {
      const r = await fetch('/api/workflows/execute', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_slug: WF.slug,
          project_name: state.project || '',
          max_tool_rounds: 30,
          message: msg,
        })
      })
      const resp = await r.json()
      if (resp.success) {
        showToast('工作流已启动', 'success')
        import('./run_panel').then(m => m.showRunPanel(resp.run_id, WF.wfName || WF.slug))
      } else {
        showToast(resp.message || '启动失败', 'error')
      }
    } catch (_) { showToast('启动执行失败', 'error') }
    if (btn) { btn.disabled = false; btn.textContent = '▶ 执行' }
  }
}
