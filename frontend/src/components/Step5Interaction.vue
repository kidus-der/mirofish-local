<template>
  <div class="interaction-panel">
    <div class="main-split-layout">
      <!-- Report -->
      <div class="left-panel" ref="leftPanel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <header class="report-head">
            <h1 class="hb-title">{{ reportOutline.title }}</h1>
            <p class="sub-title hb-lede hb-soft">{{ reportOutline.summary }}</p>
            <p class="report-id hb-small hb-soft hb-tabular">ID: {{ reportId || 'REF-2024-X92' }}</p>
            <p class="hb-simulated-note sim-note">{{ $t('home.notForecast') }}</p>
          </header>

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
                  class="section-toggle"
                  :disabled="!isSectionCompleted(idx + 1)"
                  :aria-expanded="isSectionCompleted(idx + 1) ? !collapsedSections.has(idx) : undefined"
                  @click="toggleSectionCollapse(idx)"
                >
                  <span class="section-number hb-sounding">{{ String(idx + 1).padStart(2, '0') }}</span>
                  <span class="section-title">{{ section.title }}</span>
                  <svg
                    v-if="isSectionCompleted(idx + 1)"
                    class="collapse-icon"
                    :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                    viewBox="0 0 24 24"
                    width="18"
                    height="18"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.75"
                    aria-hidden="true"
                  >
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>
              </h2>

              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1])"></div>

                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state hb-soft" role="status">
                  <span class="spinner" aria-hidden="true"></span>
                  <span>{{ $t('step4.generatingSection', { title: section.title }) }}</span>
                </div>
              </div>
            </section>
          </div>
        </div>

        <p v-if="!reportOutline" class="waiting-placeholder hb-status hb-status--running" role="status">
          {{ $t('step4.waitingForReportAgent') }}
        </p>
      </div>

      <!-- Research workspace -->
      <div class="right-panel hb-surface-land-soft" ref="rightPanel">
        <div class="action-bar hb-surface-land">
          <div class="hb-section-head">
            <h2 class="hb-heading">{{ $t('step5.interactiveTools') }}</h2>
            <span class="hb-small hb-soft hb-tabular">{{ $t('step5.agentsAvailable', { count: profiles.length }) }}</span>
          </div>

          <div class="mode-tabs" role="group" :aria-label="$t('step5.interactiveTools')">
            <button
              type="button"
              class="mode-tab"
              :class="{ active: activeTab === 'chat' && chatTarget === 'report_agent' }"
              :aria-current="activeTab === 'chat' && chatTarget === 'report_agent' ? 'true' : undefined"
              @click="selectReportAgentChat"
            >
              <span class="tab-label">{{ $t('step5.chatWithReportAgent') }}</span>
            </button>

            <div
              class="agent-dropdown"
              v-if="profiles.length > 0"
              @keydown.esc="showAgentDropdown = false; focusAgentToggle()"
            >
              <button
                type="button"
                class="mode-tab"
                :class="{ active: activeTab === 'chat' && chatTarget === 'agent' }"
                :aria-current="activeTab === 'chat' && chatTarget === 'agent' ? 'true' : undefined"
                :aria-expanded="showAgentDropdown"
                aria-controls="agent-menu"
                @click="toggleAgentDropdown"
              >
                <span class="tab-label">{{ selectedAgent ? selectedAgent.username : $t('step5.chatWithAgent') }}</span>
                <svg class="chevron" :class="{ 'is-open': showAgentDropdown }" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>

              <div v-if="showAgentDropdown" id="agent-menu" class="dropdown-menu">
                <p class="dropdown-header hb-subheading">{{ $t('step5.selectChatTarget') }}</p>
                <ul class="dropdown-list hb-list">
                  <li v-for="(agent, idx) in profiles" :key="idx">
                    <button
                      type="button"
                      class="dropdown-item"
                      :aria-current="selectedAgentIndex === idx ? 'true' : undefined"
                      @click="selectAgent(agent, idx); focusAgentToggle()"
                    >
                      <span class="initial initial--simulated" aria-hidden="true">{{ (agent.username || 'A')[0] }}</span>
                      <span class="person">
                        <span class="person-name">{{ agent.username }}</span>
                        <span class="person-role hb-soft">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                      </span>
                    </button>
                  </li>
                </ul>
              </div>
            </div>

            <button
              type="button"
              class="mode-tab"
              :class="{ active: activeTab === 'survey' }"
              :aria-current="activeTab === 'survey' ? 'true' : undefined"
              @click="selectSurveyTab"
            >
              <span class="tab-label">{{ $t('step5.sendSurvey') }}</span>
            </button>
          </div>
        </div>

        <!-- Chat and interviews -->
        <div v-if="activeTab === 'chat'" class="chat-container">
          <section v-if="chatTarget === 'report_agent'" class="context-card">
            <div class="context-head">
              <span class="initial" aria-hidden="true">R</span>
              <div class="context-info">
                <h3 class="hb-subheading">{{ $t('step5.reportAgentChat') }}</h3>
                <p class="context-sub hb-soft">{{ $t('step5.reportAgentDesc') }}</p>
              </div>
              <button
                type="button"
                class="icon-btn hb-btn"
                :aria-expanded="showToolsDetail"
                :aria-label="$t('step5.reportAgentChat')"
                @click="showToolsDetail = !showToolsDetail"
              >
                <svg class="chevron" :class="{ 'is-open': showToolsDetail }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <ul v-if="showToolsDetail" class="tools-list hb-list">
              <li>
                <span class="tool-name">{{ $t('step5.toolInsightForge') }}</span>
                <span class="tool-desc hb-soft">{{ $t('step5.toolInsightForgeDesc') }}</span>
              </li>
              <li>
                <span class="tool-name">{{ $t('step5.toolPanoramaSearch') }}</span>
                <span class="tool-desc hb-soft">{{ $t('step5.toolPanoramaSearchDesc') }}</span>
              </li>
              <li>
                <span class="tool-name">{{ $t('step5.toolQuickSearch') }}</span>
                <span class="tool-desc hb-soft">{{ $t('step5.toolQuickSearchDesc') }}</span>
              </li>
              <li>
                <span class="tool-name">{{ $t('step5.toolInterviewSubAgent') }}</span>
                <span class="tool-desc hb-soft">{{ $t('step5.toolInterviewSubAgentDesc') }}</span>
              </li>
            </ul>
          </section>

          <section v-if="chatTarget === 'agent' && selectedAgent" class="context-card">
            <div class="context-head">
              <span class="initial initial--simulated" aria-hidden="true">{{ (selectedAgent.username || 'A')[0] }}</span>
              <div class="context-info">
                <h3 class="profile-name hb-subheading">
                  <span>{{ selectedAgent.username }}</span>
                  <span class="hb-origin hb-origin--simulated">{{ simulatedLabel }}</span>
                </h3>
                <p class="context-sub hb-soft">
                  <span v-if="selectedAgent.name" class="profile-handle">@{{ selectedAgent.name }}</span>
                  <span>{{ selectedAgent.profession || $t('step2.unknownProfession') }}</span>
                </p>
              </div>
              <button
                type="button"
                class="icon-btn hb-btn"
                :aria-expanded="showFullProfile"
                :aria-label="selectedAgent.username"
                @click="showFullProfile = !showFullProfile"
              >
                <svg class="chevron" :class="{ 'is-open': showFullProfile }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showFullProfile && selectedAgent.bio" class="profile-bio">
              <h4 class="hb-subheading">{{ $t('step5.profileBio') }}</h4>
              <p>{{ selectedAgent.bio }}</p>
            </div>
          </section>

          <p v-if="chatTarget === 'agent'" class="chat-sim-note hb-simulated-note sim-note">{{ $t('home.notForecast') }}</p>

          <div
            class="chat-messages"
            ref="chatMessages"
            role="log"
            tabindex="0"
            :aria-label="chatTarget === 'report_agent' ? $t('step5.reportAgentChat') : (selectedAgent?.username || $t('step5.chatWithAgent'))"
            :aria-busy="isSending"
          >
            <div v-if="chatHistory.length === 0" class="chat-empty">
              <p class="empty-text hb-soft">
                {{ chatTarget === 'report_agent' ? $t('step5.chatEmptyReportAgent') : $t('step5.chatEmptyAgent') }}
              </p>
            </div>

            <article
              v-for="(msg, idx) in chatHistory"
              :key="idx"
              class="chat-message"
              :class="[msg.role, isAgentStatement(msg) ? 'hb-row--simulated' : 'hb-row--source', { 'is-error': msg.isError }]"
            >
              <span
                class="initial"
                :class="{ 'initial--user': msg.role === 'user', 'initial--simulated': isAgentStatement(msg) }"
                aria-hidden="true"
              >
                <template v-if="msg.role === 'user'">U</template>
                <template v-else>{{ msg.role === 'assistant' && chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</template>
              </span>
              <div class="message-content">
                <div class="message-header">
                  <span class="sender-name">
                    {{ msg.role === 'user' ? 'You' : (chatTarget === 'report_agent' ? 'Report Agent' : (selectedAgent?.username || 'Agent')) }}
                  </span>
                  <span v-if="isAgentStatement(msg)" class="hb-origin hb-origin--simulated">{{ simulatedLabel }}</span>
                  <span v-else-if="msg.isError" class="hb-status hb-status--failed hb-small">{{ $t('common.error') }}</span>
                  <span class="message-time hb-small hb-soft hb-tabular">{{ formatTime(msg.timestamp) }}</span>
                </div>
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </article>

            <div
              v-if="isSending"
              class="chat-message assistant"
              :class="chatTarget === 'agent' ? 'hb-row--simulated' : 'hb-row--source'"
            >
              <span class="initial" :class="{ 'initial--simulated': chatTarget === 'agent' }" aria-hidden="true">
                {{ chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}
              </span>
              <div class="message-content">
                <div class="typing-indicator" role="status" :aria-label="$t('common.loading')">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>

          <div class="chat-input-area">
            <textarea
              v-model="chatInput"
              class="chat-input hb-textarea"
              :placeholder="$t('step5.chatInputPlaceholder')"
              :aria-label="$t('step5.chatInputPlaceholder')"
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="isSending || (!selectedAgent && chatTarget === 'agent')"
              rows="1"
              ref="chatInputRef"
            ></textarea>
            <button
              type="button"
              class="icon-btn hb-btn hb-btn--action"
              :aria-label="sendLabel"
              @click="sendMessage"
              :disabled="!chatInput.trim() || isSending || (!selectedAgent && chatTarget === 'agent')"
            >
              <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>

        <!-- Survey -->
        <div v-if="activeTab === 'survey'" class="survey-container">
          <p class="hb-simulated-note sim-note">{{ $t('home.notForecast') }}</p>

          <div class="survey-setup">
            <div class="setup-section">
              <div class="hb-section-head">
                <h3 id="survey-targets" class="hb-subheading">{{ $t('step5.selectSurveyTarget') }}</h3>
                <span class="hb-small hb-soft hb-tabular">{{ $t('step5.selectedCount', { selected: selectedAgents.size, total: profiles.length }) }}</span>
              </div>
              <div class="agents-grid" role="group" aria-labelledby="survey-targets">
                <label
                  v-for="(agent, idx) in profiles"
                  :key="idx"
                  class="agent-checkbox"
                  :class="{ checked: selectedAgents.has(idx) }"
                >
                  <input
                    type="checkbox"
                    class="hb-check"
                    :checked="selectedAgents.has(idx)"
                    @change="toggleAgentSelection(idx)"
                  >
                  <span class="person">
                    <span class="person-name">{{ agent.username }}</span>
                    <span class="person-role hb-soft">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                  </span>
                </label>
              </div>
              <div class="selection-actions">
                <button type="button" class="text-action hb-link" @click="selectAllAgents">{{ $t('step5.selectAll') }}</button>
                <button type="button" class="text-action hb-link" @click="clearAgentSelection">{{ $t('step5.clearSelection') }}</button>
              </div>
            </div>

            <div class="setup-section">
              <label class="hb-subheading" for="survey-question">{{ $t('step5.surveyQuestions') }}</label>
              <textarea
                id="survey-question"
                v-model="surveyQuestion"
                class="survey-input hb-textarea"
                :placeholder="$t('step5.surveyInputPlaceholder')"
                rows="3"
              ></textarea>
            </div>

            <button
              type="button"
              class="survey-submit-btn hb-btn hb-btn--action"
              :disabled="selectedAgents.size === 0 || !surveyQuestion.trim() || isSurveying"
              :aria-busy="isSurveying"
              @click="submitSurvey"
            >
              <span v-if="isSurveying" class="spinner" aria-hidden="true"></span>
              <span>{{ $t('step5.submitSurvey') }}</span>
            </button>
          </div>

          <section v-if="surveyResults.length > 0" class="survey-results">
            <div class="hb-section-head">
              <h3 class="hb-heading">{{ $t('step5.surveyResults') }}</h3>
              <span class="hb-small hb-soft hb-tabular">{{ $t('step5.surveyResultsCount', { count: surveyResults.length }) }}</span>
            </div>
            <ul class="results-list hb-list">
              <li
                v-for="(result, idx) in surveyResults"
                :key="idx"
                class="result-card"
                :class="result.answer === $t('step5.noResponse') ? 'hb-row--source' : 'hb-row--simulated'"
              >
                <div class="result-header">
                  <span class="initial initial--simulated" aria-hidden="true">{{ (result.agent_name || 'A')[0] }}</span>
                  <span class="person">
                    <span class="person-name">{{ result.agent_name }}</span>
                    <span class="person-role hb-soft">{{ result.profession || $t('step2.unknownProfession') }}</span>
                  </span>
                  <span v-if="result.answer !== $t('step5.noResponse')" class="hb-origin hb-origin--simulated">{{ simulatedLabel }}</span>
                </div>
                <p class="result-question hb-soft">{{ result.question }}</p>
                <div
                  class="result-answer"
                  :class="{ 'is-empty': result.answer === $t('step5.noResponse') }"
                  v-html="renderMarkdown(result.answer)"
                ></div>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { chatWithReport, getReport, getAgentLog } from '../api/report'
import { interviewAgents, getSimulationProfilesRealtime } from '../api/simulation'

const { t, locale } = useI18n()

const props = defineProps({
  reportId: String,
  simulationId: String
})

const emit = defineEmits(['add-log', 'update-status'])

// State
const activeTab = ref('chat')
const chatTarget = ref('report_agent')
const showAgentDropdown = ref(false)
const selectedAgent = ref(null)
const selectedAgentIndex = ref(null)
const showFullProfile = ref(true)
const showToolsDetail = ref(true)

// Chat State
const chatInput = ref('')
const chatHistory = ref([])
const chatHistoryCache = ref({}) // 缓存所有对话记录: { 'report_agent': [], 'agent_0': [], 'agent_1': [], ... }
const isSending = ref(false)
const chatMessages = ref(null)
const chatInputRef = ref(null)

// Survey State
const selectedAgents = ref(new Set())
const surveyQuestion = ref('')
const surveyResults = ref([])
const isSurveying = ref(false)

// Report Data
const reportOutline = ref(null)
const generatedSections = ref({})
const collapsedSections = ref(new Set())
const currentSectionIndex = ref(null)
const profiles = ref([])

// Helper Methods
const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

// Refs
const leftPanel = ref(null)
const rightPanel = ref(null)

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// shortcut: en/zh labels live here because locale files are out of scope, move them to locales/*.json when next edited
const simulatedLabel = computed(() => (locale.value === 'zh' ? '模拟' : 'Simulated'))
const sendLabel = computed(() => (locale.value === 'zh' ? '发送' : 'Send'))

const isAgentStatement = (msg) => msg.role === 'assistant' && chatTarget.value === 'agent' && !msg.isError

const focusAgentToggle = () => document.querySelector('.agent-dropdown button')?.focus()

const toggleSectionCollapse = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const selectChatTarget = (target) => {
  chatTarget.value = target
  if (target === 'report_agent') {
    showAgentDropdown.value = false
  }
}

// 保存当前对话记录到缓存
const saveChatHistory = () => {
  if (chatHistory.value.length === 0) return
  
  if (chatTarget.value === 'report_agent') {
    chatHistoryCache.value['report_agent'] = [...chatHistory.value]
  } else if (selectedAgentIndex.value !== null) {
    chatHistoryCache.value[`agent_${selectedAgentIndex.value}`] = [...chatHistory.value]
  }
}

const selectReportAgentChat = () => {
  // 保存当前对话记录
  saveChatHistory()
  
  activeTab.value = 'chat'
  chatTarget.value = 'report_agent'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
  
  // 恢复 Report Agent 的对话记录
  chatHistory.value = chatHistoryCache.value['report_agent'] || []
}

const selectSurveyTab = () => {
  activeTab.value = 'survey'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
}

const toggleAgentDropdown = () => {
  showAgentDropdown.value = !showAgentDropdown.value
  if (showAgentDropdown.value) {
    activeTab.value = 'chat'
    chatTarget.value = 'agent'
  }
}

const selectAgent = (agent, idx) => {
  // 保存当前对话记录
  saveChatHistory()
  
  selectedAgent.value = agent
  selectedAgentIndex.value = idx
  chatTarget.value = 'agent'
  showAgentDropdown.value = false
  
  // 恢复该 Agent 的对话记录
  chatHistory.value = chatHistoryCache.value[`agent_${idx}`] || []
  addLog(t('log.selectChatTarget', { name: agent.username }))
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit'
    })
  } catch {
    return ''
  }
}

const escapeLt = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;') // LLM/user text must not inject HTML

const renderMarkdown = (content) => {
  if (!content) return ''
  content = escapeLt(content)
  
  let processedContent = content.replace(/^##\s+.+\n+/, '')
  let html = processedContent.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
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
  
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  html = '<p class="md-p">' + html + '</p>'
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

  return html
}

// Chat Methods
const sendMessage = async () => {
  if (!chatInput.value.trim() || isSending.value) return
  
  const message = chatInput.value.trim()
  chatInput.value = ''
  
  // Add user message
  chatHistory.value.push({
    role: 'user',
    content: message,
    timestamp: new Date().toISOString()
  })
  
  scrollToBottom()
  isSending.value = true
  
  try {
    if (chatTarget.value === 'report_agent') {
      await sendToReportAgent(message)
    } else {
      await sendToAgent(message)
    }
  } catch (err) {
    addLog(t('log.sendFailed', { error: err.message }))
    chatHistory.value.push({
      role: 'assistant',
      content: t('step5.errorOccurred', { error: err.message }),
      timestamp: new Date().toISOString(),
      isError: true
    })
  } finally {
    isSending.value = false
    scrollToBottom()
    // 自动保存对话记录到缓存
    saveChatHistory()
  }
}

const sendToReportAgent = async (message) => {
  addLog(t('log.sendToReportAgent', { message: message.substring(0, 50) }))
  
  // Build chat history for API
  const historyForApi = chatHistory.value
    .slice(0, -1)
    .slice(-10) // Keep last 10 messages
    .map(msg => ({
      role: msg.role,
      content: msg.content
    }))
  
  const res = await chatWithReport({
    simulation_id: props.simulationId,
    message: message,
    chat_history: historyForApi
  })
  
  if (res.success && res.data) {
    chatHistory.value.push({
      role: 'assistant',
      content: res.data.response || res.data.answer || t('step5.noResponse'),
      timestamp: new Date().toISOString()
    })
    addLog(t('log.reportAgentReplied'))
  } else {
    throw new Error(res.error || t('step5.requestFailed'))
  }
}

const sendToAgent = async (message) => {
  if (!selectedAgent.value || selectedAgentIndex.value === null) {
    throw new Error(t('step5.selectAgentFirst'))
  }
  
  addLog(t('log.sendToAgent', { name: selectedAgent.value.username, message: message.substring(0, 50) }))
  
  // Build prompt with chat history
  let prompt = message
  if (chatHistory.value.length > 1) {
    const historyContext = chatHistory.value
      .slice(0, -1)
      .slice(-6)
      .map(msg => `${msg.role === 'user' ? '提问者' : '你'}：${msg.content}`)
      .join('\n')
    prompt = `以下是我们之前的对话：\n${historyContext}\n\n现在我的新问题是：${message}`
  }
  
  const res = await interviewAgents({
    simulation_id: props.simulationId,
    interviews: [{
      agent_id: selectedAgentIndex.value,
      prompt: prompt
    }]
  })
  
  if (res.success && res.data) {
    // 正确的数据路径: res.data.result.results 是一个对象字典
    // 格式: {"twitter_0": {...}, "reddit_0": {...}} 或单平台 {"reddit_0": {...}}
    const resultData = res.data.result || res.data
    const resultsDict = resultData.results || resultData
    
    // 将对象字典转换为数组，优先获取 reddit 平台的回复
    let responseContent = null
    const agentId = selectedAgentIndex.value
    
    if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
      // 优先使用 reddit 平台回复，其次 twitter
      const redditKey = `reddit_${agentId}`
      const twitterKey = `twitter_${agentId}`
      const agentResult = resultsDict[redditKey] || resultsDict[twitterKey] || Object.values(resultsDict)[0]
      if (agentResult) {
        responseContent = agentResult.response || agentResult.answer
      }
    } else if (Array.isArray(resultsDict) && resultsDict.length > 0) {
      // 兼容数组格式
      responseContent = resultsDict[0].response || resultsDict[0].answer
    }
    
    if (responseContent) {
      chatHistory.value.push({
        role: 'assistant',
        content: responseContent,
        timestamp: new Date().toISOString()
      })
      addLog(t('log.agentReplied', { name: selectedAgent.value.username }))
    } else {
      throw new Error(t('step5.noResponse'))
    }
  } else {
    throw new Error(res.error || t('step5.requestFailed'))
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessages.value) {
      chatMessages.value.scrollTop = chatMessages.value.scrollHeight
    }
  })
}

// Survey Methods
const toggleAgentSelection = (idx) => {
  const newSet = new Set(selectedAgents.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  selectedAgents.value = newSet
}

const selectAllAgents = () => {
  const newSet = new Set()
  profiles.value.forEach((_, idx) => newSet.add(idx))
  selectedAgents.value = newSet
}

const clearAgentSelection = () => {
  selectedAgents.value = new Set()
}

const submitSurvey = async () => {
  if (selectedAgents.value.size === 0 || !surveyQuestion.value.trim()) return
  
  isSurveying.value = true
  addLog(t('log.sendSurvey', { count: selectedAgents.value.size }))
  
  try {
    const interviews = Array.from(selectedAgents.value).map(idx => ({
      agent_id: idx,
      prompt: surveyQuestion.value.trim()
    }))
    
    const res = await interviewAgents({
      simulation_id: props.simulationId,
      interviews: interviews
    })
    
    if (res.success && res.data) {
      // 正确的数据路径: res.data.result.results 是一个对象字典
      // 格式: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
      const resultData = res.data.result || res.data
      const resultsDict = resultData.results || resultData
      
      // 将对象字典转换为数组格式
      const surveyResultsList = []
      
      for (const interview of interviews) {
        const agentIdx = interview.agent_id
        const agent = profiles.value[agentIdx]
        
        // 优先使用 reddit 平台回复，其次 twitter
        let responseContent = t('step5.noResponse')

        if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
          const redditKey = `reddit_${agentIdx}`
          const twitterKey = `twitter_${agentIdx}`
          const agentResult = resultsDict[redditKey] || resultsDict[twitterKey]
          if (agentResult) {
            responseContent = agentResult.response || agentResult.answer || t('step5.noResponse')
          }
        } else if (Array.isArray(resultsDict)) {
          // 兼容数组格式
          const matchedResult = resultsDict.find(r => r.agent_id === agentIdx)
          if (matchedResult) {
            responseContent = matchedResult.response || matchedResult.answer || t('step5.noResponse')
          }
        }
        
        surveyResultsList.push({
          agent_id: agentIdx,
          agent_name: agent?.username || `Agent ${agentIdx}`,
          profession: agent?.profession,
          question: surveyQuestion.value.trim(),
          answer: responseContent
        })
      }
      
      surveyResults.value = surveyResultsList
      addLog(t('log.receivedReplies', { count: surveyResults.value.length }))
    } else {
      throw new Error(res.error || t('step5.requestFailed'))
    }
  } catch (err) {
    addLog(t('log.surveySendFailed', { error: err.message }))
  } finally {
    isSurveying.value = false
  }
}

// Load Report Data
const loadReportData = async () => {
  if (!props.reportId) return
  
  try {
    addLog(t('log.loadReportData', { id: props.reportId }))
    
    // Get report info
    const reportRes = await getReport(props.reportId)
    if (reportRes.success && reportRes.data) {
      // Load agent logs to get report outline and sections
      await loadAgentLogs()
    }
  } catch (err) {
    addLog(t('log.loadReportFailed', { error: err.message }))
  }
}

const loadAgentLogs = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, 0)
    if (res.success && res.data) {
      const logs = res.data.logs || []
      
      logs.forEach(log => {
        if (log.action === 'planning_complete' && log.details?.outline) {
          reportOutline.value = log.details.outline
        }
        
        if (log.action === 'section_complete' && log.section_index < 100 && log.details?.content) {
          generatedSections.value[log.section_index] = log.details.content
        }
      })
      
      addLog(t('log.reportDataLoaded'))
    }
  } catch (err) {
    addLog(t('log.loadReportLogFailed', { error: err.message }))
  }
}

const loadProfiles = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId)
    if (res.success && res.data) {
      profiles.value = res.data.profiles || []
      addLog(t('log.loadedProfiles', { count: profiles.value.length }))
    }
  } catch (err) {
    addLog(t('log.loadProfilesFailed', { error: err.message }))
  }
}

// Click outside to close dropdown
const handleClickOutside = (e) => {
  const dropdown = document.querySelector('.agent-dropdown')
  if (dropdown && !dropdown.contains(e.target)) {
    showAgentDropdown.value = false
  }
}

// Lifecycle
onMounted(() => {
  addLog(t('log.step5Init'))
  loadReportData()
  loadProfiles()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

watch(() => props.reportId, (newId) => {
  if (newId) {
    loadReportData()
  }
}, { immediate: true })

watch(() => props.simulationId, (newId) => {
  if (newId) {
    loadProfiles()
  }
}, { immediate: true })
</script>

<style scoped>
.interaction-panel {
  container-type: inline-size;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  color: var(--hb-navy);
  background: var(--hb-paper);
}

.main-split-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(26rem, 38cqw, 36rem);
  grid-template-rows: minmax(0, 1fr);
  height: 100%;
}

/* Report */
.left-panel {
  min-width: 0;
  overflow-y: auto;
  padding: var(--hb-space-5) var(--hb-gutter) var(--hb-space-7);
}

.report-content-wrapper {
  max-width: 46rem;
}

.report-head {
  margin-bottom: var(--hb-space-5);
}

.sub-title {
  margin-top: var(--hb-space-2);
}

.report-id {
  margin-top: var(--hb-space-2);
  overflow-wrap: anywhere;
}

.report-head .sim-note {
  margin-top: var(--hb-space-3);
}

.sim-note {
  font-size: var(--hb-text-sm);
  line-height: 1.3;
  text-wrap: pretty;
}

.sections-list {
  border-bottom: 1px solid var(--hb-rule);
}

.report-section-item {
  border-top: 1px solid var(--hb-rule);
}

.report-section-item:first-child {
  border-top-color: var(--hb-navy);
}

.section-toggle {
  display: flex;
  align-items: baseline;
  gap: var(--hb-space-3);
  width: calc(100% + var(--hb-space-4));
  margin-inline: calc(var(--hb-space-2) * -1);
  padding: var(--hb-space-3) var(--hb-space-2);
  color: inherit;
  background: none;
  border: 0;
  border-radius: var(--hb-radius);
  text-align: left;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.section-toggle:enabled {
  cursor: pointer;
}

.section-toggle:enabled:hover {
  background: var(--hb-water-soft);
}

.section-number {
  flex: none;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-lg);
}

.section-title {
  min-width: 0;
  font: 700 var(--hb-text-2xl) / 1.15 var(--hb-font-serif);
  overflow-wrap: anywhere;
  text-wrap: pretty;
}

.is-pending .section-title {
  color: var(--hb-navy-soft);
  font-weight: 500;
}

.collapse-icon {
  flex: none;
  align-self: center;
  margin-left: auto;
  transition: transform var(--hb-motion-fast) ease-out;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.section-body:not(:empty) {
  padding-bottom: var(--hb-space-4);
}

.generated-content {
  max-width: 68ch;
  font: 400 var(--hb-text-lg) / 1.45 var(--hb-font-serif);
  overflow-wrap: anywhere;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
  font-size: var(--hb-text-sm);
}

.spinner {
  flex: none;
  width: 14px;
  height: 14px;
  border: 2px solid var(--hb-rule);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: harbor-spin 900ms linear infinite;
}

@keyframes harbor-spin {
  to {
    transform: rotate(360deg);
  }
}

.waiting-placeholder {
  display: flex;
  justify-content: center;
  min-height: 100%;
  font-weight: 500;
}

/* Workspace */
.right-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border-left: 1px solid var(--hb-navy);
}

.action-bar {
  position: relative;
  z-index: 2;
  flex: none;
  display: grid;
  gap: var(--hb-space-2);
  padding: var(--hb-space-3) var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
}

.mode-tabs {
  position: relative;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  border-radius: var(--hb-radius);
}

.agent-dropdown {
  display: grid;
  min-width: 0;
}

.mode-tab {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--hb-space-1);
  min-width: 0;
  min-height: var(--hb-control);
  padding: 5px var(--hb-space-2);
  color: var(--hb-navy);
  background: transparent;
  border: 0;
  font: 500 var(--hb-text-sm) / 1.1 var(--hb-font-sans);
  text-align: center;
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.mode-tabs > * + * {
  border-left: 1px solid var(--hb-navy);
}

.mode-tab:hover {
  background: var(--hb-water-soft);
}

.mode-tab.active {
  color: var(--hb-paper);
  background: var(--hb-navy);
  font-weight: 700;
}

.mode-tab.active:hover {
  background: var(--hb-navy-hover);
}

.tab-label {
  display: -webkit-box;
  min-width: 0;
  overflow: hidden;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.chevron {
  flex: none;
  transition: transform var(--hb-motion-fast) ease-out;
}

.chevron.is-open {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + var(--hb-space-1));
  right: -1px;
  left: -1px;
  z-index: 10;
  display: flex;
  flex-direction: column;
  max-height: min(22rem, 50vh);
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  border-radius: var(--hb-radius);
}

.dropdown-header {
  flex: none;
  padding: var(--hb-space-2) var(--hb-space-3);
}

.dropdown-list {
  min-height: 0;
  overflow-y: auto;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
  width: 100%;
  min-height: var(--hb-control);
  padding: 6px var(--hb-space-3);
  color: var(--hb-navy);
  background: transparent;
  border: 0;
  border-top: 1px solid var(--hb-rule);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.dropdown-item:hover {
  background: var(--hb-water-soft);
}

.dropdown-item[aria-current] {
  background: var(--hb-water);
}

.dropdown-item:focus-visible {
  outline-offset: -2px;
}

.initial {
  flex: none;
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  color: var(--hb-navy);
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  border-radius: var(--hb-radius);
  font: 700 var(--hb-text-sm) / 1 var(--hb-font-sc);
}

.initial--user {
  color: var(--hb-paper);
  background: var(--hb-navy);
}

.initial--simulated {
  color: var(--hb-magenta);
  border: 1px dashed var(--hb-magenta);
}

.person {
  flex: 1;
  display: grid;
  gap: 1px;
  min-width: 0;
}

.person-name {
  font-size: var(--hb-text-sm);
  font-weight: 700;
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.person-role {
  font-size: var(--hb-text-xs);
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.icon-btn {
  flex: none;
  width: var(--hb-control);
  padding: 0;
}

/* Chat and interviews */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.context-card {
  flex: none;
  padding: var(--hb-space-3) var(--hb-space-4);
  border-bottom: 1px solid var(--hb-rule);
}

.context-head {
  display: flex;
  align-items: flex-start;
  gap: var(--hb-space-2);
}

.context-info {
  flex: 1;
  min-width: 0;
}

.context-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 0 var(--hb-space-2);
  margin-top: 2px;
  font-size: var(--hb-text-xs);
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.profile-name {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 var(--hb-space-2);
  overflow-wrap: anywhere;
}

.tools-list {
  max-height: 11rem;
  margin-top: var(--hb-space-2);
  overflow-y: auto;
}

.tools-list li {
  display: grid;
  gap: 1px;
  padding: 6px 0;
  border-top: 1px solid var(--hb-rule);
}

.tool-name {
  font-size: var(--hb-text-sm);
  font-weight: 700;
  line-height: 1.2;
}

.tool-desc {
  font-size: var(--hb-text-xs);
  line-height: 1.25;
}

.profile-bio {
  max-height: 8rem;
  margin-top: var(--hb-space-2);
  padding-top: 6px;
  overflow-y: auto;
  border-top: 1px solid var(--hb-rule);
}

.profile-bio p {
  margin-top: 2px;
  font-size: var(--hb-text-sm);
  overflow-wrap: anywhere;
}

.chat-sim-note {
  flex: none;
  margin: var(--hb-space-2) var(--hb-space-4) 0;
}

.chat-messages {
  flex: 1;
  min-height: 8rem;
  padding: var(--hb-space-2) var(--hb-space-4) var(--hb-space-3);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.chat-messages:focus-visible {
  outline-offset: -2px;
}

.chat-empty {
  display: grid;
  place-items: center;
  height: 100%;
}

.empty-text {
  max-width: 32ch;
  font: 400 var(--hb-text-lg) / 1.35 var(--hb-font-serif);
  text-align: center;
  text-wrap: balance;
}

.chat-message {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: var(--hb-space-3);
  padding: var(--hb-space-3) 0;
}

.message-content {
  min-width: 0;
}

.message-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px var(--hb-space-2);
  margin-bottom: 2px;
}

.sender-name {
  min-width: 0;
  font-size: var(--hb-text-sm);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.message-time {
  margin-left: auto;
}

.message-text,
.result-answer {
  font: 400 var(--hb-text-lg) / 1.4 var(--hb-font-serif);
  overflow-wrap: anywhere;
}

/* Ordered items keep counting across the separate lists renderMarkdown emits */
.message-text {
  counter-reset: list-counter;
}

.message-text :deep(.md-ol) {
  padding-left: 0;
  list-style: none;
}

.message-text :deep(.md-oli) {
  display: flex;
  gap: var(--hb-space-2);
  counter-increment: list-counter;
}

.message-text :deep(.md-oli)::before {
  content: counter(list-counter) '.';
  flex: none;
  min-width: 1.25em;
  font-weight: 700;
}

.chat-message.user .message-text,
.chat-message.is-error .message-text,
.result-answer.is-empty {
  font: 400 var(--hb-text-md) / 1.35 var(--hb-font-sans);
}

.result-answer.is-empty {
  color: var(--hb-navy-soft);
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: var(--hb-space-1);
  height: 28px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: var(--hb-navy);
  animation: harbor-sounding 1200ms ease-in-out infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 160ms;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 320ms;
}

@keyframes harbor-sounding {
  0%,
  100% {
    opacity: 0.25;
  }

  40% {
    opacity: 1;
  }
}

.chat-input-area {
  flex: none;
  display: flex;
  align-items: flex-end;
  gap: var(--hb-space-2);
  padding: var(--hb-space-3) var(--hb-space-4);
  border-top: 1px solid var(--hb-navy);
}

.chat-input {
  flex: 1;
  min-width: 0;
  min-height: var(--hb-control);
  max-height: 8rem;
  padding: 6px 9px;
  font: 400 var(--hb-text-md) / 1.35 var(--hb-font-sans);
  resize: none;
  field-sizing: content;
}

/* Survey */
.survey-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--hb-space-4);
  min-height: 0;
  padding: var(--hb-space-3) var(--hb-space-4) var(--hb-space-5);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.survey-container > * {
  flex: none;
}

.survey-setup {
  display: grid;
  gap: var(--hb-space-4);
}

.setup-section {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  column-gap: var(--hb-space-3);
  max-height: 15rem;
  overflow-y: auto;
  border-block: 1px solid var(--hb-navy);
}

.agent-checkbox {
  display: flex;
  align-items: flex-start;
  gap: var(--hb-space-2);
  min-height: var(--hb-control);
  padding: 6px;
  border-bottom: 1px solid var(--hb-rule);
  cursor: pointer;
  transition: background-color var(--hb-motion-fast) ease-out;
}

.agent-checkbox:hover {
  background: var(--hb-water-soft);
}

.agent-checkbox.checked {
  background: var(--hb-water);
}

.agent-checkbox .hb-check {
  margin-top: 1px;
}

.selection-actions {
  display: flex;
  gap: var(--hb-space-4);
}

.text-action {
  min-height: var(--hb-control);
  padding: 0;
  background: none;
  border: 0;
  font-size: var(--hb-text-sm);
  cursor: pointer;
}

.survey-input {
  min-height: 5.5rem;
  padding: var(--hb-space-2) 10px;
  font: 400 var(--hb-text-lg) / 1.35 var(--hb-font-serif);
}

.survey-submit-btn {
  justify-self: start;
}

.survey-results {
  padding-top: var(--hb-space-3);
  border-top: 1px solid var(--hb-navy);
}

.results-list {
  margin-top: var(--hb-space-2);
}

.result-card {
  padding: var(--hb-space-3) 0;
}

.result-header {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
}

.result-question {
  margin: 6px 0 var(--hb-space-1);
  font-size: var(--hb-text-sm);
  overflow-wrap: anywhere;
}

/* Rendered markdown */
:deep(.md-p) {
  margin-bottom: 0.65em;
}

:deep(.md-p:last-child) {
  margin-bottom: 0;
}

:deep(.md-h2),
:deep(.md-h3),
:deep(.md-h4),
:deep(.md-h5) {
  margin: 1em 0 0.35em;
  font-family: var(--hb-font-serif);
  font-weight: 700;
  line-height: 1.2;
  text-wrap: pretty;
}

:deep(.md-h2) {
  font-size: var(--hb-text-xl);
}

:deep(.md-h3) {
  font-size: var(--hb-text-lg);
}

:deep(.md-h4),
:deep(.md-h5) {
  font-size: var(--hb-text-md);
}

:deep(.md-ul),
:deep(.md-ol) {
  margin: 0.5em 0 0.65em;
  padding-left: 1.4em;
}

:deep(.md-li),
:deep(.md-oli) {
  margin: 0.2em 0;
}

:deep(.md-quote) {
  margin: 0.65em 0;
  padding: 0.4em 0.75em;
  background: var(--hb-water-soft);
  border-left: 1px solid var(--hb-navy);
  font-style: italic;
}

:deep(strong) {
  font-weight: 700;
}

:deep(.code-block) {
  margin: 0.65em 0;
  padding: var(--hb-space-3);
  overflow-x: auto;
  color: var(--hb-paper);
  background: var(--hb-navy);
  border-radius: var(--hb-radius);
}

:deep(.code-block code),
:deep(.inline-code) {
  font-family: ui-monospace, monospace;
  font-size: 0.8125rem;
}

:deep(.inline-code) {
  padding: 1px var(--hb-space-1);
  background: var(--hb-water-soft);
  border-radius: var(--hb-radius);
}

:deep(.md-hr) {
  margin: 1em 0;
  border: 0;
  border-top: 1px solid var(--hb-rule);
}

@container (max-width: 56rem) {
  .main-split-layout {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(11rem, 2fr) minmax(26rem, 3fr);
    overflow-y: auto;
  }

  .left-panel {
    padding: var(--hb-space-4);
  }

  .right-panel {
    border-top: 1px solid var(--hb-navy);
    border-left: 0;
  }
}

@container (max-width: 24rem) {
  .mode-tabs {
    grid-auto-flow: row;
  }

  .mode-tabs > * + * {
    border-top: 1px solid var(--hb-navy);
    border-left: 0;
  }
}
</style>
