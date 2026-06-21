// ============================================================
// Run Panel — displays workflow execution progress
// ============================================================

import { showToast } from '../utils'
import { state } from '../state'

let pollTimer: ReturnType<typeof setInterval> | null = null
let pollCount = 0
const MAX_POLLS = 300  // 10 minutes at 2s interval

export function showRunPanel(runId: string, workflowName: string): void {
  // Find or create the run panel container below the detail panel
  let rp = document.getElementById('runPanel')
  if (!rp) {
    rp = document.createElement('div')
    rp.id = 'runPanel'
    rp.className = 'run-panel'
    const detailPanel = document.getElementById('detailPanel')
    if (detailPanel) {
      detailPanel.after(rp)
    } else {
      document.querySelector('.content')?.appendChild(rp)
    }
  }

  rp.innerHTML = `
    <div class="run-header">
      <span class="run-title">▶ ${workflowName} — 执行中</span>
      <span class="run-id">${runId}</span>
      <button class="btn" id="btnRunClose" style="font-size:16px;padding:0 4px">✕</button>
    </div>
    <div class="run-body" id="runBody">
      <div class="loading"><div class="spinner"></div>连接执行引擎...</div>
    </div>`
  rp.style.display = ''

  // Bind close
  document.getElementById('btnRunClose')!.onclick = () => {
    stopPolling()
    rp!.style.display = 'none'
  }

  // Start polling
  startPolling(runId)
}

function startPolling(runId: string): void {
  stopPolling()
  pollCount = 0
  pollTimer = setInterval(() => poll(runId), 2000)
  poll(runId)
}

function stopPolling(): void {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; pollCount = 0 }
}

async function poll(runId: string): Promise<void> {
  if (++pollCount > MAX_POLLS) {
    stopPolling()
    const body = document.getElementById('runBody')
    if (body) body.innerHTML = '<div class="empty">轮询超时（10分钟）— <button class="btn" onclick="window.location.reload()">刷新页面</button></div>'
    return
  }
  try {
    const r = await fetch(`/api/runs/${runId}`)
    const json = await r.json()
    if (!json.success) {
      document.getElementById('runBody')!.innerHTML =
        `<div class="empty">Run 不存在或已过期</div>`
      stopPolling()
      return
    }
    renderRun(json.data)
    if (json.data.status === 'completed' || json.data.status === 'failed' || json.data.status === 'cancelled') {
      stopPolling()
      const title = document.querySelector('.run-title')!
      if (json.data.status === 'completed') {
        title.innerHTML = `✅ ${json.data.workflow_slug} — 完成`
      } else if (json.data.status === 'failed') {
        const err = json.data.error || ''
        const isApiKeyErr = err.includes('API Key') || err.includes('ANTHROPIC_API_KEY')
        title.innerHTML = `❌ ${json.data.workflow_slug} — 失败`
        if (isApiKeyErr) {
          const body = document.getElementById('runBody')!
          body.innerHTML += `<div style="margin-top:12px;padding:10px 12px;background:var(--bg-secondary);border-radius:6px;font-size:12px;line-height:1.6">
            <strong>💡 需要配置 API Key</strong><br>
            ${err.replace(/\n/g, '<br>')}<br>
            <button onclick="document.querySelector('.sidebar-agent-config')?.click()" style="margin-top:6px;font-size:11px;padding:4px 10px">⚙ 打开 Agent 配置</button>
          </div>`
        }
      }
    }
  } catch {
    document.getElementById('runBody')!.innerHTML =
      `<div class="empty">无法连接执行引擎</div>`
    stopPolling()
  }
}

function renderRun(data: any): void {
  const body = document.getElementById('runBody')!
  const nodes = data.nodes || {}
  const nodeIds = Object.keys(nodes)
  const icon: Record<string, string> = {
    pending: '○', running: '<span class="spinner" style="width:12px;height:12px;display:inline-block"></span>',
    completed: '✅', failed: '❌', waiting_approval: '⏸', waiting_confirmation: '🛑', waiting_question: '❓',
  }

  let h = `<div class="run-progress"><div class="run-progress-bar" style="width:${calcProgress(nodes)}%"></div></div>`
  h += '<div class="run-nodes">'
  for (const nid of nodeIds) {
    const n = nodes[nid]
    const ico = icon[n.status] || '○'
    const offset = n.status === 'completed' || n.status === 'failed' || n.status === 'running'
    h += `<div class="run-node ${n.status}">
      <span class="run-node-icon">${ico}</span>
      <span class="run-node-name">${nid}</span>
      <span class="run-node-status">${n.status || 'pending'}</span>
    </div>`
    if (offset && n.output) {
      h += `<details class="run-node-output"><summary>输出</summary><pre>${escHtml(n.output.substring(0, 2000))}</pre></details>`
    }
  }
  h += '</div>'

  if (data.status === 'waiting_approval') {
    h += `<div class="run-actions">
      <button class="btn primary" id="btnRunApprove">✅ 确认推进</button>
      <button class="btn" id="btnRunCancel" style="color:var(--color-archived)">✕ 取消</button>
    </div>`
  }

  if (data.status === 'waiting_confirmation') {
    h += `<div class="run-actions">
      <button class="btn primary" id="btnRunContinue">▶ 继续执行</button>
      <button class="btn" id="btnRunCancel" style="color:var(--color-archived)">✕ 取消</button>
    </div>`
  }

  if (data.status === 'waiting_question' && data.pending_question) {
    const pq = data.pending_question
    h += `<div class="run-question">
      <div class="run-question-header">❓ ${escHtml(pq.header || 'Agent 提问')}</div>
      <div class="run-question-text">${escHtml(pq.question || '')}</div>
      ${(pq.options && pq.options.length) ? renderQuestionOptions(pq.options) : ''}
      <div class="run-question-input">
        <textarea id="txtAnswer" rows="2" placeholder="输入你的回答..."></textarea>
        <div class="run-actions" style="margin-top:8px">
          <button class="btn primary" id="btnRunAnswer">✅ 回答并继续</button>
          <button class="btn" id="btnRunCancel" style="color:var(--color-archived)">✕ 取消</button>
        </div>
      </div>
    </div>`
  }

  // Monitoring section — show after run completes
  const isFinal = data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled'
  if (isFinal) {
    h += `<div class="run-monitor">
      <div class="run-monitor-tabs">
        <button class="monitor-tab active" data-tab="notifications">📬 通知</button>
        <button class="monitor-tab" data-tab="tasks">📋 任务</button>
        <button class="monitor-tab" data-tab="logs">📜 日志</button>
      </div>
      <div class="run-monitor-content" id="monitorContent">
        <div class="loading" style="padding:12px">加载中...</div>
      </div>
    </div>`
  }

  body.innerHTML = h

  // Bind monitoring tabs
  if (isFinal) {
    body.querySelectorAll('.monitor-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        body.querySelectorAll('.monitor-tab').forEach(t => t.classList.remove('active'))
        tab.classList.add('active')
        loadMonitorData(tab.getAttribute('data-tab')!)
      })
    })
    loadMonitorData('notifications')
  }

  // Bind actions
  document.getElementById('btnRunApprove')?.addEventListener('click', async () => {
    await fetch(`/api/runs/${data.id}/approve`, { method: 'POST' })
    startPolling(data.id)
  })
  document.getElementById('btnRunContinue')?.addEventListener('click', async () => {
    await fetch(`/api/runs/${data.id}/approve`, { method: 'POST' })
    startPolling(data.id)
  })
  document.getElementById('btnRunAnswer')?.addEventListener('click', async () => {
    const ta = document.getElementById('txtAnswer') as HTMLTextAreaElement
    const answer = (ta?.value || '').trim()
    if (!answer) return
    await fetch(`/api/runs/${data.id}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer }),
    })
    startPolling(data.id)
  })
  document.getElementById('btnRunCancel')?.addEventListener('click', async () => {
    await fetch(`/api/runs/${data.id}/cancel`, { method: 'POST' })
    stopPolling()
    document.getElementById('runPanel')!.style.display = 'none'
  })
}

function calcProgress(nodes: Record<string, any>): number {
  const ids = Object.keys(nodes)
  if (!ids.length) return 0
  const done = ids.filter(id => {
    const s = nodes[id].status
    return s === 'completed' || s === 'failed'
  }).length
  return Math.round((done / ids.length) * 100)
}

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderQuestionOptions(options: any[]): string {
  let h = '<div class="run-question-options">'
  for (const opt of options) {
    h += `<label class="run-question-option">
      <input type="radio" name="questionOption" value="${escHtml(opt.label || '')}" data-description="${escHtml(opt.description || '')}">
      <span><strong>${escHtml(opt.label || '')}</strong>${opt.description ? '<br><small>' + escHtml(opt.description) + '</small>' : ''}</span>
    </label>`
  }
  h += '</div>'
  return h
}

async function loadMonitorData(tab: string): Promise<void> {
  const mc = document.getElementById('monitorContent')
  if (!mc) return
  mc.innerHTML = '<div class="loading" style="padding:12px"><div class="spinner"></div>加载中...</div>'

  try {
    let data: any
    if (tab === 'notifications') {
      const r = await fetch('/api/notifications')
      data = await r.json()
      const items = data.notifications || []
      if (!items.length) { mc.innerHTML = '<div class="empty">暂无通知</div>'; return }
      mc.innerHTML = items.map((n: any) =>
        `<div class="monitor-item"><span class="monitor-time">${escHtml((n.timestamp || '').substring(0, 19))}</span> ${escHtml(n.message || '')}</div>`
      ).join('')
    } else if (tab === 'tasks') {
      const r = await fetch('/api/tasks')
      data = await r.json()
      const items = data.tasks || []
      if (!items.length) { mc.innerHTML = '<div class="empty">暂无任务</div>'; return }
      mc.innerHTML = items.map((t: any) =>
        `<div class="monitor-item"><span class="monitor-status status-${t.status || 'pending'}">${t.status || 'pending'}</span> ${escHtml(t.subject || '')}</div>`
      ).join('')
    } else if (tab === 'logs') {
      const r = await fetch('/api/logs')
      data = await r.json()
      const items = data.slice?.(0, 30) || []
      if (!items.length) { mc.innerHTML = '<div class="empty">暂无操作日志</div>'; return }
      mc.innerHTML = items.map((l: any) =>
        `<div class="monitor-item monitor-log">${escHtml(typeof l === 'string' ? l : JSON.stringify(l)).substring(0, 300)}</div>`
      ).join('')
    }
  } catch {
    mc.innerHTML = '<div class="empty">加载失败</div>'
  }
}
