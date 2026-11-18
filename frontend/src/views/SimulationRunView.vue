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
          :aria-current="index === 2 ? 'step' : undefined"
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
        <Step3Simulation
          :simulationId="currentSimulationId"
          :maxRounds="maxRounds"
          :minutesPerRound="minutesPerRound"
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
          :currentPhase="3"
          :isSimulating="isSimulating"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step3Simulation from '../components/Step3Simulation.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation, getSimulationConfig, stopSimulation, closeSimulationEnv, getEnvStatus } from '../api/simulation'
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
// 直接在初始化时从 query 参数获取 maxRounds，确保子组件能立即获取到值
const maxRounds = ref(route.query.maxRounds ? parseInt(route.query.maxRounds) : null)
const minutesPerRound = ref(30) // 默认每轮30分钟
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error

// --- Shell ---
const isLoopback = (hostname) => /^(localhost|127(\.\d{1,3}){3}|\[::1\])$/.test(hostname)
const addressesAreLoopback = [window.location.href, new URL(service.defaults.baseURL, window.location.href).href]
  .every(url => isLoopback(new URL(url).hostname))
const navLinks = computed(() => [{ label: t('nav.newScenario'), to: { name: 'Home' } }])
const runName = computed(() => projectData.value?.simulation_requirement || projectData.value?.name || tm('main.stepNames')[2])

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Completed'
  return 'Running'
})

const isSimulating = computed(() => currentStatus.value === 'processing')

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 200) {
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

const handleGoBack = async () => {
  // 在返回 Step 2 之前，先关闭正在运行的模拟
  addLog(t('log.preparingGoBack'))
  
  // 停止轮询
  stopGraphRefresh()
  
  try {
    // 先尝试优雅关闭模拟环境
    const envStatusRes = await getEnvStatus({ simulation_id: currentSimulationId.value })
    
    if (envStatusRes.success && envStatusRes.data?.env_alive) {
      addLog(t('log.closingSimEnv'))
      try {
        await closeSimulationEnv({ 
          simulation_id: currentSimulationId.value,
          timeout: 10
        })
        addLog(t('log.simEnvClosed'))
      } catch (closeErr) {
        addLog(t('log.closeSimEnvFailed'))
        try {
          await stopSimulation({ simulation_id: currentSimulationId.value })
          addLog(t('log.simForceStopSuccess'))
        } catch (stopErr) {
          addLog(t('log.forceStopFailed', { error: stopErr.message }))
        }
      }
    } else {
      // 环境未运行，检查是否需要停止进程
      if (isSimulating.value) {
        addLog(t('log.stoppingSimProcess'))
        try {
          await stopSimulation({ simulation_id: currentSimulationId.value })
          addLog(t('log.simStopped'))
        } catch (err) {
          addLog(t('log.stopSimFailed', { error: err.message }))
        }
      }
    }
  } catch (err) {
    addLog(t('log.checkStatusFailed', { error: err.message }))
  }
  
  // 返回到 Step 2 (环境搭建)
  router.push({ name: 'Simulation', params: { simulationId: currentSimulationId.value } })
}

const handleNextStep = () => {
  // Step3Simulation 组件会直接处理报告生成和路由跳转
  // 这个方法仅作为备用
  addLog(t('log.enterStep4'))
}

// --- Data Logic ---
const loadSimulationData = async () => {
  try {
    addLog(t('log.loadingSimData', { id: currentSimulationId.value }))
    
    // 获取 simulation 信息
    const simRes = await getSimulation(currentSimulationId.value)
    if (simRes.success && simRes.data) {
      const simData = simRes.data
      
      // 获取 simulation config 以获取 minutes_per_round
      try {
        const configRes = await getSimulationConfig(currentSimulationId.value)
        if (configRes.success && configRes.data?.time_config?.minutes_per_round) {
          minutesPerRound.value = configRes.data.time_config.minutes_per_round
          addLog(t('log.timeConfig', { minutes: minutesPerRound.value }))
        }
      } catch (configErr) {
        addLog(t('log.timeConfigFetchFailed', { minutes: minutesPerRound.value }))
      }
      
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
  // 当正在模拟时，自动刷新不显示全屏 loading，以免闪烁
  // 手动刷新或初始加载时显示 loading
  if (!isSimulating.value) {
    graphLoading.value = true
  }
  
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      if (!isSimulating.value) {
        addLog(t('log.graphDataLoadSuccess'))
      }
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

// --- Auto Refresh Logic ---
let graphRefreshTimer = null

const startGraphRefresh = () => {
  if (graphRefreshTimer) return
  addLog(t('log.graphRealtimeRefreshStart'))
  // 立即刷新一次，然后每30秒刷新
  graphRefreshTimer = setInterval(refreshGraph, 30000)
}

const stopGraphRefresh = () => {
  if (graphRefreshTimer) {
    clearInterval(graphRefreshTimer)
    graphRefreshTimer = null
    addLog(t('log.graphRealtimeRefreshStop'))
  }
}

watch(isSimulating, (newValue) => {
  if (newValue) {
    startGraphRefresh()
  } else {
    stopGraphRefresh()
  }
}, { immediate: true })

onMounted(() => {
  addLog(t('log.simRunViewInit'))
  
  // 记录 maxRounds 配置（值已在初始化时从 query 参数获取）
  if (maxRounds.value) {
    addLog(t('log.customRounds', { rounds: maxRounds.value }))
  }
  
  loadSimulationData()
})

onUnmounted(() => {
  stopGraphRefresh()
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
