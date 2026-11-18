<template>
  <div class="hb-page">
    <HarborTopBar :links="navLinks">
      <template #status>
        <span>{{ pageIsLoopback && backendIsLoopback ? $t('home.loopbackAddresses') : $t('home.nonLoopbackAddress') }}</span>
        <span>{{ $t('home.privacyBackendState') }}: <b>{{ backendState }}</b></span>
      </template>
    </HarborTopBar>

    <main class="home-main">
      <form class="scenario" aria-labelledby="scenario-title" @submit.prevent="startSimulation">
        <div>
          <h1 id="scenario-title" class="hb-title">{{ $t('nav.newScenario') }}</h1>
          <p class="hb-lede lede">{{ $t('home.lede') }}</p>
        </div>

        <section aria-labelledby="documents-title">
          <div class="hb-field-head">
            <h2 id="documents-title" class="hb-heading">{{ $t('home.documents') }}</h2>
            <label class="hb-btn">
              {{ $t('home.addDocuments') }}
              <input
                ref="fileInput"
                class="hb-vh"
                type="file"
                multiple
                accept=".pdf,.md,.txt"
                :disabled="loading"
                @change="handleFileSelect"
              />
            </label>
          </div>

          <div
            class="drop-zone"
            :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
            @dragover.prevent="handleDragOver"
            @dragleave.prevent="handleDragLeave"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <div v-if="files.length === 0" class="drop-empty">
              <svg class="doc-icon" width="20" height="24" viewBox="0 0 20 24" aria-hidden="true"><path d="M2 1h11l5 5v17H2zM13 1v5h5M6 12h8M6 16h8" /></svg>
              <div>
                <b>{{ $t('home.dragToUpload') }}</b>
                <small>{{ $t('home.orBrowse') }} · {{ $t('home.supportedFormats') }}</small>
              </div>
            </div>

            <ul v-else class="hb-list file-list">
              <li v-for="(file, index) in files" :key="index" class="file-row">
                <svg class="doc-icon" width="20" height="24" viewBox="0 0 20 24" aria-hidden="true"><path d="M2 1h11l5 5v17H2zM13 1v5h5M6 12h8M6 16h8" /></svg>
                <div class="file-text">
                  <b :title="file.name">{{ file.name }}</b>
                  <small class="hb-tabular">{{ formatFileMeta(file) }}</small>
                </div>
                <button
                  class="hb-btn"
                  type="button"
                  :aria-label="$t('home.removeFileNamed', { name: file.name })"
                  @click.stop="removeFile(index)"
                >{{ $t('home.removeFile') }}</button>
              </li>
            </ul>
          </div>
          <p v-if="error" class="file-error" role="alert">{{ error }}</p>
        </section>

        <div>
          <div class="hb-field-head">
            <label class="hb-heading" for="scenario-question">{{ $t('home.question') }}</label>
          </div>
          <textarea
            id="scenario-question"
            v-model="formData.simulationRequirement"
            class="hb-textarea"
            :placeholder="$t('home.promptPlaceholder')"
            rows="5"
            :disabled="loading"
          ></textarea>
        </div>

        <dl class="setup">
          <div><dt>{{ $t('home.setupAgents') }}</dt><dd>{{ $t('home.setupAgentsValue') }}</dd></div>
          <div><dt>{{ $t('home.setupTime') }}</dt><dd>{{ $t('home.setupTimeValue') }}</dd></div>
          <div><dt>{{ $t('home.setupPlatforms') }}</dt><dd>{{ $t('home.setupPlatformsValue') }}</dd></div>
          <div><dt>{{ $t('home.setupMemory') }}</dt><dd>{{ $t('home.setupMemoryValue') }}</dd></div>
        </dl>

        <div class="go">
          <button
            class="hb-btn hb-btn--action hb-btn--large"
            type="submit"
            :disabled="!canSubmit || loading"
            :aria-describedby="canSubmit ? undefined : 'start-hint'"
          >{{ loading ? $t('home.initializing') : $t('home.startEngine') }}</button>
          <div class="go-notes">
            <p v-if="!canSubmit" id="start-hint" class="hb-soft">{{ $t('home.startHint') }}</p>
            <p><span class="hb-simulated-note">{{ $t('home.notForecast') }}</span></p>
          </div>
        </div>
      </form>

      <section class="flow hb-surface-water" aria-labelledby="workflow-title">
        <h2 id="workflow-title" class="hb-heading">{{ $t('home.workflowSequence') }}</h2>
        <ol class="hb-list flow-steps">
          <li v-for="step in ['01', '02', '03', '04', '05']" :key="step">
            <h3><em>{{ Number(step) }}</em>{{ $t(`home.step${step}Title`) }}</h3>
            <p>{{ $t(`home.step${step}Desc`) }}</p>
          </li>
        </ol>
      </section>

      <aside class="rail hb-surface-land" :aria-label="$t('home.railLabel')">
        <HistoryDatabase @loaded="history = $event" />

        <section aria-labelledby="privacy-title">
          <h2 id="privacy-title" class="hb-heading">{{ $t('home.privacyTitle') }}</h2>
          <dl class="hb-facts privacy hb-tabular">
            <dt>{{ $t('home.privacyPage') }}</dt>
            <dd>{{ pageUrl.host }} · {{ pageIsLoopback ? $t('home.loopback') : $t('home.notLoopback') }}</dd>
            <dt>{{ $t('home.privacyBackendAddress') }}</dt>
            <dd>{{ backendUrl.host }} · {{ backendIsLoopback ? $t('home.loopback') : $t('home.notLoopback') }}</dd>
            <dt>{{ $t('home.privacyBackendState') }}</dt>
            <dd role="status">{{ backendState }}</dd>
          </dl>
          <p class="hb-small hb-soft">{{ $t('home.privacyScope') }}</p>
        </section>

        <p class="hb-small">
          <a class="hb-link" href="https://github.com/666ghj/MiroFish" target="_blank" rel="noopener noreferrer">{{ $t('nav.visitGithub') }}</a>
        </p>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import service from '../api/index'
import HarborTopBar from '../components/HarborTopBar.vue'
import HistoryDatabase from '../components/HistoryDatabase.vue'

const router = useRouter()
const { t } = useI18n()

// 表单数据
const formData = ref({
  simulationRequirement: ''
})

// 文件列表
const files = ref([])

// 状态
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// 文件输入引用
const fileInput = ref(null)

// 计算属性:是否可以提交
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// 触发文件选择
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 添加文件
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  const skipped = newFiles.filter(file => !validFiles.includes(file)).map(file => file.name)
  error.value = skipped.length ? t('home.filesSkipped', { names: skipped.join(', ') }) : ''
  files.value.push(...validFiles)
}

const formatFileMeta = (file) => {
  const ext = file.name.split('.').pop().toUpperCase()
  const kb = Math.max(1, Math.round(file.size / 1024))
  return `${ext} · ${kb.toLocaleString()} KB`
}

// 移除文件
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// Status shown here is read from this session, never assumed.
const history = ref({ reachable: null, projects: [] })

const isLoopback = (hostname) => /^(localhost|127(\.\d{1,3}){3}|\[::1\])$/.test(hostname)
const pageUrl = new URL(window.location.href)
const backendUrl = new URL(service.defaults.baseURL, window.location.href)
const pageIsLoopback = isLoopback(pageUrl.hostname)
const backendIsLoopback = isLoopback(backendUrl.hostname)

const backendState = computed(() => {
  if (history.value.reachable === null) return t('home.backendChecking')
  return t(history.value.reachable ? 'home.backendReachable' : 'home.backendUnreachable')
})

const navLinks = computed(() => {
  const { projects } = history.value
  const graphRun = projects.find(project => project.project_id)
  const reportRun = projects.find(project => project.report_id)
  return [
    { label: t('nav.newScenario'), to: { name: 'Home' } },
    ...(graphRun ? [{ label: t('nav.latestGraph'), to: { name: 'Process', params: { projectId: graphRun.project_id } } }] : []),
    ...(reportRun ? [{ label: t('nav.latestReport'), to: { name: 'Report', params: { reportId: reportRun.report_id } } }] : [])
  ]
})

// 开始模拟 - 立即跳转，API调用在Process页面进行
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  
  // 存储待上传的数据
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    
    // 立即跳转到Process页面（使用特殊标识表示新建项目）
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
.home-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(20rem, 26.5rem);
  grid-template-rows: minmax(0, 1fr) auto;
  grid-template-areas:
    'form rail'
    'flow rail';
  min-height: 0;
}

.scenario {
  grid-area: form;
  display: flex;
  flex-direction: column;
  gap: var(--hb-space-5);
  padding: 30px var(--hb-gutter) 26px;
}

.scenario > * {
  width: 100%;
  max-width: 64rem;
}

.lede {
  margin-top: var(--hb-space-2);
}

.drop-zone {
  background: var(--hb-water-soft);
  border: 1px solid var(--hb-navy);
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.drop-zone:hover,
.drop-zone.drag-over {
  background: var(--hb-water);
}

.drop-zone.drag-over {
  outline: 2px solid var(--hb-navy);
  outline-offset: 2px;
}

.drop-empty,
.file-row {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 11px 13px;
}

.doc-icon {
  flex: none;
  fill: none;
  stroke: var(--hb-navy);
  stroke-width: 1.5;
}

.drop-empty b,
.file-text b {
  font-size: var(--hb-text-lg);
}

.drop-empty small,
.file-text small {
  display: block;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.file-list {
  max-height: 13rem;
  overflow-y: auto;
}

.file-row + .file-row {
  border-top: 1px solid var(--hb-rule);
}

.file-text {
  flex: 1;
  min-width: 0;
}

.file-text b {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-error {
  margin-top: var(--hb-space-2);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.setup {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-3) var(--hb-space-7);
}

.setup dt {
  color: var(--hb-navy-soft);
  font: 500 var(--hb-text-sm) var(--hb-font-sc);
}

.setup dd {
  font-size: var(--hb-text-lg);
  font-weight: 700;
}

.go {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-3) 22px;
  margin-top: auto;
}

.go-notes {
  display: grid;
  flex: 1 1 20rem;
  gap: var(--hb-space-1);
}

.flow {
  grid-area: flow;
  padding: 15px var(--hb-gutter) 16px;
  border-top: 1px solid var(--hb-navy);
}

.flow-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--hb-space-3) var(--hb-space-4);
  max-width: 64rem;
  margin-top: 9px;
}

.flow-steps li {
  padding-top: 7px;
  border-top: 2px solid var(--hb-navy);
}

.flow-steps h3 {
  font-size: var(--hb-text-md);
  font-weight: 700;
}

.flow-steps em {
  margin-right: var(--hb-space-1);
  font: italic 500 var(--hb-text-lg) var(--hb-font-serif);
}

.flow-steps p {
  font-size: var(--hb-text-sm);
  line-height: 1.25;
}

.rail {
  grid-area: rail;
  display: flex;
  flex-direction: column;
  gap: var(--hb-space-6);
  padding: 30px 26px;
  border-left: 1px solid var(--hb-navy);
}

.privacy {
  margin-top: 9px;
  border-bottom: 1px solid var(--hb-rule);
}

.privacy + p {
  margin-top: var(--hb-space-2);
}

.rail > :last-child {
  margin-top: auto;
}

@media (max-width: 960px) {
  .home-main {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: none;
    grid-template-areas:
      'form'
      'rail'
      'flow';
  }

  .rail {
    padding: var(--hb-space-5) var(--hb-gutter);
    border-top: 1px solid var(--hb-navy);
    border-left: 0;
  }

  .flow-steps {
    grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr));
  }
}

@media (max-width: 560px) {
  .scenario {
    padding-top: var(--hb-space-5);
  }

  .hb-textarea {
    font-size: var(--hb-text-xl);
  }

  .setup {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: var(--hb-space-4);
  }

  .go .hb-btn {
    width: 100%;
  }

  .go-notes {
    flex-basis: 100%;
  }
}
</style>
