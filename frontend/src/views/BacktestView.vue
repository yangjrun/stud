<template>
  <div>
    <h1 style="margin-bottom: 20px">预测回测</h1>

    <!-- 运行配置 -->
    <div class="card">
      <div class="card-title">回测配置</div>
      <div class="config-row">
        <div class="config-item">
          <label>开始日期</label>
          <input type="date" v-model="startDate" :max="endDate" />
        </div>
        <div class="config-item">
          <label>结束日期</label>
          <input type="date" v-model="endDate" :min="startDate" :max="today" />
        </div>
        <div class="config-item" style="align-self: flex-end">
          <span class="range-hint">{{ rangeDays }} 个交易日</span>
        </div>
        <div class="config-item" style="align-self: flex-end">
          <button class="btn-run" @click="runBacktest" :disabled="running || !isValid">
            {{ running ? '回测中...' : '开始回测' }}
          </button>
        </div>
      </div>
      <div v-if="rangeError" class="error-hint">{{ rangeError }}</div>
    </div>

    <!-- 汇总卡片 -->
    <template v-if="result">
      <div class="grid-4">
        <div class="card stat-card">
          <div class="stat-label">门控准确率</div>
          <div class="stat-value" :style="{ color: accColor(result.avg_gate_accuracy) }">
            {{ result.avg_gate_accuracy != null ? result.avg_gate_accuracy + '%' : '-' }}
          </div>
          <div class="stat-sub">精确匹配 {{ result.gate_exact_match_rate != null ? result.gate_exact_match_rate + '%' : '-' }}</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">候选命中率</div>
          <div class="stat-value" :style="{ color: accColor(result.avg_candidate_hit_rate) }">
            {{ result.avg_candidate_hit_rate != null ? result.avg_candidate_hit_rate + '%' : '-' }}
          </div>
          <div class="stat-sub">{{ result.total_hits }}/{{ result.total_buy_candidates }} 命中</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">分析天数</div>
          <div class="stat-value">{{ result.total_days }}</div>
          <div class="stat-sub">跳过 {{ result.skipped_days }} 天</div>
        </div>
        <div class="card stat-card">
          <div class="stat-label">日期范围</div>
          <div style="font-size: 14px; font-weight: 600; margin-top: 8px">
            {{ result.start_date }}
          </div>
          <div class="stat-sub">至 {{ result.end_date }}</div>
        </div>
      </div>

      <!-- 档位命中率 -->
      <div class="grid-3">
        <div class="card stat-card tier-card-a">
          <div class="stat-label">A档命中率</div>
          <div class="stat-value" style="color: #ef4444">
            {{ result.avg_tier_a_hit_rate != null ? result.avg_tier_a_hit_rate + '%' : '-' }}
          </div>
          <div class="stat-sub">强推 (置信度>=70)</div>
        </div>
        <div class="card stat-card tier-card-b">
          <div class="stat-label">B档命中率</div>
          <div class="stat-value" style="color: #3b82f6">
            {{ result.avg_tier_b_hit_rate != null ? result.avg_tier_b_hit_rate + '%' : '-' }}
          </div>
          <div class="stat-sub">推荐 (置信度>=50)</div>
        </div>
        <div class="card stat-card tier-card-c">
          <div class="stat-label">C档命中率</div>
          <div class="stat-value" style="color: #9ca3af">
            {{ result.avg_tier_c_hit_rate != null ? result.avg_tier_c_hit_rate + '%' : '-' }}
          </div>
          <div class="stat-sub">观察 (置信度<50)</div>
        </div>
      </div>

      <!-- 准确率图表 -->
      <div class="card">
        <div class="card-title">逐日准确率</div>
        <div ref="chartEl" style="height: 280px"></div>
      </div>

      <!-- 逐日明细表 -->
      <div class="card">
        <div class="card-title">逐日明细 ({{ validDays.length }} 天)</div>
        <table v-if="result.days.length">
          <thead>
            <tr>
              <th>预测日</th><th>目标日</th><th>预测阶段</th><th>实际阶段</th>
              <th>门控准确</th><th>候选数</th><th>命中</th><th>命中率</th>
              <th>A档</th><th>B档</th><th>C档</th>
              <th>策略</th><th>主题材</th><th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="d in result.days" :key="d.source_date"
              :class="dayRowClass(d)"
            >
              <td>{{ d.source_date }}</td>
              <td>{{ d.target_date }}</td>
              <td>
                <span v-if="!d.skip_reason" class="tag" :class="phaseClass(d.predicted_gate_phase)">
                  {{ d.predicted_gate_phase || '-' }}
                </span>
                <span v-else>-</span>
              </td>
              <td>
                <span v-if="d.actual_gate_phase" class="tag" :class="phaseClass(d.actual_gate_phase)">
                  {{ d.actual_gate_phase }}
                </span>
                <span v-else>-</span>
              </td>
              <td>
                <span v-if="d.gate_accuracy != null" :style="{ color: accColor(d.gate_accuracy), fontWeight: 600 }">
                  {{ d.gate_accuracy }}
                </span>
                <span v-else>-</span>
              </td>
              <td>{{ d.skip_reason ? '-' : d.buy_candidate_count }}</td>
              <td>{{ d.skip_reason ? '-' : d.hit_count }}</td>
              <td>
                <span v-if="d.candidate_hit_rate != null" :style="{ color: accColor(d.candidate_hit_rate) }">
                  {{ d.candidate_hit_rate }}%
                </span>
                <span v-else>-</span>
              </td>
              <td>
                <span v-if="!d.skip_reason && d.tier_a_count" style="color: #ef4444">{{ d.tier_a_hits }}/{{ d.tier_a_count }}</span>
                <span v-else>-</span>
              </td>
              <td>
                <span v-if="!d.skip_reason && d.tier_b_count" style="color: #3b82f6">{{ d.tier_b_hits }}/{{ d.tier_b_count }}</span>
                <span v-else>-</span>
              </td>
              <td>
                <span v-if="!d.skip_reason && d.tier_c_count" style="color: #9ca3af">{{ d.tier_c_hits }}/{{ d.tier_c_count }}</span>
                <span v-else>-</span>
              </td>
              <td>{{ d.strategy_name || '-' }}</td>
              <td>{{ d.predicted_top_echelon || '-' }}</td>
              <td>
                <span v-if="d.skip_reason" class="tag tag-gray">{{ d.skip_reason }}</span>
                <span v-else-if="d.gate_accuracy === 100" class="tag tag-green">精确</span>
                <span v-else-if="d.gate_accuracy === 50" class="tag tag-orange">相邻</span>
                <span v-else class="tag tag-red">偏差</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 历史记录 -->
    <div class="card">
      <div class="card-title">历史回测记录</div>
      <div v-if="loadingHistory" style="color: #9ca3af; text-align: center; padding: 20px">加载中...</div>
      <table v-else-if="history.length">
        <thead>
          <tr>
            <th>日期范围</th><th>分析天数</th><th>门控准确</th><th>命中率</th>
            <th>命中/候选</th><th>时间</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in history" :key="h.id">
            <td>{{ h.start_date }} ~ {{ h.end_date }}</td>
            <td>{{ h.total_days }} <span style="color: #9ca3af">(跳{{ h.skipped_days }})</span></td>
            <td :style="{ color: accColor(h.avg_gate_accuracy), fontWeight: 600 }">
              {{ h.avg_gate_accuracy != null ? h.avg_gate_accuracy + '%' : '-' }}
            </td>
            <td :style="{ color: accColor(h.avg_candidate_hit_rate), fontWeight: 600 }">
              {{ h.avg_candidate_hit_rate != null ? h.avg_candidate_hit_rate + '%' : '-' }}
            </td>
            <td>{{ h.total_hits }}/{{ h.total_buy_candidates }}</td>
            <td style="color: #9ca3af; font-size: 12px">{{ formatTime(h.created_at) }}</td>
            <td>
              <button class="btn-small" @click="loadDetail(h.id)">查看</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else style="color: #9ca3af; text-align: center; padding: 20px">暂无回测记录</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { runForecastBacktest, getForecastBacktestHistory, getForecastBacktestDetail } from '../api'

const today = new Date().toISOString().slice(0, 10)
// 30个交易日约42个日历天
const thirtyAgo = new Date(Date.now() - 42 * 86400000).toISOString().slice(0, 10)

const startDate = ref(thirtyAgo)
const endDate = ref(today)
const running = ref(false)
const result = ref(null)
const history = ref([])
const loadingHistory = ref(true)
const chartEl = ref(null)
let chart = null

const rangeDays = computed(() => {
  const s = new Date(startDate.value)
  const e = new Date(endDate.value)
  const calDays = Math.round((e - s) / 86400000)
  if (calDays < 0) return 0
  // 计算交易日 (排除周末)
  let count = 0
  for (let i = 0; i <= calDays; i++) {
    const d = new Date(s.getTime() + i * 86400000)
    if (d.getDay() !== 0 && d.getDay() !== 6) count++
  }
  return count
})

const rangeError = computed(() => {
  if (new Date(startDate.value) > new Date(endDate.value)) return '开始日期不能晚于结束日期'
  if (rangeDays.value > 30) return '交易日数不能超过30天'
  return ''
})

const isValid = computed(() => !rangeError.value && rangeDays.value >= 0)

const validDays = computed(() =>
  (result.value?.days || []).filter(d => !d.skip_reason),
)

function accColor(val) {
  if (val == null) return '#9ca3af'
  if (val >= 60) return '#22c55e'
  if (val >= 40) return '#f97316'
  return '#ef4444'
}

function phaseClass(phase) {
  if (['高潮', '发酵'].includes(phase)) return 'tag-red'
  if (['冰点', '退潮'].includes(phase)) return 'tag-green'
  return 'tag-orange'
}

function dayRowClass(d) {
  if (d.skip_reason) return 'row-skip'
  if (d.gate_accuracy === 100) return 'row-exact'
  if (d.gate_accuracy === 0) return 'row-miss'
  return ''
}

function formatTime(iso) {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 16)
}

async function runBacktest() {
  running.value = true
  try {
    const res = await runForecastBacktest(startDate.value, endDate.value)
    result.value = res.data
    await nextTick()
    renderChart()
    await loadHistory()
  } catch (e) {
    alert('回测失败: ' + (e.response?.data?.detail || e.message))
  }
  running.value = false
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const res = await getForecastBacktestHistory(20)
    history.value = res.data?.data || []
  } catch {
    history.value = []
  }
  loadingHistory.value = false
}

async function loadDetail(runId) {
  try {
    const res = await getForecastBacktestDetail(runId)
    result.value = res.data
    await nextTick()
    renderChart()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    alert('加载失败: ' + (e.response?.data?.detail || e.message))
  }
}

function renderChart() {
  if (!chartEl.value || !result.value) return
  const days = validDays.value
  if (!days.length) return

  if (!chart) {
    chart = echarts.init(chartEl.value)
  }

  const dates = days.map(d => d.source_date)
  const gateAcc = days.map(d => d.gate_accuracy ?? 0)
  const candRate = days.map(d => d.candidate_hit_rate ?? 0)
  const tierARate = days.map(d =>
    d.tier_a_count ? Math.round(d.tier_a_hits / d.tier_a_count * 100) : null,
  )
  const barColors = days.map(d => {
    if (d.gate_accuracy === 100) return '#22c55e'
    if (d.gate_accuracy === 50) return '#f97316'
    return '#ef4444'
  })

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['门控准确率', '候选命中率', 'A档命中率'],
      textStyle: { color: '#9ca3af' },
    },
    grid: { left: 50, right: 50, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#9ca3af', fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: '#9ca3af', formatter: '{value}%' },
    },
    series: [
      {
        name: '门控准确率',
        type: 'bar',
        data: gateAcc,
        itemStyle: { color: (params) => barColors[params.dataIndex] },
        barWidth: '40%',
      },
      {
        name: '候选命中率',
        type: 'line',
        data: candRate,
        smooth: true,
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#3b82f6' },
      },
      {
        name: 'A档命中率',
        type: 'line',
        data: tierARate,
        smooth: true,
        connectNulls: true,
        lineStyle: { color: '#ef4444', width: 2, type: 'dashed' },
        itemStyle: { color: '#ef4444' },
      },
    ],
  }, true)
}

onMounted(loadHistory)
</script>

<style scoped>
.config-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.config-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.config-item label {
  font-size: 12px;
  color: #9ca3af;
}
.config-item input[type="date"] {
  padding: 6px 10px;
  background: #1e2030;
  border: 1px solid #3a3d4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
}
.range-hint {
  font-size: 13px;
  color: #9ca3af;
  padding: 6px 0;
}
.error-hint {
  color: #ef4444;
  font-size: 13px;
  margin-top: 8px;
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

.btn-small {
  padding: 3px 10px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.btn-small:hover { background: #2563eb; }

.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 0;
}
.stat-card {
  text-align: center;
  padding: 16px;
}
.stat-card .stat-value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 8px;
}
.stat-card .stat-label {
  font-size: 12px;
  color: #9ca3af;
}
.stat-card .stat-sub {
  font-size: 11px;
  color: #6b7280;
  margin-top: 4px;
}

.row-skip { opacity: 0.5; }
.row-exact { background: rgba(34, 197, 94, 0.05) !important; }
.row-miss { background: rgba(239, 68, 68, 0.05) !important; }

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 0;
}
.tier-card-a { border: 1px solid rgba(239, 68, 68, 0.2); }
.tier-card-b { border: 1px solid rgba(59, 130, 246, 0.2); }
.tier-card-c { border: 1px solid rgba(156, 163, 175, 0.2); }
</style>
