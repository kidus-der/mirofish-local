<template>
  <section class="simulation-panel" aria-labelledby="sim-run-title">
    <!-- Run progress and the one action on this screen -->
    <header class="run-band hb-surface-water">
      <h2 id="sim-run-title" class="run-title">{{ projectData?.name || $tm('main.stepNames')[2] }}</h2>
      <span class="hb-status" :class="`hb-status--${STATE_VIEW[runState].mark}`" role="status">
        {{ $t(STATE_VIEW[runState].label) }}
      </span>
      <div class="run-progress">
        <span class="hb-tabular">{{ roundsLabel }}</span>
        <progress v-if="totalRounds" :max="totalRounds" :value="currentRound" :aria-label="roundsLabel"></progress>
      </div>
      <button
        type="button"
        class="hb-btn hb-btn--action"
        :disabled="phase !== 2 || isGeneratingReport"
        :aria-busy="isGeneratingReport"
        @click="handleNextStep"
      >
        {{ isGeneratingReport ? $t('step3.generatingReportBtn') : $t('step3.startGenerateReportBtn') }}
      </button>
      <p v-if="runError" class="run-alert" role="alert">
        <span class="hb-status hb-status--failed">{{ $t('common.error') }}</span>
        {{ runError }}
      </p>
    </header>

    <div class="work">
      <div class="rail hb-surface-land-soft">
        <!-- Platform status -->
        <ul class="platforms hb-list">
          <li v-for="platform in platformCards" :key="platform.id" class="platform">
            <div class="hb-section-head">
              <h3 class="hb-subheading">{{ platform.name }}</h3>
              <span class="hb-status hb-small" :class="`hb-status--${STATE_VIEW[platform.state].mark}`">
                {{ $t(STATE_VIEW[platform.state].label) }}
              </span>
            </div>
            <dl class="platform-stats">
              <div>
                <dt>Round</dt>
                <dd class="hb-tabular">{{ platform.round }}<span class="hb-soft">/{{ totalRounds || '-' }}</span></dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd class="hb-tabular">{{ platform.elapsed }}</dd>
              </div>
              <div>
                <dt>Acts</dt>
                <dd class="hb-tabular">{{ platform.count }}</dd>
              </div>
            </dl>
            <details class="platform-actions">
              <summary>Available Actions</summary>
              <p>{{ platform.actions.join(' · ') }}</p>
            </details>
          </li>
        </ul>

        <!-- Agent activity, rolled up from the action feed -->
        <div class="ledger" tabindex="0" role="region" aria-labelledby="sim-agents-title">
          <div class="hb-section-head">
            <h3 id="sim-agents-title" class="hb-subheading">Agents</h3>
            <span class="hb-soft hb-small">{{ $t('history.agentsCount', { count: agentActivity.length }) }}</span>
          </div>
          <ul v-if="agentActivity.length" class="agents hb-list">
            <li
              v-for="agent in agentActivity"
              :key="agent.name"
              class="agent"
              :class="{ 'is-latest hb-surface-land': agent.latest }"
            >
              <span class="agent-name">{{ agent.name }}</span>
              <span class="agent-count hb-tabular">{{ agent.count }}</span>
              <span class="agent-last hb-soft hb-tabular">{{ agent.lastAction }} · R{{ agent.lastRound }}</span>
              <span v-if="agent.latest" class="hb-vh">Latest round</span>
            </li>
          </ul>
          <p v-else class="rail-empty hb-soft hb-small">{{ $t('common.noData') }}</p>

          <h3 id="sim-activity-title" class="hb-subheading activity-title">Activity</h3>
          <table v-if="activityRows.length" class="activity hb-tabular" aria-labelledby="sim-activity-title">
            <thead>
              <tr>
                <th scope="col">Action</th>
                <th v-for="platform in platformCards" :key="platform.id" scope="col">{{ platform.name }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in activityRows" :key="row.label">
                <th scope="row">{{ row.label }}</th>
                <td v-for="platform in platformCards" :key="platform.id">{{ row[platform.id] || '–' }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="rail-empty hb-soft hb-small">{{ $t('common.noData') }}</p>
        </div>
      </div>

      <!-- Agent actions and posts, newest first -->
      <section class="feed" aria-labelledby="sim-feed-title">
        <header class="feed-head">
          <h3 id="sim-feed-title" class="hb-heading">Agent actions</h3>
          <span v-if="allActions.length" class="feed-counts hb-small hb-tabular">
            Total events <b>{{ allActions.length }}</b>
            <span class="hb-soft">Info Plaza <b>{{ twitterActionsCount }}</b></span>
            <span class="hb-soft">Topic Community <b>{{ redditActionsCount }}</b></span>
          </span>
          <span v-if="latestActionCount" class="hb-unseen hb-tabular">{{ latestActionCount }} in latest round</span>
          <p class="feed-note hb-origin--simulated hb-small">Written by simulated agents, not real people</p>
        </header>

        <div ref="scrollContainer" class="feed-scroll" tabindex="0" role="region" aria-labelledby="sim-feed-title">
          <TransitionGroup v-if="allActions.length" name="timeline-item" tag="ol" class="hb-list">
            <li
              v-for="action in feedActions"
              :key="action._uniqueId || action.id || `${action.timestamp}-${action.agent_id}`"
              class="feed-item hb-row--simulated"
              :class="[action.platform, getActionTypeClass(action.action_type), { 'is-latest hb-surface-land-soft': isLatestAction(action) }]"
            >
              <p class="item-meta">
                <span class="agent-name">{{ action.agent_name }}</span>
                <span>{{ platformName(action.platform) }}</span>
                <span class="hb-tag">{{ getActionTypeLabel(action.action_type) }}</span>
                <span class="hb-origin hb-origin--simulated">Simulated</span>
                <span v-if="isLatestAction(action)" class="hb-unseen">Latest round</span>
                <span class="item-time hb-tabular">R{{ action.round_num }} · {{ formatActionTime(action.timestamp) }}</span>
              </p>

              <div class="item-body">
                <!-- CREATE_POST: 发布帖子 -->
                <p v-if="action.action_type === 'CREATE_POST' && action.action_args?.content" class="content-text">
                  {{ action.action_args.content }}
                </p>

                <!-- QUOTE_POST: 引用帖子 -->
                <template v-if="action.action_type === 'QUOTE_POST'">
                  <p v-if="action.action_args?.quote_content" class="content-text">
                    {{ action.action_args.quote_content }}
                  </p>
                  <blockquote v-if="action.action_args?.original_content" class="quoted">
                    <p class="item-note">@{{ action.action_args.original_author_name || 'User' }}</p>
                    <p>{{ truncateContent(action.action_args.original_content, 150) }}</p>
                  </blockquote>
                </template>

                <!-- REPOST: 转发帖子 -->
                <template v-if="action.action_type === 'REPOST'">
                  <p class="item-note">Reposted from @{{ action.action_args?.original_author_name || 'User' }}</p>
                  <blockquote v-if="action.action_args?.original_content" class="quoted">
                    {{ truncateContent(action.action_args.original_content, 200) }}
                  </blockquote>
                </template>

                <!-- LIKE_POST: 点赞帖子 -->
                <template v-if="action.action_type === 'LIKE_POST'">
                  <p class="item-note">Liked @{{ action.action_args?.post_author_name || 'User' }}'s post</p>
                  <p v-if="action.action_args?.post_content" class="item-excerpt">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </p>
                </template>

                <!-- CREATE_COMMENT: 发表评论 -->
                <template v-if="action.action_type === 'CREATE_COMMENT'">
                  <p v-if="action.action_args?.content" class="content-text">
                    {{ action.action_args.content }}
                  </p>
                  <p v-if="action.action_args?.post_id" class="item-note">Reply to post #{{ action.action_args.post_id }}</p>
                </template>

                <!-- SEARCH_POSTS: 搜索帖子 -->
                <p v-if="action.action_type === 'SEARCH_POSTS'" class="item-note">
                  Search Query: <b>"{{ action.action_args?.query || '' }}"</b>
                </p>

                <!-- FOLLOW: 关注用户 -->
                <p v-if="action.action_type === 'FOLLOW'" class="item-note">
                  Followed @{{ action.action_args?.target_user || action.action_args?.user_id || 'User' }}
                </p>

                <!-- UPVOTE / DOWNVOTE -->
                <template v-if="action.action_type === 'UPVOTE_POST' || action.action_type === 'DOWNVOTE_POST'">
                  <p class="item-note">{{ action.action_type === 'UPVOTE_POST' ? 'Upvoted' : 'Downvoted' }} Post</p>
                  <p v-if="action.action_args?.post_content" class="item-excerpt">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </p>
                </template>

                <!-- DO_NOTHING: 无操作（静默） -->
                <p v-if="action.action_type === 'DO_NOTHING'" class="item-note">Action Skipped</p>

                <!-- 通用回退：未知类型或有 content 但未被上述处理 -->
                <p
                  v-if="!['CREATE_POST', 'QUOTE_POST', 'REPOST', 'LIKE_POST', 'CREATE_COMMENT', 'SEARCH_POSTS', 'FOLLOW', 'UPVOTE_POST', 'DOWNVOTE_POST', 'DO_NOTHING'].includes(action.action_type) && action.action_args?.content"
                  class="content-text"
                >
                  {{ action.action_args.content }}
                </p>
              </div>
            </li>
          </TransitionGroup>

          <p v-else class="feed-empty hb-soft">
            {{ phase < 2 && !runError ? $t('step3.waitingForActions') : $t('common.noData') }}
          </p>
        </div>
      </section>

      <!-- Run logs -->
      <section class="logs" aria-labelledby="sim-logs-title">
        <header class="hb-section-head logs-head">
          <h3 id="sim-logs-title" class="hb-subheading">Simulation monitor</h3>
          <span class="log-id hb-soft hb-small">{{ simulationId || 'NO_SIMULATION' }}</span>
        </header>
        <div ref="logContent" class="log-content" role="log" tabindex="0" aria-labelledby="sim-logs-title">
          <ol class="hb-list">
            <li
              v-for="(log, idx) in systemLogs"
              :key="idx"
              class="log-line"
              :class="{ 'is-latest hb-surface-land-soft': idx === systemLogs.length - 1 }"
            >
              <span class="log-time hb-soft hb-tabular">{{ log.time }}</span>
              <span class="log-msg">{{ log.msg }}</span>
              <span v-if="idx === systemLogs.length - 1" class="hb-unseen">Latest</span>
            </li>
          </ol>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  startSimulation,
  stopSimulation,
  getRunStatus,
  getRunStatusDetail
} from '../api/simulation'
import { generateReport } from '../api/report'

const { t } = useI18n()

const props = defineProps({
  simulationId: String,
  maxRounds: Number, // 从Step2传入的最大轮数
  minutesPerRound: {
    type: Number,
    default: 30 // 默认每轮30分钟
  },
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

const router = useRouter()

// State
const isGeneratingReport = ref(false)
const phase = ref(0) // 0: 未开始, 1: 运行中, 2: 已完成
const isStarting = ref(false)
const isStopping = ref(false)
const startError = ref(null)
const runStatus = ref({})
const allActions = ref([]) // 所有动作（增量累积）
const actionIds = ref(new Set()) // 用于去重的动作ID集合
const scrollContainer = ref(null)

// Computed
// 按时间顺序显示动作（最新的在最后面，即底部）
const chronologicalActions = computed(() => {
  return allActions.value
})

// 各平台动作计数
const twitterActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'twitter').length
})

const redditActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'reddit').length
})

// 格式化模拟流逝时间（根据轮次和每轮分钟数计算）
const formatElapsedTime = (currentRound) => {
  if (!currentRound || currentRound <= 0) return '0h 0m'
  const totalMinutes = currentRound * props.minutesPerRound
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}h ${minutes}m`
}

// Twitter平台的模拟流逝时间
const twitterElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.twitter_current_round || 0)
})

// Reddit平台的模拟流逝时间
const redditElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.reddit_current_round || 0)
})

// Harbor Chart view model: read-only projections of the run state, no side effects.
const PLATFORMS = [
  {
    id: 'twitter',
    name: 'Info Plaza',
    elapsed: twitterElapsedTime,
    actions: ['POST', 'LIKE', 'REPOST', 'QUOTE', 'FOLLOW', 'IDLE']
  },
  {
    id: 'reddit',
    name: 'Topic Community',
    elapsed: redditElapsedTime,
    actions: ['POST', 'COMMENT', 'LIKE', 'DISLIKE', 'SEARCH', 'TREND', 'FOLLOW', 'MUTE', 'REFRESH', 'IDLE']
  }
]

const STATE_VIEW = {
  idle: { label: 'common.pending', mark: 'idle' },
  running: { label: 'common.running', mark: 'running' },
  completed: { label: 'common.completed', mark: 'completed' },
  stopped: { label: 'history.stopped', mark: 'stopped' },
  failed: { label: 'common.failed', mark: 'failed' },
  // A failed status check says nothing about the run itself, so it is not shown as "Failed".
  error: { label: 'common.error', mark: 'failed' }
}

const platformName = (id) => PLATFORMS.find(platform => platform.id === id)?.name || id

const runError = computed(() => startError.value || runStatus.value.error || null)

const runState = computed(() => {
  if (startError.value) return 'error'
  const status = runStatus.value.runner_status
  if (status === 'failed' || status === 'stopped' || status === 'completed') return status
  if (phase.value === 2) return 'stopped'
  return phase.value === 1 ? 'running' : 'idle'
})

const totalRounds = computed(() => runStatus.value.total_rounds || props.maxRounds || 0)

const currentRound = computed(() => {
  const { current_round, twitter_current_round, reddit_current_round } = runStatus.value
  const round = Math.max(current_round || 0, twitter_current_round || 0, reddit_current_round || 0)
  return totalRounds.value ? Math.min(round, totalRounds.value) : round
})

const roundsLabel = computed(() => t('history.roundsProgress', {
  current: currentRound.value,
  total: totalRounds.value || '-'
}))

const platformCards = computed(() => PLATFORMS.map(({ id, name, elapsed, actions }) => {
  const status = runStatus.value
  let state = status[`${id}_running`] ? 'running' : 'idle'
  if (status[`${id}_completed`]) state = 'completed'
  else if (phase.value === 2) state = runState.value // a stopped or failed run leaves platforms unfinished
  return {
    id,
    name,
    actions,
    state,
    elapsed: elapsed.value,
    round: status[`${id}_current_round`] || 0,
    count: status[`${id}_actions_count`] || 0
  }
}))

// The API returns each poll newest-first, so arrival order alternates; sort for display only.
const feedActions = computed(() => [...chronologicalActions.value].sort(
  (a, b) => (Date.parse(b.timestamp) || 0) - (Date.parse(a.timestamp) || 0)
))

// Taken from the actions, not runStatus: platform rounds only advance at round_end,
// and this also survives a page refresh, when every action arrives in one poll.
const latestRounds = computed(() => {
  const rounds = {}
  allActions.value.forEach(({ platform, round_num }) => {
    rounds[platform] = Math.max(rounds[platform] ?? 0, round_num || 0)
  })
  return rounds
})

const isLatestAction = (action) => action.round_num === latestRounds.value[action.platform]

const latestActionCount = computed(() => allActions.value.filter(isLatestAction).length)

const agentActivity = computed(() => {
  const agents = new Map()
  feedActions.value.forEach(action => {
    const name = action.agent_name || String(action.agent_id)
    if (!agents.has(name)) {
      agents.set(name, {
        name,
        count: 0,
        latest: false,
        lastRound: action.round_num,
        lastAction: getActionTypeLabel(action.action_type)
      })
    }
    const agent = agents.get(name)
    agent.count++
    agent.latest ||= isLatestAction(action)
  })
  return [...agents.values()]
})

const activityRows = computed(() => {
  const rows = new Map()
  allActions.value.forEach(({ action_type, platform }) => {
    const label = getActionTypeLabel(action_type)
    if (!rows.has(label)) rows.set(label, { label, twitter: 0, reddit: 0 })
    if (platform === 'twitter' || platform === 'reddit') rows.get(label)[platform]++
  })
  return [...rows.values()].sort((a, b) => (b.twitter + b.reddit) - (a.twitter + a.reddit))
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// 重置所有状态（用于重新启动模拟）
const resetAllState = () => {
  phase.value = 0
  runStatus.value = {}
  allActions.value = []
  actionIds.value = new Set()
  prevTwitterRound.value = 0
  prevRedditRound.value = 0
  startError.value = null
  isStarting.value = false
  isStopping.value = false
  stopPolling()  // 停止之前可能存在的轮询
}

// 启动模拟
const doStartSimulation = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  // 先重置所有状态，确保不会受到上一次模拟的影响
  resetAllState()
  
  isStarting.value = true
  startError.value = null
  addLog(t('log.startingDualSim'))
  emit('update-status', 'processing')
  
  try {
    const params = {
      simulation_id: props.simulationId,
      platform: 'parallel',
      force: true,  // 强制重新开始
      enable_graph_memory_update: true  // 开启动态图谱更新
    }
    
    if (props.maxRounds) {
      params.max_rounds = props.maxRounds
      addLog(t('log.setMaxRounds', { rounds: props.maxRounds }))
    }
    
    addLog(t('log.graphMemoryUpdateEnabled'))
    
    const res = await startSimulation(params)
    
    if (res.success && res.data) {
      if (res.data.force_restarted) {
        addLog(t('log.oldSimCleared'))
      }
      addLog(t('log.engineStarted'))
      addLog(`  ├─ PID: ${res.data.process_pid || '-'}`)
      
      phase.value = 1
      runStatus.value = res.data
      
      startStatusPolling()
      startDetailPolling()
    } else {
      startError.value = res.error || '启动失败'
      addLog(t('log.startFailed', { error: res.error || t('common.unknownError') }))
      emit('update-status', 'error')
    }
  } catch (err) {
    startError.value = err.message
    addLog(t('log.startException', { error: err.message }))
    emit('update-status', 'error')
  } finally {
    isStarting.value = false
  }
}

// 停止模拟
const handleStopSimulation = async () => {
  if (!props.simulationId) return
  
  isStopping.value = true
  addLog(t('log.stoppingSim'))
  
  try {
    const res = await stopSimulation({ simulation_id: props.simulationId })
    
    if (res.success) {
      addLog(t('log.simStoppedSuccess'))
      phase.value = 2
      stopPolling()
      emit('update-status', 'completed')
    } else {
      addLog(t('log.stopFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.stopException', { error: err.message }))
  } finally {
    isStopping.value = false
  }
}

// 轮询状态
let statusTimer = null
let detailTimer = null

const startStatusPolling = () => {
  statusTimer = setInterval(fetchRunStatus, 2000)
}

const startDetailPolling = () => {
  detailTimer = setInterval(fetchRunStatusDetail, 3000)
}

const stopPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
  if (detailTimer) {
    clearInterval(detailTimer)
    detailTimer = null
  }
}

// 追踪各平台的上一次轮次，用于检测变化并输出日志
const prevTwitterRound = ref(0)
const prevRedditRound = ref(0)

const fetchRunStatus = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatus(props.simulationId)
    
    if (res.success && res.data) {
      const data = res.data
      
      runStatus.value = data
      
      // 分别检测各平台的轮次变化并输出日志
      if (data.twitter_current_round > prevTwitterRound.value) {
        addLog(`[Plaza] R${data.twitter_current_round}/${data.total_rounds} | T:${data.twitter_simulated_hours || 0}h | A:${data.twitter_actions_count}`)
        prevTwitterRound.value = data.twitter_current_round
      }
      
      if (data.reddit_current_round > prevRedditRound.value) {
        addLog(`[Community] R${data.reddit_current_round}/${data.total_rounds} | T:${data.reddit_simulated_hours || 0}h | A:${data.reddit_actions_count}`)
        prevRedditRound.value = data.reddit_current_round
      }
      
      // 检测模拟是否已完成（通过 runner_status 或平台完成状态判断）
      const isCompleted = data.runner_status === 'completed' || data.runner_status === 'stopped'
      const isFailed = data.runner_status === 'failed'
      
      // runner_status is authoritative because the backend only publishes a
      // terminal state after the Zep ingestion barrier has completed.
      if (isFailed) {
        addLog(t('log.simFailed') + (data.error ? `: ${data.error}` : ''))
        phase.value = 2
        stopPolling()
        emit('update-status', 'error')
      } else if (isCompleted) {
        addLog(t('log.simCompleted'))
        phase.value = 2
        stopPolling()
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('获取运行状态失败:', err)
  }
}

// 检查所有启用的平台是否已完成
const checkPlatformsCompleted = (data) => {
  // 如果没有任何平台数据，返回 false
  if (!data) return false
  
  // 检查各平台的完成状态
  const twitterCompleted = data.twitter_completed === true
  const redditCompleted = data.reddit_completed === true
  
  // 如果至少有一个平台完成了，检查是否所有启用的平台都完成了
  // 通过 actions_count 判断平台是否被启用（如果 count > 0 或 running 曾为 true）
  const twitterEnabled = (data.twitter_actions_count > 0) || data.twitter_running || twitterCompleted
  const redditEnabled = (data.reddit_actions_count > 0) || data.reddit_running || redditCompleted
  
  // 如果没有任何平台被启用，返回 false
  if (!twitterEnabled && !redditEnabled) return false
  
  // 检查所有启用的平台是否都已完成
  if (twitterEnabled && !twitterCompleted) return false
  if (redditEnabled && !redditCompleted) return false
  
  return true
}

const fetchRunStatusDetail = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatusDetail(props.simulationId)
    
    if (res.success && res.data) {
      // 使用 all_actions 获取完整的动作列表
      const serverActions = res.data.all_actions || []
      
      // 增量添加新动作（去重）
      let newActionsAdded = 0
      serverActions.forEach(action => {
        // 生成唯一ID
        const actionId = action.id || `${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}`
        
        if (!actionIds.value.has(actionId)) {
          actionIds.value.add(actionId)
          allActions.value.push({
            ...action,
            _uniqueId: actionId
          })
          newActionsAdded++
        }
      })
      
      // 不自动滚动，让用户自由查看时间轴
      // 新动作会在底部追加
    }
  } catch (err) {
    console.warn('获取详细状态失败:', err)
  }
}

// Helpers
const getActionTypeLabel = (type) => {
  const labels = {
    'CREATE_POST': 'POST',
    'REPOST': 'REPOST',
    'LIKE_POST': 'LIKE',
    'CREATE_COMMENT': 'COMMENT',
    'LIKE_COMMENT': 'LIKE',
    'DO_NOTHING': 'IDLE',
    'FOLLOW': 'FOLLOW',
    'SEARCH_POSTS': 'SEARCH',
    'QUOTE_POST': 'QUOTE',
    'UPVOTE_POST': 'UPVOTE',
    'DOWNVOTE_POST': 'DOWNVOTE'
  }
  return labels[type] || type || 'UNKNOWN'
}

const getActionTypeClass = (type) => {
  const classes = {
    'CREATE_POST': 'badge-post',
    'REPOST': 'badge-action',
    'LIKE_POST': 'badge-action',
    'CREATE_COMMENT': 'badge-comment',
    'LIKE_COMMENT': 'badge-action',
    'QUOTE_POST': 'badge-post',
    'FOLLOW': 'badge-meta',
    'SEARCH_POSTS': 'badge-meta',
    'UPVOTE_POST': 'badge-action',
    'DOWNVOTE_POST': 'badge-action',
    'DO_NOTHING': 'badge-idle'
  }
  return classes[type] || 'badge-default'
}

const truncateContent = (content, maxLength = 100) => {
  if (!content) return ''
  if (content.length > maxLength) return content.substring(0, maxLength) + '...'
  return content
}

const formatActionTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

const handleNextStep = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  if (isGeneratingReport.value) {
    addLog(t('log.reportRequestSent'))
    return
  }
  
  isGeneratingReport.value = true
  addLog(t('log.startingReportGen'))
  
  try {
    const res = await generateReport({
      simulation_id: props.simulationId,
      force_regenerate: true
    })
    
    if (res.success && res.data) {
      const reportId = res.data.report_id
      addLog(t('log.reportGenTaskStarted', { reportId }))
      
      // 跳转到报告页面
      router.push({ name: 'Report', params: { reportId } })
    } else {
      addLog(t('log.reportGenFailed', { error: res.error || t('common.unknownError') }))
      isGeneratingReport.value = false
    }
  } catch (err) {
    addLog(t('log.reportGenException', { error: err.message }))
    isGeneratingReport.value = false
  }
}

// Scroll log to bottom
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

// This page force-starts by design, so a refresh must not restart a run already in progress.
const ACTIVE_RUN_STATES = ['starting', 'running', 'paused', 'stopping']

onMounted(async () => {
  addLog(t('log.step3Init'))
  if (!props.simulationId) return
  try {
    const res = await getRunStatus(props.simulationId)
    if (res.success && ACTIVE_RUN_STATES.includes(res.data?.runner_status)) {
      phase.value = 1
      runStatus.value = res.data
      emit('update-status', 'processing')
      startStatusPolling()
      startDetailPolling()
      return
    }
  } catch (err) {
    startError.value = err.message  // unknown state: never risk restarting a live run
    emit('update-status', 'error')
    return
  }
  doStartSimulation()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.simulation-panel {
  container: simulation / inline-size;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  height: 100%;
  overflow: hidden;
  color: var(--hb-navy);
  background: var(--hb-paper);
  font-family: var(--hb-font-sans);
  font-variant-numeric: lining-nums;
}

h2,
h3 {
  margin: 0;
}

/* Run band */
.run-band {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-2) var(--hb-space-4);
  padding: var(--hb-space-2) var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
}

.run-title {
  min-width: 0;
  font: 700 var(--hb-text-xl) / 1.2 var(--hb-font-serif);
  overflow-wrap: anywhere;
}

.run-band > .hb-status {
  font-size: var(--hb-text-sm);
  white-space: nowrap;
}

.run-progress {
  display: flex;
  align-items: center;
  gap: var(--hb-space-2);
  margin-left: auto;
  font-size: var(--hb-text-sm);
  white-space: nowrap;
}

progress {
  appearance: none;
  width: 5rem;
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

.run-alert {
  display: flex;
  flex: 1 0 100%;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-1) var(--hb-space-2);
  padding: var(--hb-space-1) var(--hb-space-2);
  background: var(--hb-paper);
  border: 1px solid var(--hb-navy);
  font-size: var(--hb-text-sm);
  overflow-wrap: anywhere;
}

/* Work areas: stacked in the split view, side by side when the panel has room */
.work {
  display: grid;
  grid-template-rows: auto minmax(18rem, 1fr) 9rem;
  grid-template-columns: minmax(0, 1fr);
  min-height: 0;
  overflow-y: auto;
}

.rail {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  min-height: 0;
  border-bottom: 1px solid var(--hb-navy);
}

.platforms {
  padding: var(--hb-space-2) var(--hb-space-4);
}

.platform + .platform {
  margin-top: var(--hb-space-2);
  padding-top: var(--hb-space-2);
  border-top: 1px solid var(--hb-rule);
}

.platform-stats {
  display: grid;
  grid-template-columns: repeat(3, auto);
  justify-content: space-between;
  gap: var(--hb-space-3);
  margin-top: var(--hb-space-1);
}

.platform-stats dt {
  color: var(--hb-navy-soft);
  font: 500 var(--hb-text-xs) / 1.2 var(--hb-font-sc);
}

.platform-stats dd {
  font-weight: 700;
}

.platform-actions {
  margin-top: var(--hb-space-1);
  font-size: var(--hb-text-xs);
}

.platform-actions summary {
  min-height: 24px;
  color: var(--hb-navy-soft);
  font-family: var(--hb-font-sc);
  font-weight: 500;
  line-height: 24px;
  cursor: pointer;
}

.platform-actions p {
  font-family: var(--hb-font-sc);
}

.ledger {
  max-height: 11rem;
  padding: var(--hb-space-2) var(--hb-space-4) var(--hb-space-3);
  overflow-y: auto;
  border-top: 1px solid var(--hb-rule);
}

.ledger:focus-visible,
.feed-scroll:focus-visible,
.log-content:focus-visible {
  outline-offset: -2px;
}

.agents {
  margin-top: var(--hb-space-1);
  border-top: 1px solid var(--hb-navy);
}

.agent {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  column-gap: var(--hb-space-2);
  padding: 3px var(--hb-space-1);
  border-bottom: 1px solid var(--hb-rule);
  font-size: var(--hb-text-sm);
}

.agent-name {
  font-weight: 500;
  overflow-wrap: anywhere;
}

.agent.is-latest .agent-name,
.agent-count {
  font-weight: 700;
}

.agent-last {
  grid-column: 1 / -1;
  font-size: var(--hb-text-xs);
}

.activity-title {
  margin-top: var(--hb-space-4);
}

.rail-empty {
  padding-top: var(--hb-space-1);
}

.activity {
  width: 100%;
  margin-top: var(--hb-space-1);
  border-collapse: collapse;
  font-size: var(--hb-text-sm);
}

.activity th,
.activity td {
  padding: 2px 0 2px var(--hb-space-2);
  border-bottom: 1px solid var(--hb-rule);
  font-weight: 400;
  text-align: right;
}

.activity th:first-child {
  padding-left: 0;
  text-align: left;
}

.activity thead th {
  border-block: 1px solid var(--hb-navy);
  font: 700 var(--hb-text-xs) / 1.15 var(--hb-font-sc);
  vertical-align: bottom;
}

.activity tbody th {
  font-family: var(--hb-font-sc);
}

.activity td {
  font-weight: 700;
}

/* Feed */
.feed {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  min-height: 0;
}

.feed-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-1) var(--hb-space-3);
  padding: var(--hb-space-2) var(--hb-space-4);
  border-bottom: 1px solid var(--hb-navy);
}

.feed-counts {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0 var(--hb-space-2);
}

.feed-note {
  flex: 1 0 100%;
}

.feed-scroll {
  min-height: 0;
  overflow-y: auto;
}

.feed-item {
  padding: var(--hb-space-2) var(--hb-space-4) var(--hb-space-3);
}

.feed-item:first-child {
  border-top: 0;
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--hb-space-1) var(--hb-space-2);
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.item-meta .agent-name {
  color: var(--hb-navy);
  font-size: var(--hb-text-md);
  font-weight: 700;
}

.item-time {
  margin-left: auto;
  white-space: nowrap;
}

.item-body {
  display: grid;
  gap: var(--hb-space-1);
  margin-top: var(--hb-space-1);
  overflow-wrap: anywhere;
}

.item-body:empty {
  display: none;
}

.content-text {
  max-width: 68ch;
  line-height: 1.3;
  text-wrap: pretty;
}

.item-note,
.item-excerpt {
  max-width: 68ch;
  color: var(--hb-navy-soft);
  font-size: var(--hb-text-sm);
}

.item-note b {
  color: var(--hb-navy);
}

.quoted {
  max-width: 68ch;
  padding: var(--hb-space-1) var(--hb-space-2);
  border: 1px solid var(--hb-rule);
  border-radius: var(--hb-radius);
  font-size: var(--hb-text-sm);
}

.feed-empty {
  padding: var(--hb-space-6) var(--hb-space-4);
  text-align: center;
}

/* New rows arrive on chart-land and settle into their resting tone */
.timeline-item-enter-active {
  transition: background-color 700ms cubic-bezier(0.16, 1, 0.3, 1);
}

.timeline-item-enter-from {
  background-color: var(--hb-land);
}

/* Logs */
.logs {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  min-height: 0;
  border-top: 1px solid var(--hb-navy);
}

.logs-head {
  padding: var(--hb-space-1) var(--hb-space-4);
  border-bottom: 1px solid var(--hb-rule);
}

.log-id {
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

.log-content {
  min-height: 0;
  padding-bottom: var(--hb-space-1);
  overflow-y: auto;
  font-size: var(--hb-text-sm);
}

.log-line {
  display: grid;
  grid-template-columns: 5rem minmax(0, 1fr) auto;
  align-items: baseline;
  column-gap: var(--hb-space-2);
  padding: 2px var(--hb-space-4);
  border-bottom: 1px solid var(--hb-rule);
}

.log-msg {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

@container simulation (min-width: 34rem) {
  .rail {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }

  .ledger {
    border-top: 0;
    border-left: 1px solid var(--hb-rule);
  }
}

@container simulation (min-width: 48rem) {
  .work {
    grid-template-rows: minmax(0, 1fr) 11rem;
    grid-template-columns: 18rem minmax(0, 1fr);
    overflow: hidden;
  }

  .rail {
    display: flex;
    grid-row: 1 / -1;
    flex-direction: column;
    border-right: 1px solid var(--hb-navy);
    border-bottom: 0;
  }

  .ledger {
    flex: 1;
    min-height: 0;
    max-height: none;
    border-top: 1px solid var(--hb-navy);
    border-left: 0;
  }

  .feed-note {
    flex: 0 1 auto;
    margin-left: auto;
  }
}

@container simulation (min-width: 75rem) {
  .work {
    grid-template-rows: minmax(0, 1fr);
    grid-template-columns: 18rem minmax(0, 1fr) 22rem;
  }

  .logs {
    border-top: 0;
    border-left: 1px solid var(--hb-navy);
  }
}
</style>
