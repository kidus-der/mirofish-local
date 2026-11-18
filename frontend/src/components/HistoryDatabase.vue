<template>
  <section class="history" aria-labelledby="history-title">
    <h2 id="history-title" class="hb-heading">{{ $t('history.title') }}</h2>

    <ul v-if="projects.length > 0" class="hb-list runs">
      <li
        v-for="project in projects"
        :key="project.simulation_id"
        class="run"
        @keydown.esc="isSelected(project) && closeAndRefocus($event)"
      >
        <button
          class="run-toggle"
          type="button"
          :aria-expanded="isSelected(project)"
          :aria-controls="`run-${project.simulation_id}`"
          @click="navigateToProject(project)"
        >
          <span class="run-title">{{ getSimulationTitle(project.simulation_requirement) }}</span>
          <span class="run-meta hb-tabular">
            <span class="hb-status" :class="`hb-status--${getProgressClass(project)}`">{{ getStatusLabel(project) }}</span>
            <span v-if="getRunMeta(project)">{{ getRunMeta(project) }}</span>
          </span>
          <svg class="run-chevron" width="10" height="6" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" /></svg>
        </button>

        <div v-if="isSelected(project)" :id="`run-${project.simulation_id}`" class="run-detail">
          <p class="run-id hb-small hb-soft hb-tabular">
            {{ formatSimulationId(project.simulation_id) }} · {{ formatDate(project.created_at) }} {{ formatTime(project.created_at) }}
          </p>

          <h3 class="hb-subheading">{{ $t('history.simRequirement') }}</h3>
          <p class="run-question">{{ project.simulation_requirement || $t('common.none') }}</p>

          <h3 class="hb-subheading">{{ $t('history.relatedFiles') }}</h3>
          <ul v-if="project.files && project.files.length > 0" class="hb-list run-files">
            <li v-for="(file, index) in project.files" :key="index">
              <span class="hb-tag">{{ getFileTypeLabel(file.filename) }}</span>
              <span class="run-file-name" :title="file.filename">{{ file.filename || $t('history.unknownFile') }}</span>
            </li>
          </ul>
          <p v-else class="hb-small">{{ $t('history.noRelatedFiles') }}</p>

          <h3 class="hb-subheading">{{ $t('history.replayTitle') }}</h3>
          <div class="run-actions">
            <button class="hb-btn" type="button" :disabled="!project.project_id" @click="goToProject">{{ $t('history.step1Button') }}</button>
            <button class="hb-btn" type="button" @click="goToSimulation">{{ $t('history.step2Button') }}</button>
            <button class="hb-btn" type="button" :disabled="!project.report_id" @click="goToReport">{{ $t('history.step4Button') }}</button>
          </div>
          <p class="hb-small hb-soft">{{ $t('history.replayHint') }}</p>
        </div>
      </li>
    </ul>

    <p v-else-if="loading" class="history-note" role="status">{{ $t('history.loadingText') }}</p>
    <div v-else-if="loadFailed" class="history-note" role="alert">
      <p>{{ $t('history.loadFailed') }}</p>
      <button class="hb-btn" type="button" @click="loadHistory">{{ $t('common.retry') }}</button>
    </div>
    <p v-else class="history-note">{{ $t('history.empty') }}</p>
  </section>
</template>

<script setup>
import { ref, onMounted, onActivated, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSimulationHistory } from '../api/simulation'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const emit = defineEmits(['loaded'])

// 状态
const projects = ref([])
const loading = ref(true)
const loadFailed = ref(false)
const selectedProject = ref(null)  // 当前展开的运行记录

// 根据运行状态与轮数获取状态
const getProgressClass = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  const runner = simulation.runner_status

  if (runner === 'completed' || (total > 0 && current >= total)) return 'completed'
  if (runner === 'starting' || runner === 'running') return 'running'
  if (runner === 'failed') return 'failed'
  return current > 0 ? 'stopped' : 'idle'
}

const getStatusLabel = (simulation) => ({
  completed: t('common.completed'),
  running: t('common.running'),
  failed: t('common.failed'),
  stopped: t('history.stopped'),
  idle: t('history.notStarted')
})[getProgressClass(simulation)]

const getRunMeta = (simulation) => [
  simulation.total_rounds ? formatRounds(simulation) : '',
  simulation.profiles_count ? t('history.agentsCount', { count: simulation.profiles_count }) : '',
  formatDate(simulation.created_at)
].filter(Boolean).join(' · ')

// 格式化日期（只显示日期部分）
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    // Use local date components (like formatTime below) so the displayed day
    // matches the displayed time. toISOString() converts to UTC and can show
    // the wrong day for non-UTC clients near midnight.
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  } catch {
    return dateStr?.slice(0, 10) || ''
  }
}

// 格式化时间（显示时:分）
const formatTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  } catch {
    return ''
  }
}

// 从模拟需求生成标题，长度由样式截断
const getSimulationTitle = (requirement) => requirement || t('history.untitledSimulation')

// 格式化 simulation_id 显示（截取前6位）
const formatSimulationId = (simulationId) => {
  if (!simulationId) return 'SIM_UNKNOWN'
  const prefix = simulationId.replace('sim_', '').slice(0, 6)
  return `SIM_${prefix.toUpperCase()}`
}

// 格式化轮数显示（当前轮/总轮数）
const formatRounds = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  if (total === 0) return t('history.notStarted')
  return t('history.roundsProgress', { current, total })
}

// 获取文件类型标签文本
const getFileTypeLabel = (filename) => {
  if (!filename) return 'FILE'
  const ext = filename.split('.').pop()?.toUpperCase()
  return ext || 'FILE'
}

const isSelected = (simulation) => selectedProject.value?.simulation_id === simulation.simulation_id

// 展开或收起运行详情
const navigateToProject = (simulation) => {
  selectedProject.value = isSelected(simulation) ? null : simulation
}

// 收起运行详情
const closeModal = () => {
  selectedProject.value = null
}

const closeAndRefocus = (event) => {
  closeModal()
  event.currentTarget.querySelector('.run-toggle')?.focus()
}

// 导航到图谱构建页面（Project）
const goToProject = () => {
  if (selectedProject.value?.project_id) {
    router.push({
      name: 'Process',
      params: { projectId: selectedProject.value.project_id }
    })
    closeModal()
  }
}

// 导航到环境配置页面（Simulation）
const goToSimulation = () => {
  if (selectedProject.value?.simulation_id) {
    router.push({
      name: 'Simulation',
      params: { simulationId: selectedProject.value.simulation_id }
    })
    closeModal()
  }
}

// 导航到分析报告页面（Report）
const goToReport = () => {
  if (selectedProject.value?.report_id) {
    router.push({
      name: 'Report',
      params: { reportId: selectedProject.value.report_id }
    })
    closeModal()
  }
}

// 加载历史项目
const loadHistory = async () => {
  let reachable = true
  try {
    loading.value = true
    loadFailed.value = false
    const response = await getSimulationHistory(20)
    if (response.success) {
      // shortcut: the API caps at 20 in directory order, so with more runs this sorts only those 20; sort in the backend to fix.
      projects.value = [...(response.data || [])].sort(
        (a, b) => (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0)
      )
    }
  } catch (error) {
    console.error('加载历史项目失败:', error)
    projects.value = []
    loadFailed.value = true
    reachable = Boolean(error.response)
  } finally {
    loading.value = false
    emit('loaded', { reachable, projects: projects.value })
  }
}

// 监听路由变化，当返回首页时重新加载数据
watch(() => route.path, (newPath) => {
  if (newPath === '/') {
    loadHistory()
  }
})

onMounted(async () => {
  // 确保 DOM 渲染完成后再加载数据
  await nextTick()
  await loadHistory()
})

// 如果使用 keep-alive，在组件激活时重新加载数据
onActivated(() => {
  loadHistory()
})
</script>

<style scoped>
.runs,
.history-note {
  margin-top: 9px;
  border-top: 1px solid var(--hb-navy);
}

.runs {
  max-height: min(52vh, 30rem);
  overflow-y: auto;
}

.run {
  border-bottom: 1px solid var(--hb-rule);
}

.run-toggle {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px var(--hb-space-3);
  width: 100%;
  padding: 11px 2px 10px;
  color: inherit;
  background: none;
  border: 0;
  font-size: var(--hb-text-sm);
  text-align: left;
  cursor: pointer;
}

.run-toggle:focus-visible {
  outline-offset: -2px;
}

.run-title {
  display: -webkit-box;
  overflow: hidden;
  font: 700 var(--hb-text-lg) / 1.25 var(--hb-font-serif);
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.run-toggle:hover .run-title {
  text-decoration: underline;
}

.run-meta {
  display: flex;
  flex-wrap: wrap;
  grid-column: 1;
  gap: 2px var(--hb-space-2);
}

.run-chevron {
  grid-column: 2;
  grid-row: 1;
  margin-top: 8px;
  fill: none;
  stroke: var(--hb-navy);
  stroke-width: 1.4;
  transition: transform var(--hb-motion-fast) ease-out;
}

[aria-expanded='true'] .run-chevron {
  transform: rotate(180deg);
}

.run-detail {
  display: grid;
  gap: var(--hb-space-1);
  padding: 2px 2px var(--hb-space-3);
}

.run-detail h3 {
  margin-top: var(--hb-space-2);
}

.run-question {
  max-height: 9rem;
  overflow-y: auto;
  font: 400 var(--hb-text-md) / 1.3 var(--hb-font-serif);
  overflow-wrap: anywhere;
}

.run-files li {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
  padding-block: 2px;
  font-size: var(--hb-text-sm);
}

.run-file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-2);
  margin-bottom: var(--hb-space-1);
}

.history-note {
  display: grid;
  justify-items: start;
  gap: var(--hb-space-2);
  padding-top: var(--hb-space-3);
}

@media (max-width: 960px) {
  .runs {
    max-height: none;
  }
}
</style>
