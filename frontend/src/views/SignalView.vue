<template>
  <div>
    <h1 style="margin-bottom: 20px">信号引擎</h1>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else-if="signal">
      <!-- 门控状态 -->
      <div class="card" style="text-align: center">
        <div class="gate-icon" :class="gateClass">
          {{ gateIcon }}
        </div>
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
          买入候选 ({{ signal.candidate_count }})
          <span v-if="signal.has_dragon_tiger_supplement" class="tag tag-blue" style="margin-left: 8px">含龙虎榜</span>
        </div>
        <table v-if="signal.candidates && signal.candidates.length">
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>信号类型</th>
              <th>板位</th>
              <th>题材</th>
              <th>置信度</th>
              <th>封单</th>
              <th>换手率</th>
              <th>游资</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in signal.candidates" :key="c.code">
              <td>{{ c.code }}</td>
              <td>{{ c.name }}</td>
              <td>
                <span class="tag" :class="signalTypeClass(c.signal_type)">{{ c.signal_type }}</span>
              </td>
              <td>{{ c.board_position }}</td>
              <td>{{ c.theme_name || '-' }}</td>
              <td>
                <span style="font-weight: 600" :style="{ color: confidenceColor(c.confidence) }">
                  {{ c.confidence }}
                </span>
              </td>
              <td>{{ c.seal_strength || '-' }}</td>
              <td>{{ c.turnover_rate?.toFixed(1) || '-' }}%</td>
              <td>
                <span v-if="c.has_known_player" class="tag tag-orange">{{ c.player_names }}</span>
                <span v-else style="color: #9ca3af">-</span>
              </td>
            </tr>
          </tbody>
        </table>
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
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getSignalToday, getSignalHistory, runSignals } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const running = ref(false)
const signal = ref(null)
const chartEl = ref(null)
let chart = null

const gateClass = computed(() => {
  const r = signal.value?.gate?.result
  if (r === 'PASS') return 'gate-pass'
  if (r === 'FAIL') return 'gate-fail'
  return 'gate-caution'
})

const gateIcon = computed(() => {
  const r = signal.value?.gate?.result
  if (r === 'PASS') return '●'
  if (r === 'FAIL') return '●'
  return '●'
})

const gateTextClass = computed(() => {
  const r = signal.value?.gate?.result
  if (r === 'PASS') return 'text-green'
  if (r === 'FAIL') return 'text-red'
  return 'text-orange'
})

const phaseTagClass = computed(() => {
  const p = signal.value?.gate?.phase
  if (['高潮', '发酵'].includes(p)) return 'tag-red'
  if (['冰点', '退潮'].includes(p)) return 'tag-green'
  return 'tag-orange'
})

function signalTypeClass(type) {
  if (type === '分歧转一致') return 'tag-red'
  if (type === '梯队确认') return 'tag-blue'
  if (type === '龙头换手') return 'tag-orange'
  return 'tag-gray'
}

function confidenceColor(c) {
  if (c >= 70) return '#ef4444'
  if (c >= 50) return '#f97316'
  if (c >= 30) return '#eab308'
  return '#9ca3af'
}

async function loadData() {
  loading.value = true
  try {
    const [sigRes, histRes] = await Promise.all([
      getSignalToday(props.tradeDate),
      getSignalHistory(30),
    ])
    signal.value = sigRes.data?.error ? null : sigRes.data

    await nextTick()
    if (chartEl.value && histRes.data?.data?.length) {
      renderChart(histRes.data.data)
    }
  } catch (e) {
    signal.value = null
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

function renderChart(data) {
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
</script>

<style scoped>
.gate-icon {
  font-size: 64px;
  line-height: 1;
}
.gate-pass { color: #22c55e; }
.gate-fail { color: #ef4444; }
.gate-caution { color: #f97316; }

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
</style>
