<template>
  <div>
    <h1 style="margin-bottom: 20px">信号引擎</h1>

    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'signal' }" @click="activeTab = 'signal'">
        今日信号
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'forecast' }" @click="activeTab = 'forecast'">
        明日预测
      </button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <!-- ═══ 今日信号 Tab ═══ -->
    <template v-else-if="activeTab === 'signal'">
      <template v-if="signal">
        <!-- 门控状态 -->
        <div class="card" style="text-align: center">
          <div class="gate-icon" :class="gateClass">●</div>
          <div style="font-size: 24px; font-weight: 700; margin: 8px 0" :class="gateTextClass">
            {{ signal.gate.result }}
          </div>
          <div style="margin-bottom: 8px">
            <span class="tag" :class="phaseTagClass">{{ signal.gate.phase }}</span>
            <span style="margin-left: 12px; color: #9ca3af">评分 {{ signal.gate.score }}</span>
            <span style="margin-left: 12px; color: #9ca3af">高度 {{ signal.gate.max_height }}</span>
          </div>
          <div style="color: #9ca3af; font-size: 13px">{{ signal.gate.reason }}</div>
        </div>

        <!-- 题材梯队 -->
        <div class="card" v-if="signal.echelons">
          <div class="card-title">题材梯队 ({{ signal.echelons.count }} 个)</div>
          <div v-if="signal.echelons.top_name" style="margin-bottom: 12px">
            <span style="font-weight: 600">{{ signal.echelons.top_name }}</span>
            <span class="tag tag-blue" style="margin-left: 8px">{{ signal.echelons.top_formation }}</span>
            <div class="progress-bar" style="margin-top: 8px">
              <div class="progress-fill" :style="{ width: (signal.echelons.top_completeness || 0) + '%' }"></div>
            </div>
            <div style="font-size: 12px; color: #9ca3af; margin-top: 4px">
              完整度 {{ signal.echelons.top_completeness }}%
            </div>
          </div>
          <div v-else style="color: #9ca3af">暂无合格梯队</div>
        </div>

        <!-- 卖出信号 -->
        <div v-if="signal.sell_signals && signal.sell_signals.length" class="card">
          <div class="card-title text-red">卖出告警 ({{ signal.sell_signals.length }})</div>
          <div
            v-for="(ss, i) in signal.sell_signals"
            :key="i"
            class="sell-alert"
            :class="ss.severity === 'URGENT' ? 'alert-urgent' : 'alert-warn'"
          >
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">{{ ss.name }} ({{ ss.code }})</span>
              <span class="tag" :class="ss.severity === 'URGENT' ? 'tag-red' : 'tag-orange'">
                {{ ss.severity }}
              </span>
            </div>
            <div style="font-size: 13px; margin-top: 4px; color: #9ca3af">
              {{ ss.trigger_type }} · {{ ss.reason }}
            </div>
          </div>
        </div>

        <!-- 候选表格 -->
        <div class="card">
          <div class="card-title">
            买入候选 ({{ filteredSignalCandidates.length }}/{{ signal.candidates?.length || 0 }})
            <span v-if="signal.has_dragon_tiger_supplement" class="tag tag-blue" style="margin-left: 8px">含龙虎榜</span>
          </div>
          <!-- 过滤栏 -->
          <div class="filter-bar" v-if="signal.candidates && signal.candidates.length">
            <div class="filter-item">
              <label>信号类型</label>
              <select v-model="filterSignalType">
                <option value="">全部</option>
                <option value="分歧转一致">分歧转一致</option>
                <option value="梯队确认">梯队确认</option>
                <option value="龙头换手">龙头换手</option>
              </select>
            </div>
            <div class="filter-item">
              <label>题材名称</label>
              <select v-model="filterThemeName">
                <option value="">全部</option>
                <option v-for="t in themeNameOptions" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <div class="filter-item">
              <label>连板高度</label>
              <select v-model="filterBoardPosition">
                <option value="">全部</option>
                <option v-for="n in 10" :key="n" :value="String(n)">{{ n }}板</option>
              </select>
            </div>
            <div class="filter-item">
              <label>最低置信度</label>
              <select v-model.number="filterConfidence">
                <option :value="0">全部</option>
                <option :value="30">≥30</option>
                <option :value="50">≥50</option>
                <option :value="70">≥70</option>
              </select>
            </div>
            <div class="filter-count">
              显示 {{ filteredSignalCandidates.length }}/{{ signal.candidates.length }} 条
            </div>
          </div>
          <table v-if="filteredSignalCandidates.length">
            <thead>
              <tr>
                <th>代码</th><th>名称</th><th>信号类型</th><th>板位</th>
                <th>题材</th><th>置信度</th><th>封单</th><th>换手率</th><th>游资</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in filteredSignalCandidates" :key="c.code">
                <td>{{ c.code }}</td>
                <td>{{ c.name }}</td>
                <td><span class="tag" :class="signalTypeClass(c.signal_type)">{{ c.signal_type }}</span></td>
                <td>{{ c.board_position }}</td>
                <td>{{ c.theme_name || '-' }}</td>
                <td><span style="font-weight: 600" :style="{ color: confidenceColor(c.confidence) }">{{ c.confidence }}</span></td>
                <td>{{ c.seal_strength || '-' }}</td>
                <td>{{ c.turnover_rate?.toFixed(1) || '-' }}%</td>
                <td>
                  <span v-if="c.has_known_player" class="tag tag-orange">{{ c.player_names }}</span>
                  <span v-else style="color: #9ca3af">-</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="signal.candidates && signal.candidates.length" style="color: #9ca3af; text-align: center; padding: 20px">无匹配候选 (共 {{ signal.candidates.length }} 条)</div>
          <div v-else style="color: #9ca3af; text-align: center; padding: 20px">暂无候选标的</div>
        </div>

        <!-- 历史图表 -->
        <div class="card">
          <div class="card-title">历史信号 (近30日)</div>
          <div ref="chartEl" style="height: 280px"></div>
        </div>

        <!-- 手动触发 -->
        <div style="text-align: center; margin-top: 16px">
          <button class="btn-run" @click="manualRun" :disabled="running">
            {{ running ? '生成中...' : '手动生成信号' }}
          </button>
        </div>
      </template>
      <div v-else class="card" style="text-align: center">
        <div style="padding: 20px; color: #9ca3af">当日无信号数据</div>
        <button class="btn-run" @click="manualRun" :disabled="running">
          {{ running ? '生成中...' : '手动生成信号' }}
        </button>
      </div>
    </template>

    <!-- ═══ 明日预测 Tab ═══ -->
    <template v-else-if="activeTab === 'forecast'">
      <template v-if="forecast">
        <!-- 阶段转换预测 -->
        <div class="card" style="text-align: center">
          <div class="forecast-badge">PREDICTED</div>
          <div class="gate-icon" :class="forecastGateClass">●</div>
          <div style="font-size: 24px; font-weight: 700; margin: 8px 0" :class="forecastGateTextClass">
            {{ forecast.gate.predicted_result }}
          </div>
          <!-- 阶段转换箭头 -->
          <div class="phase-transition">
            <span class="tag" :class="phaseTagClassFor(currentPhase)">{{ currentPhase }}</span>
            <span class="transition-arrow">→</span>
            <span class="tag" :class="phaseTagClassFor(forecast.gate.predicted_phase)">{{ forecast.gate.predicted_phase }}</span>
            <span class="transition-confidence">{{ forecast.gate.transition_confidence }}%</span>
          </div>
          <div style="margin-top: 8px; color: #9ca3af; font-size: 13px">
            预测评分 {{ forecast.gate.predicted_score }}
          </div>
          <!-- 门控因子指标 -->
          <div v-if="forecast.gate.factors" class="factor-row">
            涨停{{ forecast.gate.factors.limit_up_momentum > 0 ? '+' : '' }}{{ (forecast.gate.factors.limit_up_momentum * 100).toFixed(0) }}% |
            炸板{{ (forecast.gate.factors.burst_rate * 100).toFixed(0) }}% |
            溢价{{ forecast.gate.factors.premium_avg?.toFixed(1) }}% |
            趋势{{ forecast.gate.factors.trend_score > 0 ? '↑' : forecast.gate.factors.trend_score < 0 ? '↓' : '→' }}
          </div>
        </div>

        <!-- 梯队延续预测 -->
        <div class="card" v-if="forecast.echelons">
          <div class="card-title">
            梯队延续预测 ({{ forecast.echelons.count }} 个)
            <span class="forecast-badge" style="margin-left: 8px">FORECAST</span>
          </div>
          <div v-if="forecast.echelons.top_name" style="margin-bottom: 12px">
            <span style="font-weight: 600">{{ forecast.echelons.top_name }}</span>
            <div class="progress-bar" style="margin-top: 8px">
              <div class="progress-fill progress-fill-forecast" :style="{ width: (forecast.echelons.continuation_score || 0) + '%' }"></div>
            </div>
            <div style="font-size: 12px; color: #9ca3af; margin-top: 4px">
              延续评分 {{ forecast.echelons.continuation_score }}%
            </div>
          </div>
          <div v-else style="color: #9ca3af">无延续梯队</div>
        </div>

        <!-- 策略卡片 -->
        <div class="card strategy-card" v-if="forecast.strategy">
          <div class="card-title">
            明日策略: {{ forecast.strategy.name }}
            <span v-if="forecast.strategy.intensity && forecast.strategy.intensity !== 'normal'" class="tag" :class="forecast.strategy.intensity === 'strong' ? 'tag-red' : 'tag-gray'" style="margin-left: 4px; font-size: 11px">
              {{ forecast.strategy.intensity === 'strong' ? '强' : '弱' }}
            </span>
            <span class="forecast-badge" style="margin-left: 8px">STRATEGY</span>
          </div>
          <div style="font-size: 14px; margin-bottom: 8px">{{ forecast.strategy.summary }}</div>
          <div style="font-size: 13px; color: #9ca3af">
            推荐: {{ forecast.strategy.allow_roles?.length ? forecast.strategy.allow_roles.join(' > ') : '暂不推荐' }}
          </div>
        </div>

        <!-- 预测卖出预警 -->
        <div v-if="forecast.sell_warnings && forecast.sell_warnings.length" class="card">
          <div class="card-title text-red">
            明日卖出预警 ({{ forecast.sell_warnings.length }})
            <span class="forecast-badge" style="margin-left: 8px">FORECAST</span>
          </div>
          <div v-for="(sw, i) in forecast.sell_warnings" :key="i" class="sell-alert alert-warn">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: 600">{{ sw.name }} ({{ sw.code }})</span>
              <span style="font-weight: 600" :style="{ color: confidenceColor(sw.confidence) }">{{ sw.confidence }}</span>
            </div>
            <div style="font-size: 13px; margin-top: 4px; color: #9ca3af">{{ sw.reason }}</div>
          </div>
        </div>

        <!-- 预测买入候选表格 -->
        <div class="card">
          <div class="card-title">
            明日买入候选 ({{ filteredForecastCandidates.length }}/{{ forecast.buy_candidates?.length || 0 }})
            <span class="forecast-badge" style="margin-left: 8px">FORECAST</span>
          </div>
          <!-- 过滤栏 -->
          <div class="filter-bar" v-if="forecast.buy_candidates && forecast.buy_candidates.length">
            <div class="filter-item">
              <label>预测类型</label>
              <select v-model="filterSignalType">
                <option value="">全部</option>
                <option value="leader_confirm">龙头确认</option>
                <option value="leader_promote">龙头晋级</option>
                <option value="second_follow">二龙跟随</option>
                <option value="third_follow">三龙跟随</option>
                <option value="theme_spread">普涨跟风</option>
                <option value="new_leader">新龙头</option>
                <option value="echelon_continuation">梯队延续</option>
              </select>
            </div>
            <div class="filter-item">
              <label>题材名称</label>
              <select v-model="filterThemeName">
                <option value="">全部</option>
                <option v-for="t in themeNameOptions" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <div class="filter-item">
              <label>预测板位</label>
              <select v-model="filterBoardPosition">
                <option value="">全部</option>
                <option v-for="n in 10" :key="n" :value="String(n)">{{ n }}板</option>
              </select>
            </div>
            <div class="filter-item">
              <label>档位</label>
              <select v-model="filterTier">
                <option value="">全部</option>
                <option value="A">A档</option>
                <option value="B">B档</option>
                <option value="C">C档</option>
              </select>
            </div>
            <div class="filter-item">
              <label>最低置信度</label>
              <select v-model.number="filterConfidence">
                <option :value="0">全部</option>
                <option :value="30">≥30</option>
                <option :value="50">≥50</option>
                <option :value="70">≥70</option>
              </select>
            </div>
            <div class="filter-count">
              显示 {{ filteredForecastCandidates.length }}/{{ forecast.buy_candidates.length }} 条
            </div>
          </div>
          <table v-if="filteredForecastCandidates.length">
            <thead>
              <tr>
                <th>档位</th><th>代码</th><th>名称</th><th>角色</th><th>预测类型</th><th>预测板位</th>
                <th>题材</th><th>置信度</th><th>晋级率</th><th>理由</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in filteredForecastCandidates" :key="c.code" :class="tierRowClass(c.tier)">
                <td>
                  <span class="tier-badge" :class="tierBadgeClass(c.tier)">{{ tierLabel(c.tier) }}</span>
                </td>
                <td>{{ c.code }}</td>
                <td>{{ c.name }}</td>
                <td>
                  <span class="tag" :class="roleTagClass(c.market_role)">{{ c.market_role || '-' }}</span>
                  <span v-if="c.has_known_player" class="tag tag-purple" style="margin-left: 4px">游资</span>
                  <span v-else-if="c.has_dragon_tiger" class="tag tag-blue" style="margin-left: 4px; font-size: 11px">龙虎</span>
                </td>
                <td><span class="tag" :class="forecastTypeClass(c.forecast_type)">{{ forecastTypeLabel(c.forecast_type) }}</span></td>
                <td>{{ c.predicted_board || '-' }}</td>
                <td>{{ c.theme_name || '-' }}</td>
                <td><span style="font-weight: 600" :style="{ color: confidenceColor(c.confidence) }">{{ c.confidence }}</span></td>
                <td>{{ c.historical_rate != null ? c.historical_rate.toFixed(0) + '%' : '-' }}</td>
                <td style="max-width: 320px; font-size: 12px; color: #9ca3af; white-space: pre-line">{{ c.rationale }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="forecast.buy_candidates && forecast.buy_candidates.length" style="color: #9ca3af; text-align: center; padding: 20px">无匹配候选 (共 {{ forecast.buy_candidates.length }} 条)</div>
          <div v-else style="color: #9ca3af; text-align: center; padding: 20px">暂无预测候选</div>
        </div>

        <!-- 准确率 -->
        <div class="card" v-if="forecast.accuracy && (forecast.accuracy.gate != null || forecast.accuracy.candidates != null)">
          <div class="card-title">预测准确率 (本次)</div>
          <div class="grid-2">
            <div style="text-align: center">
              <div class="stat-label">门控准确率</div>
              <div style="font-size: 20px; font-weight: 600" :style="{ color: confidenceColor(forecast.accuracy.gate || 0) }">
                {{ forecast.accuracy.gate != null ? forecast.accuracy.gate + '%' : '待验证' }}
              </div>
            </div>
            <div style="text-align: center">
              <div class="stat-label">候选命中率</div>
              <div style="font-size: 20px; font-weight: 600" :style="{ color: confidenceColor(forecast.accuracy.candidates || 0) }">
                {{ forecast.accuracy.candidates != null ? forecast.accuracy.candidates + '%' : '待验证' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 免责声明 -->
        <div style="text-align: center; color: #6b7280; font-size: 12px; margin-top: 12px; padding: 8px">
          预测基于当日数据推算, 仅供参考, 不构成投资建议
        </div>

        <!-- 手动生成预测 -->
        <div style="text-align: center; margin-top: 8px">
          <button class="btn-forecast" @click="manualForecast" :disabled="forecasting">
            {{ forecasting ? '生成中...' : '生成明日预测' }}
          </button>
        </div>
      </template>
      <div v-else class="card" style="text-align: center">
        <div style="padding: 20px; color: #9ca3af">暂无预测数据</div>
        <button class="btn-forecast" @click="manualForecast" :disabled="forecasting">
          {{ forecasting ? '生成中...' : '生成明日预测' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getSignalToday, getSignalHistory, runSignals, getForecast, runForecast } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const running = ref(false)
const forecasting = ref(false)
const activeTab = ref('signal')
const signal = ref(null)
const forecast = ref(null)
const chartEl = ref(null)
let chart = null

// ═══ 过滤器状态 ═══
const filterSignalType = ref('')
const filterThemeName = ref('')
const filterBoardPosition = ref('')
const filterConfidence = ref(0)
const filterTier = ref('')

// 当前阶段 (从今日信号获取)
const currentPhase = computed(() => signal.value?.gate?.phase || '-')

// 今日信号 computed
const gateClass = computed(() => {
  const r = signal.value?.gate?.result
  if (r === 'PASS') return 'gate-pass'
  if (r === 'FAIL') return 'gate-fail'
  return 'gate-caution'
})

const gateTextClass = computed(() => {
  const r = signal.value?.gate?.result
  if (r === 'PASS') return 'text-green'
  if (r === 'FAIL') return 'text-red'
  return 'text-orange'
})

const phaseTagClass = computed(() => phaseTagClassFor(signal.value?.gate?.phase))

// 预测 computed
const forecastGateClass = computed(() => {
  const r = forecast.value?.gate?.predicted_result
  if (r === 'PASS') return 'gate-pass'
  if (r === 'FAIL') return 'gate-fail'
  return 'gate-caution'
})

const forecastGateTextClass = computed(() => {
  const r = forecast.value?.gate?.predicted_result
  if (r === 'PASS') return 'text-green'
  if (r === 'FAIL') return 'text-red'
  return 'text-orange'
})

function phaseTagClassFor(phase) {
  if (['高潮', '发酵'].includes(phase)) return 'tag-red'
  if (['冰点', '退潮'].includes(phase)) return 'tag-green'
  return 'tag-orange'
}

function signalTypeClass(type) {
  if (type === '分歧转一致') return 'tag-red'
  if (type === '梯队确认') return 'tag-blue'
  if (type === '龙头换手') return 'tag-orange'
  return 'tag-gray'
}

function forecastTypeClass(type) {
  if (['leader_confirm', 'leader_promote'].includes(type)) return 'tag-red'
  if (['second_follow', 'new_leader'].includes(type)) return 'tag-orange'
  if (type === 'third_follow') return 'tag-yellow'
  if (type === 'theme_spread') return 'tag-gray'
  return 'tag-blue'
}

function forecastTypeLabel(type) {
  const labels = {
    leader_confirm: '龙头确认',
    leader_promote: '龙头晋级',
    second_follow: '二龙跟随',
    third_follow: '三龙跟随',
    theme_spread: '普涨跟风',
    promotion: '晋级',
    new_leader: '新龙头',
    echelon_continuation: '梯队延续',
  }
  return labels[type] || type
}

function roleTagClass(role) {
  if (role === '龙头') return 'tag-red'
  if (role === '二龙') return 'tag-orange'
  if (role === '三龙') return 'tag-yellow'
  return 'tag-gray'
}

function tierLabel(tier) {
  if (tier === 'A') return 'A档·强推'
  if (tier === 'B') return 'B档·推荐'
  if (tier === 'C') return 'C档·观察'
  return '-'
}

function tierBadgeClass(tier) {
  if (tier === 'A') return 'tier-a'
  if (tier === 'B') return 'tier-b'
  return 'tier-c'
}

function tierRowClass(tier) {
  if (tier === 'A') return 'row-tier-a'
  if (tier === 'B') return 'row-tier-b'
  return 'row-tier-c'
}

function confidenceColor(c) {
  if (c >= 70) return '#ef4444'
  if (c >= 50) return '#f97316'
  if (c >= 30) return '#eab308'
  return '#9ca3af'
}

// ═══ 过滤器 computed ═══
const themeNameOptions = computed(() => {
  const names = new Set()
  for (const c of signal.value?.candidates || []) {
    if (c.theme_name) names.add(c.theme_name)
  }
  for (const c of forecast.value?.buy_candidates || []) {
    if (c.theme_name) names.add(c.theme_name)
  }
  return [...names].sort()
})

function matchesFilters(candidate, isForecast) {
  if (filterSignalType.value) {
    const type = isForecast ? candidate.forecast_type : candidate.signal_type
    if (type !== filterSignalType.value) return false
  }
  if (filterThemeName.value && candidate.theme_name !== filterThemeName.value) return false
  if (filterBoardPosition.value) {
    const pos = isForecast ? candidate.predicted_board : candidate.board_position
    if (String(pos) !== filterBoardPosition.value) return false
  }
  if (filterConfidence.value && (candidate.confidence || 0) < filterConfidence.value) return false
  if (filterTier.value && isForecast && (candidate.tier || '') !== filterTier.value) return false
  return true
}

const filteredSignalCandidates = computed(() => {
  const list = signal.value?.candidates || []
  return list.filter(c => matchesFilters(c, false))
})

const filteredForecastCandidates = computed(() => {
  const list = forecast.value?.buy_candidates || []
  return list.filter(c => matchesFilters(c, true))
})

function resetFilters() {
  filterSignalType.value = ''
  filterThemeName.value = ''
  filterBoardPosition.value = ''
  filterConfidence.value = 0
  filterTier.value = ''
}

async function loadData() {
  loading.value = true
  try {
    const [sigRes, histRes, fcRes] = await Promise.all([
      getSignalToday(props.tradeDate),
      getSignalHistory(30),
      getForecast(props.tradeDate).catch(() => ({ data: null })),
    ])
    signal.value = sigRes.data?.error ? null : sigRes.data
    forecast.value = fcRes.data?.error ? null : fcRes.data
    resetFilters()

    await nextTick()
    if (chartEl.value && histRes.data?.data?.length) {
      renderChart(histRes.data.data)
    }
  } catch (e) {
    signal.value = null
    forecast.value = null
  }
  loading.value = false
}

async function manualRun() {
  running.value = true
  try {
    await runSignals(props.tradeDate)
    await loadData()
  } catch (e) {
    alert('信号生成失败: ' + (e.response?.data?.detail || e.message))
  }
  running.value = false
}

async function manualForecast() {
  forecasting.value = true
  try {
    console.log('Calling forecast API for date:', props.tradeDate)
    const res = await runForecast(props.tradeDate)
    console.log('Forecast API response:', res)
    await loadData()
    alert('预测生成完成')
  } catch (e) {
    console.error('Forecast error:', e)
    const errorMsg = e.response?.data?.detail || e.response?.data?.error || e.message || '未知错误'
    const fullError = `预测生成失败:\n${errorMsg}\n\n请检查:\n1. 是否已生成今日信号\n2. 是否配置了正确的 AI API\n3. 查看浏览器控制台获取更多信息`
    alert(fullError)
  }
  forecasting.value = false
}

function renderChart(data) {
  if (!chartEl.value) return
  if (!chart) {
    chart = echarts.init(chartEl.value)
  }
  const dates = data.map(d => d.trade_date)
  const scores = data.map(d => d.gate_score ?? 0)
  const counts = data.map(d => d.candidate_count ?? 0)
  const colors = data.map(d => {
    if (d.gate_result === 'PASS') return '#22c55e'
    if (d.gate_result === 'FAIL') return '#ef4444'
    return '#f97316'
  })

  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 50, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '评分', min: 0, max: 100, axisLabel: { color: '#9ca3af' } },
      { type: 'value', name: '候选数', axisLabel: { color: '#9ca3af' } },
    ],
    series: [
      {
        name: '门控评分',
        type: 'line',
        data: scores,
        smooth: true,
        lineStyle: { color: '#ff6b35', width: 2 },
        itemStyle: { color: '#ff6b35' },
      },
      {
        name: '候选数',
        type: 'bar',
        yAxisIndex: 1,
        data: counts,
        itemStyle: {
          color: (params) => colors[params.dataIndex] || '#9ca3af',
        },
      },
    ],
  })
}

onMounted(loadData)
watch(() => props.tradeDate, loadData)
watch(activeTab, () => { filterSignalType.value = '' })
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  background: #1e2030;
  border-radius: 8px;
  padding: 4px;
}
.tab-btn {
  flex: 1;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}
.tab-btn.active {
  background: #ff6b35;
  color: white;
}
.tab-btn:hover:not(.active) {
  color: #e0e0e0;
}

.gate-icon {
  font-size: 64px;
  line-height: 1;
}
.gate-pass { color: #22c55e; }
.gate-fail { color: #ef4444; }
.gate-caution { color: #f97316; }

.forecast-badge {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.phase-transition {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
}
.transition-arrow {
  font-size: 20px;
  color: #60a5fa;
  font-weight: 700;
}
.transition-confidence {
  font-size: 13px;
  color: #60a5fa;
  font-weight: 600;
}

.progress-bar {
  height: 8px;
  background: #1e2030;
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #22c55e);
  border-radius: 4px;
  transition: width 0.3s;
}
.progress-fill-forecast {
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
}

.sell-alert {
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 8px;
}
.alert-urgent {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.alert-warn {
  background: rgba(249, 115, 22, 0.1);
  border: 1px solid rgba(249, 115, 22, 0.3);
}

.btn-run {
  padding: 8px 24px;
  background: #ff6b35;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn-run:hover { background: #e55a2b; }
.btn-run:disabled { background: #666; cursor: not-allowed; }

.btn-forecast {
  padding: 8px 24px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn-forecast:hover { background: #2563eb; }
.btn-forecast:disabled { background: #666; cursor: not-allowed; }

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.tag-yellow {
  background: rgba(234, 179, 8, 0.15);
  color: #eab308;
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.strategy-card {
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.05);
}

.tag-purple {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.factor-row {
  margin-top: 8px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
  font-size: 12px;
  color: #9ca3af;
  letter-spacing: 0.3px;
}

.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 12px;
  background: #1e2030;
  border: 1px solid #3a3d4a;
  border-radius: 8px;
  flex-wrap: wrap;
}
.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.filter-item label {
  font-size: 11px;
  color: #9ca3af;
}
.filter-item select {
  padding: 4px 8px;
  background: #2a2d3e;
  color: #e0e0e0;
  border: 1px solid #3a3d4a;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  outline: none;
}
.filter-item select:focus {
  border-color: #ff6b35;
}
.filter-count {
  margin-left: auto;
  font-size: 12px;
  color: #9ca3af;
  white-space: nowrap;
  align-self: flex-end;
  padding-bottom: 2px;
}

/* 档位标签 */
.tier-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.tier-a {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.tier-b {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}
.tier-c {
  background: rgba(156, 163, 175, 0.15);
  color: #9ca3af;
  border: 1px solid rgba(156, 163, 175, 0.3);
}

/* 档位行背景 */
.row-tier-a { background: rgba(239, 68, 68, 0.05) !important; }
.row-tier-b { background: rgba(59, 130, 246, 0.05) !important; }
.row-tier-c { background: transparent !important; }
</style>
