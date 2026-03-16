<template>
  <div>
    <h1 style="margin-bottom: 20px">情绪周期</h1>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else-if="emotion">
      <!-- 情绪概览 -->
      <div class="grid-3">
        <div class="card" style="text-align: center">
          <div class="stat-label">情绪评分</div>
          <div class="stat-value" :style="{ color: scoreColor }">{{ emotion.score }}</div>
          <div class="stat-label">/ 100</div>
        </div>
        <div class="card" style="text-align: center">
          <div class="stat-label">当前阶段</div>
          <div class="stat-value">{{ emotion.phase }}</div>
          <div class="stat-label">
            {{ emotion.trend_direction > 0 ? '↑ 上升' : emotion.trend_direction < 0 ? '↓ 下降' : '→ 横盘' }}
            · 持续 {{ emotion.phase_days }} 天
          </div>
        </div>
        <div class="card" style="text-align: center">
          <div class="stat-label">连板高度</div>
          <div class="stat-value text-orange">{{ emotion.raw?.max_continuous || 0 }}</div>
          <div class="stat-label">{{ emotion.raw?.max_continuous_name || '-' }}</div>
        </div>
      </div>

      <!-- 分项评分 -->
      <div class="card">
        <div class="card-title">分项评分</div>
        <div class="grid-2">
          <div v-for="(val, key) in emotion.sub_scores" :key="key" style="display:flex; justify-content:space-between; padding: 8px 0; border-bottom: 1px solid #1e2030">
            <span>{{ key }}</span>
            <span style="font-weight: 600">{{ val }} / 25</span>
          </div>
        </div>
      </div>

      <!-- 市场数据 -->
      <div class="card">
        <div class="card-title">市场数据</div>
        <div class="grid-3">
          <div>
            <div class="stat-label">涨停</div>
            <div class="text-red" style="font-size: 20px; font-weight: 600">{{ emotion.raw?.limit_up_count_real || 0 }}</div>
          </div>
          <div>
            <div class="stat-label">跌停</div>
            <div class="text-green" style="font-size: 20px; font-weight: 600">{{ emotion.raw?.limit_down_count || 0 }}</div>
          </div>
          <div>
            <div class="stat-label">炸板</div>
            <div class="text-orange" style="font-size: 20px; font-weight: 600">{{ emotion.raw?.burst_count || 0 }}</div>
          </div>
          <div>
            <div class="stat-label">封板率</div>
            <div style="font-size: 20px; font-weight: 600">{{ emotion.raw?.seal_success_rate?.toFixed(1) || '-' }}%</div>
          </div>
          <div>
            <div class="stat-label">昨涨停溢价</div>
            <div style="font-size: 20px; font-weight: 600">{{ emotion.raw?.yesterday_premium_avg?.toFixed(2) || '-' }}%</div>
          </div>
          <div>
            <div class="stat-label">涨跌比</div>
            <div style="font-size: 20px; font-weight: 600">{{ emotion.raw?.advance_decline_ratio?.toFixed(2) || '-' }}</div>
          </div>
        </div>
      </div>

      <!-- 历史曲线 -->
      <div class="card">
        <div class="card-title">情绪曲线 (近60日)</div>
        <div ref="chartEl" style="height: 300px"></div>
      </div>
    </template>
    <div v-else class="card">当日无数据</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getEmotionToday, getEmotionHistory } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const emotion = ref(null)
const chartEl = ref(null)
let chart = null

const scoreColor = computed(() => {
  const s = emotion.value?.score || 0
  if (s >= 75) return '#ef4444'
  if (s >= 50) return '#f97316'
  if (s >= 30) return '#eab308'
  return '#22c55e'
})

async function loadData() {
  loading.value = true
  try {
    const [emoRes, histRes] = await Promise.all([
      getEmotionToday(props.tradeDate),
      getEmotionHistory(60, props.tradeDate),
    ])
    emotion.value = emoRes.data?.error ? null : emoRes.data

    await nextTick()
    if (chartEl.value && histRes.data?.data?.length) {
      renderChart(histRes.data.data)
    }
  } catch (e) {
    emotion.value = null
  }
  loading.value = false
}

function renderChart(data) {
  if (!chart) {
    chart = echarts.init(chartEl.value)
  }
  const dates = data.map(d => d.trade_date)
  const scores = data.map(d => d.score ?? 0)
  const limitUps = data.map(d => d.limit_up_count ?? 0)

  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 50, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '评分', min: 0, max: 100, axisLabel: { color: '#9ca3af' } },
      { type: 'value', name: '涨停数', axisLabel: { color: '#9ca3af' } },
    ],
    series: [
      {
        name: '情绪评分',
        type: 'line',
        data: scores,
        smooth: true,
        lineStyle: { color: '#ff6b35', width: 2 },
        itemStyle: { color: '#ff6b35' },
        areaStyle: { color: 'rgba(255,107,53,0.1)' },
      },
      {
        name: '涨停数',
        type: 'bar',
        yAxisIndex: 1,
        data: limitUps,
        itemStyle: { color: 'rgba(239,68,68,0.3)' },
      },
    ],
  })
}

onMounted(loadData)
watch(() => props.tradeDate, loadData)
</script>
