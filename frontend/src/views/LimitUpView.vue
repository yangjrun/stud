<template>
  <div>
    <h1 style="margin-bottom: 20px">连板生态</h1>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <!-- 连板梯队 -->
      <div class="grid-2" v-if="ladder">
        <div class="card">
          <div class="card-title">连板梯队</div>
          <div class="ladder-chart">
            <div v-for="(count, height) in sortedBoards" :key="height" class="ladder-row">
              <span class="ladder-label">{{ height }}板</span>
              <div class="ladder-bar" :style="{ width: barWidth(count) + '%' }">{{ count }}只</div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-title">概览</div>
          <div style="margin-bottom: 16px">
            <div class="stat-label">最高连板</div>
            <div class="stat-value text-red">{{ ladder.max_height }}</div>
            <div class="stat-label">{{ ladder.max_height_stocks?.map(s => s.name).join(', ') }}</div>
          </div>
          <div class="grid-2">
            <div>
              <div class="stat-label">涨停</div>
              <div style="font-size: 22px; font-weight: 600" class="text-red">{{ ladder.total_limit_up }}</div>
            </div>
            <div>
              <div class="stat-label">炸板</div>
              <div style="font-size: 22px; font-weight: 600" class="text-orange">{{ ladder.total_burst }}</div>
            </div>
          </div>
          <!-- 晋级率 -->
          <div v-if="promotion" style="margin-top: 20px">
            <div class="card-title">晋级率</div>
            <div v-for="(rate, key) in promotion.rates" :key="key" style="display:flex; justify-content:space-between; padding: 6px 0">
              <span>{{ key.replace('to', ' → ') }}</span>
              <span :class="rate > 0.3 ? 'text-red' : rate > 0.15 ? 'text-orange' : 'text-green'" style="font-weight: 600">
                {{ rate != null ? (rate * 100).toFixed(0) + '%' : '-' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 涨停列表 -->
      <div class="card">
        <div class="card-title">涨停列表 (按质量评分)</div>
        <table>
          <thead>
            <tr>
              <th>代码</th><th>名称</th><th>连板</th><th>封单强度</th>
              <th>封单比</th><th>首封时间</th><th>炸板次数</th><th>评分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in stocks" :key="s.code">
              <td>{{ s.code }}</td>
              <td>{{ s.name }}</td>
              <td><span class="tag" :class="s.continuous_count >= 3 ? 'tag-red' : s.continuous_count >= 2 ? 'tag-orange' : 'tag-gray'">{{ s.continuous_count }}板</span></td>
              <td><span class="tag" :class="s.seal_strength === '强封' ? 'tag-red' : s.seal_strength === '中等' ? 'tag-orange' : 'tag-gray'">{{ s.seal_strength }}</span></td>
              <td>{{ s.seal_ratio }}</td>
              <td>{{ s.first_seal_grade }}</td>
              <td>{{ s.open_count }}</td>
              <td style="font-weight: 600" :class="s.score >= 80 ? 'text-red' : s.score >= 60 ? 'text-orange' : ''">{{ s.score }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getLimitUpToday, getLadder, getPromotion } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const ladder = ref(null)
const promotion = ref(null)
const stocks = ref([])

const sortedBoards = computed(() => {
  if (!ladder.value?.board_counts) return {}
  const entries = Object.entries(ladder.value.board_counts)
    .map(([k, v]) => [Number(k), v])
    .sort((a, b) => b[0] - a[0])
  return Object.fromEntries(entries)
})

function barWidth(count) {
  const max = Math.max(...Object.values(ladder.value?.board_counts || { 1: 1 }))
  return Math.max(8, (count / max) * 100)
}

async function loadData() {
  loading.value = true
  try {
    const [ladderRes, promoRes, luRes] = await Promise.all([
      getLadder(props.tradeDate),
      getPromotion(props.tradeDate),
      getLimitUpToday(props.tradeDate),
    ])
    ladder.value = ladderRes.data
    promotion.value = promoRes.data
    stocks.value = luRes.data?.stocks || []
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

onMounted(loadData)
watch(() => props.tradeDate, loadData)
</script>

<style scoped>
.ladder-chart { display: flex; flex-direction: column; gap: 8px; }
.ladder-row { display: flex; align-items: center; gap: 12px; }
.ladder-label { width: 40px; text-align: right; font-size: 13px; color: #9ca3af; }
.ladder-bar {
  background: linear-gradient(90deg, rgba(239,68,68,0.6), rgba(239,68,68,0.2));
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  min-width: 50px;
  transition: width 0.3s;
}
</style>
