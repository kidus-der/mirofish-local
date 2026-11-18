<template>
  <div class="report-panel">
    <!-- Main Split Layout -->
    <div class="main-split-layout">
      <!-- LEFT PANEL: Report -->
      <div class="left-panel report-style" ref="leftPanel" role="region" aria-label="Report" tabindex="0">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- Report Header -->
          <header class="report-header-block">
            <h1 class="main-title hb-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <p class="report-meta">
              <span class="report-tag hb-tag">Simulation report</span>
              <span class="report-id hb-tabular">ID: {{ reportId || 'REF-2024-X92' }}</span>
            </p>
            <p class="sim-notice">{{ $t('home.notForecast') }}</p>
          </header>

          <!-- Sections List -->
          <div class="sections-list">
            <section
              v-for="(section, idx) in reportOutline.sections"
              :key="idx"
              class="report-section-item"
              :class="{
                'is-active': currentSectionIndex === idx + 1,
                'is-completed': isSectionCompleted(idx + 1),
                'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1
              }"
            >
              <h2 class="section-heading">
                <button
                  type="button"
                  class="section-header-row"
                  :class="{ 'clickable': isSectionCompleted(idx + 1) }"
                  :disabled="!isSectionCompleted(idx + 1)"
                  :aria-expanded="isSectionCompleted(idx + 1) ? !collapsedSections.has(idx) : undefined"
                  @click="toggleSectionCollapse(idx)"
                >
                  <span class="section-number hb-sounding">{{ String(idx + 1).padStart(2, '0') }}</span>
                  <span class="section-title">{{ section.title }}</span>
                  <svg aria-hidden="true"
                    v-if="isSectionCompleted(idx + 1)"
                    class="collapse-icon"
                    :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                    viewBox="0 0 24 24"
                    width="18"
                    height="18"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>
              </h2>

              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <!-- Completed Content -->
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1])"></div>

                <!-- Loading State -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state hb-status hb-status--running" role="status">
                  <span class="loading-text">{{ $t('step4.generatingSection', { title: section.title }) }}</span>
                </div>
              </div>
            </section>
          </div>
        </div>

        <!-- Waiting State -->
        <div v-if="!reportOutline" class="waiting-placeholder" role="status">
          <div class="waiting-animation" aria-hidden="true">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">Waiting for Report Agent...</span>
        </div>
      </div>

      <!-- RIGHT PANEL: Workflow Timeline -->
      <div class="right-panel hb-surface-land-soft" ref="rightPanel" role="region" aria-label="Report generation activity" tabindex="0">
        <div class="panel-header hb-surface-water" :class="`panel-header--${activeStep.status}`" v-if="!isComplete">
          <span class="header-dot" v-if="activeStep.status === 'active'"></span>
          <span class="header-index hb-sounding">{{ activeStep.noLabel }}</span>
          <span class="header-title">{{ activeStep.title }}</span>
          <span class="header-meta" v-if="activeStep.meta">{{ activeStep.meta }}</span>
        </div>

        <!-- Workflow Overview -->
        <div class="workflow-overview hb-surface-land" v-if="agentLogs.length > 0 || reportOutline">
          <div class="workflow-metrics">
            <div class="metric">
              <span class="metric-label">Sections</span>
              <span class="metric-value hb-sounding">{{ completedSections }}/{{ totalSections }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Elapsed</span>
              <span class="metric-value hb-sounding">{{ formatElapsedTime }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Tools</span>
              <span class="metric-value hb-sounding">{{ totalToolCalls }}</span>
            </div>
            <div class="metric metric-right">
              <span
                class="metric-pill hb-status"
                :class="{ processing: 'hb-status--running', completed: 'hb-status--completed', pending: 'hb-status--idle' }[statusClass]"
              >{{ statusText }}</span>
            </div>
          </div>

          <ol class="workflow-steps hb-list" v-if="workflowSteps.length > 0">
            <li
              v-for="(step, sidx) in workflowSteps"
              :key="step.key"
              class="wf-step"
              :class="`wf-step--${step.status}`"
              :aria-current="step.status === 'active' ? 'step' : undefined"
            >
              <div class="wf-step-connector">
                <div class="wf-step-dot"></div>
                <div class="wf-step-line" v-if="sidx < workflowSteps.length - 1"></div>
              </div>

              <div class="wf-step-content">
                <div class="wf-step-title-row">
                  <span class="wf-step-index hb-sounding">{{ step.noLabel }}</span>
                  <span class="wf-step-title">{{ step.title }}</span>
                  <span class="wf-step-meta" v-if="step.meta">{{ step.meta }}</span>
                </div>
              </div>
            </li>
          </ol>

          <!-- Next Step Button - 在完成后显示 -->
          <button v-if="isComplete" type="button" class="next-step-btn hb-btn hb-btn--action" @click="goToInteraction">
            <span>{{ $t('step4.goToInteraction') }}</span>
            <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </button>
        </div>

        <div class="workflow-timeline">
          <TransitionGroup name="timeline-item">
            <div 
              v-for="(log, idx) in displayLogs" 
              :key="log.timestamp + '-' + idx"
              class="timeline-item"
              :class="getTimelineItemClass(log, idx, displayLogs.length)"
            >
              <!-- Timeline Connector -->
              <div class="timeline-connector">
                <div class="connector-dot" :class="getConnectorClass(log, idx, displayLogs.length)"></div>
                <div class="connector-line" v-if="idx < displayLogs.length - 1"></div>
              </div>
              
              <!-- Timeline Content -->
              <div class="timeline-content">
                <div class="timeline-header">
                  <span class="action-label">{{ getActionLabel(log.action) }}</span>
                  <span class="action-time hb-tabular">{{ formatTime(log.timestamp) }}</span>
                </div>
                
                <!-- Action Body - Different for each type -->
                <div class="timeline-body" :class="{ 'collapsed': isLogCollapsed(log) }" @click="toggleLogExpand(log)">
                  
                  <!-- Report Start -->
                  <template v-if="log.action === 'report_start'">
                    <div class="info-row">
                      <span class="info-key">Simulation</span>
                      <span class="info-val hb-tabular">{{ log.details?.simulation_id }}</span>
                    </div>
                    <div class="info-row" v-if="log.details?.simulation_requirement">
                      <span class="info-key">Requirement</span>
                      <span class="info-val">{{ log.details.simulation_requirement }}</span>
                    </div>
                  </template>

                  <!-- Planning -->
                  <template v-if="log.action === 'planning_start'">
                    <div class="status-message planning">{{ log.details?.message }}</div>
                  </template>
                  <template v-if="log.action === 'planning_complete'">
                    <div class="status-message success">{{ log.details?.message }}</div>
                    <div class="outline-badge hb-tag" v-if="log.details?.outline">
                      {{ log.details.outline.sections?.length || 0 }} sections planned
                    </div>
                  </template>

                  <!-- Section Start -->
                  <template v-if="log.action === 'section_start'">
                    <div class="section-tag">
                      <span class="tag-num hb-sounding">#{{ log.section_index }}</span>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>
                  
                  <!-- Section Content Generated (内容生成完成，但整个章节可能还没完成) -->
                  <template v-if="log.action === 'section_content'">
                    <div class="section-tag content-ready">
                      <svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20h9"></path>
                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                      </svg>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>

                  <!-- Section Complete (章节生成完成) -->
                  <template v-if="log.action === 'section_complete'">
                    <div class="section-tag completed">
                      <svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>

                  <!-- Tool Call -->
                  <template v-if="log.action === 'tool_call'">
                    <div class="tool-badge" :class="'tool-' + getToolColor(log.details?.tool_name)">
                      <!-- Deep Insight - Lightbulb -->
                      <svg aria-hidden="true" v-if="getToolIcon(log.details?.tool_name) === 'lightbulb'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                      </svg>
                      <!-- Panorama Search - Globe -->
                      <svg aria-hidden="true" v-else-if="getToolIcon(log.details?.tool_name) === 'globe'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                      </svg>
                      <!-- Agent Interview - Users -->
                      <svg aria-hidden="true" v-else-if="getToolIcon(log.details?.tool_name) === 'users'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                      </svg>
                      <!-- Quick Search - Zap -->
                      <svg aria-hidden="true" v-else-if="getToolIcon(log.details?.tool_name) === 'zap'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                      </svg>
                      <!-- Graph Stats - Chart -->
                      <svg aria-hidden="true" v-else-if="getToolIcon(log.details?.tool_name) === 'chart'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                      </svg>
                      <!-- Entity Query - Database -->
                      <svg aria-hidden="true" v-else-if="getToolIcon(log.details?.tool_name) === 'database'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                      </svg>
                      <!-- Default - Tool -->
                      <svg aria-hidden="true" v-else class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                      </svg>
                      {{ getToolDisplayName(log.details?.tool_name) }}
                    </div>
                    <div v-if="log.details?.parameters && expandedLogs.has(log.timestamp)" class="tool-params">
                      <pre>{{ formatParams(log.details.parameters) }}</pre>
                    </div>
                  </template>

                  <!-- Tool Result -->
                  <template v-if="log.action === 'tool_result'">
                    <div class="result-wrapper" :class="'result-' + log.details?.tool_name">
                      <!-- Hide result-meta for tools that show stats in their own header -->
                      <div v-if="!['interview_agents', 'insight_forge', 'panorama_search', 'quick_search'].includes(log.details?.tool_name)" class="result-meta">
                        <span class="result-tool">{{ getToolDisplayName(log.details?.tool_name) }}</span>
                        <span class="result-size hb-tabular">{{ formatResultSize(log.details?.result_length) }}</span>
                      </div>
                      
                      <!-- Structured Result Display -->
                      <div v-if="!showRawResult[log.timestamp]" class="result-structured">
                        <!-- Interview Agents - Special Display -->
                        <template v-if="log.details?.tool_name === 'interview_agents'">
                          <InterviewDisplay :result="parseInterview(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Insight Forge -->
                        <template v-else-if="log.details?.tool_name === 'insight_forge'">
                          <InsightDisplay :result="parseInsightForge(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Panorama Search -->
                        <template v-else-if="log.details?.tool_name === 'panorama_search'">
                          <PanoramaDisplay :result="parsePanorama(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Quick Search -->
                        <template v-else-if="log.details?.tool_name === 'quick_search'">
                          <QuickSearchDisplay :result="parseQuickSearch(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Default -->
                        <template v-else>
                          <pre class="raw-preview"><MarkedText :text="truncateText(log.details?.result, 300)" /></pre>
                        </template>
                      </div>
                      
                      <!-- Raw Result -->
                      <div v-else class="result-raw">
                        <pre><MarkedText :text="log.details?.result" /></pre>
                      </div>
                    </div>
                  </template>

                  <!-- LLM Response -->
                  <template v-if="log.action === 'llm_response'">
                    <div class="llm-meta">
                      <span class="meta-tag">Iteration {{ log.details?.iteration }}</span>
                      <span class="meta-tag" :class="{ active: log.details?.has_tool_calls }">
                        Tools: {{ log.details?.has_tool_calls ? 'Yes' : 'No' }}
                      </span>
                      <span class="meta-tag" :class="{ active: log.details?.has_final_answer, 'final-answer': log.details?.has_final_answer }">
                        Final: {{ log.details?.has_final_answer ? 'Yes' : 'No' }}
                      </span>
                    </div>
                    <!-- 当是最终答案时，显示特殊提示 -->
                    <div v-if="log.details?.has_final_answer" class="final-answer-hint">
                      <svg aria-hidden="true" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      <span>Section "{{ log.section_title }}" content generated</span>
                    </div>
                    <div v-if="expandedLogs.has(log.timestamp) && log.details?.response" class="llm-content">
                      <pre><MarkedText :text="log.details.response" /></pre>
                    </div>
                  </template>

                  <!-- Report Complete -->
                  <template v-if="log.action === 'report_complete'">
                    <div class="complete-banner">
                      <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                      </svg>
                      <span>Report Generation Complete</span>
                    </div>
                  </template>
                </div>

                <!-- Footer: Elapsed Time + Action Buttons -->
                <div class="timeline-footer" v-if="log.elapsed_seconds || (log.action === 'tool_call' && log.details?.parameters) || log.action === 'tool_result' || (log.action === 'llm_response' && log.details?.response)">
                  <span v-if="log.elapsed_seconds" class="elapsed-badge hb-sounding">+{{ log.elapsed_seconds.toFixed(1) }}s</span>
                  <span v-else class="elapsed-placeholder"></span>
                  
                  <div class="footer-actions">
                    <!-- Tool Call: Show/Hide Params -->
                    <button v-if="log.action === 'tool_call' && log.details?.parameters" type="button" class="action-btn hb-btn" @click.stop="toggleLogExpand(log)">
                      {{ expandedLogs.has(log.timestamp) ? 'Hide Params' : 'Show Params' }}
                    </button>
                    
                    <!-- Tool Result: Raw/Structured View -->
                    <button v-if="log.action === 'tool_result'" type="button" class="action-btn hb-btn" @click.stop="toggleRawResult(log.timestamp, $event)">
                      {{ showRawResult[log.timestamp] ? 'Structured View' : 'Raw Output' }}
                    </button>
                    
                    <!-- LLM Response: Show/Hide Response -->
                    <button v-if="log.action === 'llm_response' && log.details?.response" type="button" class="action-btn hb-btn" @click.stop="toggleLogExpand(log)">
                      {{ expandedLogs.has(log.timestamp) ? 'Hide Response' : 'Show Response' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </TransitionGroup>

          <!-- Empty State -->
          <div v-if="agentLogs.length === 0 && !isComplete" class="workflow-empty" role="status">
            <div class="empty-pulse" aria-hidden="true"></div>
            <span>Waiting for agent activity...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Console Logs -->
    <div class="console-logs hb-surface-water-soft">
      <div class="log-header">
        <span class="log-title">CONSOLE OUTPUT</span>
        <span class="log-id hb-tabular">{{ reportId || 'NO_REPORT' }}</span>
      </div>
      <div class="log-content" ref="logContent" role="log" aria-label="Console output" tabindex="0">
        <div class="log-line" v-for="(log, idx) in consoleLogs" :key="idx">
          <span class="log-msg" :class="getLogLevelClass(log)"><MarkedText :text="log" /></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, h, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getAgentLog, getConsoleLog } from '../api/report'

const router = useRouter()
const { t } = useI18n()

const props = defineProps({
  reportId: String,
  simulationId: String,
  systemLogs: Array
})

const emit = defineEmits(['add-log', 'update-status'])

// Navigation
const goToInteraction = () => {
  if (props.reportId) {
    router.push({ name: 'Interaction', params: { reportId: props.reportId } })
  }
}

// State
const agentLogs = ref([])
const consoleLogs = ref([])
const agentLogLine = ref(0)
const consoleLogLine = ref(0)
const reportOutline = ref(null)
const currentSectionIndex = ref(null)
const generatedSections = ref({})
const expandedContent = ref(new Set())
const expandedLogs = ref(new Set())
const collapsedSections = ref(new Set())
const isComplete = ref(false)
const startTime = ref(null)
const leftPanel = ref(null)
const rightPanel = ref(null)
const logContent = ref(null)
const showRawResult = reactive({})

// Toggle functions
const toggleRawResult = (timestamp, event) => {
  // 保存按钮相对于视口的位置
  const button = event?.target
  const buttonRect = button?.getBoundingClientRect()
  const buttonTopBeforeToggle = buttonRect?.top
  
  // 切换状态
  showRawResult[timestamp] = !showRawResult[timestamp]
  
  // 等待 DOM 更新后，调整滚动位置以保持按钮在相同位置
  if (button && buttonTopBeforeToggle !== undefined && rightPanel.value) {
    nextTick(() => {
      const newButtonRect = button.getBoundingClientRect()
      const buttonTopAfterToggle = newButtonRect.top
      const scrollDelta = buttonTopAfterToggle - buttonTopBeforeToggle
      
      // 调整滚动位置
      rightPanel.value.scrollTop += scrollDelta
    })
  }
}

const toggleSectionContent = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(expandedContent.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  expandedContent.value = newSet
}

const toggleSectionCollapse = (idx) => {
  // 只有已完成的章节才能折叠
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const toggleLogExpand = (log) => {
  const newSet = new Set(expandedLogs.value)
  if (newSet.has(log.timestamp)) {
    newSet.delete(log.timestamp)
  } else {
    newSet.add(log.timestamp)
  }
  expandedLogs.value = newSet
}

const isLogCollapsed = (log) => {
  if (['tool_call', 'tool_result', 'llm_response'].includes(log.action)) {
    return !expandedLogs.value.has(log.timestamp)
  }
  return false
}

// Tool configurations with display names and colors
const toolConfig = {
  'insight_forge': {
    name: 'Deep Insight',
    color: 'purple',
    icon: 'lightbulb' // 灯泡图标 - 代表洞察
  },
  'panorama_search': {
    name: 'Panorama Search',
    color: 'blue',
    icon: 'globe' // 地球图标 - 代表全景搜索
  },
  'interview_agents': {
    name: 'Agent Interview',
    color: 'green',
    icon: 'users' // 用户图标 - 代表对话
  },
  'quick_search': {
    name: 'Quick Search',
    color: 'orange',
    icon: 'zap' // 闪电图标 - 代表快速
  },
  'get_graph_statistics': {
    name: 'Graph Stats',
    color: 'cyan',
    icon: 'chart' // 图表图标 - 代表统计
  },
  'get_entities_by_type': {
    name: 'Entity Query',
    color: 'pink',
    icon: 'database' // 数据库图标 - 代表实体
  }
}

const getToolDisplayName = (toolName) => {
  return toolConfig[toolName]?.name || toolName
}

const getToolColor = (toolName) => {
  return toolConfig[toolName]?.color || 'gray'
}

const getToolIcon = (toolName) => {
  return toolConfig[toolName]?.icon || 'tool'
}

// Parse functions
const parseInsightForge = (text) => {
  const result = {
    query: '',
    simulationRequirement: '',
    stats: { facts: 0, entities: 0, relationships: 0 },
    subQueries: [],
    facts: [],
    entities: [],
    relations: []
  }
  
  try {
    // 提取分析问题
    const queryMatch = text.match(/分析问题:\s*(.+?)(?:\n|$)/)
    if (queryMatch) result.query = queryMatch[1].trim()
    
    // 提取预测场景
    const reqMatch = text.match(/预测场景:\s*(.+?)(?:\n|$)/)
    if (reqMatch) result.simulationRequirement = reqMatch[1].trim()
    
    // 提取统计数据 - 匹配"相关预测事实: X条"格式
    const factMatch = text.match(/相关预测事实:\s*(\d+)/)
    const entityMatch = text.match(/涉及实体:\s*(\d+)/)
    const relMatch = text.match(/关系链:\s*(\d+)/)
    if (factMatch) result.stats.facts = parseInt(factMatch[1])
    if (entityMatch) result.stats.entities = parseInt(entityMatch[1])
    if (relMatch) result.stats.relationships = parseInt(relMatch[1])
    
    // 提取子问题 - 完整提取，不限制数量
    const subQSection = text.match(/### 分析的子问题\n([\s\S]*?)(?=\n###|$)/)
    if (subQSection) {
      const lines = subQSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.subQueries = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }
    
    // 提取关键事实 - 完整提取，不限制数量
    const factsSection = text.match(/### 【关键事实】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/)
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => {
        const match = l.match(/^\d+\.\s*"?(.+?)"?\s*$/)
        return match ? match[1].replace(/^"|"$/g, '').trim() : l.replace(/^\d+\.\s*/, '').trim()
      }).filter(Boolean)
    }
    
    // 提取核心实体 - 完整提取，包含摘要和相关事实数
    const entitySection = text.match(/### 【核心实体】\n([\s\S]*?)(?=\n###|$)/)
    if (entitySection) {
      const entityText = entitySection[1]
      // 按 "- **" 分割实体块
      const entityBlocks = entityText.split(/\n(?=- \*\*)/).filter(b => b.trim().startsWith('- **'))
      result.entities = entityBlocks.map(block => {
        const nameMatch = block.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        const summaryMatch = block.match(/摘要:\s*"?(.+?)"?(?:\n|$)/)
        const relatedMatch = block.match(/相关事实:\s*(\d+)/)
        return {
          name: nameMatch ? nameMatch[1].trim() : '',
          type: nameMatch ? nameMatch[2].trim() : '',
          summary: summaryMatch ? summaryMatch[1].trim() : '',
          relatedFactsCount: relatedMatch ? parseInt(relatedMatch[1]) : 0
        }
      }).filter(e => e.name)
    }
    
    // 提取关系链 - 完整提取，不限制数量
    const relSection = text.match(/### 【关系链】\n([\s\S]*?)(?=\n###|$)/)
    if (relSection) {
      const lines = relSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.relations = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse insight_forge failed:', e)
  }
  
  return result
}

const parsePanorama = (text) => {
  const result = {
    query: '',
    stats: { nodes: 0, edges: 0, activeFacts: 0, historicalFacts: 0 },
    activeFacts: [],
    historicalFacts: [],
    entities: []
  }
  
  try {
    // 提取查询
    const queryMatch = text.match(/查询:\s*(.+?)(?:\n|$)/)
    if (queryMatch) result.query = queryMatch[1].trim()
    
    // 提取统计数据
    const nodesMatch = text.match(/总节点数:\s*(\d+)/)
    const edgesMatch = text.match(/总边数:\s*(\d+)/)
    const activeMatch = text.match(/当前有效事实:\s*(\d+)/)
    const histMatch = text.match(/历史\/过期事实:\s*(\d+)/)
    if (nodesMatch) result.stats.nodes = parseInt(nodesMatch[1])
    if (edgesMatch) result.stats.edges = parseInt(edgesMatch[1])
    if (activeMatch) result.stats.activeFacts = parseInt(activeMatch[1])
    if (histMatch) result.stats.historicalFacts = parseInt(histMatch[1])
    
    // 提取当前有效事实 - 完整提取，不限制数量
    const activeSection = text.match(/### 【当前有效事实】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/)
    if (activeSection) {
      const lines = activeSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.activeFacts = lines.map(l => {
        // 移除编号和引号
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }
    
    // 提取历史/过期事实 - 完整提取，不限制数量
    const histSection = text.match(/### 【历史\/过期事实】[\s\S]*?\n([\s\S]*?)(?=\n###|$)/)
    if (histSection) {
      const lines = histSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.historicalFacts = lines.map(l => {
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }
    
    // 提取涉及实体 - 完整提取，不限制数量
    const entitySection = text.match(/### 【涉及实体】\n([\s\S]*?)(?=\n###|$)/)
    if (entitySection) {
      const lines = entitySection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.entities = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse panorama failed:', e)
  }
  
  return result
}

const parseInterview = (text) => {
  const result = {
    topic: '',
    agentCount: '',
    successCount: 0,
    totalCount: 0,
    selectionReason: '',
    interviews: [],
    summary: ''
  }
  
  try {
    // 提取采访主题
    const topicMatch = text.match(/\*\*采访主题:\*\*\s*(.+?)(?:\n|$)/)
    if (topicMatch) result.topic = topicMatch[1].trim()
    
    // 提取采访人数（如 "5 / 9 位模拟Agent"）
    const countMatch = text.match(/\*\*采访人数:\*\*\s*(\d+)\s*\/\s*(\d+)/)
    if (countMatch) {
      result.successCount = parseInt(countMatch[1])
      result.totalCount = parseInt(countMatch[2])
      result.agentCount = `${countMatch[1]} / ${countMatch[2]}`
    }
    
    // 提取采访对象选择理由
    const reasonMatch = text.match(/### 采访对象选择理由\n([\s\S]*?)(?=\n---\n|\n### 采访实录)/)
    if (reasonMatch) {
      result.selectionReason = reasonMatch[1].trim()
    }
    
    // 解析每个人的选择理由
    const parseIndividualReasons = (reasonText) => {
      const reasons = {}
      if (!reasonText) return reasons
      
      const lines = reasonText.split(/\n+/)
      let currentName = null
      let currentReason = []
      
      for (const line of lines) {
        let headerMatch = null
        let name = null
        let reasonStart = null
        
        // 格式1: 数字. **名字（index=X）**：理由
        // 例如: 1. **校友_345（index=1）**：作为武大校友...
        headerMatch = line.match(/^\d+\.\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
        if (headerMatch) {
          name = headerMatch[1].trim()
          reasonStart = headerMatch[2]
        }
        
        // 格式2: - 选择名字（index X）：理由
        // 例如: - 选择家长_601（index 0）：作为家长群体代表...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*选择([^（(]+)(?:[（(]index\s*=?\s*\d+[)）])?[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }
        
        // 格式3: - **名字（index X）**：理由
        // 例如: - **家长_601（index 0）**：作为家长群体代表...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }
        
        if (name) {
          // 保存上一个人的理由
          if (currentName && currentReason.length > 0) {
            reasons[currentName] = currentReason.join(' ').trim()
          }
          // 开始新的人
          currentName = name
          currentReason = reasonStart ? [reasonStart.trim()] : []
        } else if (currentName && line.trim() && !line.match(/^未选|^综上|^最终选择/)) {
          // 理由的续行（排除结尾总结段落）
          currentReason.push(line.trim())
        }
      }
      
      // 保存最后一个人的理由
      if (currentName && currentReason.length > 0) {
        reasons[currentName] = currentReason.join(' ').trim()
      }
      
      return reasons
    }
    
    const individualReasons = parseIndividualReasons(result.selectionReason)
    
    // 提取每个采访记录
    const interviewBlocks = text.split(/#### 采访 #\d+:/).slice(1)
    
    interviewBlocks.forEach((block, index) => {
      const interview = {
        num: index + 1,
        title: '',
        name: '',
        role: '',
        bio: '',
        selectionReason: '',
        questions: [],
        twitterAnswer: '',
        redditAnswer: '',
        quotes: []
      }
      
      // 提取标题（如 "学生"、"教育从业者" 等）
      const titleMatch = block.match(/^(.+?)\n/)
      if (titleMatch) interview.title = titleMatch[1].trim()
      
      // 提取姓名和角色
      const nameRoleMatch = block.match(/\*\*(.+?)\*\*\s*\((.+?)\)/)
      if (nameRoleMatch) {
        interview.name = nameRoleMatch[1].trim()
        interview.role = nameRoleMatch[2].trim()
        // 设置该人的选择理由
        interview.selectionReason = individualReasons[interview.name] || ''
      }
      
      // 提取简介
      const bioMatch = block.match(/_简介:\s*([\s\S]*?)_\n/)
      if (bioMatch) {
        interview.bio = bioMatch[1].trim().replace(/\.\.\.$/, '...')
      }
      
      // 提取问题列表
      const qMatch = block.match(/\*\*Q:\*\*\s*([\s\S]*?)(?=\n\n\*\*A:\*\*|\*\*A:\*\*)/)
      if (qMatch) {
        const qText = qMatch[1].trim()
        // 按数字编号分割问题
        const questions = qText.split(/\n\d+\.\s+/).filter(q => q.trim())
        if (questions.length > 0) {
          // 如果第一个问题前面有"1."，需要特殊处理
          const firstQ = qText.match(/^1\.\s+(.+)/)
          if (firstQ) {
            interview.questions = [firstQ[1].trim(), ...questions.slice(1).map(q => q.trim())]
          } else {
            interview.questions = questions.map(q => q.trim())
          }
        }
      }
      
      // 提取回答 - 分Twitter和Reddit
      const answerMatch = block.match(/\*\*A:\*\*\s*([\s\S]*?)(?=\*\*关键引言|$)/)
      if (answerMatch) {
        const answerText = answerMatch[1].trim()
        
        // 分离Twitter和Reddit回答
        const twitterMatch = answerText.match(/【Twitter平台回答】\n?([\s\S]*?)(?=【Reddit平台回答】|$)/)
        const redditMatch = answerText.match(/【Reddit平台回答】\n?([\s\S]*?)$/)
        
        if (twitterMatch) {
          interview.twitterAnswer = twitterMatch[1].trim()
        }
        if (redditMatch) {
          interview.redditAnswer = redditMatch[1].trim()
        }
        
        // 平台回退逻辑（兼容旧格式：只有一个平台标记的情况）
        if (!twitterMatch && redditMatch) {
          // 只有 Reddit 回答，仅在非占位文本时复制为默认显示
          if (interview.redditAnswer && interview.redditAnswer !== '（该平台未获得回复）') {
            interview.twitterAnswer = interview.redditAnswer
          }
        } else if (twitterMatch && !redditMatch) {
          if (interview.twitterAnswer && interview.twitterAnswer !== '（该平台未获得回复）') {
            interview.redditAnswer = interview.twitterAnswer
          }
        } else if (!twitterMatch && !redditMatch) {
          // 没有分平台标记（极旧格式），整体作为回答
          interview.twitterAnswer = answerText
        }
      }
      
      // 提取关键引言（兼容多种引号格式）
      const quotesMatch = block.match(/\*\*关键引言:\*\*\n([\s\S]*?)(?=\n---|\n####|$)/)
      if (quotesMatch) {
        const quotesText = quotesMatch[1]
        // 优先匹配 > "text" 格式
        let quoteMatches = quotesText.match(/> "([^"]+)"/g)
        // 回退：匹配 > "text" 或 > \u201Ctext\u201D（中文引号）
        if (!quoteMatches) {
          quoteMatches = quotesText.match(/> [\u201C""]([^\u201D""]+)[\u201D""]/g)
        }
        if (quoteMatches) {
          interview.quotes = quoteMatches
            .map(q => q.replace(/^> [\u201C""]|[\u201D""]$/g, '').trim())
            .filter(q => q)
        }
      }
      
      if (interview.name || interview.title) {
        result.interviews.push(interview)
      }
    })
    
    // 提取采访摘要
    const summaryMatch = text.match(/### 采访摘要与核心观点\n([\s\S]*?)$/)
    if (summaryMatch) {
      result.summary = summaryMatch[1].trim()
    }
  } catch (e) {
    console.warn('Parse interview failed:', e)
  }
  
  return result
}

const parseQuickSearch = (text) => {
  const result = {
    query: '',
    count: 0,
    facts: [],
    edges: [],
    nodes: []
  }
  
  try {
    // 提取搜索查询
    const queryMatch = text.match(/搜索查询:\s*(.+?)(?:\n|$)/)
    if (queryMatch) result.query = queryMatch[1].trim()
    
    // 提取结果数量
    const countMatch = text.match(/找到\s*(\d+)\s*条/)
    if (countMatch) result.count = parseInt(countMatch[1])
    
    // 提取相关事实 - 完整提取，不限制数量
    const factsSection = text.match(/### 相关事实:\n([\s\S]*)$/)
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }
    
    // 尝试提取边信息（如果有）
    const edgesSection = text.match(/### 相关边:\n([\s\S]*?)(?=\n###|$)/)
    if (edgesSection) {
      const lines = edgesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.edges = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }
    
    // 尝试提取节点信息（如果有）
    const nodesSection = text.match(/### 相关节点:\n([\s\S]*?)(?=\n###|$)/)
    if (nodesSection) {
      const lines = nodesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.nodes = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        const simpleMatch = l.match(/^-\s*(.+)$/)
        if (simpleMatch) return { name: simpleMatch[1].trim(), type: '' }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse quick_search failed:', e)
  }
  
  return result
}

// ========== Simulated material ==========
// The text stays verbatim; only the [SIMULATED] label is wrapped so it can be styled.
const SIMULATED_LABEL_CLASS = 'hb-origin hb-origin--simulated'
const isSimulatedFact = (text) => /^\s*"?(?:\[[^\]]*\]\s*)?\[SIMULATED\]/.test(text ?? '')
const markSimulated = (text) => String(text ?? '').split(/(\[SIMULATED\])/).map(part =>
  part === '[SIMULATED]' ? h('span', { class: SIMULATED_LABEL_CLASS }, part) : part
)
const MarkedText = (props) => markSimulated(props.text)
MarkedText.props = ['text']
const factClass = (fact, extra) => ['fact-item', extra, { 'hb-row--simulated': isSimulatedFact(fact) }]

// ========== Sub Components ==========

// Insight Display Component - Enhanced with full data rendering (Interview-like style)
const InsightDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const { t } = useI18n()
    const activeTab = ref('facts') // 'facts', 'entities', 'relations', 'subqueries'
    const expandedFacts = ref(false)
    const expandedEntities = ref(false)
    const expandedRelations = ref(false)
    const INITIAL_SHOW_COUNT = 5
    
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    return () => h('div', { class: 'insight-display' }, [
      // Header Section - like interview header
      h('div', { class: 'insight-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, 'Deep Insight'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.facts || props.result.facts.length),
              h('span', { class: 'stat-label' }, 'Facts')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.entities || props.result.entities.length),
              h('span', { class: 'stat-label' }, 'Entities')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.relationships || props.result.relations.length),
              h('span', { class: 'stat-label' }, 'Relations')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query),
        props.result.simulationRequirement && h('div', { class: 'header-scenario' }, [
          h('span', { class: 'scenario-label' }, t('step4.scenarioLabel')),
          h('span', { class: 'scenario-text' }, props.result.simulationRequirement)
        ])
      ]),
      
      // Tab Navigation
      h('div', { class: 'insight-tabs' }, [
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'facts' }],
          'aria-pressed': activeTab.value === 'facts',
          onClick: () => { activeTab.value = 'facts' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabKeyFacts', { count: props.result.facts.length }))
        ]),
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'entities' }],
          'aria-pressed': activeTab.value === 'entities',
          onClick: () => { activeTab.value = 'entities' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabCoreEntities', { count: props.result.entities.length }))
        ]),
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'relations' }],
          'aria-pressed': activeTab.value === 'relations',
          onClick: () => { activeTab.value = 'relations' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabRelationChains', { count: props.result.relations.length }))
        ]),
        props.result.subQueries.length > 0 && h('button', {
          class: ['insight-tab', { active: activeTab.value === 'subqueries' }],
          'aria-pressed': activeTab.value === 'subqueries',
          onClick: () => { activeTab.value = 'subqueries' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabSubQueries', { count: props.result.subQueries.length }))
        ])
      ]),
      
      // Tab Content
      h('div', { class: 'insight-content' }, [
        // Facts Tab
        activeTab.value === 'facts' && props.result.facts.length > 0 && h('div', { class: 'facts-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelKeyFacts')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.facts.length }))
          ]),
          h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: factClass(fact), key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, markSimulated(fact))
              ])
            )
          ),
          props.result.facts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn hb-btn',
            onClick: () => { expandedFacts.value = !expandedFacts.value }
          }, expandedFacts.value ? t('step4.collapse') : t('step4.expandAll', { count: props.result.facts.length }))
        ]),

        // Entities Tab
        activeTab.value === 'entities' && props.result.entities.length > 0 && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelCoreEntities')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.entities.length }))
          ]),
          h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 12)).map((entity, i) => 
              h('div', { class: 'entity-tag', key: i, title: entity.summary || '' }, [
                h('span', { class: 'entity-name' }, entity.name),
                h('span', { class: 'entity-type' }, entity.type),
                entity.relatedFactsCount > 0 && h('span', { class: 'entity-fact-count' }, t('step4.factCount', { count: entity.relatedFactsCount }))
              ])
            )
          ),
          props.result.entities.length > 12 && h('button', {
            class: 'expand-btn hb-btn',
            onClick: () => { expandedEntities.value = !expandedEntities.value }
          }, expandedEntities.value ? t('step4.collapse') : t('step4.expandAllEntities', { count: props.result.entities.length }))
        ]),

        // Relations Tab
        activeTab.value === 'relations' && props.result.relations.length > 0 && h('div', { class: 'relations-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelRelationChains')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.relations.length }))
          ]),
          h('div', { class: 'relations-list' },
            (expandedRelations.value ? props.result.relations : props.result.relations.slice(0, INITIAL_SHOW_COUNT)).map((rel, i) => 
              h('div', { class: 'relation-item', key: i }, [
                h('span', { class: 'rel-source' }, rel.source),
                h('span', { class: 'rel-arrow' }, [
                  h('span', { class: 'rel-line' }),
                  h('span', { class: 'rel-label' }, rel.relation),
                  h('span', { class: 'rel-line' })
                ]),
                h('span', { class: 'rel-target' }, rel.target)
              ])
            )
          ),
          props.result.relations.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn hb-btn',
            onClick: () => { expandedRelations.value = !expandedRelations.value }
          }, expandedRelations.value ? t('step4.collapse') : t('step4.expandAll', { count: props.result.relations.length }))
        ]),

        // Sub-queries Tab
        activeTab.value === 'subqueries' && props.result.subQueries.length > 0 && h('div', { class: 'subqueries-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelSubQueries')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.subQueries.length }))
          ]),
          h('div', { class: 'subqueries-list' },
            props.result.subQueries.map((sq, i) => 
              h('div', { class: 'subquery-item', key: i }, [
                h('span', { class: 'subquery-number' }, `Q${i + 1}`),
                h('div', { class: 'subquery-text' }, sq)
              ])
            )
          )
        ]),
        
        // Empty state
        activeTab.value === 'facts' && props.result.facts.length === 0 && h('div', { class: 'empty-state' }, t('step4.emptyKeyFacts')),
        activeTab.value === 'entities' && props.result.entities.length === 0 && h('div', { class: 'empty-state' }, t('step4.emptyCoreEntities')),
        activeTab.value === 'relations' && props.result.relations.length === 0 && h('div', { class: 'empty-state' }, t('step4.emptyRelationChains'))
      ])
    ])
  }
}

// Panorama Display Component - Enhanced with Active/Historical tabs
const PanoramaDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const { t } = useI18n()
    const activeTab = ref('active') // 'active', 'historical', 'entities'
    const expandedActive = ref(false)
    const expandedHistorical = ref(false)
    const expandedEntities = ref(false)
    const INITIAL_SHOW_COUNT = 5
    
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    return () => h('div', { class: 'panorama-display' }, [
      // Header Section
      h('div', { class: 'panorama-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, 'Panorama Search'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.nodes),
              h('span', { class: 'stat-label' }, 'Nodes')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.edges),
              h('span', { class: 'stat-label' }, 'Edges')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query)
      ]),
      
      // Tab Navigation
      h('div', { class: 'panorama-tabs' }, [
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'active' }],
          'aria-pressed': activeTab.value === 'active',
          onClick: () => { activeTab.value = 'active' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabActiveFacts', { count: props.result.activeFacts.length }))
        ]),
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'historical' }],
          'aria-pressed': activeTab.value === 'historical',
          onClick: () => { activeTab.value = 'historical' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabHistoricalFacts', { count: props.result.historicalFacts.length }))
        ]),
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'entities' }],
          'aria-pressed': activeTab.value === 'entities',
          onClick: () => { activeTab.value = 'entities' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabEntities', { count: props.result.entities.length }))
        ])
      ]),
      
      // Tab Content
      h('div', { class: 'panorama-content' }, [
        // Active Facts Tab
        activeTab.value === 'active' && h('div', { class: 'facts-panel active-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelActiveFacts')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.activeFacts.length }))
          ]),
          props.result.activeFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedActive.value ? props.result.activeFacts : props.result.activeFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: factClass(fact, 'active'), key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, markSimulated(fact))
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptyActiveFacts')),
          props.result.activeFacts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn hb-btn',
            onClick: () => { expandedActive.value = !expandedActive.value }
          }, expandedActive.value ? t('step4.collapse') : t('step4.expandAll', { count: props.result.activeFacts.length }))
        ]),
        
        // Historical Facts Tab
        activeTab.value === 'historical' && h('div', { class: 'facts-panel historical-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelHistoricalFacts')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.historicalFacts.length }))
          ]),
          props.result.historicalFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedHistorical.value ? props.result.historicalFacts : props.result.historicalFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: factClass(fact, 'historical'), key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, [
                  // 尝试提取时间信息 [time - time]
                  (() => {
                    const timeMatch = fact.match(/^\[(.+?)\]\s*(.*)$/)
                    if (timeMatch) {
                      return [
                        h('span', { class: 'fact-time' }, timeMatch[1]),
                        h('span', { class: 'fact-text' }, markSimulated(timeMatch[2]))
                      ]
                    }
                    return h('span', { class: 'fact-text' }, markSimulated(fact))
                  })()
                ])
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptyHistoricalFacts')),
          props.result.historicalFacts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn hb-btn',
            onClick: () => { expandedHistorical.value = !expandedHistorical.value }
          }, expandedHistorical.value ? t('step4.collapse') : t('step4.expandAll', { count: props.result.historicalFacts.length }))
        ]),
        
        // Entities Tab
        activeTab.value === 'entities' && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelEntities')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.entities.length }))
          ]),
          props.result.entities.length > 0 ? h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 8)).map((entity, i) => 
              h('div', { class: 'entity-tag', key: i }, [
                h('span', { class: 'entity-name' }, entity.name),
                entity.type && h('span', { class: 'entity-type' }, entity.type)
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptyEntities')),
          props.result.entities.length > 8 && h('button', {
            class: 'expand-btn hb-btn',
            onClick: () => { expandedEntities.value = !expandedEntities.value }
          }, expandedEntities.value ? t('step4.collapse') : t('step4.expandAllEntities', { count: props.result.entities.length }))
        ])
      ])
    ])
  }
}

// Interview Display Component - Conversation Style (Q&A Format)
const InterviewDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    // Clean quote text - remove leading list numbers to avoid double numbering
    const cleanQuoteText = (text) => {
      if (!text) return ''
      // Remove leading patterns like "1. ", "2. ", "1、", "（1）", "(1)" etc.
      return text.replace(/^\s*\d+[\.\、\)）]\s*/, '').trim()
    }
    
    const activeIndex = ref(0)
    const expandedAnswers = ref(new Set())
    // 为每个问题-回答对维护独立的平台选择状态
    const platformTabs = reactive({}) // { 'agentIdx-qIdx': 'twitter' | 'reddit' }
    
    // 获取某个问题的当前平台选择
    const getPlatformTab = (agentIdx, qIdx) => {
      const key = `${agentIdx}-${qIdx}`
      return platformTabs[key] || 'twitter'
    }
    
    // 设置某个问题的平台选择
    const setPlatformTab = (agentIdx, qIdx, platform) => {
      const key = `${agentIdx}-${qIdx}`
      platformTabs[key] = platform
    }
    
    const toggleAnswer = (key) => {
      const newSet = new Set(expandedAnswers.value)
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
      expandedAnswers.value = newSet
    }
    
    const formatAnswer = (text, expanded) => {
      if (!text) return ''
      if (expanded || text.length <= 400) return text
      return text.substring(0, 400) + '...'
    }
    
    // 检查是否为平台占位文本
    const isPlaceholderText = (text) => {
      if (!text) return true
      const t = text.trim()
      return t === '（该平台未获得回复）' || t === '(该平台未获得回复)' || t === '[无回复]'
    }

    // 尝试按问题编号分割回答
    const splitAnswerByQuestions = (answerText, questionCount) => {
      if (!answerText || questionCount <= 0) return [answerText]
      if (isPlaceholderText(answerText)) return ['']

      // 支持两种编号格式：
      // 1. "问题X：" 或 "问题X:" （中文格式，后端新格式）
      // 2. "1. " 或 "\n1. " （数字+点，旧格式兼容）
      let matches = []
      let match

      // 优先尝试 "问题X：" 格式
      const cnPattern = /(?:^|[\r\n]+)问题(\d+)[：:]\s*/g
      while ((match = cnPattern.exec(answerText)) !== null) {
        matches.push({
          num: parseInt(match[1]),
          index: match.index,
          fullMatch: match[0]
        })
      }

      // 如果没匹配到，回退到 "数字." 格式
      if (matches.length === 0) {
        const numPattern = /(?:^|[\r\n]+)(\d+)\.\s+/g
        while ((match = numPattern.exec(answerText)) !== null) {
          matches.push({
            num: parseInt(match[1]),
            index: match.index,
            fullMatch: match[0]
          })
        }
      }

      // 如果没有找到编号或只找到一个，返回整体
      if (matches.length <= 1) {
        const cleaned = answerText
          .replace(/^问题\d+[：:]\s*/, '')
          .replace(/^\d+\.\s+/, '')
          .trim()
        return [cleaned || answerText]
      }

      // 按编号提取各部分
      const parts = []
      for (let i = 0; i < matches.length; i++) {
        const current = matches[i]
        const next = matches[i + 1]

        const startIdx = current.index + current.fullMatch.length
        const endIdx = next ? next.index : answerText.length

        let part = answerText.substring(startIdx, endIdx).trim()
        part = part.replace(/[\r\n]+$/, '').trim()
        parts.push(part)
      }

      if (parts.length > 0 && parts.some(p => p)) {
        return parts
      }

      return [answerText]
    }
    
    // 获取某个问题对应的回答
    const getAnswerForQuestion = (interview, qIdx, platform) => {
      const answer = platform === 'twitter' ? interview.twitterAnswer : (interview.redditAnswer || interview.twitterAnswer)
      if (!answer || isPlaceholderText(answer)) return answer || ''

      const questionCount = interview.questions?.length || 1
      const answers = splitAnswerByQuestions(answer, questionCount)

      // 分割成功且索引有效
      if (answers.length > 1 && qIdx < answers.length) {
        return answers[qIdx] || ''
      }

      // 分割失败：第一个问题返回完整回答，其余返回空
      return qIdx === 0 ? answer : ''
    }
    
    // 检查某个问题是否有双平台回答（过滤占位文本）
    const hasMultiplePlatforms = (interview, qIdx) => {
      if (!interview.twitterAnswer || !interview.redditAnswer) return false
      const twitterAnswer = getAnswerForQuestion(interview, qIdx, 'twitter')
      const redditAnswer = getAnswerForQuestion(interview, qIdx, 'reddit')
      // 两个平台都有真实回答（非占位文本）且内容不同
      return !isPlaceholderText(twitterAnswer) && !isPlaceholderText(redditAnswer) && twitterAnswer !== redditAnswer
    }
    
    return () => h('div', { class: 'interview-display' }, [
      // Header Section
      h('div', { class: 'interview-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, [
            'Agent Interview',
            h('span', { class: SIMULATED_LABEL_CLASS }, 'Simulated')
          ]),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.successCount || props.result.interviews.length),
              h('span', { class: 'stat-label' }, 'Interviewed')
            ]),
            props.result.totalCount > 0 && h('span', { class: 'stat-divider' }, '/'),
            props.result.totalCount > 0 && h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.totalCount),
              h('span', { class: 'stat-label' }, 'Total')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.topic && h('div', { class: 'header-topic' }, props.result.topic)
      ]),
      
      // Agent Selector Tabs
      props.result.interviews.length > 0 && h('div', { class: 'agent-tabs' }, 
        props.result.interviews.map((interview, i) => h('button', {
          class: ['agent-tab', { active: activeIndex.value === i }],
          'aria-pressed': activeIndex.value === i,
          key: i,
          onClick: () => { activeIndex.value = i }
        }, [
          h('span', { class: 'tab-avatar' }, interview.name ? interview.name.charAt(0) : (i + 1)),
          h('span', { class: 'tab-name' }, interview.title || interview.name || `Agent ${i + 1}`)
        ]))
      ),
      
      // Active Interview Detail
      props.result.interviews.length > 0 && h('div', { class: 'interview-detail' }, [
        // Agent Profile Card
        h('div', { class: 'agent-profile' }, [
          h('div', { class: 'profile-avatar' }, props.result.interviews[activeIndex.value]?.name?.charAt(0) || 'A'),
          h('div', { class: 'profile-info' }, [
            h('div', { class: 'profile-name' }, props.result.interviews[activeIndex.value]?.name || 'Agent'),
            h('div', { class: 'profile-role' }, props.result.interviews[activeIndex.value]?.role || ''),
            props.result.interviews[activeIndex.value]?.bio && h('div', { class: 'profile-bio' }, props.result.interviews[activeIndex.value].bio)
          ])
        ]),
        
        // Selection Reason - 选择理由
        props.result.interviews[activeIndex.value]?.selectionReason && h('div', { class: 'selection-reason' }, [
          h('div', { class: 'reason-label' }, '选择理由'),
          h('div', { class: 'reason-content' }, props.result.interviews[activeIndex.value].selectionReason)
        ]),
        
        // Q&A Conversation Thread - 一问一答样式
        h('div', { class: 'qa-thread' }, 
          (props.result.interviews[activeIndex.value]?.questions?.length > 0 
            ? props.result.interviews[activeIndex.value].questions 
            : [props.result.interviews[activeIndex.value]?.question || 'No question available']
          ).map((question, qIdx) => {
            const interview = props.result.interviews[activeIndex.value]
            const currentPlatform = getPlatformTab(activeIndex.value, qIdx)
            const answerText = getAnswerForQuestion(interview, qIdx, currentPlatform)
            const hasDualPlatform = hasMultiplePlatforms(interview, qIdx)
            const expandKey = `${activeIndex.value}-${qIdx}`
            const isExpanded = expandedAnswers.value.has(expandKey)
            const isPlaceholder = isPlaceholderText(answerText)

            return h('div', { class: 'qa-pair', key: qIdx }, [
              // Question Block
              h('div', { class: 'qa-question' }, [
                h('div', { class: 'qa-badge q-badge' }, `Q${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-sender' }, 'Interviewer'),
                  h('div', { class: 'qa-text' }, question)
                ])
              ]),

              // Answer Block
              answerText && h('div', { class: ['qa-answer', { 'answer-placeholder': isPlaceholder }] }, [
                h('div', { class: 'qa-badge a-badge' }, `A${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-answer-header' }, [
                    h('div', { class: 'qa-sender' }, interview?.name || 'Agent'),
                    // 双平台切换按钮（仅在有真实双平台回答时显示）
                    hasDualPlatform && h('div', { class: 'platform-switch' }, [
                      h('button', {
                        class: ['platform-btn', { active: currentPlatform === 'twitter' }],
                        'aria-pressed': currentPlatform === 'twitter',
                        onClick: (e) => { e.stopPropagation(); setPlatformTab(activeIndex.value, qIdx, 'twitter') }
                      }, [
                        h('svg', { class: 'platform-icon', 'aria-hidden': 'true', viewBox: '0 0 24 24', width: 12, height: 12, fill: 'none', stroke: 'currentColor', 'stroke-width': 2 }, [
                          h('circle', { cx: '12', cy: '12', r: '10' }),
                          h('line', { x1: '2', y1: '12', x2: '22', y2: '12' }),
                          h('path', { d: 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' })
                        ]),
                        h('span', {}, t('step4.world1'))
                      ]),
                      h('button', {
                        class: ['platform-btn', { active: currentPlatform === 'reddit' }],
                        'aria-pressed': currentPlatform === 'reddit',
                        onClick: (e) => { e.stopPropagation(); setPlatformTab(activeIndex.value, qIdx, 'reddit') }
                      }, [
                        h('svg', { class: 'platform-icon', 'aria-hidden': 'true', viewBox: '0 0 24 24', width: 12, height: 12, fill: 'none', stroke: 'currentColor', 'stroke-width': 2 }, [
                          h('path', { d: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z' })
                        ]),
                        h('span', {}, t('step4.world2'))
                      ])
                    ])
                  ]),
                  h('div', {
                    class: ['qa-text', 'answer-text', { 'placeholder-text': isPlaceholder }],
                    innerHTML: isPlaceholder
                      ? answerText
                      : escapeLt(formatAnswer(answerText, isExpanded))
                          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                          .replace(/\n/g, '<br>')
                  }),
                  // Expand/Collapse Button（占位文本不显示）
                  !isPlaceholder && answerText.length > 400 && h('button', {
                    class: 'expand-answer-btn hb-link',
                    onClick: () => toggleAnswer(expandKey)
                  }, isExpanded ? 'Show Less' : 'Show More')
                ])
              ])
            ])
          })
        ),
        
        // Key Quotes Section
        props.result.interviews[activeIndex.value]?.quotes?.length > 0 && h('div', { class: 'quotes-section' }, [
          h('div', { class: 'quotes-header' }, 'Key Quotes'),
          h('div', { class: 'quotes-list' },
            props.result.interviews[activeIndex.value].quotes.slice(0, 3).map((quote, qi) => {
              const cleanedQuote = cleanQuoteText(quote)
              const displayQuote = cleanedQuote.length > 200 ? cleanedQuote.substring(0, 200) + '...' : cleanedQuote
              return h('blockquote', { 
                key: qi, 
                class: 'quote-item',
                innerHTML: renderMarkdown(displayQuote)
              })
            })
          )
        ])
      ]),

      // Summary Section (Collapsible)
      props.result.summary && h('div', { class: 'summary-section' }, [
        h('div', { class: 'summary-header' }, 'Interview Summary'),
        h('div', { 
          class: 'summary-content',
          innerHTML: renderMarkdown(props.result.summary.length > 500 ? props.result.summary.substring(0, 500) + '...' : props.result.summary)
        })
      ])
    ])
  }
}

// Quick Search Display Component - Enhanced with full data rendering
const QuickSearchDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const { t } = useI18n()
    const activeTab = ref('facts') // 'facts', 'edges', 'nodes'
    const expandedFacts = ref(false)
    const INITIAL_SHOW_COUNT = 5
    
    // Check if there are edges or nodes to show tabs
    const hasEdges = computed(() => props.result.edges && props.result.edges.length > 0)
    const hasNodes = computed(() => props.result.nodes && props.result.nodes.length > 0)
    const showTabs = computed(() => hasEdges.value || hasNodes.value)
    
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    return () => h('div', { class: 'quick-search-display' }, [
      // Header Section
      h('div', { class: 'quicksearch-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, 'Quick Search'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.count || props.result.facts.length),
              h('span', { class: 'stat-label' }, 'Results')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-query' }, [
          h('span', { class: 'query-label' }, t('step4.searchLabel')),
          h('span', { class: 'query-text' }, props.result.query)
        ])
      ]),
      
      // Tab Navigation (only show if there are edges or nodes)
      showTabs.value && h('div', { class: 'quicksearch-tabs' }, [
        h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'facts' }],
          'aria-pressed': activeTab.value === 'facts',
          onClick: () => { activeTab.value = 'facts' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabFacts', { count: props.result.facts.length }))
        ]),
        hasEdges.value && h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'edges' }],
          'aria-pressed': activeTab.value === 'edges',
          onClick: () => { activeTab.value = 'edges' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabEdges', { count: props.result.edges.length }))
        ]),
        hasNodes.value && h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'nodes' }],
          'aria-pressed': activeTab.value === 'nodes',
          onClick: () => { activeTab.value = 'nodes' }
        }, [
          h('span', { class: 'tab-label' }, t('step4.tabNodes', { count: props.result.nodes.length }))
        ])
      ]),
      
      // Content Area
      h('div', { class: ['quicksearch-content', { 'no-tabs': !showTabs.value }] }, [
        // Facts (always show if no tabs, or when facts tab is active)
        ((!showTabs.value) || activeTab.value === 'facts') && h('div', { class: 'facts-panel' }, [
          !showTabs.value && h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelSearchResults')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.facts.length }))
          ]),
          props.result.facts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: factClass(fact), key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, markSimulated(fact))
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptySearchResults')),
          props.result.facts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn hb-btn',
            onClick: () => { expandedFacts.value = !expandedFacts.value }
          }, expandedFacts.value ? t('step4.collapse') : t('step4.expandAll', { count: props.result.facts.length }))
        ]),
        
        // Edges Tab
        activeTab.value === 'edges' && hasEdges.value && h('div', { class: 'edges-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelRelatedEdges')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.edges.length }))
          ]),
          h('div', { class: 'edges-list' },
            props.result.edges.map((edge, i) => 
              h('div', { class: 'edge-item', key: i }, [
                h('span', { class: 'edge-source' }, edge.source),
                h('span', { class: 'edge-arrow' }, [
                  h('span', { class: 'edge-line' }),
                  h('span', { class: 'edge-label' }, edge.relation),
                  h('span', { class: 'edge-line' })
                ]),
                h('span', { class: 'edge-target' }, edge.target)
              ])
            )
          )
        ]),
        
        // Nodes Tab
        activeTab.value === 'nodes' && hasNodes.value && h('div', { class: 'nodes-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelRelatedNodes')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.nodes.length }))
          ]),
          h('div', { class: 'nodes-grid' },
            props.result.nodes.map((node, i) => 
              h('div', { class: 'node-tag', key: i }, [
                h('span', { class: 'node-name' }, node.name),
                node.type && h('span', { class: 'node-type' }, node.type)
              ])
            )
          )
        ])
      ])
    ])
  }
}

// Computed
const statusClass = computed(() => {
  if (isComplete.value) return 'completed'
  if (agentLogs.value.length > 0) return 'processing'
  return 'pending'
})

const statusText = computed(() => {
  if (isComplete.value) return 'Completed'
  if (agentLogs.value.length > 0) return 'Generating...'
  return 'Waiting'
})

const totalSections = computed(() => {
  return reportOutline.value?.sections?.length || 0
})

const completedSections = computed(() => {
  return Object.keys(generatedSections.value).length
})

const progressPercent = computed(() => {
  if (totalSections.value === 0) return 0
  return Math.round((completedSections.value / totalSections.value) * 100)
})

const totalToolCalls = computed(() => {
  return agentLogs.value.filter(l => l.action === 'tool_call').length
})

const formatElapsedTime = computed(() => {
  if (!startTime.value) return '0s'
  const lastLog = agentLogs.value[agentLogs.value.length - 1]
  const elapsed = lastLog?.elapsed_seconds || 0
  if (elapsed < 60) return `${Math.round(elapsed)}s`
  const mins = Math.floor(elapsed / 60)
  const secs = Math.round(elapsed % 60)
  return `${mins}m ${secs}s`
})

const displayLogs = computed(() => {
  return agentLogs.value
})

// Workflow steps overview (status-based, no nested cards)
const activeSectionIndex = computed(() => {
  if (isComplete.value) return null
  if (currentSectionIndex.value) return currentSectionIndex.value
  if (totalSections.value > 0 && completedSections.value < totalSections.value) return completedSections.value + 1
  return null
})

const isPlanningDone = computed(() => {
  return !!reportOutline.value?.sections?.length || agentLogs.value.some(l => l.action === 'planning_complete')
})

const isPlanningStarted = computed(() => {
  return agentLogs.value.some(l => l.action === 'planning_start' || l.action === 'report_start')
})

const isFinalizing = computed(() => {
  return !isComplete.value && isPlanningDone.value && totalSections.value > 0 && completedSections.value >= totalSections.value
})

// 当前活跃的步骤（用于顶部显示）
const activeStep = computed(() => {
  const steps = workflowSteps.value
  // 找到当前 active 的步骤
  const active = steps.find(s => s.status === 'active')
  if (active) return active
  
  // 如果没有 active，返回最后一个 done 的步骤
  const doneSteps = steps.filter(s => s.status === 'done')
  if (doneSteps.length > 0) return doneSteps[doneSteps.length - 1]
  
  // 否则返回第一个步骤
  return steps[0] || { noLabel: '--', title: '等待开始', status: 'todo', meta: '' }
})

const workflowSteps = computed(() => {
  const steps = []

  // Planning / Outline
  const planningStatus = isPlanningDone.value ? 'done' : (isPlanningStarted.value ? 'active' : 'todo')
  steps.push({
    key: 'planning',
    noLabel: 'PL',
    title: 'Planning / Outline',
    status: planningStatus,
    meta: planningStatus === 'active' ? 'IN PROGRESS' : ''
  })

  // Sections (if outline exists)
  const sections = reportOutline.value?.sections || []
  sections.forEach((section, i) => {
    const idx = i + 1
    const status = (isComplete.value || !!generatedSections.value[idx])
      ? 'done'
      : (activeSectionIndex.value === idx ? 'active' : 'todo')

    steps.push({
      key: `section-${idx}`,
      noLabel: String(idx).padStart(2, '0'),
      title: section.title,
      status,
      meta: status === 'active' ? 'IN PROGRESS' : ''
    })
  })

  // Complete
  const completeStatus = isComplete.value ? 'done' : (isFinalizing.value ? 'active' : 'todo')
  steps.push({
    key: 'complete',
    noLabel: 'OK',
    title: 'Complete',
    status: completeStatus,
    meta: completeStatus === 'active' ? 'FINALIZING' : ''
  })

  return steps
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    })
  } catch {
    return ''
  }
}

const formatParams = (params) => {
  if (!params) return ''
  try {
    return JSON.stringify(params, null, 2)
  } catch {
    return String(params)
  }
}

const formatResultSize = (length) => {
  if (!length) return ''
  if (length < 1000) return `${length} chars`
  return `${(length / 1000).toFixed(1)}k chars`
}

const truncateText = (text, maxLen) => {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.substring(0, maxLen) + '...'
}

const escapeLt = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;') // LLM/user text must not inject HTML

const renderMarkdown = (content) => {
  if (!content) return ''
  content = escapeLt(content)
  
  // 去掉开头的二级标题（## xxx），因为章节标题已在外层显示
  let processedContent = content.replace(/^##\s+.+\n+/, '')
  
  // 处理代码块
  let html = processedContent.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  
  // 处理行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  
  // 处理标题
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  
  // 处理引用块
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')
  
  // 处理列表 - 支持子列表
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (match, indent, num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })

  // 包装无序列表
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  // 包装有序列表
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')

  // 清理列表项之间的所有空白
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  // 清理列表开始标签后的空白
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  // 清理列表结束标签前的空白
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')
  
  // 处理粗体和斜体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  
  // 处理分隔线
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  
  // 处理换行 - 空行变成段落分隔，单换行变成 <br>
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  
  // 包装在段落中
  html = '<p class="md-p">' + html + '</p>'
  
  // 清理空段落
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  // 清理块级元素前后的 <br> 标签
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>)\s*<br>/g, '$1')
  // 清理 <p><br> 紧跟块级元素的情况（多余空行导致）
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr)/g, '$2')
  // 清理连续的 <br> 标签
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  // 清理块级元素后紧跟的段落开始标签前的 <br>
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>)<br>(<p|<div)/g, '$1$2')

  // 修复非连续有序列表的编号：当单项 <ol> 被段落内容隔开时，保持编号递增
  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence) {
      if (/<h[2-5]/.test(tokens[i])) {
        olCounter = 0
        inSequence = false
      }
    }
  }
  html = tokens.join('')

  // Every tag matched here was generated above: content cannot contain a raw "<".
  return html
    .replace(/<(p|li|blockquote)( class="md-[a-z]+"[^>]*)>(?=\s*(?:<(?:strong|em)>)?["\u201C]?\[SIMULATED\])/g, '<$1$2 data-origin="simulated">')
    .replace(/\[SIMULATED\]/g, `<span class="${SIMULATED_LABEL_CLASS}">[SIMULATED]</span>`)
}

const getTimelineItemClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  const isMilestone = log.action === 'section_complete' || log.action === 'report_complete'
  return {
    'node--active': isLatest,
    'node--done': !isLatest && isMilestone,
    'node--muted': !isLatest && !isMilestone,
    'node--tool': log.action === 'tool_call' || log.action === 'tool_result'
  }
}

const getConnectorClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  if (isLatest) return 'dot-active'
  if (log.action === 'section_complete' || log.action === 'report_complete') return 'dot-done'
  return 'dot-muted'
}

const getActionLabel = (action) => {
  const labels = {
    'report_start': 'Report Started',
    'planning_start': 'Planning',
    'planning_complete': 'Plan Complete',
    'section_start': 'Section Start',
    'section_content': 'Content Ready',
    'section_complete': 'Section Done',
    'tool_call': 'Tool Call',
    'tool_result': 'Tool Result',
    'llm_response': 'LLM Response',
    'report_complete': 'Complete'
  }
  return labels[action] || action
}

const getLogLevelClass = (log) => {
  if (log.includes('ERROR') || log.includes('错误')) return 'error'
  if (log.includes('WARNING') || log.includes('警告')) return 'warning'
  // INFO 使用默认颜色，不标记为 success
  return ''
}

// Polling
let agentLogTimer = null
let consoleLogTimer = null

const fetchAgentLog = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, agentLogLine.value)
    
    if (res.success && res.data) {
      const newLogs = res.data.logs || []
      
      if (newLogs.length > 0) {
        newLogs.forEach(log => {
          agentLogs.value.push(log)
          
          if (log.action === 'planning_complete' && log.details?.outline) {
            reportOutline.value = log.details.outline
          }
          
          if (log.action === 'section_start') {
            currentSectionIndex.value = log.section_index
          }

          // section_complete - 章节生成完成
          if (log.action === 'section_complete') {
            if (log.details?.content) {
              generatedSections.value[log.section_index] = log.details.content
              // 自动展开刚生成的章节
              expandedContent.value.add(log.section_index - 1)
              currentSectionIndex.value = null
            }
          }
          
          if (log.action === 'report_complete') {
            isComplete.value = true
            currentSectionIndex.value = null  // 确保清除 loading 状态
            emit('update-status', 'completed')
            stopPolling()
            // 滚动逻辑统一在循环结束后的 nextTick 中处理
          }
          
          if (log.action === 'report_start') {
            startTime.value = new Date(log.timestamp)
          }
        })
        
        agentLogLine.value = res.data.from_line + newLogs.length
        
        nextTick(() => {
          if (rightPanel.value) {
            // 如果任务已完成，滚动到顶部；否则滚动到底部跟随最新日志
            if (isComplete.value) {
              rightPanel.value.scrollTop = 0
            } else {
              rightPanel.value.scrollTop = rightPanel.value.scrollHeight
            }
          }
        })
      }
    }
  } catch (err) {
    console.warn('Failed to fetch agent log:', err)
  }
}

// 提取最终答案内容 - 从 LLM response 中提取章节内容
const extractFinalContent = (response) => {
  if (!response) return null
  
  // 尝试提取 <final_answer> 标签内的内容
  const finalAnswerTagMatch = response.match(/<final_answer>([\s\S]*?)<\/final_answer>/)
  if (finalAnswerTagMatch) {
    return finalAnswerTagMatch[1].trim()
  }
  
  // 尝试找 Final Answer: 后面的内容（支持多种格式）
  // 格式1: Final Answer:\n\n内容
  // 格式2: Final Answer: 内容
  const finalAnswerMatch = response.match(/Final\s*Answer:\s*\n*([\s\S]*)$/i)
  if (finalAnswerMatch) {
    return finalAnswerMatch[1].trim()
  }
  
  // 尝试找 最终答案: 后面的内容
  const chineseFinalMatch = response.match(/最终答案[:：]\s*\n*([\s\S]*)$/i)
  if (chineseFinalMatch) {
    return chineseFinalMatch[1].trim()
  }
  
  // 如果以 ## 或 # 或 > 开头，可能是直接的 markdown 内容
  const trimmedResponse = response.trim()
  if (trimmedResponse.match(/^[#>]/)) {
    return trimmedResponse
  }
  
  // 如果内容较长且包含markdown格式，尝试移除思考过程后返回
  if (response.length > 300 && (response.includes('**') || response.includes('>'))) {
    // 移除 Thought: 开头的思考过程
    const thoughtMatch = response.match(/^Thought:[\s\S]*?(?=\n\n[^T]|\n\n$)/i)
    if (thoughtMatch) {
      const afterThought = response.substring(thoughtMatch[0].length).trim()
      if (afterThought.length > 100) {
        return afterThought
      }
    }
  }
  
  return null
}

const fetchConsoleLog = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getConsoleLog(props.reportId, consoleLogLine.value)
    
    if (res.success && res.data) {
      const newLogs = res.data.logs || []
      
      if (newLogs.length > 0) {
        consoleLogs.value.push(...newLogs)
        consoleLogLine.value = res.data.from_line + newLogs.length
        
        nextTick(() => {
          if (logContent.value) {
            logContent.value.scrollTop = logContent.value.scrollHeight
          }
        })
      }
    }
  } catch (err) {
    console.warn('Failed to fetch console log:', err)
  }
}

const startPolling = () => {
  if (agentLogTimer || consoleLogTimer) return
  
  fetchAgentLog()
  fetchConsoleLog()
  
  agentLogTimer = setInterval(fetchAgentLog, 2000)
  consoleLogTimer = setInterval(fetchConsoleLog, 1500)
}

const stopPolling = () => {
  if (agentLogTimer) {
    clearInterval(agentLogTimer)
    agentLogTimer = null
  }
  if (consoleLogTimer) {
    clearInterval(consoleLogTimer)
    consoleLogTimer = null
  }
}

// Lifecycle
onMounted(() => {
  if (props.reportId) {
    addLog(`Report Agent initialized: ${props.reportId}`)
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

watch(() => props.reportId, (newId) => {
  if (newId) {
    agentLogs.value = []
    consoleLogs.value = []
    agentLogLine.value = 0
    consoleLogLine.value = 0
    reportOutline.value = null
    currentSectionIndex.value = null
    generatedSections.value = {}
    expandedContent.value = new Set()
    expandedLogs.value = new Set()
    collapsedSections.value = new Set()
    isComplete.value = false
    startTime.value = null
    
    startPolling()
  }
}, { immediate: true })
</script>

<style scoped>
.report-panel {
  --report-mono: ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  container-type: inline-size;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--hb-paper);
  color: var(--hb-navy);
  font-family: var(--hb-font-sans);
}

.main-split-layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(380px, 38%, 520px);
  grid-template-rows: minmax(0, 1fr);
  min-height: 0;
}

.left-panel,
.right-panel,
.log-content {
  overflow-y: auto;
  overscroll-behavior: contain;
}

.left-panel:focus-visible,
.right-panel:focus-visible,
.log-content:focus-visible {
  outline-offset: -2px;
}

/* Report */
.left-panel {
  min-height: 0;
  padding: var(--hb-space-5) clamp(16px, 3.5cqi, 34px) var(--hb-space-7);
}

.report-content-wrapper {
  max-width: 46rem;
}

.report-header-block {
  padding-bottom: var(--hb-space-5);
  border-bottom: 1px solid var(--hb-navy);
}

.main-title {
  font-size: 1.875rem;
  line-height: 1.1;
  overflow-wrap: break-word;
}

.sub-title {
  max-width: 68ch;
  margin-top: var(--hb-space-2);
  color: var(--hb-navy-soft);
  font: italic 400 var(--hb-text-xl) / 1.4 var(--hb-font-serif);
  text-wrap: pretty;
}

.report-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-1) var(--hb-space-3);
  margin-top: var(--hb-space-3);
}

.report-id {
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
  overflow-wrap: anywhere;
}

.sim-notice {
  margin-top: var(--hb-space-3);
  padding: 7px 11px;
  color: var(--hb-magenta);
  border: 1.5px dashed var(--hb-magenta);
  font-weight: 700;
  text-wrap: pretty;
}

.report-section-item {
  border-bottom: 1px solid var(--hb-rule);
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: var(--hb-space-3);
  width: 100%;
  padding: var(--hb-space-4) var(--hb-space-1) var(--hb-space-3) 0;
  color: inherit;
  background: none;
  border: 0;
  font: inherit;
  text-align: left;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.section-header-row.clickable {
  cursor: pointer;
}

.section-header-row.clickable:hover {
  background: var(--hb-water-soft);
}

.section-number {
  flex: none;
  width: 1.5rem;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-lg);
}

.section-title {
  flex: 1;
  min-width: 0;
  font: 700 var(--hb-text-2xl) / 1.2 var(--hb-font-serif);
  overflow-wrap: break-word;
  text-wrap: balance;
}

.is-pending .section-title {
  color: var(--hb-navy-soft);
  font-weight: 500;
}

.collapse-icon {
  flex: none;
  align-self: center;
  transition: transform var(--hb-motion-fast) ease-out;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.section-body {
  min-width: 0;
  padding-left: calc(1.5rem + var(--hb-space-3));
}

.generated-content {
  max-width: 68ch;
  padding-bottom: var(--hb-space-5);
  font: 400 var(--hb-text-xl) / 1.55 var(--hb-font-serif);
  overflow-wrap: break-word;
}

.generated-content :deep(p) {
  margin-bottom: 0.8em;
  text-wrap: pretty;
}

.generated-content :deep(:is(.md-h2, .md-h3)) {
  margin: 1.4em 0 0.4em;
  font: 700 1.25rem / 1.2 var(--hb-font-serif);
}

.generated-content :deep(:is(.md-h4, .md-h5)) {
  margin: 1.3em 0 0.35em;
  font: 700 var(--hb-text-lg) / 1.2 var(--hb-font-sc);
  letter-spacing: 0.015em;
}

.generated-content :deep(:is(.md-h2, .md-h3, .md-h4, .md-h5):first-child) {
  margin-top: 0;
}

.generated-content :deep(:is(.md-ul, .md-ol)) {
  margin: 0 0 0.8em;
  padding-left: 1.3em;
}

.generated-content :deep(:is(.md-li, .md-oli)) {
  margin: 0.3em 0;
  padding-left: 0.2em;
}

.generated-content :deep(:is(.md-li, .md-oli)::marker) {
  color: var(--hb-navy-soft);
}

.generated-content :deep(.md-quote) {
  margin: 1em 0;
  padding-left: var(--hb-space-4);
  border-left: 1px solid var(--hb-navy);
  font-style: italic;
}

.generated-content :deep([data-origin='simulated']) {
  padding-top: 0.35em;
  border-top: 1px dashed var(--hb-magenta);
}

.generated-content :deep(.md-quote[data-origin='simulated']) {
  border-left: 1px dashed var(--hb-magenta);
}

.generated-content :deep(.md-hr) {
  margin: 1.4em 0;
  border: 0;
  border-top: 1px solid var(--hb-rule);
}

.generated-content :deep(strong) {
  font-weight: 700;
}

.generated-content :deep(.inline-code) {
  padding: 0 3px;
  background: var(--hb-water-soft);
  font: 0.82em var(--report-mono);
}

.generated-content :deep(.code-block) {
  margin: 1em 0;
  padding: var(--hb-space-3);
  overflow-x: auto;
  background: var(--hb-field);
  border: 1px solid var(--hb-rule);
  font: var(--hb-text-xs) / 1.45 var(--report-mono);
}

.loading-state {
  padding-bottom: var(--hb-space-5);
}

.loading-state::before,
.header-dot,
.waiting-ring,
.empty-pulse {
  animation: report-pulse 1.6s ease-in-out infinite alternate;
}

@keyframes report-pulse {
  to {
    opacity: 0.35;
  }
}

.loading-text {
  font-weight: 500;
}

.waiting-placeholder,
.workflow-empty {
  display: flex;
  align-items: center;
  gap: var(--hb-space-3);
  color: var(--hb-navy-soft);
}

.waiting-animation {
  display: flex;
  gap: var(--hb-space-1);
}

.waiting-ring,
.empty-pulse {
  flex: none;
  width: 10px;
  height: 10px;
  background: var(--hb-water);
  border: 1.5px solid var(--hb-navy);
}

.waiting-ring:nth-child(2) {
  animation-delay: 0.25s;
}

.waiting-ring:nth-child(3) {
  animation-delay: 0.5s;
}

/* Workflow rail */
.right-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-left: 1px solid var(--hb-navy);
}

.panel-header {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  flex: none;
  align-items: baseline;
  gap: var(--hb-space-2);
  padding: var(--hb-space-2) var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
}

.header-dot {
  flex: none;
  align-self: center;
  width: 10px;
  height: 10px;
  background: var(--hb-paper);
  border: 1.5px solid var(--hb-navy);
}

.header-title {
  min-width: 0;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.header-meta,
.wf-step-meta {
  flex: none;
  margin-left: auto;
  font: 500 var(--hb-text-xs) / 1.2 var(--hb-font-sc);
  text-transform: lowercase;
}

.workflow-overview {
  flex: none;
  padding: var(--hb-space-3) var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
}

.workflow-metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--hb-space-1) var(--hb-space-4);
}

.metric {
  display: inline-flex;
  flex-direction: row-reverse;
  align-items: baseline;
  gap: 5px;
}

.metric-right {
  margin-left: auto;
}

.metric-label {
  font-size: var(--hb-text-sm);
  font-weight: 700;
}

.metric-value {
  font-size: var(--hb-text-2xl);
  line-height: 1.1;
}

.metric-pill {
  font-size: var(--hb-text-sm);
}

.workflow-steps {
  margin-top: var(--hb-space-2);
  padding-top: var(--hb-space-2);
  border-top: 1px solid var(--hb-navy);
}

.wf-step,
.timeline-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  column-gap: var(--hb-space-3);
}

.wf-step-connector,
.timeline-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.wf-step-dot,
.connector-dot {
  flex: none;
  width: 10px;
  height: 10px;
  margin-top: 4px;
  background: var(--hb-paper);
  border: 1.5px solid var(--hb-navy);
}

.wf-step-line,
.connector-line {
  flex: 1;
  width: 1px;
  background: var(--hb-navy);
}

.wf-step--active .wf-step-dot,
.dot-active {
  background: var(--hb-water);
}

.wf-step--done .wf-step-dot,
.dot-done {
  background: var(--hb-navy);
}

.dot-muted {
  border-color: var(--hb-navy-soft);
}

.wf-step-content {
  min-width: 0;
  padding-bottom: 5px;
}

.wf-step-title-row {
  display: flex;
  align-items: baseline;
  gap: var(--hb-space-2);
  font-size: var(--hb-text-sm);
}

.wf-step-index {
  flex: none;
  min-width: 1.25rem;
}

.wf-step-title {
  min-width: 0;
  overflow-wrap: anywhere;
}

.wf-step--active .wf-step-title {
  font-weight: 700;
}

.wf-step--todo .wf-step-title-row {
  color: var(--hb-navy-soft);
}

.next-step-btn {
  width: 100%;
  margin-top: var(--hb-space-3);
  white-space: normal;
}

.next-step-btn svg {
  flex: none;
}

/* Timeline */
.workflow-timeline {
  flex: 1;
  padding: var(--hb-space-4);
}

.timeline-content {
  min-width: 0;
  padding-bottom: var(--hb-space-4);
}

.timeline-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--hb-space-3);
  margin-bottom: var(--hb-space-1);
}

.action-label {
  font: 700 var(--hb-text-sm) / 1.3 var(--hb-font-sc);
  letter-spacing: 0.015em;
}

.node--muted .action-label {
  font-weight: 500;
}

.action-time,
.elapsed-badge,
.result-size,
.tag-num {
  flex: none;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.timeline-body {
  min-width: 0;
  font-size: var(--hb-text-md);
  overflow-wrap: anywhere;
}

.timeline-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--hb-space-3);
  margin-top: var(--hb-space-2);
}

.footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-2);
  margin-left: auto;
}

.action-btn {
  font-size: var(--hb-text-sm);
}

.info-row {
  display: grid;
  grid-template-columns: 6rem minmax(0, 1fr);
  gap: var(--hb-space-2);
  padding: 3px 0;
  font-size: var(--hb-text-sm);
}

.info-key {
  color: var(--hb-navy-soft);
}

.outline-badge {
  margin-top: var(--hb-space-1);
}

.section-tag,
.tool-badge,
.final-answer-hint,
.complete-banner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
}

.section-tag svg,
.tool-icon,
.final-answer-hint svg,
.complete-banner svg {
  flex: none;
}

.tag-title {
  min-width: 0;
  font-weight: 500;
}

.tool-badge {
  padding: 2px 7px;
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  border-radius: var(--hb-radius);
  font-size: var(--hb-text-sm);
  font-weight: 700;
}

.final-answer-hint {
  display: flex;
  margin-top: var(--hb-space-2);
  font-size: var(--hb-text-sm);
  font-weight: 500;
}

.complete-banner {
  display: flex;
  padding: var(--hb-space-2) var(--hb-space-3);
  color: var(--hb-paper);
  background: var(--hb-navy);
  font-weight: 700;
}

.llm-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-1);
}

.meta-tag {
  padding: 0 7px;
  border: 1px solid var(--hb-navy-soft);
  border-radius: var(--hb-radius);
  font: 500 var(--hb-text-xs) / 20px var(--hb-font-sc);
}

.meta-tag.active {
  background: var(--hb-water);
  border-color: var(--hb-navy);
}

.meta-tag.final-answer {
  color: var(--hb-paper);
  background: var(--hb-navy);
  border-color: var(--hb-navy);
  font-weight: 700;
}

.result-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--hb-space-3);
  margin-bottom: var(--hb-space-1);
}

.result-tool {
  font-weight: 700;
}

.tool-params,
.llm-content,
.result-raw {
  margin-top: var(--hb-space-2);
}

.llm-content,
.result-raw {
  max-height: 20rem;
  overflow-y: auto;
}

pre {
  padding: var(--hb-space-2) var(--hb-space-3);
  background: var(--hb-field);
  border: 1px solid var(--hb-rule);
  font: var(--hb-text-xs) / 1.45 var(--report-mono);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.workflow-empty {
  padding: var(--hb-space-2) 0;
}

.timeline-item-enter-active {
  transition: opacity 180ms ease-out;
}

.timeline-item-enter-from {
  opacity: 0;
}

/* Structured tool results */
.result-structured :deep(.header-main) {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 2px var(--hb-space-3);
}

.result-structured :deep(.header-title) {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--hb-space-2);
  font: 700 var(--hb-text-md) / 1.2 var(--hb-font-sc);
  letter-spacing: 0.015em;
}

.result-structured :deep(.header-stats),
.result-structured :deep(.stat-item) {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 3px;
}

.result-structured :deep(.header-stats) {
  column-gap: 5px;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.result-structured :deep(.stat-value) {
  color: var(--hb-navy);
  font: italic 500 var(--hb-text-lg) / 1 var(--hb-font-serif);
  font-variant-numeric: oldstyle-nums;
}

.result-structured :deep(:is(.header-topic, .header-query, .header-scenario)) {
  margin-top: 3px;
  font: 400 var(--hb-text-lg) / 1.3 var(--hb-font-serif);
}

.result-structured :deep(.header-scenario) {
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-md);
}

.result-structured :deep(:is(.scenario-label, .query-label)) {
  font-weight: 700;
}

.result-structured :deep(:is(.insight-tabs, .panorama-tabs, .quicksearch-tabs, .agent-tabs)) {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-1);
  margin-top: var(--hb-space-2);
}

.result-structured :deep(:is(.insight-tab, .panorama-tab, .quicksearch-tab, .agent-tab, .platform-btn)) {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 28px;
  max-width: 100%;
  padding: 2px 8px;
  color: var(--hb-navy);
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  border-radius: var(--hb-radius);
  font-size: var(--hb-text-sm);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.result-structured :deep(:is(.insight-tab, .panorama-tab, .quicksearch-tab, .agent-tab, .platform-btn):hover) {
  background: var(--hb-water-soft);
}

.result-structured :deep(:is(.insight-tab, .panorama-tab, .quicksearch-tab, .agent-tab, .platform-btn).active) {
  color: var(--hb-paper);
  background: var(--hb-navy);
  font-weight: 700;
}

.result-structured :deep(:is(.insight-content, .panorama-content, .quicksearch-content)) {
  margin-top: var(--hb-space-2);
}

.result-structured :deep(.panel-header) {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--hb-space-3);
  padding-bottom: var(--hb-space-1);
}

.result-structured :deep(.panel-title) {
  font: 700 var(--hb-text-sm) / 1.2 var(--hb-font-sc);
  letter-spacing: 0.015em;
}

.result-structured :deep(.panel-count) {
  flex: none;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.result-structured :deep(:is(.fact-item, .subquery-item, .relation-item, .edge-item)) {
  display: flex;
  gap: var(--hb-space-2);
  padding: 6px 0;
  border-top: 1px solid var(--hb-rule);
  font-size: var(--hb-text-md);
  line-height: 1.32;
}

.result-structured :deep(.fact-item.hb-row--simulated) {
  border-top: 1px dashed var(--hb-magenta);
}

.result-structured :deep(:is(.fact-number, .subquery-number)) {
  flex: none;
  min-width: 1.25rem;
  color: var(--hb-navy-soft);
  font-family: var(--hb-font-serif);
  font-style: italic;
  font-weight: 500;
  font-variant-numeric: oldstyle-nums;
}

.result-structured :deep(.fact-item.hb-row--simulated .fact-number) {
  color: var(--hb-magenta);
}

.result-structured :deep(:is(.fact-content, .subquery-text)) {
  flex: 1;
  min-width: 0;
}

.result-structured :deep(.fact-time) {
  display: block;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
  font-variant-numeric: lining-nums tabular-nums;
}

.result-structured :deep(.fact-text) {
  display: block;
}

.result-structured :deep(:is(.relation-item, .edge-item)) {
  flex-wrap: wrap;
  align-items: center;
  column-gap: 6px;
}

.result-structured :deep(:is(.rel-source, .rel-target, .edge-source, .edge-target)) {
  min-width: 0;
  font-weight: 700;
}

.result-structured :deep(:is(.rel-arrow, .edge-arrow)) {
  display: flex;
  flex: 1 1 7rem;
  align-items: center;
  gap: var(--hb-space-1);
  min-width: 0;
}

/* Relations carry no origin here, so they use the chart's "no label" line. */
.result-structured :deep(:is(.rel-line, .edge-line)) {
  flex: 1;
  min-width: var(--hb-space-3);
  border-top: 1.5px dotted var(--hb-navy-soft);
}

.result-structured :deep(:is(.rel-label, .edge-label)) {
  color: var(--hb-navy-soft);
  font: 500 var(--hb-text-xs) / 1.2 var(--hb-font-sc);
}

.result-structured :deep(:is(.entities-grid, .nodes-grid)) {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hb-space-1);
  padding-top: var(--hb-space-2);
  border-top: 1px solid var(--hb-rule);
}

.result-structured :deep(:is(.entity-tag, .node-tag)) {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 5px;
  max-width: 100%;
  padding: 1px 7px;
  background: var(--hb-paper);
  border: 1px solid var(--hb-rule);
  border-radius: var(--hb-radius);
  font-size: var(--hb-text-sm);
}

.result-structured :deep(:is(.entity-name, .node-name)) {
  font-weight: 700;
}

.result-structured :deep(:is(.entity-type, .node-type, .entity-fact-count)) {
  color: var(--hb-navy-soft);
  font: 500 var(--hb-text-xs) / 1.3 var(--hb-font-sc);
}

.result-structured :deep(.expand-btn) {
  width: 100%;
  margin-top: var(--hb-space-2);
  font-size: var(--hb-text-sm);
  white-space: normal;
}

.result-structured :deep(.empty-state) {
  padding: var(--hb-space-2) 0;
  color: var(--hb-navy-soft);
  border-top: 1px solid var(--hb-rule);
  font-size: var(--hb-text-sm);
}

/* Agent interviews: every answer comes from a simulated agent */
.result-structured :deep(.agent-tabs) {
  flex-wrap: nowrap;
  padding-bottom: var(--hb-space-1);
  overflow-x: auto;
}

.result-structured :deep(.agent-tab) {
  flex: none;
}

.result-structured :deep(.tab-avatar) {
  font-family: var(--hb-font-serif);
  font-weight: 700;
}

.result-structured :deep(.tab-name) {
  max-width: 9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-structured :deep(.interview-detail) {
  margin-top: var(--hb-space-2);
}

.result-structured :deep(.agent-profile) {
  display: flex;
  gap: var(--hb-space-2);
}

.result-structured :deep(.profile-avatar) {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--hb-land);
  border: 1px solid var(--hb-navy);
  font: 700 var(--hb-text-lg) / 1 var(--hb-font-serif);
}

.result-structured :deep(.profile-info) {
  flex: 1;
  min-width: 0;
}

.result-structured :deep(.profile-name) {
  font-weight: 700;
}

.result-structured :deep(:is(.profile-role, .profile-bio)) {
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.result-structured :deep(.profile-bio) {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.result-structured :deep(.selection-reason) {
  margin-top: var(--hb-space-2);
  padding-top: var(--hb-space-2);
  border-top: 1px solid var(--hb-rule);
  font-size: var(--hb-text-sm);
}

.result-structured :deep(:is(.reason-label, .quotes-header, .summary-header)) {
  margin-bottom: 3px;
  font: 700 var(--hb-text-sm) / 1.2 var(--hb-font-sc);
  letter-spacing: 0.015em;
}

.result-structured :deep(.qa-thread) {
  margin-top: var(--hb-space-2);
}

.result-structured :deep(:is(.qa-question, .qa-answer)) {
  display: flex;
  gap: var(--hb-space-2);
  padding: 6px 0;
  border-top: 1px solid var(--hb-rule);
}

.result-structured :deep(.qa-answer) {
  border-top: 1px dashed var(--hb-magenta);
}

.result-structured :deep(.qa-badge) {
  flex: none;
  min-width: 1.5rem;
  color: var(--hb-navy-soft);
  font: italic 500 var(--hb-text-md) / 1.3 var(--hb-font-serif);
  font-variant-numeric: oldstyle-nums;
}

.result-structured :deep(.a-badge) {
  color: var(--hb-magenta);
}

.result-structured :deep(.qa-content) {
  flex: 1;
  min-width: 0;
}

.result-structured :deep(.qa-answer-header) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--hb-space-1) var(--hb-space-2);
}

.result-structured :deep(.qa-sender) {
  color: var(--hb-navy-soft);
  font: 500 var(--hb-text-xs) / 1.3 var(--hb-font-sc);
}

.result-structured :deep(.qa-text) {
  font-size: var(--hb-text-md);
  line-height: 1.35;
}

.result-structured :deep(.answer-text) {
  font: 400 var(--hb-text-lg) / 1.4 var(--hb-font-serif);
}

.result-structured :deep(.answer-text strong) {
  font-weight: 700;
}

.result-structured :deep(.placeholder-text) {
  color: var(--hb-navy-soft);
  font-style: italic;
}

.result-structured :deep(.platform-switch) {
  display: flex;
  gap: var(--hb-space-1);
}

.result-structured :deep(.platform-btn) {
  min-height: 24px;
  padding: 0 6px;
  font-size: var(--hb-text-xs);
}

.result-structured :deep(.platform-icon) {
  flex: none;
}

.result-structured :deep(.expand-answer-btn) {
  margin-top: var(--hb-space-1);
  padding: 0;
  color: var(--hb-navy);
  background: none;
  border: 0;
  font-size: var(--hb-text-sm);
  cursor: pointer;
}

.result-structured :deep(:is(.quotes-section, .summary-section)) {
  margin-top: var(--hb-space-2);
  padding-top: var(--hb-space-2);
  border-top: 1px solid var(--hb-navy);
}

.result-structured :deep(.quote-item) {
  padding: 6px 0;
  border-top: 1px dashed var(--hb-magenta);
  font: italic 400 var(--hb-text-lg) / 1.35 var(--hb-font-serif);
}

.result-structured :deep(.summary-content) {
  font: 400 var(--hb-text-lg) / 1.4 var(--hb-font-serif);
}

.result-structured :deep(.summary-content .md-p) {
  margin-bottom: 0.5em;
}

.result-structured :deep(.summary-content :is(ul, ol)) {
  margin-bottom: 0.5em;
  padding-left: 1.2em;
}

.result-structured :deep(.summary-content :is(h2, h3, h4, h5)) {
  margin: 0.7em 0 0.2em;
  font: 700 var(--hb-text-md) / 1.2 var(--hb-font-sc);
}

.result-structured :deep(.summary-content blockquote) {
  padding-left: var(--hb-space-3);
  border-left: 1px solid var(--hb-navy);
  font-style: italic;
}

/* Console */
.console-logs {
  flex: none;
  padding: var(--hb-space-2) var(--hb-space-4);
  border-top: 1px solid var(--hb-navy);
}

.log-header {
  display: flex;
  justify-content: space-between;
  gap: var(--hb-space-3);
  padding-bottom: var(--hb-space-1);
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.log-title {
  color: var(--hb-navy);
  font: 700 var(--hb-text-sm) / 1.3 var(--hb-font-sc);
  letter-spacing: 0.015em;
  text-transform: lowercase;
}

.log-id {
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

.log-content {
  height: 5.5rem;
  border-top: 1px solid var(--hb-rule);
}

.log-line {
  padding: 1px 0;
  font-size: var(--hb-text-sm);
  font-variant-numeric: lining-nums tabular-nums;
  line-height: 1.3;
}

.log-msg {
  overflow-wrap: anywhere;
}

.log-msg.warning {
  background: var(--hb-land-soft);
  font-weight: 500;
}

.log-msg.error {
  background: var(--hb-land);
  font-weight: 700;
}

@container (max-width: 860px) {
  .main-split-layout {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 3fr) minmax(0, 2fr);
  }

  .right-panel {
    border-top: 1px solid var(--hb-navy);
    border-left: 0;
  }

  .log-content {
    height: 4rem;
  }
}

@container (max-width: 520px) {
  .section-body {
    padding-left: 0;
  }

  .info-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }
}
</style>
