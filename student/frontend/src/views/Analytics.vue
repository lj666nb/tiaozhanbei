<template>
  <div class="analytics-page">
    <PageHero
      eyebrow="LEARNING REVIEW"
      title="学情复盘"
      description="把练习、正确率和知识掌握度放在一起看，找到下一阶段最值得投入的方向。"
      icon="DataAnalysis"
    >
      <template #meta>
        <el-tag effect="plain">最近 7 天</el-tag>
        <el-tag type="success" effect="plain">数据自动更新</el-tag>
      </template>
    </PageHero>

    <section class="overview-grid" aria-label="学习数据概览">
      <div v-for="s in overviewCards" :key="s.label" class="overview-card">
        <span class="overview-icon"><el-icon><component :is="s.icon" /></el-icon></span>
        <span class="overview-copy">
          <small>{{ s.label }}</small>
          <strong>{{ Number(s.value || 0).toFixed(s.precision ?? 0) }}</strong>
        </span>
        <i>↗</i>
      </div>
    </section>

    <section class="analytics-grid">
      <el-card shadow="hover" class="chart-panel">
        <template #header>
          <div class="chart-heading"><div><span>MASTERY</span><strong>知识点掌握度</strong></div><small>按知识模块统计</small></div>
        </template>
        <div ref="masteryChart" class="chart-canvas"></div>
      </el-card>
      <el-card shadow="hover" class="chart-panel">
        <template #header>
          <div class="chart-heading"><div><span>WEEKLY TREND</span><strong>本周学习趋势</strong></div><small>题量与正确率</small></div>
        </template>
        <div ref="weekChart" class="chart-canvas"></div>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useStatStore } from '../stores/statStore'
import * as echarts from 'echarts'
import { recordStudyVisit } from '../api/learning'
import PageHero from '../components/PageHero.vue'

const statStore = useStatStore()
// 概览卡片（computed 从 Pinia 获取）
const overviewCards = computed(() => [
  { label: '学习天数', value: statStore.studyDays, icon: 'Timer', precision: 0 },
  { label: '做题总数', value: statStore.totalQuestions, icon: 'EditPen', precision: 0 },
  { label: '平均正确率(%)', value: statStore.avgCorrectRate, icon: 'TrendCharts', precision: 1 },
  { label: '测评次数', value: statStore.quizCount, icon: 'DocumentChecked', precision: 0 },
])

const masteryChart = ref(null)
const weekChart = ref(null)

let masteryChartInst = null
let weekChartInst = null

// ===== 页面挂载 =====
onMounted(async () => {
  recordStudyVisit()
  // 注册 watcher（数据后续变化时自动重绘）
  watch(() => statStore.moduleMastery, () => { nextTick(() => initMasteryChart()) }, { deep: true })
  watch(() => statStore.weeklyStats, () => { nextTick(() => initWeekChart()) }, { deep: true })
  // Pinia 为空时补拉一次
  if (!statStore.hasMasteryData) {
    await statStore.refreshAll()
  }
  // 无论是否拉取，都立即渲染一次（Pinia 可能已有 Dashboard 加载的数据）
  await nextTick()
  initMasteryChart()
  initWeekChart()
})

function initMasteryChart() {
  if (!masteryChart.value) { console.log('[Analytics] 柱图 DOM 未就绪'); return }
  if (!masteryChartInst) {
    masteryChartInst = echarts.init(masteryChart.value)
    window.addEventListener('resize', () => masteryChartInst?.resize())
  }
  const mastery = statStore.moduleMastery
  const names = statStore.moduleNames || Object.keys(mastery)
  console.log('[Analytics] initMasteryChart 模块数:', names.length)
  if (names.length === 0) { console.log('[Analytics] mastery 为空，跳过柱图渲染'); return }
  masteryChartInst.setOption({
    tooltip: {},
    xAxis: { type: 'value', max: 100, name: '掌握度(%)' },
    yAxis: { type: 'category', data: names, inverse: true },
    series: [{ type: 'bar', data: names.map(n => mastery[n] || 0), itemStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#409EFF' }, { offset: 1, color: '#67C23A' }])
    }, label: { show: true, position: 'right', formatter: '{c}%' } }],
    grid: { left: 200, right: 50, top: 10, bottom: 20 }
  })
}

function initWeekChart() {
  if (!weekChart.value) return
  if (!weekChartInst) {
    weekChartInst = echarts.init(weekChart.value)
    window.addEventListener('resize', () => weekChartInst?.resize())
  }
  const data = statStore.weeklyStats
  if (data.length === 0) return
  weekChartInst.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map(w => w.date?.slice(5)) },
    yAxis: [
      { type: 'value', name: '做题数' },
      { type: 'value', name: '正确率(%)', min: 0, max: 100 }
    ],
    series: [
      { name: '做题数量', type: 'bar', data: data.map(w => w.questions || 0), itemStyle: { color: '#409EFF', borderRadius: 4 } },
      { name: '正确率(%)', type: 'line', yAxisIndex: 1, data: data.map(w => w.correct_rate || 0), smooth: true, itemStyle: { color: '#67C23A' } }
    ],
    grid: { left: 60, right: 70, top: 30, bottom: 30 }
  })
}

</script>

<style scoped>
.analytics-page { padding-bottom: 28px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 13px; }
.overview-card { display: flex; align-items: center; gap: 13px; min-width: 0; padding: 17px 18px; border: 1px solid var(--line); border-radius: 15px; text-align: left; background: rgba(255,255,255,.95); box-shadow: var(--shadow-sm); cursor: default; }
.overview-icon { display: grid; width: 42px; height: 42px; flex: 0 0 42px; place-items: center; border-radius: 12px; color: var(--primary); background: #eef0fc; }
.overview-copy { min-width: 0; flex: 1; }
.overview-copy small, .overview-copy strong { display: block; }
.overview-copy small { color: var(--ink-400); font-size: 10px; }
.overview-copy strong { margin-top: 3px; color: var(--ink-950); font: 650 25px/1.1 Georgia, serif; }
.overview-card > i { color: #ccd2df; font-style: normal; }
.analytics-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; margin-top: 16px; }
.chart-heading { display: flex; align-items: end; justify-content: space-between; }
.chart-heading div span, .chart-heading div strong { display: block; }
.chart-heading div span { color: var(--primary); font-size: 8px; font-weight: 800; letter-spacing: .15em; }
.chart-heading div strong { margin-top: 4px; color: var(--ink-950); font-size: 14px; }
.chart-heading small { color: var(--ink-400); font-size: 9px; }
.chart-canvas { height: 360px; }
@media (max-width: 980px) { .overview-grid { grid-template-columns: repeat(2,1fr); }.analytics-grid { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .overview-grid { grid-template-columns: 1fr; }.chart-canvas { height: 300px; } }
</style>
