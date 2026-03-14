<template>
  <div>
    <h1 style="margin-bottom: 20px">题材追踪</h1>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <div class="card" style="margin-bottom: 12px">
        <span class="stat-label">活跃题材 </span>
        <span style="font-weight: 600">{{ data?.total || 0 }}</span>
      </div>

      <div class="card" v-for="t in themes" :key="t.concept_name">
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div>
            <span style="font-size: 16px; font-weight: 600">{{ t.concept_name }}</span>
            <span v-if="t.is_new_theme" class="tag tag-red" style="margin-left: 8px">新!</span>
            <span v-if="t.consecutive_days > 1" class="tag tag-blue" style="margin-left: 8px">持续{{ t.consecutive_days }}天</span>
          </div>
          <div style="text-align: right">
            <span class="tag" :class="t.limit_up_count >= 5 ? 'tag-red' : t.limit_up_count >= 3 ? 'tag-orange' : 'tag-gray'">
              涨停 {{ t.limit_up_count }} 只
            </span>
            <span v-if="t.change_pct != null" style="margin-left: 12px" :class="t.change_pct > 0 ? 'text-red' : 'text-green'">
              {{ t.change_pct > 0 ? '+' : '' }}{{ t.change_pct?.toFixed(2) }}%
            </span>
          </div>
        </div>
        <div v-if="t.leader_name" style="margin-top: 8px; color: #9ca3af; font-size: 13px">
          龙头: <span style="color: #f97316">{{ t.leader_name }}</span>
          <span v-if="t.leader_continuous > 1"> ({{ t.leader_continuous }}板)</span>
          <span v-if="t.leader_code" style="margin-left: 8px; color: #6b7280">{{ t.leader_code }}</span>
        </div>
      </div>

      <div v-if="!themes.length" class="card">暂无题材数据</div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { getThemesToday } from '../api'

const props = defineProps({ tradeDate: String })
const loading = ref(true)
const data = ref(null)
const themes = ref([])

async function loadData() {
  loading.value = true
  try {
    const res = await getThemesToday(props.tradeDate, 20)
    data.value = res.data
    themes.value = res.data?.themes || []
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

onMounted(loadData)
watch(() => props.tradeDate, loadData)
</script>
