<template>
  <div class="work">
    <header class="now hb-surface-water">
      <div class="now-main">
        <div class="now-state">
          <span class="now-title" role="status">
            <span class="hb-status" :class="`hb-status--${now.state}`">{{ now.label }}</span>
            <span class="hb-heading">{{ now.stage }}</span>
          </span>
          <span v-if="currentPhase === 1" class="now-progress hb-small hb-tabular">
            <progress max="100" :value="buildProgress?.progress || 0" :aria-label="now.stage"></progress>
            <span>{{ buildProgress?.progress || 0 }}%</span>
          </span>
        </div>
        <p v-if="latestLog" class="now-log hb-small">
          <span class="hb-soft hb-tabular">{{ latestLog.time }}</span>
          <span class="now-log-msg" :title="latestLog.msg">{{ latestLog.msg }}</span>
        </p>
      </div>
      <div class="now-actions">
        <button
          class="hb-btn hb-btn--action"
          type="button"
          :disabled="currentPhase < 2 || creatingSimulation"
          @click="handleEnterEnvSetup"
        >
          {{ creatingSimulation ? $t('step1.creating') : $t('step1.enterEnvSetup') }}
        </button>
      </div>
    </header>

    <ol class="hb-list stages" tabindex="0" :aria-label="$t('main.stepNames[0]')">
      <!-- Step 01: Ontology -->
      <li class="stage" :class="{ 'active': currentPhase === 0, 'completed': currentPhase > 0 }">
        <span class="stage-num hb-sounding" aria-hidden="true">1</span>
        <div class="stage-head">
          <h2 class="hb-heading">{{ $t('step1.ontologyGeneration') }}</h2>
          <span v-if="currentPhase > 0" class="hb-status hb-status--completed">{{ $t('step1.ontologyCompleted') }}</span>
          <span v-else-if="currentPhase === 0" class="hb-status hb-status--running">{{ $t('step1.ontologyGenerating') }}</span>
          <span v-else class="hb-status hb-status--idle">{{ $t('step1.ontologyPending') }}</span>
        </div>

        <p class="stage-desc hb-small">{{ $t('step1.ontologyDesc') }}</p>
        <p class="stage-api hb-small hb-soft">POST /api/graph/ontology/generate</p>

        <p v-if="currentPhase === 0 && ontologyProgress" class="stage-message hb-small">
          {{ ontologyProgress.message || $t('step1.analyzingDocs') }}
        </p>

        <!-- Generated Entity Tags -->
        <div v-if="projectData?.ontology?.entity_types" class="block">
          <h3 class="hb-subheading">Generated entity types</h3>
          <div class="tags">
            <button
              v-for="entity in projectData.ontology.entity_types"
              :key="entity.name"
              class="hb-tag chip"
              type="button"
              :aria-pressed="isSelectedItem(entity, 'entity')"
              @click="selectOntologyItem(entity, 'entity')"
            >
              {{ entity.name }}
            </button>
          </div>
        </div>

        <!-- Generated Relation Tags -->
        <div v-if="projectData?.ontology?.edge_types" class="block">
          <h3 class="hb-subheading">Generated relation types</h3>
          <div class="tags">
            <button
              v-for="rel in projectData.ontology.edge_types"
              :key="rel.name"
              class="hb-tag chip"
              type="button"
              :aria-pressed="isSelectedItem(rel, 'relation')"
              @click="selectOntologyItem(rel, 'relation')"
            >
              {{ rel.name }}
            </button>
          </div>
        </div>

        <!-- Detail: below the tags so choosing one never moves them -->
        <section
          v-if="selectedOntologyItem"
          class="ontology-detail hb-surface-land-soft"
          :aria-label="selectedOntologyItem.name"
        >
          <div class="detail-head">
            <div class="detail-title">
              <span class="hb-tag">{{ selectedOntologyItem.itemType === 'entity' ? 'Entity' : 'Relation' }}</span>
              <strong class="detail-name">{{ selectedOntologyItem.name }}</strong>
            </div>
            <button class="hb-btn icon-btn" type="button" :aria-label="$t('common.close')" @click="selectedOntologyItem = null">
              <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M1 1l10 10M11 1L1 11" fill="none" stroke="currentColor" stroke-width="1.5" /></svg>
            </button>
          </div>
          <p class="detail-desc hb-small">{{ selectedOntologyItem.description }}</p>

          <!-- Attributes -->
          <div v-if="selectedOntologyItem.attributes?.length" class="detail-section">
            <h4 class="hb-subheading">Attributes</h4>
            <ul class="hb-list detail-list">
              <li v-for="attr in selectedOntologyItem.attributes" :key="attr.name">
                <strong>{{ attr.name }}</strong>
                <span class="hb-soft"> ({{ attr.type }})</span>
                <span> {{ attr.description }}</span>
              </li>
            </ul>
          </div>

          <!-- Examples (Entity) -->
          <div v-if="selectedOntologyItem.examples?.length" class="detail-section">
            <h4 class="hb-subheading">Examples</h4>
            <div class="tags">
              <span v-for="ex in selectedOntologyItem.examples" :key="ex" class="hb-tag wrap-tag">{{ ex }}</span>
            </div>
          </div>

          <!-- Source/Target (Relation) -->
          <div v-if="selectedOntologyItem.source_targets?.length" class="detail-section">
            <h4 class="hb-subheading">Connections</h4>
            <ul class="hb-list detail-list">
              <li v-for="(conn, idx) in selectedOntologyItem.source_targets" :key="idx" class="connection">
                <span>{{ conn.source }}</span>
                <svg width="16" height="8" viewBox="0 0 16 8" aria-hidden="true"><path d="M0 4h14M11 1l3 3-3 3" fill="none" stroke="currentColor" stroke-width="1.2" /></svg>
                <span>{{ conn.target }}</span>
              </li>
            </ul>
          </div>
        </section>
      </li>

      <!-- Step 02: Graph Build -->
      <li class="stage" :class="{ 'active': currentPhase === 1, 'completed': currentPhase > 1 }">
        <span class="stage-num hb-sounding" aria-hidden="true">2</span>
        <div class="stage-head">
          <h2 class="hb-heading">{{ $t('step1.graphRagBuild') }}</h2>
          <span v-if="currentPhase > 1" class="hb-status hb-status--completed">{{ $t('step1.ontologyCompleted') }}</span>
          <span v-else-if="currentPhase === 1" class="hb-status hb-status--running hb-tabular">{{ buildProgress?.progress || 0 }}%</span>
          <span v-else class="hb-status hb-status--idle">{{ $t('step1.ontologyPending') }}</span>
        </div>

        <p class="stage-desc hb-small">{{ $t('step1.graphRagDesc') }}</p>
        <p class="stage-api hb-small hb-soft">POST /api/graph/build</p>

        <p v-if="currentPhase === 1 && buildProgress?.message" class="stage-message hb-small">{{ buildProgress.message }}</p>

        <dl class="readout hb-tabular">
          <div>
            <dt>{{ $t('step1.entityNodes') }}</dt>
            <dd>{{ graphStats.nodes }}</dd>
          </div>
          <div>
            <dt>{{ $t('step1.relationEdges') }}</dt>
            <dd>{{ graphStats.edges }}</dd>
          </div>
          <div>
            <dt>{{ $t('step1.schemaTypes') }}</dt>
            <dd>{{ graphStats.types }}</dd>
          </div>
        </dl>
      </li>

      <!-- Step 03: Complete -->
      <li class="stage" :class="{ 'active': currentPhase === 2, 'completed': currentPhase >= 2 }">
        <span class="stage-num hb-sounding" aria-hidden="true">3</span>
        <div class="stage-head">
          <h2 class="hb-heading">{{ $t('step1.buildComplete') }}</h2>
          <span v-if="currentPhase >= 2" class="hb-status hb-status--running">{{ $t('step1.inProgress') }}</span>
        </div>

        <p class="stage-desc hb-small">{{ $t('step1.buildCompleteDesc') }}</p>
        <p class="stage-api hb-small hb-soft">POST /api/simulation/create</p>
      </li>
    </ol>

    <!-- Bottom Info / Logs -->
    <details class="logs hb-surface-land-soft" open>
      <summary class="logs-head">
        <svg width="10" height="6" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" /></svg>
        <span class="hb-subheading">System dashboard</span>
        <span class="logs-id hb-small hb-soft hb-tabular">{{ projectData?.project_id || $t('common.none') }}</span>
      </summary>
      <div class="log-content" ref="logContent" role="log" tabindex="0" aria-label="System dashboard">
        <p v-if="!systemLogs.length" class="hb-soft">{{ $t('common.noData') }}</p>
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time hb-soft hb-tabular">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </details>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createSimulation } from '../api/simulation'

const router = useRouter()
const { t } = useI18n()

const props = defineProps({
  currentPhase: { type: Number, default: 0 },
  projectData: Object,
  ontologyProgress: Object,
  buildProgress: Object,
  graphData: Object,
  systemLogs: { type: Array, default: () => [] },
  error: { type: String, default: '' }
})

defineEmits(['next-step'])

const selectedOntologyItem = ref(null)
const logContent = ref(null)
const creatingSimulation = ref(false)

// 进入环境搭建 - 创建 simulation 并跳转
const handleEnterEnvSetup = async () => {
  if (!props.projectData?.project_id || !props.projectData?.graph_id) {
    console.error('缺少项目或图谱信息')
    return
  }
  
  creatingSimulation.value = true
  
  try {
    const res = await createSimulation({
      project_id: props.projectData.project_id,
      graph_id: props.projectData.graph_id,
      enable_twitter: true,
      enable_reddit: true
    })
    
    if (res.success && res.data?.simulation_id) {
      // 跳转到 simulation 页面
      router.push({
        name: 'Simulation',
        params: { simulationId: res.data.simulation_id }
      })
    } else {
      console.error('创建模拟失败:', res.error)
      alert(t('step1.createSimulationFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    console.error('创建模拟异常:', err)
    alert(t('step1.createSimulationException', { error: err.message }))
  } finally {
    creatingSimulation.value = false
  }
}

const selectOntologyItem = (item, type) => {
  selectedOntologyItem.value = { ...item, itemType: type }
}

const isSelectedItem = (item, type) =>
  selectedOntologyItem.value?.name === item.name && selectedOntologyItem.value?.itemType === type

// What a returning researcher reads first, before scanning the stages.
const now = computed(() => {
  if (props.error) return { state: 'failed', label: t('common.failed'), stage: props.error }
  if (props.currentPhase >= 2) return { state: 'completed', label: t('common.ready'), stage: t('step1.buildComplete') }
  if (props.currentPhase === 1) return { state: 'running', label: t('step1.inProgress'), stage: t('step1.graphRagBuild') }
  if (props.currentPhase === 0) return { state: 'running', label: t('step1.ontologyGenerating'), stage: t('step1.ontologyGeneration') }
  return { state: 'idle', label: t('step1.ontologyPending'), stage: t('step1.ontologyGeneration') }
})

const latestLog = computed(() => props.systemLogs.at(-1))

const graphStats = computed(() => {
  const nodes = props.graphData?.node_count || props.graphData?.nodes?.length || 0
  const edges = props.graphData?.edge_count || props.graphData?.edges?.length || 0
  const types = props.projectData?.ontology?.entity_types?.length || 0
  return { nodes, edges, types }
})

const formatDate = (dateStr) => {
  if (!dateStr) return '--:--:--'
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + d.getMilliseconds()
}

// Auto-scroll logs
watch(() => props.systemLogs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.work {
  --pad: var(--hb-space-4);
  container-type: inline-size;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  color: var(--hb-navy);
  background: var(--hb-paper);
}

.now {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-2) var(--hb-space-4);
  padding: 9px var(--pad);
  border-bottom: 1px solid var(--hb-navy);
}

.now-main {
  flex: 1 1 20rem;
  min-width: 0;
}

.now-state {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px var(--hb-space-3);
}

.now-title {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 10px;
  min-width: 0;
}

.now-progress {
  display: inline-flex;
  align-items: center;
  gap: var(--hb-space-2);
  margin-left: auto;
  white-space: nowrap;
}

.now-log {
  display: flex;
  gap: var(--hb-space-2);
  margin-top: 2px;
}

.now-log-msg {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.now-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-2);
  max-width: 100%;
}

.now-actions .hb-btn {
  max-width: 100%;
  padding-block: 4px;
  line-height: 1.1;
  white-space: normal;
}

progress {
  appearance: none;
  width: 72px;
  height: 8px;
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
}

progress::-webkit-progress-bar {
  background: var(--hb-paper);
}

progress::-webkit-progress-value {
  background: var(--hb-navy);
}

progress::-moz-progress-bar {
  background: var(--hb-navy);
}

.stages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.stages:focus-visible,
.log-content:focus-visible,
.scroll-list:focus-visible {
  outline-offset: -2px;
}

.stage {
  position: relative;
  padding: var(--hb-space-3) var(--pad) var(--hb-space-4) calc(var(--pad) + 28px);
  border-bottom: 1px solid var(--hb-rule);
}

.stage:last-child {
  border-bottom: 0;
}

.stage.active {
  background: var(--hb-water-soft);
}

.stage::before {
  content: '';
  position: absolute;
  top: 36px;
  bottom: -10px;
  left: calc(var(--pad) + 7px);
  border-left: 1px dotted var(--hb-navy-soft);
}

.stage.completed::before {
  border-left: 1px solid var(--hb-navy);
}

.stage:last-child::before {
  display: none;
}

.stage-num {
  position: absolute;
  top: 10px;
  left: var(--pad);
  width: 16px;
  font-size: var(--hb-text-xl);
  line-height: 1.3;
  text-align: center;
}

.stage-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 2px var(--hb-space-3);
}

.stage-head .hb-status {
  font-size: var(--hb-text-sm);
  white-space: nowrap;
}

.stage-desc {
  max-width: 72ch;
  margin-top: 3px;
  text-wrap: pretty;
}

.stage-api {
  margin-top: 2px;
  overflow-wrap: anywhere;
}

.block {
  margin-top: var(--hb-space-4);
}

.block-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 2px var(--hb-space-3);
  padding-bottom: 5px;
  border-bottom: 1px solid var(--hb-navy);
}

.readout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr));
  gap: var(--hb-space-1) var(--hb-space-4);
  margin-top: var(--hb-space-3);
  padding-top: 7px;
  border-top: 1px solid var(--hb-navy);
}

.readout dt {
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.readout dd {
  font-size: var(--hb-text-xl);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 7px;
}

.icon-btn {
  flex: none;
  width: var(--hb-control);
  padding: 0;
}

.logs {
  flex: none;
  border-top: 1px solid var(--hb-navy);
}

.logs-head {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
  min-height: var(--hb-control);
  padding: 0 var(--pad);
  list-style: none;
  cursor: pointer;
}

.logs-head::-webkit-details-marker {
  display: none;
}

.logs-head svg {
  flex: none;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4;
  transform: rotate(-90deg);
}

.logs[open] .logs-head svg {
  transform: none;
}

.logs-id {
  min-width: 0;
  margin-left: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-content {
  height: 7.25rem;
  padding: 0 var(--pad) var(--hb-space-2);
  overflow-y: auto;
  font-size: var(--hb-text-sm);
}

.log-line {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--hb-space-3);
  padding: 2px 0;
  border-top: 1px solid var(--hb-rule);
}

.log-msg {
  overflow-wrap: anywhere;
}

@media (max-height: 680px) {
  .log-content {
    height: 4.25rem;
  }
}

.stage-message {
  margin-top: var(--hb-space-2);
  font-weight: 500;
}

.chip {
  max-width: 100%;
  min-height: 26px;
  overflow: hidden;
  color: var(--hb-navy);
  background: var(--hb-paper);
  line-height: 24px;
  text-overflow: ellipsis;
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.chip:hover {
  background: var(--hb-water-soft);
}

.chip[aria-pressed='true'] {
  color: var(--hb-paper);
  background: var(--hb-navy);
}

.wrap-tag {
  max-width: 100%;
  white-space: normal;
}

.ontology-detail {
  margin-top: var(--hb-space-4);
  padding: var(--hb-space-3);
  border: 1px solid var(--hb-navy);
}

.detail-head,
.detail-title {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
}

.detail-head {
  justify-content: space-between;
}

.detail-title {
  flex-wrap: wrap;
  min-width: 0;
}

.detail-name {
  font-size: var(--hb-text-lg);
  overflow-wrap: anywhere;
}

.detail-desc {
  max-width: 72ch;
  margin-top: var(--hb-space-1);
}

.detail-section {
  margin-top: var(--hb-space-3);
}

.detail-list {
  margin-top: var(--hb-space-1);
  font-size: var(--hb-text-sm);
}

.detail-list li {
  padding: 4px 0;
  border-top: 1px solid var(--hb-rule);
  overflow-wrap: anywhere;
}

.detail-list .connection {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-2);
}

@media (pointer: coarse) {
  .chip {
    min-height: var(--hb-control);
    line-height: calc(var(--hb-control) - 2px);
  }
}
</style>
