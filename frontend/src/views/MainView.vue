<template>
  <div class="stage">
    <HarborTopBar :links="navLinks">
      <template #status>
        <span>{{ addressesAreLoopback ? $t('home.loopbackAddresses') : $t('home.nonLoopbackAddress') }}</span>
      </template>
    </HarborTopBar>

    <div class="stage-bar hb-surface-water">
      <h1 class="run-name" :title="runName">{{ runName }}</h1>
      <ol class="hb-list steps" :aria-label="$t('main.workflowStages', 'Workflow stages')">
        <li
          v-for="(name, index) in $tm('main.stepNames')"
          :key="index"
          :aria-current="index === currentStep - 1 ? 'step' : undefined"
        >
          <em class="hb-sounding">{{ index + 1 }}</em>
          <span class="step-name">{{ name }}</span>
        </li>
      </ol>
      <span
        class="hb-status run-status"
        :class="`hb-status--${ { processing: 'running', completed: 'completed', error: 'failed', ready: 'idle' }[statusClass] }`"
        role="status"
      >{{ statusText }}</span>
      <div class="view-switcher" role="group" :aria-label="$t('main.layoutLabel', 'Layout')">
        <button
          v-for="mode in ['graph', 'split', 'workbench']"
          :key="mode"
          type="button"
          :aria-pressed="viewMode === mode"
          @click="viewMode = mode"
        >
          {{ { graph: $t('main.layoutGraph'), split: $t('main.layoutSplit'), workbench: $t('main.layoutWorkbench') }[mode] }}
        </button>
      </div>
    </div>

    <main class="stage-work" :data-view="viewMode">
      <div class="pane pane--work">
        <Step1GraphBuild
          v-if="currentStep === 1"
          :currentPhase="currentPhase"
          :projectData="projectData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          :error="error"
          @next-step="handleNextStep"
        />
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
        />
      </div>

      <div class="pane pane--graph">
        <GraphPanel
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import GraphPanel from '../components/GraphPanel.vue'
import Step1GraphBuild from '../components/Step1GraphBuild.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { generateOntology, getProject, buildGraph, getTaskStatus, getGraphData } from '../api/graph'
import { getPendingUpload, clearPendingUpload } from '../store/pendingUpload'
import HarborTopBar from '../components/HarborTopBar.vue'
import service from '../api/index'

const route = useRoute()
const router = useRouter()
const { t, tm } = useI18n()

// Layout State
const viewMode = ref('split') // graph | split | workbench

// Step State
const currentStep = ref(1) // 1: 图谱构建, 2: 环境搭建, 3: 开始模拟, 4: 报告生成, 5: 深度互动
const stepNames = computed(() => tm('main.stepNames'))

// Data State
const currentProjectId = ref(route.params.projectId)
const loading = ref(false)
const graphLoading = ref(false)
const error = ref('')
const projectData = ref(null)
const graphData = ref(null)
const currentPhase = ref(-1) // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyProgress = ref(null)
const buildProgress = ref(null)
const systemLogs = ref([])

// Polling timers
let pollTimer = null
let graphPollTimer = null

// --- Shell ---
const isLoopback = (hostname) => /^(localhost|127(\.\d{1,3}){3}|\[::1\])$/.test(hostname)
const addressesAreLoopback = [window.location.href, new URL(service.defaults.baseURL, window.location.href).href]
  .every(url => isLoopback(new URL(url).hostname))
const navLinks = computed(() => [
  { label: t('nav.newScenario'), to: { name: 'Home' } },
  ...(projectData.value?.graph_id ? [{ label: t('main.layoutGraph'), to: { name: 'Process', params: { projectId: projectData.value.project_id } } }] : [])
])
const runName = computed(() => projectData.value?.simulation_requirement || projectData.value?.name || tm('main.stepNames')[currentStep.value - 1])

// --- Status Computed ---
const statusClass = computed(() => {
  if (error.value) return 'error'
  if (currentPhase.value >= 2) return 'completed'
  return 'processing'
})

const statusText = computed(() => {
  if (error.value) return 'Error'
  if (currentPhase.value >= 2) return 'Ready'
  if (currentPhase.value === 1) return 'Building Graph'
  if (currentPhase.value === 0) return 'Generating Ontology'
  return 'Initializing'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  // Keep last 100 logs
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleNextStep = (params = {}) => {
  if (currentStep.value < 5) {
    currentStep.value++
    addLog(t('log.enterStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
    
    // 如果是从 Step 2 进入 Step 3，记录模拟轮数配置
    if (currentStep.value === 3 && params.maxRounds) {
      addLog(t('log.customSimRounds', { rounds: params.maxRounds }))
    }
  }
}

const handleGoBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    addLog(t('log.returnToStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
  }
}

// --- Data Logic ---

const initProject = async () => {
  addLog('Project view initialized.')
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadProject()
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()
  if (!pending.isPending || pending.files.length === 0) {
    error.value = 'No pending files found.'
    addLog('Error: No pending files found for new project.')
    return
  }
  
  try {
    loading.value = true
    currentPhase.value = 0
    ontologyProgress.value = { message: 'Uploading and analyzing docs...' }
    addLog('Starting ontology generation: Uploading files...')
    
    const formData = new FormData()
    pending.files.forEach(f => formData.append('files', f))
    formData.append('simulation_requirement', pending.simulationRequirement)
    
    const res = await generateOntology(formData)
    if (res.success) {
      clearPendingUpload()
      currentProjectId.value = res.data.project_id
      projectData.value = res.data
      
      router.replace({ name: 'Process', params: { projectId: res.data.project_id } })
      ontologyProgress.value = null
      addLog(`Ontology generated successfully for project ${res.data.project_id}`)
      await startBuildGraph()
    } else {
      error.value = res.error || 'Ontology generation failed'
      addLog(`Error generating ontology: ${error.value}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in handleNewProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const loadProject = async () => {
  try {
    loading.value = true
    addLog(`Loading project ${currentProjectId.value}...`)
    const res = await getProject(currentProjectId.value)
    if (res.success) {
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      addLog(`Project loaded. Status: ${res.data.status}`)
      
      if (res.data.status === 'ontology_generated' && !res.data.graph_id) {
        await startBuildGraph()
      } else if (res.data.status === 'graph_building' && res.data.graph_build_task_id) {
        currentPhase.value = 1
        startPollingTask(res.data.graph_build_task_id)
      } else if (res.data.status === 'graph_completed' && res.data.graph_id) {
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
      }
    } else {
      error.value = res.error
      addLog(`Error loading project: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in loadProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

const updatePhaseByStatus = (status) => {
  switch (status) {
    case 'created':
    case 'ontology_generated': currentPhase.value = 0; break;
    case 'graph_building': currentPhase.value = 1; break;
    case 'graph_completed': currentPhase.value = 2; break;
    case 'failed': error.value = 'Project failed'; break;
  }
}

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    buildProgress.value = { progress: 0, message: 'Starting build...' }
    addLog('Initiating graph build...')
    
    const res = await buildGraph({ project_id: currentProjectId.value })
    if (res.success) {
      if (res.data.reused && res.data.graph_id) {
        currentPhase.value = 2
        buildProgress.value = null
        const projectRes = await getProject(currentProjectId.value)
        if (projectRes.success) {
          projectData.value = projectRes.data
        }
        await loadGraph(res.data.graph_id)
        return
      }

      addLog(`Graph build task started. Task ID: ${res.data.task_id}`)
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(`Error starting build: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in startBuildGraph: ${err.message}`)
  }
}

const startGraphPolling = () => {
  addLog('Started polling for graph data...')
  fetchGraphData()
  graphPollTimer = setInterval(fetchGraphData, 10000)
}

const fetchGraphData = async () => {
  try {
    // Refresh project info to check for graph_id
    const projRes = await getProject(currentProjectId.value)
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id)
      if (gRes.success) {
        graphData.value = gRes.data
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0
        addLog(`Graph data refreshed. Nodes: ${nodeCount}, Edges: ${edgeCount}`)
      }
    }
  } catch (err) {
    console.warn('Graph fetch error:', err)
  }
}

const startPollingTask = (taskId) => {
  pollTaskStatus(taskId)
  pollTimer = setInterval(() => pollTaskStatus(taskId), 2000)
}

const pollTaskStatus = async (taskId) => {
  try {
    const res = await getTaskStatus(taskId)
    if (res.success) {
      const task = res.data
      
      // Log progress message if it changed
      if (task.message && task.message !== buildProgress.value?.message) {
        addLog(task.message)
      }
      
      buildProgress.value = { progress: task.progress || 0, message: task.message }
      
      if (task.status === 'completed') {
        addLog('Graph build task completed.')
        stopPolling()
        stopGraphPolling() // Stop polling, do final load
        currentPhase.value = 2
        
        // Final load
        const projRes = await getProject(currentProjectId.value)
        if (projRes.success && projRes.data.graph_id) {
            projectData.value = projRes.data
            await loadGraph(projRes.data.graph_id)
        }
      } else if (task.status === 'failed') {
        stopPolling()
        error.value = task.error
        addLog(`Graph build task failed: ${task.error}`)
      }
    }
  } catch (e) {
    console.error(e)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  addLog(`Loading full graph data: ${graphId}`)
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully.')
    } else {
      addLog(`Failed to load graph data: ${res.error}`)
    }
  } catch (e) {
    addLog(`Exception loading graph: ${e.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog('Manual graph refresh triggered.')
    loadGraph(projectData.value.graph_id)
  }
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer)
    graphPollTimer = null
    addLog('Graph polling stopped.')
  }
}

onMounted(() => {
  initProject()
})

onUnmounted(() => {
  stopPolling()
  stopGraphPolling()
})
</script>

<style scoped>
.stage {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.stage-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 13px;
  min-height: var(--hb-topbar);
  padding: 6px 18px;
  border-bottom: 1px solid var(--hb-navy);
}

.run-name {
  display: -webkit-box;
  flex: 1 1 12rem;
  min-width: 0;
  overflow: hidden;
  font: 700 var(--hb-text-xl) / 1.15 var(--hb-font-serif);
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.steps {
  display: flex;
  align-items: center;
  font-size: var(--hb-text-sm);
  white-space: nowrap;
}

.steps li {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border-radius: var(--hb-radius);
}

.steps li + li {
  margin-left: 11px;
}

.steps li + li::before {
  content: '';
  position: absolute;
  top: 50%;
  left: -11px;
  width: 11px;
  height: 1.5px;
  background: var(--hb-navy);
}

.steps [aria-current] {
  background: var(--hb-navy);
  color: var(--hb-paper);
  font-weight: 700;
}

.run-status {
  font-size: var(--hb-text-sm);
  white-space: nowrap;
}

.view-switcher {
  display: flex;
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  border-radius: var(--hb-radius);
}

.view-switcher button {
  position: relative;
  min-height: calc(var(--hb-control) - 2px);
  padding: 0 11px;
  color: var(--hb-navy);
  background: transparent;
  border: 0;
  border-left: 1px solid var(--hb-navy);
  font: 500 var(--hb-text-sm) / 1 var(--hb-font-sans);
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.view-switcher button:first-child {
  border-left: 0;
}

.view-switcher button:hover {
  background: var(--hb-water-soft);
}

.view-switcher button:focus-visible {
  z-index: 1;
}

.view-switcher button[aria-pressed='true'] {
  color: var(--hb-paper);
  background: var(--hb-navy);
  font-weight: 700;
}

.stage-work {
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(420px, 42%, 680px);
  min-height: 0;
}

.stage-work[data-view='graph'] {
  grid-template-columns: 0 minmax(0, 1fr);
}

.stage-work[data-view='workbench'] {
  grid-template-columns: minmax(0, 1fr) 0;
}

.pane {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.pane--graph {
  border-left: 1px solid var(--hb-navy);
}

/* Hidden panes stay mounted so run state and scroll position survive a layout switch. */
.stage-work[data-view='graph'] .pane--work,
.stage-work[data-view='workbench'] .pane--graph {
  visibility: hidden;
  border: 0;
}

@media (max-width: 1280px) {
  .steps {
    order: 5;
    flex: 0 0 100%;
    overflow-x: auto;
  }
}

@media (max-width: 980px) {
  .stage {
    height: auto;
    min-height: 100vh;
    min-height: 100dvh;
    overflow: visible;
  }

  .stage-work,
  .stage-work[data-view] {
    grid-template-columns: minmax(0, 1fr);
  }

  .pane--work {
    height: max(560px, 78dvh);
  }

  .pane--graph {
    height: max(340px, 56dvh);
    border-top: 1px solid var(--hb-navy);
    border-left: 0;
  }

  .stage-work[data-view='graph'] .pane--work,
  .stage-work[data-view='workbench'] .pane--graph {
    height: 0;
  }

  .stage-work[data-view='graph'] .pane--graph {
    height: max(420px, calc(100dvh - 150px));
    border-top: 0;
  }
}

@media (max-width: 620px) {
  .stage-bar {
    padding-inline: var(--hb-space-4);
  }

  .run-name {
    flex-basis: 100%;
  }

  .steps li:not([aria-current]) .step-name {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .view-switcher {
    margin-left: auto;
  }
}
</style>
