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
          :aria-current="index === 1 ? 'step' : undefined"
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
        <Step2EnvSetup
          :simulationId="currentSimulationId"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
          @update-status="updateStatus"
        />
      </div>

      <div class="pane pane--graph">
        <GraphPanel
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="2"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, stopSimulation, getEnvStatus, closeSimulationEnv } from '../api/simulation'
import HarborTopBar from '../components/HarborTopBar.vue'
import service from '../api/index'
import { useI18n } from 'vue-i18n'

const { t, tm } = useI18n()
const route = useRoute()
const router = useRouter()

// Props
const props = defineProps({
  simulationId: String
})

// Layout State
const viewMode = ref('split')

// Data State
const currentSimulationId = ref(route.params.simulationId)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error

// --- Shell ---
const isLoopback = (hostname) => /^(localhost|127(\.\d{1,3}){3}|\[::1\])$/.test(hostname)
const addressesAreLoopback = [window.location.href, new URL(service.defaults.baseURL, window.location.href).href]
  .every(url => isLoopback(new URL(url).hostname))
const navLinks = computed(() => [
  { label: t('nav.newScenario'), to: { name: 'Home' } },
  ...(projectData.value?.graph_id ? [{ label: t('main.layoutGraph'), to: { name: 'Process', params: { projectId: projectData.value.project_id } } }] : [])
])
const runName = computed(() => projectData.value?.simulation_requirement || projectData.value?.name || tm('main.stepNames')[1])

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Ready'
  return 'Preparing'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleGoBack = () => {
  // 返回到 process 页面
  if (projectData.value?.project_id) {
    router.push({ name: 'Process', params: { projectId: projectData.value.project_id } })
  } else {
    router.push('/')
  }
}

const handleNextStep = (params = {}) => {
  addLog(t('log.enterStep3'))

  // 记录模拟轮数配置
  if (params.maxRounds) {
    addLog(t('log.customRoundsConfig', { rounds: params.maxRounds }))
  } else {
    addLog(t('log.useAutoRounds'))
  }
  
  // 构建路由参数
  const routeParams = {
    name: 'SimulationRun',
    params: { simulationId: currentSimulationId.value }
  }
  
  // 如果有自定义轮数，通过 query 参数传递
  if (params.maxRounds) {
    routeParams.query = { maxRounds: params.maxRounds }
  }
  
  // 跳转到 Step 3 页面
  router.push(routeParams)
}

// --- Data Logic ---

/**
 * 检查并关闭正在运行的模拟
 * 当用户从 Step 3 返回到 Step 2 时，默认用户要退出模拟
 */
const checkAndStopRunningSimulation = async () => {
  if (!currentSimulationId.value) return
  
  try {
    // 先检查模拟环境是否存活
    const envStatusRes = await getEnvStatus({ simulation_id: currentSimulationId.value })
    
    if (envStatusRes.success && envStatusRes.data?.env_alive) {
      addLog(t('log.detectedSimEnvRunning'))
      
      // 尝试优雅关闭模拟环境
      try {
        const closeRes = await closeSimulationEnv({ 
          simulation_id: currentSimulationId.value,
          timeout: 10  // 10秒超时
        })
        
        if (closeRes.success) {
          addLog(t('log.simEnvClosed'))
        } else {
          addLog(t('log.closeSimEnvFailedWithError', { error: closeRes.error || t('common.unknownError') }))
          // 如果优雅关闭失败，尝试强制停止
          await forceStopSimulation()
        }
      } catch (closeErr) {
        addLog(t('log.closeSimEnvException', { error: closeErr.message }))
        // 如果优雅关闭异常，尝试强制停止
        await forceStopSimulation()
      }
    } else {
      // 环境未运行，但可能进程还在，检查模拟状态
      const simRes = await getSimulation(currentSimulationId.value)
      if (simRes.success && simRes.data?.status === 'running') {
        addLog(t('log.detectedSimRunning'))
        await forceStopSimulation()
      }
    }
  } catch (err) {
    // 检查环境状态失败不影响后续流程
    console.warn('检查模拟状态失败:', err)
  }
}

/**
 * 强制停止模拟
 */
const forceStopSimulation = async () => {
  try {
    const stopRes = await stopSimulation({ simulation_id: currentSimulationId.value })
    if (stopRes.success) {
      addLog(t('log.simForceStopSuccess'))
    } else {
      addLog(t('log.forceStopSimFailed', { error: stopRes.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.forceStopSimException', { error: err.message }))
  }
}

const loadSimulationData = async () => {
  try {
    addLog(t('log.loadingSimData', { id: currentSimulationId.value }))

    // 获取 simulation 信息
    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data

      // 获取 project 信息
      if (simData.project_id) {
        const projRes = await getProject(simData.project_id)
        if (projRes.success && projRes.data) {
          projectData.value = projRes.data
          addLog(t('log.projectLoadSuccess', { id: projRes.data.project_id }))
          
          // 获取 graph 数据
          if (projRes.data.graph_id) {
            await loadGraph(projRes.data.graph_id)
          }
        }
      }
    } else {
      addLog(t('log.loadSimDataFailed', { error: simRes.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.loadException', { error: err.message }))
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog(t('log.graphDataLoadSuccess'))
    }
  } catch (err) {
    addLog(t('log.graphLoadFailed', { error: err.message }))
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

onMounted(async () => {
  addLog(t('log.simViewInit'))
  
  // 检查并关闭正在运行的模拟（用户从 Step 3 返回时）
  await checkAndStopRunningSimulation()
  
  // 加载模拟数据
  loadSimulationData()
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
