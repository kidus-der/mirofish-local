<template>
  <section class="graph-panel" :aria-label="$t('graph.panelTitle')">
    <header class="panel-header">
      <h2 class="hb-heading panel-title">{{ $t('graph.panelTitle') }}</h2>
      <div class="header-tools">
        <button type="button" class="hb-btn tool-btn" :disabled="loading" :title="$t('graph.refreshGraph')" @click="$emit('refresh')">
          <svg class="tool-icon" :class="{ spinning: loading }" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.7-4M12 1.5V4.2H9.3" />
          </svg>
          <span>Refresh</span>
        </button>
        <button type="button" class="hb-btn tool-btn tool-btn--icon" :title="$t('graph.toggleMaximize')" :aria-label="$t('graph.toggleMaximize')" @click="$emit('toggle-maximize')">
          <svg class="tool-icon" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10" />
          </svg>
        </button>
      </div>
    </header>

    <div v-if="graphData" class="graph-key hb-surface-land-soft">
      <div class="key-group" role="group" :aria-label="$t('graph.factOrigin', 'Fact origin')">
        <label v-for="origin in ORIGINS" :key="origin" class="key-check">
          <input v-model="shownFacts[origin]" class="hb-check" type="checkbox" />
          <svg class="line-key" width="30" height="8" aria-hidden="true">
            <line :class="`hb-line hb-line--${origin}`" x1="1" y1="4" x2="29" y2="4" />
          </svg>
          {{ originName(origin) }}
          <b class="hb-tabular">{{ factCounts[origin] }}</b>
        </label>
        <label class="key-check">
          <input v-model="shownFacts.ended" class="hb-check" type="checkbox" />
          {{ $t('graph.originEnded', 'Ended') }}
          <b class="hb-tabular">{{ factCounts.ended }}</b>
        </label>
      </div>
      <label class="key-check">
        <input v-model="showEdgeLabels" class="hb-check" type="checkbox" />
        Show Edge Labels
      </label>
    </div>

    <div ref="graphContainer" class="graph-container hb-graph-canvas">
      <div v-if="graphData" class="graph-view">
        <svg
          ref="graphSvg"
          class="graph-svg"
          :class="{
            'hide-source': !shownFacts.source,
            'hide-simulated': !shownFacts.simulated,
            'hide-unlinked': !shownFacts.unlinked,
            'hide-ended': !shownFacts.ended
          }"
          role="group"
          :aria-label="$t('graph.panelTitle')"
        ></svg>

        <p v-if="currentPhase === 1 || isSimulating" class="graph-hint" role="status">
          <span class="hb-status hb-status--running">
            {{ isSimulating ? $t('graph.graphMemoryRealtime') : $t('graph.realtimeUpdating') }}
          </span>
        </p>

        <div v-if="showSimulationFinishedHint" class="graph-hint" role="status">
          <span>{{ $t('graph.pendingContentHint') }}</span>
          <button type="button" class="icon-btn" :title="$t('graph.closeHint')" :aria-label="$t('graph.closeHint')" @click="dismissFinishedHint">
            <svg class="tool-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" /></svg>
          </button>
        </div>

        <aside v-if="selectedItem" class="detail-panel" :aria-label="selectedItem.type === 'node' ? $t('graph.nodeDetails') : $t('graph.relationship')">
          <div class="detail-panel-header">
            <h3 class="hb-heading">{{ selectedItem.type === 'node' ? $t('graph.nodeDetails') : $t('graph.relationship') }}</h3>
            <span v-if="selectedItem.type === 'node'" class="hb-tag detail-type">
              <svg class="mark-key" viewBox="-9 -9 18 18" aria-hidden="true">
                <path :class="`hb-graph-node mark--${selectedItem.mark.tone}`" :d="markPath(selectedItem.mark, 90)" />
              </svg>
              {{ selectedItem.entityType }}
            </span>
            <button type="button" class="icon-btn" :title="$t('common.close')" :aria-label="$t('common.close')" @click="closeDetailPanel">
              <svg class="tool-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" /></svg>
            </button>
          </div>

          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <p class="entity-name">{{ selectedItem.data.name }}</p>
            <dl class="hb-facts">
              <dt>UUID</dt>
              <dd class="uuid-text">{{ selectedItem.data.uuid }}</dd>
              <template v-if="selectedItem.data.created_at">
                <dt>Created</dt>
                <dd>{{ formatDateTime(selectedItem.data.created_at) }}</dd>
              </template>
            </dl>

            <section v-if="selectedItem.data.summary" class="detail-section">
              <h4 class="hb-subheading">Summary</h4>
              <p class="summary-text">{{ selectedItem.data.summary }}</p>
            </section>

            <section v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0" class="detail-section">
              <h4 class="hb-subheading">Properties</h4>
              <dl class="hb-facts">
                <template v-for="(value, key) in selectedItem.data.attributes" :key="key">
                  <dt>{{ key }}</dt>
                  <dd>{{ value || 'None' }}</dd>
                </template>
              </dl>
            </section>

            <section v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0" class="detail-section">
              <h4 class="hb-subheading">Labels</h4>
              <ul class="hb-list tag-list">
                <li v-for="label in selectedItem.data.labels" :key="label" class="hb-tag">{{ label }}</li>
              </ul>
            </section>

            <section v-if="selectedFacts.length" class="detail-section">
              <h4 class="hb-subheading">{{ $t('graph.factsAtEntity', 'Facts at this entity') }}</h4>
              <p class="fact-totals">
                <span v-for="origin in ORIGINS" :key="origin" :class="`hb-origin--${origin}`">
                  <span class="hb-sounding">{{ selectedFacts.filter(fact => fact.origin === origin).length }}</span>
                  {{ originName(origin) }}
                </span>
              </p>
              <ul class="hb-list">
                <li v-for="fact in selectedFacts" :key="fact.uuid" :class="fact.origin === 'simulated' ? 'hb-row--simulated' : 'hb-row--source'">
                  <button
                    type="button"
                    class="fact-row"
                    @click="selectFact(fact)"
                    @mouseenter="traceFact(fact.uuid)"
                    @mouseleave="traceFact(null)"
                    @focus="traceFact(fact.uuid)"
                    @blur="traceFact(null)"
                  >
                    <svg class="line-key" width="30" height="8" aria-hidden="true">
                      <line :class="`hb-line hb-line--${fact.origin}`" x1="1" y1="4" x2="29" y2="4" />
                    </svg>
                    <span class="fact-body">
                      <span class="fact-head">
                        <b>{{ fact.route }}</b>
                        <span class="hb-origin" :class="`hb-origin--${fact.origin}`">{{ originName(fact.origin) }}<template v-if="fact.ended"> · {{ $t('graph.originEnded', 'Ended') }}</template></span>
                      </span>
                      <span>{{ fact.text }}</span>
                    </span>
                  </button>
                </li>
              </ul>
            </section>
          </div>

          <div v-else class="detail-content">
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <p class="edge-relation-header">
                {{ selectedItem.data.source_name }} - Self Relations
                <span class="hb-tag">{{ selectedItem.data.selfLoopCount }} items</span>
              </p>

              <ul class="hb-list">
                <li
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges"
                  :key="loop.uuid || idx"
                  :class="factOrigin(loop) === 'simulated' ? 'hb-row--simulated' : 'hb-row--source'"
                >
                  <button
                    type="button"
                    class="self-loop-toggle"
                    :aria-expanded="expandedSelfLoops.has(loop.uuid || idx)"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="hb-sounding">{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ loop.name || loop.fact_type || 'RELATED' }}</span>
                    <span class="hb-origin" :class="`hb-origin--${factOrigin(loop)}`">{{ originName(factOrigin(loop)) }}</span>
                    <svg class="tool-icon" viewBox="0 0 16 16" aria-hidden="true">
                      <path :d="expandedSelfLoops.has(loop.uuid || idx) ? 'M3 8h10' : 'M3 8h10M8 3v10'" />
                    </svg>
                  </button>

                  <dl v-show="expandedSelfLoops.has(loop.uuid || idx)" class="hb-facts self-loop-facts">
                    <template v-if="loop.uuid">
                      <dt>UUID</dt>
                      <dd class="uuid-text">{{ loop.uuid }}</dd>
                    </template>
                    <template v-if="loop.fact">
                      <dt>Fact</dt>
                      <dd>{{ loop.fact }}</dd>
                    </template>
                    <template v-if="loop.fact_type">
                      <dt>Type</dt>
                      <dd>{{ loop.fact_type }}</dd>
                    </template>
                    <template v-if="loop.created_at">
                      <dt>Created</dt>
                      <dd>{{ formatDateTime(loop.created_at) }}</dd>
                    </template>
                    <template v-if="loop.episodes && loop.episodes.length > 0">
                      <dt>Episodes</dt>
                      <dd>
                        <span v-for="ep in loop.episodes" :key="ep" class="episode-tag">{{ ep }}</span>
                      </dd>
                    </template>
                  </dl>
                </li>
              </ul>
            </template>

            <template v-else>
              <p class="edge-relation-header">
                {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || 'RELATED_TO' }} → {{ selectedItem.data.target_name }}
              </p>
              <p class="edge-origin">
                <svg class="line-key" width="30" height="8" aria-hidden="true">
                  <line :class="`hb-line hb-line--${factOrigin(selectedItem.data)}`" x1="1" y1="4" x2="29" y2="4" />
                </svg>
                <span class="hb-origin" :class="`hb-origin--${factOrigin(selectedItem.data)}`">
                  {{ originName(factOrigin(selectedItem.data)) }}<template v-if="isEnded(selectedItem.data)"> · {{ $t('graph.originEnded', 'Ended') }}</template>
                </span>
              </p>

              <dl class="hb-facts">
                <template v-if="selectedItem.data.fact">
                  <dt>Fact</dt>
                  <dd>{{ selectedItem.data.fact }}</dd>
                </template>
                <dt>Label</dt>
                <dd>{{ selectedItem.data.name || 'RELATED_TO' }}</dd>
                <dt>Type</dt>
                <dd>{{ selectedItem.data.fact_type || 'Unknown' }}</dd>
                <dt>UUID</dt>
                <dd class="uuid-text">{{ selectedItem.data.uuid }}</dd>
                <template v-if="selectedItem.data.created_at">
                  <dt>Created</dt>
                  <dd>{{ formatDateTime(selectedItem.data.created_at) }}</dd>
                </template>
                <template v-if="selectedItem.data.valid_at">
                  <dt>Valid From</dt>
                  <dd>{{ formatDateTime(selectedItem.data.valid_at) }}</dd>
                </template>
              </dl>

              <section v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0" class="detail-section">
                <h4 class="hb-subheading">Episodes</h4>
                <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">{{ ep }}</span>
              </section>
            </template>
          </div>
        </aside>
      </div>

      <p v-else-if="loading" class="graph-state" role="status">
        <span class="hb-status hb-status--running">{{ $t('graph.graphDataLoading') }}</span>
      </p>

      <p v-else class="graph-state hb-soft">{{ $t('graph.waitingOntology') }}</p>
    </div>

    <div v-if="graphData && entityTypes.length" class="graph-legend">
      <h3 class="hb-subheading">Entity Types</h3>
      <ul class="hb-list legend-items">
        <li v-for="type in entityTypes" :key="type.name" class="legend-item">
          <svg class="mark-key" viewBox="-9 -9 18 18" aria-hidden="true">
            <path :class="`hb-graph-node mark--${type.mark.tone}`" :d="markPath(type.mark, 90)" />
          </svg>
          {{ type.name }}
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import * as d3 from 'd3'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean
})

const emit = defineEmits(['refresh', 'toggle-maximize'])

const { t } = useI18n()

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true) // 默认显示边标签
const expandedSelfLoops = ref(new Set()) // 展开的自环项
const showSimulationFinishedHint = ref(false) // 模拟结束后的提示
const wasSimulating = ref(false) // 追踪之前是否在模拟中
const shownFacts = ref({ source: true, simulated: true, unlinked: true, ended: true })

// Entity types repeat after eight, so shape and fill both carry the distinction.
const MARKS = [
  { symbol: d3.symbolSquare, tone: 'land' },
  { symbol: d3.symbolCircle, tone: 'navy' },
  { symbol: d3.symbolDiamond, tone: 'water' },
  { symbol: d3.symbolTriangle, tone: 'paper' },
  { symbol: d3.symbolCircle, tone: 'land' },
  { symbol: d3.symbolSquare, tone: 'navy' },
  { symbol: d3.symbolTriangle, tone: 'water' },
  { symbol: d3.symbolDiamond, tone: 'paper' }
]
const markPath = (mark, size = 130) => d3.symbol(mark.symbol, size)()

const ORIGINS = ['source', 'simulated', 'unlinked']
const originName = (origin) => ({
  source: t('graph.originSource', 'Source'),
  simulated: t('graph.originSimulated', 'Simulated'),
  unlinked: t('graph.originUnlinked', 'No label')
})[origin]

const factOrigin = (edge) => {
  const origin = edge.attributes?.origin
  if (origin === 'simulation' || /^\s*\[SIMULATED\]/.test(edge.fact || '')) return 'simulated'
  return origin === 'document' ? 'source' : 'unlinked'
}
const isEnded = (edge) => Boolean(edge.expired_at || edge.invalid_at)

// A merged self-loop is drawn as simulated if any fact in it is, so simulated material is never shown as source.
const groupOrigin = (edges) => ['simulated', 'source', 'unlinked']
  .find(origin => edges.some(edge => factOrigin(edge) === origin))

const factCounts = computed(() => {
  const counts = { source: 0, simulated: 0, unlinked: 0, ended: 0 }
  const nodeIds = new Set((props.graphData?.nodes || []).map(node => node.uuid))
  ;(props.graphData?.edges || [])
    .filter(edge => nodeIds.has(edge.source_node_uuid) && nodeIds.has(edge.target_node_uuid))
    .forEach(edge => {
      counts[factOrigin(edge)]++
      if (isEnded(edge)) counts.ended++
    })
  return counts
})

const selectedFacts = computed(() => {
  const item = selectedItem.value
  if (item?.type !== 'node') return []
  const names = Object.fromEntries((props.graphData?.nodes || []).map(node => [node.uuid, node.name]))
  return (props.graphData?.edges || [])
    .filter(edge => edge.source_node_uuid === item.data.uuid || edge.target_node_uuid === item.data.uuid)
    .map(edge => ({
      uuid: edge.uuid,
      origin: factOrigin(edge),
      ended: isEnded(edge),
      route: `${names[edge.source_node_uuid]} → ${names[edge.target_node_uuid]}`,
      text: (edge.fact || edge.name || '').replace(/^\s*\[SIMULATED\]\s*/, '')
    }))
    .sort((a, b) => a.ended - b.ended || ORIGINS.indexOf(a.origin) - ORIGINS.indexOf(b.origin))
})

// 关闭模拟结束提示
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// 监听 isSimulating 变化，检测模拟结束
watch(() => props.isSimulating, (newValue, oldValue) => {
  if (wasSimulating.value && !newValue) {
    // 从模拟中变为非模拟状态，显示结束提示
    showSimulationFinishedHint.value = true
  }
  wasSimulating.value = newValue
}, { immediate: true })

// 切换自环项展开/折叠状态
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

// 计算实体类型用于图例
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}

  props.graphData.nodes.forEach(node => {
    const type = node.labels?.find(l => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, mark: MARKS[Object.keys(typeMap).length % MARKS.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

// 格式化时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true 
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  expandedSelfLoops.value = new Set() // 重置展开状态
}


let currentSimulation = null
let linkLabelsRef = null
let graphParts = null
let drawnSize = null
let resizeObserver = null

const edgeHasFact = (d, uuid) => d.rawData.uuid === uuid || d.rawData.selfLoopEdges?.some(loop => loop.uuid === uuid)

const paintSelection = () => {
  if (!graphParts) return
  const { link, linkLabels, node, nodeLabels } = graphParts
  const item = selectedItem.value
  const nodeId = item?.type === 'node' ? item.data.uuid : null
  const edgeKey = item?.type === 'edge' ? item.key : null
  const isOn = d => d.key === edgeKey || d.source.id === nodeId || d.target.id === nodeId
  link.classed('is-on', isOn)
  linkLabels.classed('is-on', isOn)
  node.classed('is-selected', d => d.id === nodeId)
  nodeLabels.classed('is-selected', d => d.id === nodeId)
}

const traceFact = (uuid) => {
  graphParts?.link.classed('is-traced', d => Boolean(uuid) && edgeHasFact(d, uuid))
}

const selectFact = (fact) => {
  const edge = graphParts?.edges.find(d => edgeHasFact(d, fact.uuid))
  if (edge) selectedItem.value = { type: 'edge', data: edge.rawData, key: edge.key }
}

// With reduced motion the layout is computed up front instead of animating into place.
const settle = (simulation) => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    simulation.stop().tick(300)
    simulation.on('tick')()
  } else {
    simulation.restart()
  }
}

const renderGraph = () => {
  if (!graphSvg.value || !props.graphData) return

  // 停止之前的仿真
  if (currentSimulation) {
    currentSimulation.stop()
  }
  currentSimulation = null
  graphParts = null

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  // A hidden pane has no size; the resize observer draws the graph when it is shown.
  if (!width || !height) return
  drawnSize = { width, height }

  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    
  svg.selectAll('*').remove()
  
  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []
  
  if (nodesData.length === 0) return

  // Prep data
  const nodeMap = {}
  nodesData.forEach(n => nodeMap[n.uuid] = n)
  
  const nodes = nodesData.map(n => ({
    id: n.uuid,
    name: n.name || 'Unnamed',
    type: n.labels?.find(l => l !== 'Entity') || 'Entity',
    rawData: n
  }))
  
  const nodeIds = new Set(nodes.map(n => n.id))
  
  // 处理边数据，计算同一对节点间的边数量和索引
  const edgePairCount = {}
  const selfLoopEdges = {} // 按节点分组的自环边
  const tempEdges = edgesData
    .filter(e => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))
  
  // 统计每对节点之间的边数量，收集自环边
  tempEdges.forEach(e => {
    if (e.source_node_uuid === e.target_node_uuid) {
      // 自环 - 收集到数组中
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })
  
  // 记录当前处理到每对节点的第几条边
  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set() // 已处理的自环节点
  
  const edges = []
  
  tempEdges.forEach(e => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid
    
    if (isSelfLoop) {
      // 自环边 - 每个节点只添加一条合并的自环
      if (processedSelfLoopNodes.has(e.source_node_uuid)) {
        return // 已处理过，跳过
      }
      processedSelfLoopNodes.add(e.source_node_uuid)
      
      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || 'Unknown'
      
      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        type: 'SELF_LOOP',
        name: `Self Relations (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        key: `loop:${e.source_node_uuid}`,
        origin: groupOrigin(allSelfLoops),
        ended: allSelfLoops.every(isEnded),
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops // 存储所有自环边的详细信息
        }
      })
      return
    }
    
    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1
    
    // 判断边的方向是否与标准化方向一致（源UUID < 目标UUID）
    const isReversed = e.source_node_uuid > e.target_node_uuid
    
    // 计算曲率：多条边时分散开，单条边为直线
    let curvature = 0
    if (totalCount > 1) {
      // 均匀分布曲率，确保明显区分
      // 曲率范围根据边数量增加，边越多曲率范围越大
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      
      // 如果边的方向与标准化方向相反，翻转曲率
      // 这样确保所有边在同一参考系下分布，不会因方向不同而重叠
      if (isReversed) {
        curvature = -curvature
      }
    }
    
    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      type: e.fact_type || e.name || 'RELATED',
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      key: e.uuid || `${pairKey}:${currentIndex}`,
      origin: factOrigin(e),
      ended: isEnded(e),
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })

  // Simulation - 根据边数量动态调整节点间距
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      // 根据这对节点之间的边数量动态调整距离
      // 基础距离 150，每多一条边增加 40
      const baseDistance = 150
      const edgeCount = d.pairTotal || 1
      return baseDistance + (edgeCount - 1) * 50
    }))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(50))
    // 添加向中心的引力，让独立的节点群聚集到中心区域
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
  
  currentSimulation = simulation

  const g = svg.append('g')
  
  // Zoom
  svg.call(d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.1, 4]).on('zoom', (event) => {
    g.attr('transform', event.transform)
  }))

  // Links - 使用 path 支持曲线
  const linkGroup = g.append('g').attr('class', 'links')
  
  // 计算曲线路径
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // 检测自环
    if (d.isSelfLoop) {
      // 自环：绘制一个圆弧从节点出发再返回
      const loopRadius = 30
      // 从节点右侧出发，绕一圈回来
      const x1 = sx + 8  // 起点偏移
      const y1 = sy - 4
      const x2 = sx + 8  // 终点偏移
      const y2 = sy + 4
      // 使用圆弧绘制自环（sweep-flag=1 顺时针）
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }
    
    if (d.curvature === 0) {
      // 直线
      return `M${sx},${sy} L${tx},${ty}`
    }
    
    // 计算曲线控制点 - 根据边数量和距离动态调整
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    // 垂直于连线方向的偏移，根据距离比例计算，保证曲线明显可见
    // 边越多，偏移量占距离的比例越大
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05 // 基础25%，每多一条边增加5%
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }
  
  // 计算曲线中点（用于标签定位）
  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // 检测自环
    if (d.isSelfLoop) {
      // 自环标签位置：节点右侧
      return { x: sx + 70, y: sy }
    }
    
    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }
    
    // 二次贝塞尔曲线的中点 t=0.5
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    // 二次贝塞尔曲线公式 B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2, t=0.5
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    
    return { x: midX, y: midY }
  }
  

  const edgeClass = d => `edge--${d.origin}${d.ended ? ' edge--ended' : ''}`
  const selectEdge = (event, d) => {
    event.stopPropagation()
    selectedItem.value = { type: 'edge', data: d.rawData, key: d.key }
  }

  // Source facts are solid chart lines, simulated facts dashed magenta tracks.
  const link = linkGroup.selectAll('path.edge-line')
    .data(edges)
    .enter().append('path')
    .attr('class', d => `edge-line hb-line hb-line--${d.origin}${d.ended ? ' hb-line--ended' : ''} ${edgeClass(d)}`)

  // Thin dashed lines are hard to hit, so a wider invisible stroke takes the pointer.
  const linkHit = linkGroup.selectAll('path.edge-hit')
    .data(edges)
    .enter().append('path')
    .attr('class', d => `edge-hit ${edgeClass(d)}`)
    .on('click', selectEdge)
  linkHit.append('title')
    .text(d => `${d.rawData.source_name} → ${d.rawData.target_name}: ${d.rawData.fact || d.name}`)

  // Link labels
  const linkLabels = linkGroup.selectAll('text')
    .data(edges)
    .enter().append('text')
    .text(d => d.name)
    .attr('class', d => `edge-name edge-name--${d.origin} ${edgeClass(d)}`)
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', selectEdge)

  // 保存引用供外部控制显隐
  linkLabelsRef = linkLabels

  // Nodes group
  const nodeGroup = g.append('g').attr('class', 'nodes')
  const markByType = Object.fromEntries(entityTypes.value.map(type => [type.name, type.mark]))
  const selectNode = (d) => {
    selectedItem.value = {
      type: 'node',
      data: d.rawData,
      entityType: d.type,
      mark: markByType[d.type]
    }
  }

  const node = nodeGroup.selectAll('path')
    .data(nodes)
    .enter().append('path')
    .attr('class', d => `graph-node hb-graph-node mark--${markByType[d.type].tone}`)
    .attr('d', d => markPath(markByType[d.type]))
    .attr('tabindex', 0)
    .attr('role', 'button')
    .attr('aria-label', d => `${d.name}, ${d.type}`)
    .call(d3.drag()
      .on('start', (event, d) => {
        // 只记录位置，不重启仿真（区分点击和拖拽）
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        // 检测是否真正开始拖拽（移动超过阈值）
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (!d._isDragging && distance > 3) {
          // 首次检测到真正拖拽，才重启仿真
          d._isDragging = true
          simulation.alphaTarget(0.3).restart()
        }
        
        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        // 只有真正拖拽过才让仿真逐渐停止
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      selectNode(d)
    })
    .on('keydown', (event, d) => {
      if (event.key !== 'Enter' && event.key !== ' ') return
      event.preventDefault()
      event.stopPropagation()
      selectNode(d)
    })
  node.append('title').text(d => `${d.name} · ${d.type}`)

  // Node Labels
  const nodeLabels = nodeGroup.selectAll('text')
    .data(nodes)
    .enter().append('text')
    .text(d => d.name.length > 22 ? d.name.substring(0, 22) + '…' : d.name)
    .attr('class', 'hb-graph-label graph-node-label')
    .attr('dx', 13)
    .attr('dy', 4)

  simulation.on('tick', () => {
    // 更新曲线路径
    link.attr('d', getLinkPath)
    linkHit.attr('d', getLinkPath)

    // 更新边标签位置（无旋转，水平显示更清晰）
    linkLabels.each(function(d) {
      const mid = getLinkMidpoint(d)
      d3.select(this)
        .attr('x', mid.x)
        .attr('y', mid.y)
    })

    node.attr('transform', d => `translate(${d.x},${d.y})`)

    nodeLabels
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })

  // 点击空白处关闭详情面板
  svg.on('click', () => {
    selectedItem.value = null
  })

  graphParts = { link, linkLabels, node, nodeLabels, edges }
  paintSelection()
  settle(simulation)
}

watch(selectedItem, paintSelection)

watch(() => props.graphData, () => {
  nextTick(renderGraph)
}, { deep: true })

// 监听边标签显示开关
watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) {
    linkLabelsRef.style('display', newVal ? 'block' : 'none')
  }
})

// Panels resize with the layout switch as well as the window, so watch the container itself.
const handleResize = () => {
  const width = graphContainer.value?.clientWidth
  const height = graphContainer.value?.clientHeight
  if (!width || !height || !props.graphData) return
  if (!currentSimulation) {
    renderGraph()
    return
  }
  if (width === drawnSize.width && height === drawnSize.height) return

  // Refit in place so positions, zoom and the selection survive.
  drawnSize = { width, height }
  d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
  currentSimulation.force('center').x(width / 2).y(height / 2)
  currentSimulation.force('x').x(width / 2)
  currentSimulation.force('y').y(height / 2)
  settle(currentSimulation.alpha(0.3))
}

onMounted(() => {
  resizeObserver = new ResizeObserver(handleResize)
  resizeObserver.observe(graphContainer.value)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  if (currentSimulation) {
    currentSimulation.stop()
  }
})
</script>

<style scoped>
.graph-panel {
  container-type: inline-size;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--hb-paper);
}

.panel-header {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: var(--hb-space-3);
  padding: 7px var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
}

.panel-title {
  min-width: 0;
  overflow-wrap: anywhere;
}

.header-tools {
  display: flex;
  flex: none;
  gap: var(--hb-space-2);
}

.tool-btn {
  font-size: var(--hb-text-sm);
}

.tool-btn--icon {
  width: var(--hb-control);
  padding: 0;
}

.tool-icon {
  flex: none;
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
}

.tool-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.icon-btn {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: var(--hb-control);
  height: var(--hb-control);
  color: var(--hb-navy);
  background: transparent;
  border: 0;
  border-radius: var(--hb-radius);
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.icon-btn:hover {
  background: var(--hb-water-soft);
}

.graph-key {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px var(--hb-space-4);
  padding: 5px var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
  font-size: var(--hb-text-sm);
}

.key-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
}

.key-check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 26px;
  white-space: nowrap;
  cursor: pointer;
}

.line-key {
  flex: none;
}

.graph-container {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}

.graph-view,
.graph-svg {
  display: block;
  width: 100%;
  height: 100%;
}

.graph-svg {
  cursor: grab;
}

.graph-svg:active {
  cursor: grabbing;
}

.graph-svg :deep(.edge-line) {
  pointer-events: none;
  vector-effect: non-scaling-stroke;
  transition: stroke-width var(--hb-motion-fast) ease-out;
}

.graph-svg :deep(.edge-line:not(.is-on):not(.is-traced)) {
  opacity: 0.72;
}

.graph-svg :deep(.edge-line.hb-line--ended:not(.is-on):not(.is-traced)) {
  opacity: 0.48;
}

.graph-svg :deep(.edge-line.is-on) {
  stroke-width: 2.3;
}

.graph-svg :deep(.edge-line.is-traced) {
  stroke-width: 3.4;
}

.graph-svg :deep(.edge-hit) {
  fill: none;
  stroke: transparent;
  stroke-width: 12;
  vector-effect: non-scaling-stroke;
  cursor: pointer;
}

.graph-svg :deep(.edge-name) {
  fill: var(--hb-navy-soft);
  font: 500 var(--hb-text-xs) var(--hb-font-sans);
  paint-order: stroke;
  stroke: var(--hb-water-soft);
  stroke-width: 4px;
  stroke-linejoin: round;
  cursor: pointer;
}

.graph-svg :deep(.edge-name--simulated) {
  fill: var(--hb-magenta);
}

.graph-svg :deep(.edge-name.is-on) {
  font-weight: 700;
}

.graph-svg.hide-source :deep(.edge--source),
.graph-svg.hide-simulated :deep(.edge--simulated),
.graph-svg.hide-unlinked :deep(.edge--unlinked),
.graph-svg.hide-ended :deep(.edge--ended) {
  display: none;
}

.graph-svg :deep(.graph-node) {
  cursor: pointer;
  transition: stroke-width var(--hb-motion-fast) ease-out;
}

.graph-svg :deep(.graph-node:hover) {
  stroke-width: 2.4;
}

.graph-svg :deep(.graph-node.is-selected),
.graph-svg :deep(.graph-node:focus-visible) {
  stroke-width: 3;
}

.graph-svg :deep(.graph-node-label) {
  pointer-events: none;
}

.graph-svg :deep(.graph-node-label.is-selected) {
  font-weight: 800;
}

.graph-panel :deep(.mark--land) { fill: var(--hb-land); }
.graph-panel :deep(.mark--navy) { fill: var(--hb-navy); }
.graph-panel :deep(.mark--water) { fill: var(--hb-water); }
.graph-panel :deep(.mark--paper) { fill: var(--hb-paper); }

.mark-key {
  flex: none;
  width: 14px;
  height: 14px;
}

.graph-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--hb-space-5);
  text-align: center;
}

.graph-hint {
  position: absolute;
  bottom: var(--hb-space-3);
  left: var(--hb-space-3);
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
  max-width: min(460px, calc(100% - 24px));
  min-height: var(--hb-control);
  padding: 4px 10px;
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  border-radius: var(--hb-radius);
  font-size: var(--hb-text-sm);
}

.graph-hint:has(.icon-btn) {
  padding-right: 0;
}

.graph-legend {
  display: flex;
  flex: none;
  align-items: baseline;
  gap: 4px var(--hb-space-3);
  max-height: 64px;
  padding: 5px var(--hb-space-4);
  overflow-y: auto;
  border-top: 1px solid var(--hb-navy);
}

.graph-legend h3 {
  flex: none;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 14px;
  font-size: var(--hb-text-sm);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  overflow-wrap: anywhere;
}

.detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  width: min(380px, 100%);
  background: var(--hb-paper);
  border-left: 1px solid var(--hb-navy);
}

.detail-panel-header {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--hb-space-2);
  padding: 5px 6px 5px var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
}

.detail-panel-header h3 {
  flex: 1;
  min-width: 0;
}

.detail-type {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-content {
  flex: 1;
  min-height: 0;
  padding: var(--hb-space-3) var(--hb-space-4) var(--hb-space-4);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.entity-name {
  margin-bottom: var(--hb-space-2);
  font: 700 var(--hb-text-2xl) / 1.12 var(--hb-font-serif);
  overflow-wrap: anywhere;
}

.uuid-text {
  font-size: var(--hb-text-xs);
  font-variant-numeric: tabular-nums;
}

.detail-section {
  margin-top: var(--hb-space-4);
}

.detail-section h4 {
  margin-bottom: 5px;
}

.summary-text {
  font-size: var(--hb-text-sm);
  line-height: 1.4;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-1);
}

.fact-totals {
  display: flex;
  flex-wrap: wrap;
  gap: 2px var(--hb-space-4);
  padding: 5px 0;
  border-block: 1px solid var(--hb-navy);
  font-size: var(--hb-text-sm);
}

.fact-totals .hb-sounding {
  font-size: var(--hb-text-xl);
}

.fact-row,
.self-loop-toggle {
  display: flex;
  gap: 9px;
  width: 100%;
  padding: 5px 3px;
  color: var(--hb-navy);
  background: transparent;
  border: 0;
  font: 400 var(--hb-text-sm) / 1.25 var(--hb-font-sans);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.fact-row:hover,
.self-loop-toggle:hover {
  background: var(--hb-water-soft);
}

.fact-row .line-key {
  margin-top: 5px;
}

.fact-body {
  display: grid;
  flex: 1;
  gap: 1px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.fact-head {
  display: flex;
  justify-content: space-between;
  gap: var(--hb-space-2);
}

.fact-head .hb-origin {
  padding-top: 2px;
}

.edge-relation-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px var(--hb-space-2);
  margin-bottom: var(--hb-space-2);
  font: 700 var(--hb-text-xl) / 1.2 var(--hb-font-serif);
  overflow-wrap: anywhere;
}

.edge-origin {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
  margin-bottom: var(--hb-space-3);
}

.self-loop-toggle {
  align-items: center;
}

.self-loop-name {
  flex: 1;
  min-width: 0;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.self-loop-facts {
  padding: 0 3px var(--hb-space-2);
}

.episode-tag {
  display: block;
  font-size: var(--hb-text-xs);
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}

@container (max-width: 520px) {
  .detail-panel {
    top: auto;
    left: 0;
    width: auto;
    height: 62%;
    border-top: 1px solid var(--hb-navy);
    border-left: 0;
  }
}
</style>
