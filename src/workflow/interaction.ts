// ============================================================
// Workflow Interaction — mouse, keyboard, wheel handlers
// ============================================================

import { WF } from './engine'

export function onMouseDown(this: typeof WF, e: MouseEvent): void {
  if (e.button === 1) { e.preventDefault(); if ((e.target as HTMLElement).closest('#wfSidebar')) return; this.panning = { startX: e.clientX, startY: e.clientY, startPanX: this.panX, startPanY: this.panY }; return }
  if (e.button !== 0) return
  const target = e.target as HTMLElement
  if (target.closest('#wfSidebar') || target.closest('#wfPropsOverlay')) return

  // Handle click
  if (target.classList.contains('node-handle')) {
    e.stopPropagation()
    const nodeId = target.dataset.nodeId!
    const node = this.nodes.find(n => n.id === nodeId)
    if (!node) return
    if (target.dataset.handle === 'input') return
    const cx = node.position.x + 200; const cy = node.position.y + 30
    this.drawing = { fromNodeId: nodeId, fromX: cx, fromY: cy, mouseX: cx, mouseY: cy }
    return
  }

  // Delete button
  const delBtn = target.closest('[data-del]') as HTMLElement
  if (delBtn) {
    e.stopPropagation(); e.preventDefault()
    const nid = delBtn.dataset.del
    if (nid) { this.selectedId = nid; this.deleteSelected(); this.propsOverlay?.classList.remove('open'); this._lastPropsNode = null }
    return
  }

  // Node body
  const nodeEl = target.closest('.wf-node') as HTMLElement
  if (nodeEl) {
    e.stopPropagation()
    const nodeId = nodeEl.dataset.nodeId!
    this.selectedId = nodeId; this.render()
    const node = this.nodes.find(n => n.id === nodeId)
    if (node) { this.dragging = { nodeId, startX: e.clientX, startY: e.clientY, origX: node.position.x, origY: node.position.y } }
    return
  }

  // Edge
  const edgeEl = target.closest('[data-edge-id]') as HTMLElement
  if (edgeEl) { e.stopPropagation(); this.selectedId = edgeEl.dataset.edgeId!; this.render(); return }

  // Blank canvas
  this.panning = { startX: e.clientX, startY: e.clientY, startPanX: this.panX, startPanY: this.panY, wasBlank: true }
}

export function onMouseMove(this: typeof WF, e: MouseEvent): void {
  if (this.dragging) {
    const node = this.nodes.find(n => n.id === this.dragging!.nodeId)
    if (node) {
      const dx = (e.clientX - this.dragging.startX) / this.zoom; const dy = (e.clientY - this.dragging.startY) / this.zoom
      node.position.x = this.dragging.origX + dx; node.position.y = this.dragging.origY + dy
      const el = this.nodesGroup?.querySelector(`[data-node-id="${this.dragging.nodeId}"]`)
      if (el) el.setAttribute('transform', `translate(${node.position.x},${node.position.y})`)
      this.updateEdgesForNode(this.dragging.nodeId)
    }
    return
  }
  if (this.drawing) { this.drawing.mouseX = e.clientX; this.drawing.mouseY = e.clientY; renderTempEdge.call(this); return }
  if (this.panning) { this.panX = this.panning.startPanX + (e.clientX - this.panning.startX); this.panY = this.panning.startPanY + (e.clientY - this.panning.startY); this.updateViewport() }
}

export function onMouseUp(this: typeof WF, e: MouseEvent): void {
  if (this.dragging) {
    const moved = Math.abs(e.clientX - this.dragging.startX) + Math.abs(e.clientY - this.dragging.startY)
    this.dragging = null
    if (moved > 3) this.pushSnapshot()
    this.render(); return
  }
  if (this.drawing) {
    const target = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement
    const handle = target?.closest?.('.node-handle[data-handle="input"]') as HTMLElement
    if (handle) {
      const toNodeId = handle.dataset.nodeId!
      if (toNodeId && toNodeId !== this.drawing.fromNodeId && !this.edges.some(ed => ed.from === this.drawing!.fromNodeId && ed.to === toNodeId)) {
        this.edges.push({ id: 'e' + (this.nextId++), from: this.drawing.fromNodeId, to: toNodeId, condition: this.mode === 'auto' ? 'auto' : 'manual' })
        this.pushSnapshot()
      }
    }
    this.drawing = null
    if (this.tempEdge) this.tempEdge.style.display = 'none'
    this.render(); return
  }
  if (this.panning) {
    const wasBlank = this.panning.wasBlank
    const moved = Math.abs(e.clientX - this.panning.startX) + Math.abs(e.clientY - this.panning.startY)
    this.panning = null
    if (wasBlank && moved < 4) {
      if (this.selectedId === null && this.propsOverlay?.classList.contains('open')) { this.propsOverlay.classList.remove('open'); this._lastPropsNode = null }
      this.selectedId = null; this._lastPropsNode = null; this.render()
    }
  }
}

export function onDblClick(this: typeof WF, e: MouseEvent): void {
  const target = e.target as HTMLElement
  if (target.closest('#wfSidebar') || target.closest('#wfPropsOverlay')) return
  if (!target.closest('.wf-node') && !target.closest('[data-edge-id]')) {
    this.propsOverlay?.classList.remove('open')
    this.selectedId = null; this._lastPropsNode = null; this.render()
  }
}

export function onKeyDown(this: typeof WF, e: KeyboardEvent): void {
  if (!this.canvasWrap?.contains(document.activeElement) && document.activeElement !== document.body) return
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); this.undo() }
  if ((e.ctrlKey || e.metaKey) && e.key === 'y') { e.preventDefault(); this.redo() }
  if (e.metaKey && e.shiftKey && e.key === 'z') { e.preventDefault(); this.redo() }  // macOS
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); document.querySelector('#btnWfSaveCanvas')?.dispatchEvent(new Event('click')) }
  if (e.key === 'f' || (e.ctrlKey && e.key === '0')) { e.preventDefault(); this.fitView() }
  if (e.key === 'Delete' || e.key === 'Backspace') {
    const ae = document.activeElement as HTMLElement | null
    const isInput = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' || ae.tagName === 'SELECT' || (ae as any).isContentEditable)
    if (this.selectedId && !isInput) { e.preventDefault(); this.deleteSelected() }
  }
  if (e.key === 'Escape') {
    if (this.drawing) { this.drawing = null; if (this.tempEdge) this.tempEdge.style.display = 'none' }
    this.propsOverlay?.classList.remove('open')
    this.selectedId = null; this._lastPropsNode = null; this.render()
  }
}

export function onWheel(this: typeof WF, e: WheelEvent): void {
  if ((e.target as HTMLElement).closest('#wfSidebar') || (e.target as HTMLElement).closest('#wfPropsOverlay')) return
  e.preventDefault()
  const delta = e.deltaY > 0 ? -0.08 : 0.08
  const rect = this.svg!.getBoundingClientRect()
  const mx = e.clientX - rect.left, my = e.clientY - rect.top
  const oldZoom = this.zoom
  this.zoom = Math.max(0.2, Math.min(2.5, this.zoom + delta))
  this.panX = mx - (mx - this.panX) * (this.zoom / oldZoom)
  this.panY = my - (my - this.panY) * (this.zoom / oldZoom)
  this.updateViewport()
}

function renderTempEdge(this: typeof WF): void {
  if (!this.drawing || !this.tempEdge) return
  const [x1, y1] = [this.drawing.fromX, this.drawing.fromY]
  const rect = this.svg!.getBoundingClientRect()
  const x2 = (this.drawing.mouseX - rect.left - this.panX) / this.zoom
  const y2 = (this.drawing.mouseY - rect.top - this.panY) / this.zoom
  this.tempEdge.setAttribute('d', this.bezierPath(x1, y1, x2, y2))
  this.tempEdge.style.display = ''
}
