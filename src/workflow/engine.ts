// ============================================================
// Workflow Engine — state management, undo/redo, zoom/pan, core operations
// ============================================================

import type { WfNode, WfEdge, WorkflowData, DragState, DrawState, PanState, CachedRef, Position, WfMode, NodeType } from '../types'
import { esc, escAttr, trunc, fetchJSON } from '../utils'
import { API } from '../state'

export const WF = {
  nodes: [] as WfNode[],
  edges: [] as WfEdge[],
  mode: 'auto' as WfMode,
  slug: '',
  wfName: '',
  description: '',
  selectedId: null as string | null,
  nextId: 1,
  undoStack: [] as string[],
  redoStack: [] as string[],
  panX: 0, panY: 0, zoom: 1,
  dragging: null as DragState | null,
  drawing: null as DrawState | null,
  panning: null as PanState | null,

  // DOM refs
  canvasWrap: null as HTMLElement | null,
  svg: null as SVGSVGElement | null,
  viewport: null as SVGGElement | null,
  edgesGroup: null as SVGGElement | null,
  nodesGroup: null as SVGGElement | null,
  tempEdge: null as SVGPathElement | null,
  sidebarEl: null as HTMLElement | null,
  propsOverlay: null as HTMLElement | null,
  propsTitle: null as HTMLElement | null,
  propsBody: null as HTMLElement | null,
  propsClose: null as HTMLElement | null,
  _lastPropsNode: null as string | null,
  _lastPropsData: null as string | null,
  _abort: null as AbortController | null,

  // Cached reference data
  _cachedAgents: [] as CachedRef[],
  _cachedSkills: [] as CachedRef[],
  _cachedMcps: [] as CachedRef[],
  _cachedTools: [] as CachedRef[],

  // --- Init ---
  init(container: HTMLElement, data: WorkflowData): void {
    this.destroy()
    this.canvasWrap = container
    this.nodes = (data.nodes || []).map(n => ({ ...n }))
    this.edges = (data.edges || []).map(e => ({ ...e }))
    this.mode = (data.mode as WfMode) || 'auto'
    this.slug = data.slug || ''
    this.wfName = data.name || ''
    this.description = data.description || ''
    this.selectedId = null
    this.undoStack = []; this.redoStack = []
    this.panX = 0; this.panY = 0; this.zoom = 1

    const maxN = Math.max(0, ...this.nodes.map(n => parseInt(String(n.id).replace(/[^0-9]/g, '')) || 0))
    const maxE = Math.max(0, ...this.edges.map(e => parseInt(String(e.id).replace(/[^0-9]/g, '')) || 0))
    this.nextId = Math.max(maxN, maxE) + 1

    container.innerHTML = `
      <div class="wf-toolbar">
        <span class="wf-title">${esc(this.wfName || this.slug)}</span>
        <span class="wf-mode-badge ${this.mode}">${this.mode === 'step' ? 'Step 阶段门禁' : 'Auto 自动编排'}</span>
        <span class="wf-spacer"></span>
        <span class="wf-status" id="wfStatus"></span>
        <button class="btn primary" id="btnWfSaveCanvas" style="font-size:11px;padding:4px 10px">💾 保存</button>
        <button class="btn" id="btnWfExecute" style="font-size:11px;padding:4px 10px;background:var(--color-active);color:#fff;border:1px solid var(--color-active);border-radius:4px;cursor:pointer">▶ 执行</button>
        <button class="btn" id="btnWfExportCanvas" style="font-size:11px;padding:4px 8px">📤 导出</button>
        <button class="btn" id="btnWfCopyCanvas" style="font-size:11px;padding:4px 8px">📋 复制</button>
        <button class="btn" id="btnWfDeleteCanvas" style="color:var(--color-archived);font-size:11px;padding:4px 8px">🗑 删除</button>
      </div>
      <div class="wf-main">
        <div class="wf-sidebar" id="wfSidebar">
          <div class="wf-sidebar-section">
            <div class="wf-sidebar-label">节点类型</div>
            <button class="wf-node-type-btn" data-add="agent">📋 节点</button>
            <button class="wf-node-type-btn" data-add="gate">🔷 门禁</button>
          </div>
          <div class="wf-sidebar-section" style="flex:1;display:flex;flex-direction:column;min-height:0;padding-bottom:0">
            <div class="wf-sidebar-tabs">
              <button class="wf-tab active" data-tab="agents" title="Agents">🤖</button>
              <button class="wf-tab" data-tab="skills" title="Skills">✨</button>
              <button class="wf-tab" data-tab="commands" title="Commands">⌨</button>
              <button class="wf-tab" data-tab="rules" title="Rules">📜</button>
              <button class="wf-tab" data-tab="mcps" title="MCP">🔌</button>
              <button class="wf-tab" data-tab="tools" title="Tools">🔧</button>
            </div>
            <div class="wf-sidebar-list" id="wfSidebarList">
              <div style="color:var(--text-secondary);font-size:11px;padding:8px">加载中...</div>
            </div>
            <div style="font-size:10px;color:var(--text-secondary);padding:6px 0 10px;line-height:1.3;flex-shrink:0">点击列表项添加到画布。<br>拖拽节点手柄创建连线。</div>
          </div>
        </div>
        <div class="wf-canvas-wrap" id="wfCanvas">
          <svg id="wfSvg">
            <defs>
              <marker id="wfArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/>
              </marker>
            </defs>
            <g id="wfViewport" transform="translate(0,0) scale(1)">
              <g id="wfEdgesLayer"></g>
              <g id="wfNodesLayer"></g>
              <path id="wfTempEdge" class="wf-edge-temp" d="" style="display:none"/>
            </g>
          </svg>
          <div class="wf-controls">
            <button onclick="window.WF.zoomBy(0.15)" title="放大">+</button>
            <button onclick="window.WF.zoomBy(-0.15)" title="缩小">−</button>
            <button onclick="window.WF.fitView()" title="适应画布">⊡</button>
          </div>
          <div class="wf-props-overlay" id="wfPropsOverlay">
            <div class="wf-props-header">
              <span id="wfPropsTitle">节点属性</span>
              <div style="display:flex;gap:4px">
                <button id="wfPropsDelete" title="删除" style="color:var(--color-archived)">🗑</button>
                <button id="wfPropsClose" title="关闭">✕</button>
              </div>
            </div>
            <div class="wf-props-body" id="wfPropsBody"></div>
          </div>
        </div>
      </div>`

    this.svg = container.querySelector('#wfSvg') as SVGSVGElement
    this.viewport = container.querySelector('#wfViewport') as SVGGElement
    this.edgesGroup = container.querySelector('#wfEdgesLayer') as SVGGElement
    this.nodesGroup = container.querySelector('#wfNodesLayer') as SVGGElement
    this.tempEdge = container.querySelector('#wfTempEdge') as SVGPathElement
    this.sidebarEl = container.querySelector('#wfSidebar') as HTMLElement
    this.propsOverlay = container.querySelector('#wfPropsOverlay') as HTMLElement
    this.propsTitle = container.querySelector('#wfPropsTitle') as HTMLElement
    this.propsBody = container.querySelector('#wfPropsBody') as HTMLElement
    this.propsClose = container.querySelector('#wfPropsClose') as HTMLElement

    // Delete button in overlay
    const delBtn = container.querySelector('#wfPropsDelete') as HTMLButtonElement
    if (delBtn) delBtn.onclick = () => {
      if (this.selectedId) { this.deleteSelected(); this.propsOverlay.classList.remove('open'); this._lastPropsNode = null }
    }

    // Overlay drag
    const header = container.querySelector('.wf-props-header') as HTMLElement
    if (header) {
      header.addEventListener('mousedown', (e: MouseEvent) => {
        if ((e.target as HTMLElement).tagName === 'BUTTON') return
        e.preventDefault()
        const overlay = this.propsOverlay!
        const rect = overlay.getBoundingClientRect()
        const sx = e.clientX, sy = e.clientY
        const ol = rect.left, ot = rect.top
        const pr = overlay.parentElement!.getBoundingClientRect()
        const onMove = (ev: MouseEvent) => {
          overlay.style.right = 'auto'; overlay.style.left = (ol - pr.left + ev.clientX - sx) + 'px'
          overlay.style.top = (ot - pr.top + ev.clientY - sy) + 'px'
        }
        const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp) }
        document.addEventListener('mousemove', onMove)
        document.addEventListener('mouseup', onUp)
      })
    }

    // Event listeners
    const ac = new AbortController()
    this._abort = ac
    const wrap = container.querySelector('#wfCanvas')!
    // Lazy-load interaction module once, reuse across all events
    let interactionModule: any = null
    const getInteraction = (): Promise<any> => interactionModule ? Promise.resolve(interactionModule) : import('./interaction').then(m => { interactionModule = m; return m })
    wrap.addEventListener('mousedown', ((e: MouseEvent) => { getInteraction().then(m => m.onMouseDown.call(WF, e)) }) as EventListener, { signal: ac.signal })
    document.addEventListener('mousemove', ((e: MouseEvent) => { getInteraction().then(m => m.onMouseMove.call(WF, e)) }) as EventListener, { signal: ac.signal })
    document.addEventListener('mouseup', ((e: MouseEvent) => { getInteraction().then(m => m.onMouseUp.call(WF, e)) }) as EventListener, { signal: ac.signal })
    wrap.addEventListener('dblclick', ((e: MouseEvent) => { getInteraction().then(m => m.onDblClick.call(WF, e)) }) as EventListener, { signal: ac.signal })
    document.addEventListener('keydown', ((e: KeyboardEvent) => { getInteraction().then(m => m.onKeyDown.call(WF, e)) }) as EventListener, { signal: ac.signal })
    wrap.addEventListener('wheel', ((e: WheelEvent) => { getInteraction().then(m => m.onWheel.call(WF, e)) }) as EventListener, { signal: ac.signal })

    // Sidebar
    this.bindSidebarEvents()
    this.loadSidebarItems('agents')
    this.preloadRefs()

    // Zoom controls
    this.render()
    this.pushSnapshot()
    this.updateStatus()
  },

  destroy(): void {
    if (this._abort) { this._abort.abort(); this._abort = null }
    this.nodes = []; this.edges = []; this.selectedId = null
    this.undoStack = []; this.redoStack = []
    this.svg = null as any; this.viewport = null as any; this.edgesGroup = null as any; this.nodesGroup = null as any
    this.dragging = null; this.drawing = null; this.panning = null
    if (this.canvasWrap) this.canvasWrap.innerHTML = ''
  },

  // --- Undo/Redo ---
  pushSnapshot(): void {
    const snap = JSON.stringify({ nodes: this.nodes, edges: this.edges, mode: this.mode })
    this.undoStack.push(snap)
    if (this.undoStack.length > 50) this.undoStack.shift()
    this.redoStack = []
    this.updateStatus()
  },

  markClean(): void {
    const snap = JSON.stringify({ slug: this.slug, name: this.wfName, description: this.description, nodes: this.nodes, edges: this.edges, mode: this.mode })
    this.undoStack = [snap]; this.redoStack = []
    this.updateStatus()
  },

  isDirty(): boolean {
    const current = JSON.stringify({ slug: this.slug, name: this.wfName, description: this.description, nodes: this.nodes, edges: this.edges, mode: this.mode })
    return this.undoStack.length > 0 && this.undoStack[this.undoStack.length - 1] !== current
  },

  undo(): void {
    if (this.undoStack.length <= 1) return
    const current = JSON.stringify({ nodes: this.nodes, edges: this.edges, mode: this.mode })
    this.redoStack.push(current)
    const prev = JSON.parse(this.undoStack.pop()!)
    this.nodes = prev.nodes; this.edges = prev.edges; this.mode = prev.mode
    this.selectedId = null; this._lastPropsNode = null
    this.render()
  },

  redo(): void {
    if (!this.redoStack.length) return
    const current = JSON.stringify({ nodes: this.nodes, edges: this.edges, mode: this.mode })
    this.undoStack.push(current)
    const next = JSON.parse(this.redoStack.pop()!)
    this.nodes = next.nodes; this.edges = next.edges; this.mode = next.mode
    this.selectedId = null; this._lastPropsNode = null
    this.render()
  },

  // --- Zoom/Pan ---
  zoomBy(delta: number): void {
    this.zoom = Math.max(0.2, Math.min(2.5, this.zoom + delta))
    this.updateViewport()
  },

  fitView(): void {
    if (!this.nodes.length) { this.panX = 0; this.panY = 0; this.zoom = 1; this.updateViewport(); return }
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    this.nodes.forEach(n => {
      minX = Math.min(minX, n.position.x); minY = Math.min(minY, n.position.y)
      maxX = Math.max(maxX, n.position.x + 200); maxY = Math.max(maxY, n.position.y + 70)
    })
    const w = maxX - minX + 120, h = maxY - minY + 120
    const rect = this.svg!.getBoundingClientRect()
    const sx = rect.width / w, sy = rect.height / h
    this.zoom = Math.min(sx, sy, 1.2)
    this.panX = -minX * this.zoom + (rect.width - w * this.zoom) / 2
    this.panY = -minY * this.zoom + (rect.height - h * this.zoom) / 2
    this.updateViewport()
  },

  updateViewport(): void {
    if (this.viewport) this.viewport.setAttribute('transform', `translate(${this.panX},${this.panY}) scale(${this.zoom})`)
  },

  updateStatus(): void {
    const el = this.canvasWrap?.querySelector('#wfStatus') as HTMLElement
    if (!el) return
    const dirty = this.isDirty()
    el.innerHTML = dirty ? '<span class="unsaved">● 未保存</span>' : '已保存'
  },

  // --- Node operations ---
  addNode(type: NodeType, x: number, y: number, fromNodeId?: string): void {
    const id = 'n' + (this.nextId++)
    const node: WfNode = { id, type, label: type === 'agent' ? '新步骤' : '门禁', position: { x, y } }
    if (type === 'agent') {
      node.label = '新步骤'; node.packId = ''; node.agentId = null; node.skillIds = []; node.mcpIds = []; node.toolIds = []
      node.permissions = { allows: ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob', 'WebFetch', 'WebSearch'], blocks: [] }
      node.produces = []
      node.hooks = []
      node.timeout = 10
    } else if (type === 'gate') {
      node.gateConfig = { condition: 'auto', autoDetect: '', manualAdvance: '', expression: '' }
    }
    this.nodes.push(node)
    if (fromNodeId) {
      this.edges.push({ id: 'e' + (this.nextId++), from: fromNodeId, to: id, condition: this.mode === 'auto' ? 'auto' : 'manual' })
    }
    this.selectedId = id
    this.pushSnapshot()
    this.render()
  },

  deleteSelected(): void {
    if (!this.selectedId) return
    const isNode = this.nodes.some(n => n.id === this.selectedId)
    if (isNode) {
      this.nodes = this.nodes.filter(n => n.id !== this.selectedId)
      this.edges = this.edges.filter(e => e.from !== this.selectedId && e.to !== this.selectedId)
    } else {
      this.edges = this.edges.filter(e => e.id !== this.selectedId)
    }
    this.selectedId = null; this._lastPropsNode = null
    this.pushSnapshot(); this.render()
  },

  toJSON(): WorkflowData {
    return { slug: this.slug, name: this.wfName, description: this.description, mode: this.mode, nodes: this.nodes, edges: this.edges }
  },

  // --- Edge geometry ---
  getOutputPos(node: WfNode): [number, number] {
    if (node.type === 'gate') return [node.position.x + 120, node.position.y + 35]
    return [node.position.x + 200, node.position.y + 32]
  },

  getInputPos(node: WfNode): [number, number] {
    if (node.type === 'gate') return [node.position.x, node.position.y + 35]
    return [node.position.x, node.position.y + 32]
  },

  bezierPath(x1: number, y1: number, x2: number, y2: number): string {
    const dx = Math.abs(x2 - x1) * 0.5
    return `M ${x1},${y1} C ${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`
  },

  updateEdgesForNode(nodeId: string): void {
    this.edges.forEach(e => {
      if (e.from !== nodeId && e.to !== nodeId) return
      const from = this.nodes.find(n => n.id === e.from)
      const to = this.nodes.find(n => n.id === e.to)
      if (!from || !to) return
      const pathEl = this.edgesGroup?.querySelector(`[data-edge-id="${e.id}"]`)
      if (pathEl) {
        const [x1, y1] = this.getOutputPos(from); const [x2, y2] = this.getInputPos(to)
        pathEl.setAttribute('d', this.bezierPath(x1, y1, x2, y2))
      }
    })
  },

  // --- Sidebar ---
  bindSidebarEvents(): void {
    if (!this.sidebarEl) return
    this.sidebarEl.querySelectorAll<HTMLElement>('.wf-node-type-btn[data-add]').forEach(el => {
      el.onclick = () => {
        const type = el.dataset.add as NodeType
        const rect = this.svg!.getBoundingClientRect()
        const cx = (rect.width / 2 - this.panX) / this.zoom
        const cy = (rect.height / 2 - this.panY) / this.zoom
        this.addNode(type, cx - 100, cy - 30)
      }
    })
    this.sidebarEl.querySelectorAll<HTMLElement>('.wf-tab').forEach(tab => {
      tab.onclick = () => {
        this.sidebarEl!.querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'))
        tab.classList.add('active')
        this.loadSidebarItems(tab.dataset.tab!)
      }
    })
  },

  async loadSidebarItems(category: string): Promise<void> {
    const listEl = this.canvasWrap?.querySelector('#wfSidebarList')
    if (!listEl) return
    listEl.innerHTML = '<div style="color:var(--text-secondary);font-size:11px;padding:8px">加载中...</div>'
    const typeMap: Record<string, string> = { agents: 'agent', skills: 'skill', commands: 'command', rules: 'rule', mcps: 'mcp', tools: 'tool' }
    const iconMap: Record<string, string> = { agents: '🤖', skills: '✨', commands: '⌨', rules: '📜', mcps: '🔌', tools: '🔧' }
    const itemType = typeMap[category] || 'agent'
    const icon = iconMap[category] || '•'
    try {
      const items = await fetchJSON<any[]>(`${API}/api/items?type=${category}&status=active`)
      const filtered = items.filter(i => i.type === itemType)
      if (!filtered.length) { listEl.innerHTML = '<div style="color:var(--text-secondary);font-size:11px;padding:8px">无可用项</div>'; return }
      listEl.innerHTML = filtered.map(i => `
        <div class="wf-list-item" data-slug="${escAttr(i.name)}">
          <span class="item-icon">${icon}</span>
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.name)}</span>
        </div>`).join('')
      listEl.querySelectorAll<HTMLElement>('.wf-list-item').forEach(el => {
        el.onclick = () => {
          const slug = el.dataset.slug!
          const rect = this.svg!.getBoundingClientRect()
          const cx = (rect.width / 2 - this.panX) / this.zoom; const cy = (rect.height / 2 - this.panY) / this.zoom
          const id = 'n' + (this.nextId++)
          const isCommand = itemType === 'command'
          this.nodes.push({
            id, type: isCommand ? 'command' : 'agent', label: slug, position: { x: cx - 100, y: cy - 30 },
            packId: '',
            agentId: itemType === 'agent' ? slug : null,
            commandId: isCommand ? slug : null,
            skillIds: itemType === 'skill' ? [slug] : [],
            mcpIds: itemType === 'mcp' ? [slug] : [],
            toolIds: itemType === 'tool' ? [slug] : [],
            permissions: { allows: ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob', 'WebFetch', 'WebSearch'], blocks: [] },
            produces: [], hooks: [], timeout: 10
          })
          this.selectedId = id; this.pushSnapshot(); this.render()
        }
      })
    } catch (_) {
      listEl.innerHTML = '<div style="color:var(--color-archived);font-size:11px;padding:8px">加载失败</div>'
    }
  },

  async preloadRefs(): Promise<void> {
    try {
      const [agents, skills, mcps, tools] = await Promise.all([
        fetchJSON<any[]>(`${API}/api/items?type=agents&status=active`),
        fetchJSON<any[]>(`${API}/api/items?type=skills&status=active`),
        fetchJSON<any[]>(`${API}/api/items?type=mcps&status=active`),
        fetchJSON<any[]>(`${API}/api/items?type=tools&status=active`)
      ])
      this._cachedAgents = agents.filter(i => i.type === 'agent').map(i => ({ slug: i.name, name: i.name }))
      this._cachedSkills = skills.filter(i => i.type === 'skill').map(i => ({ slug: i.name, name: i.name }))
      this._cachedMcps = mcps.filter(i => i.type === 'mcp').map(i => ({ slug: i.name, name: i.name }))
      this._cachedTools = tools.filter(i => i.type === 'tool').map(i => ({ slug: i.name, name: i.name }))
    } catch (_) { /* silent */ }
  },

  render(): void { import('./renderer').then(m => m.renderAll.call(WF)).catch(e => console.error('WF render failed:', e)) },
  renderProps(): void { import('./properties').then(m => m.renderProps.call(WF)).catch(e => console.error('WF renderProps failed:', e)) },
}

// Global exposure for inline onclick handlers
;(window as any).WF = WF
