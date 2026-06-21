// ============================================================
// Workflow Properties — node/edge/workflow property editing overlay
// ============================================================

import { esc, escAttr } from '../utils'
import { WF } from './engine'

const Q = (parent: HTMLElement, sel: string): HTMLElement => parent.querySelector(sel) as HTMLElement
const QA = (parent: HTMLElement, sel: string): HTMLInputElement => parent.querySelector(sel) as HTMLInputElement
const QS = (parent: HTMLElement, sel: string): HTMLSelectElement => parent.querySelector(sel) as HTMLSelectElement
const QB = (parent: HTMLElement, sel: string): HTMLButtonElement => parent.querySelector(sel) as HTMLButtonElement
const QTA = (parent: HTMLElement, sel: string): HTMLTextAreaElement => parent.querySelector(sel) as HTMLTextAreaElement

export function renderProps(this: typeof WF): void {
  if (!this.propsOverlay) return
  const selNode = this.nodes.find(n => n.id === this.selectedId)
  const selEdge = this.edges.find(e => e.id === this.selectedId)

  if (this.propsClose) this.propsClose.onclick = () => { this.propsOverlay!.classList.remove('open'); this.selectedId = null; this._lastPropsNode = null; this.render() }

  // --- Edge properties ---
  if (selEdge) {
    if (this._lastPropsNode === selEdge.id && this.propsOverlay.classList.contains('open')) return
    this._lastPropsNode = selEdge.id
    this.propsOverlay.classList.add('open')
    const e = selEdge
    if (!e.condition) e.condition = 'auto'
    const fromName = (this.nodes.find(n => n.id === e.from) || {}).label || e.from
    const toName = (this.nodes.find(n => n.id === e.to) || {}).label || e.to
    if (e.condition === 'expression') {
      e.condition = 'auto'
      import('../utils').then(u => u.showToast('此连线的表达式条件已迁移为自动。需要表达式判断请使用 Gate 闸门节点。', 'error'))
    }
    this.propsTitle!.textContent = '🔗 连线属性'
    this.propsBody!.innerHTML = `
      <div class="wf-field"><label>连接</label><div style="font-size:11px;color:var(--text-secondary)">${esc(fromName)} → ${esc(toName)}</div></div>
      <div class="wf-field"><label>流转方式</label>
        <div class="wf-radios" id="wfEdgeCond">
          <button data-cond="auto" class="${e.condition === 'auto' ? ' active' : ''}">自动</button>
          <button data-cond="manual" class="${e.condition === 'manual' ? ' active' : ''}">手动</button>
        </div>
      </div>
      <div class="wf-field" id="wfEdgeManual" style="display:${e.condition === 'manual' ? '' : 'none'}"><label>手动推进说明</label><input id="wfEdgeManualAdv" value="${escAttr(e.manualAdvance || '')}" placeholder="如: 确认后进入下一步"></div>
      <div style="font-size:10px;color:var(--text-secondary);margin-top:8px;line-height:1.4">💡 需要复杂判断？拖入 <b>🔷 Gate 闸门</b> 节点代替连线控制。</div>`

    const updateEdge = () => {
      e.manualAdvance = (this.propsBody!.querySelector('#wfEdgeManualAdv') as HTMLInputElement)?.value || ''
      this.updateStatus()
    }

    this.propsBody.querySelectorAll<HTMLButtonElement>('#wfEdgeCond button').forEach(btn => {
      btn.onclick = () => {
        e.condition = btn.dataset.cond as any
        ;(this.propsBody!.querySelectorAll('#wfEdgeCond button') as any as HTMLElement[]).forEach((b: HTMLElement) => b.classList.toggle('active', b === btn))
        ;(this.propsBody!.querySelector('#wfEdgeManual') as HTMLElement).style.display = e.condition === 'manual' ? '' : 'none'
        if (e.condition === 'manual') setTimeout(() => (this.propsBody!.querySelector('#wfEdgeManualAdv') as HTMLInputElement)?.focus(), 50)
        updateEdge()
      }
    })
    this.propsBody.querySelector('#wfEdgeManualAdv')?.addEventListener('input', updateEdge)
    return
  }

  // --- Workflow-level properties ---
  if (!selNode) {
    if (this._lastPropsNode === '__wf__' && this.propsOverlay.classList.contains('open')) return
    this._lastPropsNode = '__wf__'
    this.propsOverlay.classList.add('open')
    this.propsTitle!.textContent = '⚙ 工作流属性'
    this.propsBody!.innerHTML = `
      <div class="wf-field"><label>名称</label><input id="wfPropWfName" value="${escAttr(this.wfName || '')}" placeholder="工作流名称"></div>
      <div class="wf-field"><label>Slug</label><input id="wfPropWfSlug" value="${escAttr(this.slug || '')}" placeholder="文件名标识"></div>
      <div class="wf-field"><label>描述</label><textarea id="wfPropWfDesc" rows="3" placeholder="描述">${esc(this.description || '')}</textarea></div>
      <div class="wf-field"><label>模式</label>
        <div class="wf-radios" id="wfModeToggle">
          <button data-mode="auto" class="${this.mode === 'auto' ? ' active' : ''}">Auto 自动编排</button>
          <button data-mode="step" class="${this.mode === 'step' ? ' active' : ''}">Step 阶段门禁</button>
        </div>
        <div style="font-size:10px;color:var(--text-secondary);margin-top:4px" id="wfModeHint"></div>
      </div>`

    const updateWf = () => {
      this.wfName = (this.propsBody!.querySelector('#wfPropWfName') as HTMLInputElement)?.value || ''
      this.slug = (this.propsBody!.querySelector('#wfPropWfSlug') as HTMLInputElement)?.value || ''
      this.description = (this.propsBody!.querySelector('#wfPropWfDesc') as HTMLTextAreaElement)?.value || ''
      this.updateStatus()
    };
    (this.propsBody.querySelector('#wfPropWfName') as HTMLInputElement).oninput = updateWf;
    (this.propsBody.querySelector('#wfPropWfSlug') as HTMLInputElement).oninput = updateWf;
    (this.propsBody.querySelector('#wfPropWfDesc') as HTMLTextAreaElement).oninput = updateWf

    Array.from(this.propsBody!.querySelectorAll('#wfModeToggle button')).forEach((btn: HTMLElement) => {
      btn.onclick = () => {
        const newMode = btn.dataset.mode!
        if (newMode !== this.mode) {
          this.mode = newMode as any
          if (newMode === 'step') {
            this.nodes.forEach(n => {
              if (n.type === 'agent' || n.type === 'command') {
                if (!n.permissions) n.permissions = { allows: ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob', 'WebFetch', 'WebSearch'], blocks: [] }
                if (!n.produces) n.produces = []
                if (!n.hooks) n.hooks = []
              }
            })
          }
          (this.propsBody!.querySelectorAll('#wfModeToggle button') as any as HTMLElement[]).forEach((b: HTMLElement) => b.classList.toggle('active', b.dataset.mode === this.mode))
          const badge = this.canvasWrap?.querySelector('.wf-mode-badge') as HTMLElement
          if (badge) { badge.textContent = newMode === 'step' ? 'Step 阶段门禁' : 'Auto 自动编排'; badge.className = 'wf-mode-badge ' + newMode }
          const hint = this.propsBody!.querySelector('#wfModeHint') as HTMLElement
          hint.textContent = newMode === 'auto' ? 'Auto 自动编排 — 节点将自动依次执行' : '⚠ 已解锁 Gate 节点和手动连线控制'
          const gateBtn = this.sidebarEl?.querySelector('.wf-node-type-btn[data-add="gate"]') as HTMLElement
          if (gateBtn) gateBtn.style.display = newMode === 'step' ? '' : 'none'
          this.pushSnapshot()
        }
      }
    })
    return
  }

  // --- Node properties ---
  if (this._lastPropsNode === selNode.id && this.propsOverlay.classList.contains('open')) return
  this._lastPropsNode = selNode.id
  this.propsOverlay.classList.add('open')
  const n = selNode

  if (n.type === 'agent') {
    this.propsTitle!.textContent = '📋 节点属性'
    const currentSkills = n.skillIds || []
    const currentMcps = n.mcpIds || []
    const currentTools = n.toolIds || []
    const agents = (WF._cachedAgents || []).map(a => `<option value="${escAttr(a.slug)}"${n.agentId === a.slug ? ' selected' : ''}>${esc(a.name || a.slug)}</option>`).join('')
    const skillChecks = (WF._cachedSkills || []).map(s => {
      const checked = currentSkills.includes(s.slug)
      return `<label class="wf-skill-check"><input type="checkbox" value="${escAttr(s.slug)}"${checked ? ' checked' : ''}> ${esc(s.name || s.slug)}</label>`
    }).join('')
    const mcpChecks = (WF._cachedMcps || []).map(m => {
      const checked = currentMcps.includes(m.slug)
      return `<label class="wf-skill-check"><input type="checkbox" value="${escAttr(m.slug)}"${checked ? ' checked' : ''}> 🔌 ${esc(m.name || m.slug)}</label>`
    }).join('')
    const toolChecks = (WF._cachedTools || []).map(t => {
      const checked = currentTools.includes(t.slug)
      return `<label class="wf-skill-check"><input type="checkbox" value="${escAttr(t.slug)}"${checked ? ' checked' : ''}> 🔧 ${esc(t.name || t.slug)}</label>`
    }).join('')

    const PERM_OPTIONS = ['Read', 'Write', 'Edit', 'Bash', 'Skill', 'WebFetch', 'WebSearch', 'TaskCreate', 'TaskUpdate', 'Glob', 'Grep', 'PushNotification', 'AskUserQuestion']
    const PERM_SUGGEST_BASE = ['Write(*.md)', 'Write(*.java)', 'Write(*.py)', 'Write(*.json)', 'Write(*.ts)', 'Write(*.tsx)', 'Write(*.vue)',
      'Edit(*.md)', 'Edit(*.java)', 'Edit(*.py)', 'Edit(*.ts)', 'Edit(*.tsx)', 'Edit(*.vue)', 'Edit(*.json)', 'Edit(*.yaml)',
      'Bash(pytest)', 'Bash(mvn test)', 'Bash(gradle test)', 'Bash(python)', 'Bash(npm test)', 'Bash(npm run build)']
    const PERM_SUGGEST = [...PERM_SUGGEST_BASE];
    (WF._cachedSkills || []).forEach(s => { const p = `Skill(${s.slug})`; if (!PERM_SUGGEST.includes(p)) PERM_SUGGEST.push(p) })

    const permAllows = n.permissions?.allows || []
    const permBlocks = n.permissions?.blocks || []
    const renderPermChecks = (list: string[], prefix: string): string => {
      let h = '<div class="wf-perm-checks">'
      PERM_OPTIONS.forEach(p => {
        h += `<label class="wf-perm-check"><input type="checkbox" value="${p}" data-perm="${prefix}"${list.includes(p) ? ' checked' : ''}> ${p}</label>`
      })
      const custom = list.filter(p => !PERM_OPTIONS.includes(p))
      h += '</div><div class="wf-perm-custom">'
      custom.forEach(p => {
        h += `<span class="wf-tag">${esc(p)}<button class="wf-tag-x" data-perm-val="${escAttr(p)}" data-perm="${prefix}">×</button></span>`
      })
      h += `<div style="display:flex;align-items:center;gap:4px;margin-top:4px"><input class="wf-perm-input" data-perm="${prefix}" placeholder="自定义…" style="font-size:10px;padding:3px 6px;border:1px solid var(--border);border-radius:4px;width:140px"><button class="btn wf-perm-add-btn" data-perm="${prefix}" style="font-size:10px;padding:3px 8px">添加</button></div>`
      h += '<div class="wf-perm-suggest">'
      PERM_SUGGEST.forEach(s => { h += `<button class="wf-perm-chip" data-perm="${prefix}" data-val="${escAttr(s)}">${esc(s)}</button>` })
      h += '</div></div>'
      return h
    }

    const produceTags = (n.produces || []).map(p => `<span class="wf-tag">${esc(p)}<button class="wf-tag-x" data-produce="${escAttr(p)}">×</button></span>`).join(' ')
    const nodeHooks = (n.hooks || []).map((h, i) => `<div class="wf-hook-row"><span style="font-size:10px;color:var(--text-secondary)">${h.timing === 'onEnter' ? '进入' : '离开'}·${h.type}</span> <span style="flex:1;font-size:11px">${esc(h.value || '')}</span><button class="wf-hook-del" data-hook-idx="${i}">×</button></div>`).join('')

    // Build pack options from global state
    const packOpts = '<option value="">未选择</option>' + Object.entries((window as any).__packs || {}).map(([name, p]: [string, any]) => {
      const total = (p.skills||[]).length + (p.agents||[]).length
      return `<option value="${escAttr(name)}"${n.packId === name ? ' selected' : ''}>📦 ${esc(name)} (${total})</option>`
    }).join('')

    this.propsBody!.innerHTML = `
      <div class="wf-field"><label>节点类型</label><select id="wfPropType">
        <option value="agent" selected>📋 Agent 节点</option>
        <option value="gate">🔷 Gate 门禁</option>
      </select></div>
      <div class="wf-field"><label>标签</label><input id="wfPropLabel" value="${escAttr(n.label || '')}" placeholder="节点名称"></div>
      <div class="wf-field"><label>超时（分钟）</label><input id="wfPropTimeout" type="number" value="${n.timeout || 10}" min="1" max="120" step="1" style="width:80px"> <span style="font-size:10px;color:var(--text-muted)">默认 10 分钟</span></div>
      <div class="wf-field"><label>📦 配置包（快捷填充）</label><select id="wfPropPack">${packOpts}</select>
        <div style="font-size:9px;color:var(--text-muted);margin-top:2px">选择配置包自动填充下方 Skills/Agent</div>
      </div>
      <div class="wf-field"><label>Agent</label><select id="wfPropAgent"><option value="">未指定</option>${agents}</select></div>
      <div class="wf-field"><label>Skills（多选）</label>
        <input id="wfSkillSearch" placeholder="搜索 Skill..." style="padding:5px 8px;font-size:11px;border:1px solid var(--border);border-radius:4px;outline:none;margin-bottom:4px" oninput="window.WF.filterSkillList()">
        <div class="wf-skill-list" id="wfSkillList">${skillChecks || '<span style="font-size:11px;color:var(--text-secondary)">无可用</span>'}</div>
      </div>
      <div class="wf-field"><label>MCP Servers（多选）</label>
        <input id="wfMcpSearch" placeholder="搜索 MCP..." style="padding:5px 8px;font-size:11px;border:1px solid var(--border);border-radius:4px;outline:none;margin-bottom:4px" oninput="window.WF.filterMcpList()">
        <div class="wf-skill-list" id="wfMcpList">${mcpChecks || '<span style="font-size:11px;color:var(--text-secondary)">无可用</span>'}</div>
      </div>
      <div class="wf-field"><label>Tools（多选）</label>
        <input id="wfToolSearch" placeholder="搜索 Tool..." style="padding:5px 8px;font-size:11px;border:1px solid var(--border);border-radius:4px;outline:none;margin-bottom:4px" oninput="window.WF.filterToolList()">
        <div class="wf-skill-list" id="wfToolList">${toolChecks || '<span style="font-size:11px;color:var(--text-secondary)">无可用</span>'}</div>
      </div>
      <div class="wf-field"><label>Permissions · Allows</label>${renderPermChecks(permAllows, 'allows')}</div>
      <div class="wf-field"><label>Permissions · Blocks</label>${renderPermChecks(permBlocks, 'blocks')}</div>
      <div class="wf-field"><label>Produces（产出文件）</label>
        <div style="display:flex;gap:4px"><input id="wfPropProducesAdd" placeholder="产出文件名" style="flex:1;font-size:11px"><button id="wfPropProducesBtn" class="btn" style="font-size:10px;padding:4px 8px">+添加</button></div>
        <div class="wf-tag-list" id="wfPropProducesList">${produceTags || '<span style="font-size:10px;color:var(--text-secondary)">无</span>'}</div>
      </div>
      <div class="wf-field"><label>Hooks</label>
        <div style="font-size:10px;color:var(--text-secondary);margin-bottom:4px">
          <select id="wfHookTiming" style="font-size:10px;padding:2px"><option value="onEnter">进入时</option><option value="onLeave">离开时</option></select>
          <select id="wfHookType" style="font-size:10px;padding:2px"><option value="shell">Shell</option><option value="agent">Agent</option></select>
          <input id="wfHookVal" placeholder="命令/agent名" style="font-size:10px;width:100px;padding:2px">
          <button id="wfHookAdd" class="btn" style="font-size:10px;padding:2px 6px">+</button>
        </div>
        <div class="wf-hook-list" id="wfHookList">${nodeHooks || '<span style="font-size:10px;color:var(--text-secondary)">无</span>'}</div>
      </div>`

    // Pack selection handler — populate skills + agent + mcps + tools
    const packEl = this.propsBody.querySelector('#wfPropPack') as HTMLSelectElement
    if (packEl) {
      packEl.onchange = () => {
        const name = packEl.value
        n.packId = name || ''
        if (name) {
          const packs: Record<string, any> = (window as any).__packs || {}
          const pack = packs[name]
          if (pack) {
            let added: string[] = []
            if (pack.skills?.length) {
              n.skillIds = [...new Set([...(n.skillIds||[]), ...pack.skills])]
              added.push(`${pack.skills.length} Skills`)
            }
            if (pack.agents?.length && !n.agentId) {
              n.agentId = pack.agents[0]
              added.push(`Agent: ${pack.agents[0]}`)
            }
            if (pack.mcps?.length) {
              n.mcpIds = [...new Set([...(n.mcpIds||[]), ...pack.mcps])]
              added.push(`${pack.mcps.length} MCPs`)
            }
            if (pack.tools?.length) {
              n.toolIds = [...new Set([...(n.toolIds||[]), ...pack.tools])]
              added.push(`${pack.tools.length} Tools`)
            }
            this._lastPropsNode = null
            this.renderProps()
            if (added.length) {
              import('../utils').then(u => u.showToast(`📦 已填充: ${added.join(', ')}`, 'success'))
            }
          }
        }
      }
    }

    // Type switch (agent → gate)
    const typeEl = this.propsBody.querySelector('#wfPropType') as HTMLSelectElement
    if (typeEl) typeEl.onchange = () => {
      if (typeEl.value !== n.type) {
        n.type = typeEl.value as any
        if (n.type === 'gate') {
          delete (n as any).agentId; delete (n as any).skillIds; delete (n as any).mcpIds
          delete (n as any).toolIds; delete (n as any).permissions; delete (n as any).produces
          delete (n as any).hooks; delete (n as any).packId; delete (n as any).timeout
        }
        this.renderProps(); this.pushSnapshot()
      }
    }

    const labelEl = this.propsBody.querySelector('#wfPropLabel') as HTMLInputElement
    const timeoutEl = this.propsBody.querySelector('#wfPropTimeout') as HTMLInputElement
    const agentEl = this.propsBody.querySelector('#wfPropAgent') as HTMLSelectElement
    const onChange = () => {
      n.label = labelEl.value; n.agentId = agentEl.value || null
      n.timeout = parseInt(timeoutEl?.value, 10) || 10
      const skillCBs = this.propsBody!.querySelectorAll<HTMLInputElement>('#wfSkillList input[type=checkbox]')
      const mcpCBs = this.propsBody!.querySelectorAll<HTMLInputElement>('#wfMcpList input[type=checkbox]')
      const toolCBs = this.propsBody!.querySelectorAll<HTMLInputElement>('#wfToolList input[type=checkbox]')
      n.skillIds = [...skillCBs].filter(cb => cb.checked).map(cb => cb.value)
      n.mcpIds = [...mcpCBs].filter(cb => cb.checked).map(cb => cb.value)
      n.toolIds = [...toolCBs].filter(cb => cb.checked).map(cb => cb.value)
      this.render(); this.updateStatus(); this.pushSnapshot()
    }
    if (labelEl) labelEl.oninput = onChange
    if (timeoutEl) timeoutEl.onchange = onChange
    if (agentEl) agentEl.onchange = onChange
    this.propsBody.querySelectorAll<HTMLInputElement>('#wfSkillList input[type=checkbox], #wfMcpList input[type=checkbox], #wfToolList input[type=checkbox]').forEach(cb => { cb.onchange = onChange })

    // Permissions / Produces / Hooks — always functional
    n.permissions = n.permissions || { allows: [], blocks: [] }; n.produces = n.produces || []; n.hooks = n.hooks || []
    const snapshot = () => { this.render(); this.updateStatus(); this.pushSnapshot() }
    const addPermCustom = (prefix: string) => {
      const inp = this.propsBody!.querySelector(`.wf-perm-input[data-perm="${prefix}"]`) as HTMLInputElement
      const val = inp.value.trim(); if (!val) return
      const list = prefix === 'allows' ? n.permissions!.allows : n.permissions!.blocks
      if (!list.includes(val)) { list.push(val); this._lastPropsNode = null; this.renderProps() }
      inp.value = ''
    }
    this.propsBody.querySelectorAll<HTMLInputElement>('.wf-perm-check input[type=checkbox]').forEach(cb => {
      cb.onchange = () => {
        const list = cb.dataset.perm === 'allows' ? n.permissions!.allows : n.permissions!.blocks
        if (cb.checked) { if (!list.includes(cb.value)) list.push(cb.value) }
        else { const idx = list.indexOf(cb.value); if (idx >= 0) list.splice(idx, 1) }
        this._lastPropsNode = null; this.renderProps()
      }
    })
    this.propsBody.querySelectorAll<HTMLButtonElement>('.wf-perm-add-btn').forEach(btn => { btn.onclick = () => addPermCustom(btn.dataset.perm!) })
    this.propsBody.querySelectorAll<HTMLInputElement>('.wf-perm-input').forEach(inp => {
      inp.onkeydown = (e: KeyboardEvent) => { if (e.key === 'Enter') { e.preventDefault(); addPermCustom(inp.dataset.perm!) } }
    })
    this.propsBody.querySelectorAll<HTMLElement>('.wf-perm-chip').forEach(chip => {
      chip.onclick = () => {
        const prefix = chip.dataset.perm!; const val = chip.dataset.val!
        const list = prefix === 'allows' ? n.permissions!.allows : n.permissions!.blocks
        if (!list.includes(val)) { list.push(val); this._lastPropsNode = null; this.renderProps() }
      }
    })
    this.propsBody.querySelectorAll<HTMLElement>('.wf-tag-x[data-perm-val]').forEach(btn => {
      btn.onclick = () => {
        const prefix = btn.dataset.perm!; const val = btn.dataset.permVal!
        const list = prefix === 'allows' ? n.permissions!.allows : n.permissions!.blocks
        const idx = list.indexOf(val); if (idx >= 0) { list.splice(idx, 1); this._lastPropsNode = null; this.renderProps() }
      }
    })
    // Produces
    this.propsBody.querySelector('#wfPropProducesBtn')!.addEventListener('click', () => {
      const inp = this.propsBody!.querySelector('#wfPropProducesAdd') as HTMLInputElement
      const val = inp.value.trim()
      if (val && !n.produces!.includes(val)) { n.produces!.push(val); snapshot() }
      inp.value = ''
    })
    // Produces delete — only target tags with data-produce attribute
    this.propsBody.querySelectorAll<HTMLElement>('.wf-tag-x[data-produce]').forEach(btn => {
      btn.onclick = () => { n.produces = n.produces!.filter(p => p !== btn.dataset.produce); snapshot() }
    })
    // Hooks
    this.propsBody.querySelector('#wfHookAdd')!.addEventListener('click', () => {
      const t = (this.propsBody!.querySelector('#wfHookTiming') as HTMLSelectElement).value
      const ty = (this.propsBody!.querySelector('#wfHookType') as HTMLSelectElement).value
      const v = (this.propsBody!.querySelector('#wfHookVal') as HTMLInputElement).value.trim()
      if (v) { n.hooks!.push({ timing: t as any, type: ty as any, value: v }); snapshot() }
    })
    this.propsBody.querySelectorAll<HTMLElement>('.wf-hook-del').forEach(btn => {
      btn.onclick = () => { n.hooks!.splice(parseInt(btn.dataset.hookIdx!), 1); snapshot() }
    })
  } else if (n.type === 'gate') {
    this.propsTitle!.textContent = '🔷 门禁属性'
    const gc = n.gateConfig || { condition: 'auto', autoDetect: '', manualAdvance: '', expression: '' }
    if (!n.gateConfig) n.gateConfig = gc
    const sel = (c: string) => gc.condition === c ? ' active' : ''
    this.propsBody!.innerHTML = `
      <div class="wf-field"><label>节点类型</label><select id="wfPropType">
        <option value="gate" selected>🔷 Gate 门禁</option>
        <option value="agent">📋 Agent 节点</option>
      </select></div>
      <div class="wf-field"><label>标签</label><input id="wfPropLabel" value="${escAttr(n.label || '')}"></div>
      <div class="wf-field"><label>条件类型</label>
        <div class="wf-radios" id="wfGateCond">
          <button data-cond="auto" class="${sel('auto')}">自动检测</button>
          <button data-cond="manual" class="${sel('manual')}">手动确认</button>
          <button data-cond="expression" class="${sel('expression')}">表达式</button>
        </div>
      </div>
      <div class="wf-field" id="wfGateAuto" style="display:${gc.condition === 'auto' ? '' : 'none'}"><label>自动检测规则</label><input id="wfGateAutoDetect" value="${escAttr(gc.autoDetect)}"></div>
      <div class="wf-field" id="wfGateManual" style="display:${gc.condition === 'manual' ? '' : 'none'}"><label>手动推进说明</label><input id="wfGateManualAdv" value="${escAttr(gc.manualAdvance)}"></div>
      <div class="wf-field" id="wfGateExpr" style="display:${gc.condition === 'expression' ? '' : 'none'}"><label>表达式</label><input id="wfGateExpression" value="${escAttr(gc.expression)}"></div>`

    // Type switch (gate → agent)
    const typeEl = this.propsBody.querySelector('#wfPropType') as HTMLSelectElement
    if (typeEl) typeEl.onchange = () => {
      if (typeEl.value !== n.type) {
        if (typeEl.value === 'agent') { delete (n as any).gateConfig }
        n.type = typeEl.value as any
        this.renderProps(); this.pushSnapshot()
      }
    }

    const labelEl = this.propsBody.querySelector('#wfPropLabel') as HTMLInputElement
    if (labelEl) labelEl.oninput = () => { n.label = labelEl.value; this.render(); this.updateStatus() }

    (this.propsBody.querySelectorAll('#wfGateCond button') as any as HTMLElement[]).forEach((btn: HTMLElement) => {
      btn.onclick = () => {
        gc.condition = btn.dataset.cond as any
        ;(this.propsBody.querySelectorAll('#wfGateCond button') as any as HTMLElement[]).forEach((b: HTMLElement) => b.classList.toggle('active', b === btn));
        (this.propsBody.querySelector('#wfGateAuto') as HTMLElement).style.display = gc.condition === 'auto' ? '' : 'none';
        (this.propsBody.querySelector('#wfGateManual') as HTMLElement).style.display = gc.condition === 'manual' ? '' : 'none';
        (this.propsBody.querySelector('#wfGateExpr') as HTMLElement).style.display = gc.condition === 'expression' ? '' : 'none'
        this.pushSnapshot()
      }
    });
    (this.propsBody.querySelector('#wfGateAutoDetect') as HTMLInputElement).oninput = function (this: HTMLInputElement) { gc.autoDetect = this.value };
    (this.propsBody.querySelector('#wfGateManualAdv') as HTMLInputElement).oninput = function (this: HTMLInputElement) { gc.manualAdvance = this.value };
    (this.propsBody.querySelector('#wfGateExpression') as HTMLInputElement).oninput = function (this: HTMLInputElement) { gc.expression = this.value }
  } else if (n.type === 'command') {
    this.propsTitle!.textContent = '⌨ 命令属性'
    this.propsBody!.innerHTML = `
      <div class="wf-field"><label>节点类型</label><select id="wfPropType">
        <option value="command" selected>⌨ Command 命令</option>
        <option value="agent">📋 Agent 节点</option>
      </select></div>
      <div class="wf-field"><label>标签</label><input id="wfPropLabel" value="${escAttr(n.label || '')}"></div>
      <div class="wf-field"><label>超时（分钟）</label><input id="wfPropTimeout" type="number" value="${n.timeout || 10}" min="1" max="120" step="1" style="width:80px"> <span style="font-size:10px;color:var(--text-muted)">默认 10 分钟</span></div>
      <div class="wf-field"><label>Permissions · Allows</label><div style="font-size:11px;color:var(--text-secondary)">命令节点的权限由命令文件自身定义</div></div>
      <div class="wf-field"><label>Produces（产出文件）</label>
        <div style="display:flex;gap:4px"><input id="wfPropProducesAdd" placeholder="产出文件名" style="flex:1;font-size:11px"><button id="wfPropProducesBtn" class="btn" style="font-size:10px;padding:4px 8px">+添加</button></div>
        <div class="wf-tag-list" id="wfPropProducesList">${(n.produces || []).map(p => `<span class="wf-tag">${esc(p)}<button class="wf-tag-x" data-produce="${escAttr(p)}">×</button></span>`).join(' ') || '<span style="font-size:10px;color:var(--text-secondary)">无</span>'}</div>
      </div>`

    const typeEl = this.propsBody.querySelector('#wfPropType') as HTMLSelectElement
    if (typeEl) typeEl.onchange = () => {
      if (typeEl.value !== n.type) {
        if (typeEl.value === 'agent') { delete (n as any).commandId }
        n.type = typeEl.value as any
        this.renderProps(); this.pushSnapshot()
      }
    }

    const labelEl = this.propsBody.querySelector('#wfPropLabel') as HTMLInputElement
    if (labelEl) labelEl.oninput = () => { n.label = labelEl.value; this.render(); this.updateStatus() }
    const timeoutEl = this.propsBody.querySelector('#wfPropTimeout') as HTMLInputElement
    if (timeoutEl) timeoutEl.onchange = () => { n.timeout = parseInt(timeoutEl.value, 10) || 10 }

    n.produces = n.produces || []; n.hooks = n.hooks || []
    this.propsBody.querySelector('#wfPropProducesBtn')!.addEventListener('click', () => {
      const inp = this.propsBody!.querySelector('#wfPropProducesAdd') as HTMLInputElement
      const val = inp.value.trim()
      if (val && !n.produces!.includes(val)) { n.produces!.push(val); this.render(); this.updateStatus(); this.pushSnapshot() }
      inp.value = ''
    })
    this.propsBody.querySelectorAll<HTMLElement>('.wf-tag-x[data-produce]').forEach(btn => {
      btn.onclick = () => { n.produces = n.produces!.filter(p => p !== btn.dataset.produce); this.render(); this.updateStatus(); this.pushSnapshot() }
    })
  }
}

// Skill search filter (exposed on window)
;(WF as any).filterSkillList = function (this: typeof WF): void {
  const searchEl = this.propsBody?.querySelector('#wfSkillSearch') as HTMLInputElement
  const listEl = this.propsBody?.querySelector('#wfSkillList')
  if (!searchEl || !listEl) return
  const q = searchEl.value.toLowerCase()
  listEl.querySelectorAll<HTMLElement>('.wf-skill-check').forEach(el => {
    el.style.display = !q || el.textContent!.toLowerCase().includes(q) ? '' : 'none'
  })
}
;(WF as any).filterMcpList = function (this: typeof WF): void {
  const searchEl = this.propsBody?.querySelector('#wfMcpSearch') as HTMLInputElement
  const listEl = this.propsBody?.querySelector('#wfMcpList')
  if (!searchEl || !listEl) return
  const q = searchEl.value.toLowerCase()
  listEl.querySelectorAll<HTMLElement>('.wf-skill-check').forEach(el => {
    el.style.display = !q || el.textContent!.toLowerCase().includes(q) ? '' : 'none'
  })
}
;(WF as any).filterToolList = function (this: typeof WF): void {
  const searchEl = this.propsBody?.querySelector('#wfToolSearch') as HTMLInputElement
  const listEl = this.propsBody?.querySelector('#wfToolList')
  if (!searchEl || !listEl) return
  const q = searchEl.value.toLowerCase()
  listEl.querySelectorAll<HTMLElement>('.wf-skill-check').forEach(el => {
    el.style.display = !q || el.textContent!.toLowerCase().includes(q) ? '' : 'none'
  })
}
