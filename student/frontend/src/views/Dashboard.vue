<template>
  <div class="dashboard">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner">
      <div class="welcome-content">
        <div class="welcome-left">
          <span class="welcome-eyebrow">TODAY'S LEARNING ROUTE</span>
          <h1 class="welcome-title">{{ greeting }}，{{ userStore.user?.nickname || '同学' }}</h1>
          <p class="welcome-subtitle">{{ welcomeQuote }}</p>
          <div class="welcome-meta">
            <span class="stage-badge"><i></i>{{ userStore.learningStage || '入门' }}阶段</span>
            <span class="welcome-date">{{ todayDate }}</span>
          </div>
        </div>
        <div class="welcome-right">
          <div class="welcome-stats-row">
            <!-- 直接从 Pinia 读取，不用中间变量，保证响应式 -->
            <div class="welcome-mini-stat">
              <div class="wms-value">{{ statStore.studyDays }}</div>
              <div class="wms-label">学习天数</div>
            </div>
            <div class="welcome-mini-stat">
              <div class="wms-value">{{ Number(statStore.avgCorrectRate).toFixed(1) }}%</div>
              <div class="wms-label">正确率</div>
            </div>
            <div class="welcome-mini-stat">
              <div class="wms-value">{{ statStore.totalQuestions }}</div>
              <div class="wms-label">做题总数</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="section-heading">
      <div>
        <span class="section-eyebrow">QUICK START</span>
        <h2>开始今天的学习</h2>
      </div>
      <button type="button" class="section-link" @click="router.push('/code-lab')">进入编程实验室 <span>→</span></button>
    </div>
    <div class="quick-actions">
      <button type="button" class="qa-card" v-for="act in quickActions" :key="act.label" @click="router.push(act.route)">
        <div class="qa-icon" :style="{ background: act.bg }">
          <el-icon :size="22"><component :is="act.icon" /></el-icon>
        </div>
        <div class="qa-label">{{ act.label }}</div>
        <div class="qa-desc">{{ act.desc }}</div>
      </button>
    </div>

    <div class="stats-grid">
      <button type="button" class="stat-card" v-for="stat in statsCards" :key="stat.label" @click="router.push(stat.route)">
        <div class="stat-icon-wrap" :style="{ background: stat.bg }">
          <el-icon :size="21" :style="{ color: stat.color }"><component :is="stat.icon" /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value">{{ stat.value }}</div>
        </div>
        <span class="stat-arrow">↗</span>
      </button>
    </div>

    <!-- 图表 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="14">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><TrendCharts /></el-icon> 学习成长趋势</span>
              <el-tag size="small" type="info">近7天</el-tag>
            </div>
          </template>
          <div ref="growthChart" style="height:300px"></div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><PieChart /></el-icon> 知识点掌握度</span>
            </div>
          </template>
          <!-- v-show 保持 DOM 存在，数据到达时 watch 能正常初始化图表 -->
          <div v-if="hasModuleData" ref="radarChart" style="height:300px"></div>
          <el-empty v-else description="完成测评后即可查看知识掌握度" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 今日任务 + 学习动态 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="12">
        <el-card shadow="hover" class="task-card">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><Sunny /></el-icon> 今日学习任务</span>
              <el-tag v-if="dailyTasks?.tasks?.length" size="small" :type="dailyTasks?.completed ? 'success' : 'warning'">
                {{ dailyTasks?.completed ? '已完成' : '进行中' }}
              </el-tag>
            </div>
          </template>
          <div v-if="dailyTasks?.tasks?.length">
            <div v-for="(task, idx) in dailyTasks.tasks" :key="idx" class="task-row">
              <div class="task-check">
                <el-icon :size="18" :color="task.done ? '#67C23A' : '#DCDFE6'">
                  <component :is="task.done ? 'CircleCheckFilled' : 'CircleCheck'" />
                </el-icon>
              </div>
              <div class="task-info">
                <div class="task-topic" :class="{ done: task.done }">{{ task.topic }}</div>
                <div class="task-action">{{ task.action }}</div>
              </div>
            </div>
            <div v-if="dailyTasks.study_tips" class="tips-bar">
              <el-icon><InfoFilled /></el-icon> {{ dailyTasks.study_tips }}
            </div>
            <div class="task-footer">
              <el-button type="primary" :disabled="dailyTasks?.completed" @click="markTaskDone">
                {{ dailyTasks?.completed ? '✓ 今日任务已完成' : '完成今日所有任务' }}
              </el-button>
            </div>
          </div>
          <el-empty v-else description="暂无今日任务">
            <el-button type="primary" @click="router.push('/learning-path')">去生成学习路径</el-button>
          </el-empty>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="activity-card">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><Clock /></el-icon> 最近学习动态</span>
            </div>
          </template>
          <el-timeline v-if="statStore.recentActivity.length">
            <el-timeline-item
              v-for="(item, idx) in statStore.recentActivity.slice(0, 6)"
              :key="idx"
              :timestamp="relativeTime(item.createTime)"
              :color="activityColor(item.type)"
              :icon="activityIcon(item.type)"
            >
              <div class="activity-item">
                <span class="activity-desc">{{ item.content }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无学习记录，快去学习吧！" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
// ===== Dashboard.vue — 学习控制台 =====
// 数据来源：statStore（Pinia），不直接调 api/statistics.js
// 页面只读取 store.xxx，保证响应式

import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useStatStore } from '../stores/statStore'
import { getDailyTasks, recordStudyVisit } from '../api/learning'
import { listCourses } from '../api/course'
import { useLearningStore } from '../stores/learning'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { relativeTime } from '../composables/useTime'

const router = useRouter()
const userStore = useUserStore()
const statStore = useStatStore()
const learningStore = useLearningStore()

const dailyTasks = ref({})
const growthChart = ref(null)
const radarChart = ref(null)
let growthChartInst = null
let radarChartInst = null

const activityIconMap = { exam: 'EditPen', chat: 'ChatDotRound', wrong: 'View' }
const activityColorMap = { exam: '#409EFF', chat: '#67C23A', wrong: '#E6A23C' }
function activityIcon(type) { return activityIconMap[type] || 'More' }
function activityColor(type) { return activityColorMap[type] || '#909399' }

// ===== 问候语 =====
const todayDate = computed(() => {
  const now = new Date()
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${['日','一','二','三','四','五','六'][now.getDay()]}`
})
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'; if (h < 9) return '早上好'; if (h < 12) return '上午好'
  if (h < 14) return '中午好'; if (h < 18) return '下午好'; return '晚上好'
})
const welcomeQuotes = ['每天进步一点点，AI的世界等你探索','坚持是最好的学习方法，今天也要加油','知识改变命运，AI创造未来','学习如逆水行舟，不进则退','今天的努力是明天的基石']
const welcomeQuote = ref(welcomeQuotes[Math.floor(Math.random() * welcomeQuotes.length)])
const courseCount = ref(0)

function getStudentName() {
  try {
    const raw = localStorage.getItem('user')
    if (raw) { const state = JSON.parse(raw); const u = state.user || state; return u.username || u.nickname || '学生' }
  } catch { /* */ }
  return '学生'
}

async function fetchCourseCount() {
  try {
    const res = await listCourses()
    const all = res.data?.data?.items || []
    const name = getStudentName()
    courseCount.value = all.filter(c => (c.student_list || []).some(s => s.name === name)).length
  } catch { courseCount.value = 0 }
}

// ===== 快捷功能 =====
const quickActions = [
  { label: '学情自测', desc: '定位知识盲区', icon: 'EditPen', bg: 'linear-gradient(145deg, #4657d8, #6273e6)', route: '/diagnosis' },
  { label: '我的课程', desc: '查看课程及作业', icon: 'Reading', bg: 'linear-gradient(145deg, #4657d8, #6c7cf0)', route: '/my-courses' },
  { label: '学习路径', desc: '规划下一步', icon: 'Guide', bg: 'linear-gradient(145deg, #ff8166, #ef9a67)', route: '/learning-path' },
  { label: '智能答疑', desc: '拆解复杂问题', icon: 'ChatDotRound', bg: 'linear-gradient(145deg, #3899bd, #61bfde)', route: '/qa' },
  { label: '学习资源', desc: '精选可信资料', icon: 'Collection', bg: 'linear-gradient(145deg, #319a7a, #4bc49e)', route: '/resources' },
  { label: '错题本', desc: '回看薄弱环节', icon: 'Notebook', bg: 'linear-gradient(145deg, #d7833b, #ecad55)', route: '/error-book' },
  { label: '学情复盘', desc: '看见真实成长', icon: 'DataAnalysis', bg: 'linear-gradient(145deg, #6953a8, #8c73c4)', route: '/analytics' },
]

// ===== 统计卡片（computed 从 Pinia 取值，保证响应式） =====
const statsCards = computed(() => [
  { label: '学习天数', value: statStore.studyDays, icon: 'Timer', bg: '#eef0fc', color: '#4657d8', route: '/analytics', trend: null },
  { label: '做题总数', value: statStore.totalQuestions, icon: 'EditPen', bg: '#edf9f5', color: '#319a7a', route: '/error-book', trend: null },
  { label: '平均正确率', value: Number(statStore.avgCorrectRate).toFixed(1) + '%', icon: 'TrendCharts', bg: '#fff5ed', color: '#e08243', route: '/analytics', trend: null },
  { label: '已加入课程', value: courseCount.value, icon: 'Reading', bg: '#eef0fc', color: '#4657d8', route: '/my-courses', trend: null },
])

// ===== 今日任务 =====
function enrichTasks(data) { if (!data?.tasks) return data; data.tasks = data.tasks.map(t => ({ ...t, done: data.completed })); return data }

async function markTaskDone() {
  try {
    const isCompleted = dailyTasks.value?.completed
    await learningStore.finishTask('', isCompleted ? 0 : 1)
    dailyTasks.value = enrichTasks(await getDailyTasks()) || {}
    ElMessage.success(isCompleted ? '任务已重新打开' : '今日任务全部完成！')
  } catch (e) { ElMessage.error('更新失败') }
}

// ===== 页面挂载：先注册 watcher，再拉数据（watcher 能捕获初始赋值） =====
onMounted(async () => {
  recordStudyVisit()
  fetchCourseCount()
  // 先注册 watcher，后续 Pinia 变化自动重绘
  watch(() => statStore.weeklyStats, () => { nextTick(() => initGrowthChart()) }, { deep: true })
  watch(() => statStore.moduleMastery, () => { nextTick(() => initRadarChart()) }, { deep: true })
  // 拉数据
  try { await statStore.refreshAll() } catch (e) { console.error(e) }
  // 首次渲染
  await nextTick()
  initGrowthChart()
  initRadarChart()
  try { dailyTasks.value = enrichTasks(await getDailyTasks()) || {} } catch (e) {}
})

// ===== ECharts 图表 =====
function initGrowthChart() {
  if (!growthChart.value) return
  if (!growthChartInst) {
    growthChartInst = echarts.init(growthChart.value)
    window.addEventListener('resize', () => growthChartInst?.resize())
  }
  const data = statStore.weeklyStats
  const dates = data.length > 0 ? data.map(w => (w.date || '').slice(5)) : Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - (6 - i)); return `${d.getMonth() + 1}/${d.getDate()}` })
  growthChartInst.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['做题数量', '正确率(%)'], bottom: 0 },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: [{ type: 'value', name: '题数', minInterval: 1 }, { type: 'value', name: '%', max: 100 }],
    series: [
      { name: '做题数量', type: 'bar', data: data.map(w => w.questions || 0), itemStyle: { color: '#4657d8', borderRadius: [7, 7, 2, 2] }, barWidth: 18 },
      { name: '正确率(%)', type: 'line', yAxisIndex: 1, data: data.map(w => Math.round(w.correct_rate || 0)), itemStyle: { color: '#ff8166' }, smooth: true, symbol: 'circle', symbolSize: 7, lineStyle: { width: 3, color: '#ff8166' } }
    ],
    grid: { left: 60, right: 70, top: 30, bottom: 40 }
  })
}

// 雷达图：展示六大模块掌握度
const hasModuleData = computed(() => Object.keys(statStore.moduleMastery).length > 0)

function initRadarChart() {
  if (!radarChart.value) return
  if (!radarChartInst) {
    radarChartInst = echarts.init(radarChart.value)
    window.addEventListener('resize', () => radarChartInst?.resize())
  }
  const mastery = statStore.moduleMastery
  const keys = Object.keys(mastery || {})
  if (keys.length === 0) return
  const names = statStore.moduleNames || keys
  const values = names.map(n => mastery[n] || 0)
  radarChartInst.setOption({
    tooltip: { trigger: 'item' },
    radar: {
      indicator: names.map(n => ({ name: n.length > 8 ? n.slice(0, 8) + '..' : n, max: 100 })),
      center: ['50%', '55%'], radius: '65%',
      axisName: { color: '#606266', fontSize: 12 }
    },
    series: [{ name: '掌握度', type: 'radar', data: [{ value: values, name: '当前掌握度' }], areaStyle: { color: 'rgba(70, 87, 216, 0.2)' }, lineStyle: { color: '#4657d8', width: 2 }, itemStyle: { color: '#ff8166' }, symbol: 'circle', symbolSize: 6 }]
  })
}
</script>

<style scoped>
.welcome-banner { position: relative; overflow: hidden; margin-bottom: 22px; padding: 29px 34px; border-radius: 22px; color: #fff; background: radial-gradient(circle at 76% 18%, rgba(86,183,220,.26), transparent 25%), linear-gradient(118deg, #1b284d 0%, #202d5c 60%, #324a75 100%); box-shadow: 0 18px 46px rgba(24,36,76,.18); }
.welcome-banner::before, .welcome-banner::after { position: absolute; border: 1px solid rgba(112,196,226,.24); border-radius: 50%; content: ''; transform: rotate(-14deg); }.welcome-banner::before { right: -45px; top: -68px; width: 370px; height: 220px; }.welcome-banner::after { right: 85px; bottom: -120px; width: 290px; height: 220px; }
.welcome-content { position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 28px; }
.welcome-eyebrow { display: block; margin-bottom: 13px; color: #79c7e5; font-size: 10px; font-weight: 750; letter-spacing: .17em; }
.welcome-title { margin: 0 0 9px; color: #fff; font-size: clamp(25px, 2.4vw, 35px); font-weight: 740; letter-spacing: -.035em; }.welcome-subtitle { margin: 0 0 18px; color: rgba(255,255,255,.63); font-size: 13px; }
.welcome-meta { display: flex; align-items: center; gap: 14px; }.stage-badge { display: inline-flex; align-items: center; gap: 7px; padding: 7px 11px; border: 1px solid rgba(255,255,255,.14); border-radius: 999px; color: rgba(255,255,255,.84); background: rgba(255,255,255,.07); font-size: 11px; font-weight: 650; }.stage-badge i { width: 6px; height: 6px; border-radius: 50%; background: #ff927a; }.welcome-date { color: rgba(255,255,255,.4); font-size: 11px; }
.welcome-stats-row { display: flex; gap: 8px; }.welcome-mini-stat { min-width: 94px; padding: 14px 16px; border: 1px solid rgba(255,255,255,.11); border-radius: 15px; text-align: center; background: rgba(255,255,255,.07); backdrop-filter: blur(8px); }.wms-value { color: #fff; font-family: Georgia, serif; font-size: 27px; }.wms-label { margin-top: 5px; color: rgba(255,255,255,.43); font-size: 10px; }
.section-heading { display: flex; align-items: end; justify-content: space-between; margin: 0 2px 13px; }.section-eyebrow { color: var(--primary); font-size: 9px; font-weight: 800; letter-spacing: .16em; }.section-heading h2 { margin: 4px 0 0; color: var(--ink-950); font-size: 18px; }.section-link { padding: 0 2px 2px; border: 0; color: var(--ink-600); background: transparent; font-size: 11px; font-weight: 700; cursor: pointer; }.section-link span { margin-left: 5px; color: var(--primary); }.section-link:hover { color: var(--primary); }
.quick-actions { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 11px; margin-bottom: 14px; }.qa-card { position: relative; display: grid; grid-template-columns: 38px 1fr; grid-template-rows: auto auto; column-gap: 11px; overflow: hidden; padding: 13px; border: 1px solid var(--line); border-radius: 15px; text-align: left; background: rgba(255,255,255,.94); box-shadow: var(--shadow-sm); cursor: pointer; transition: .22s ease; }.qa-card:hover { border-color: #cfd5f3; transform: translateY(-2px); box-shadow: 0 11px 25px rgba(30,45,84,.09); }.qa-icon { display: flex; grid-row: 1 / 3; width: 38px; height: 38px; align-items: center; justify-content: center; border-radius: 11px; color: #fff; box-shadow: 0 7px 15px rgba(44,57,101,.14); }.qa-label { align-self: end; color: var(--ink-950); font-size: 12px; font-weight: 720; }.qa-desc { align-self: start; margin-top: 3px; color: var(--ink-400); font-size: 9px; white-space: nowrap; }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }.stat-card { position: relative; display: flex; align-items: center; gap: 12px; overflow: hidden; min-width: 0; padding: 15px 16px; border: 1px solid var(--line); border-radius: 15px; text-align: left; background: rgba(255,255,255,.94); box-shadow: var(--shadow-sm); cursor: pointer; transition: .2s ease; }.stat-card:hover { border-color: #ccd3ef; transform: translateY(-2px); box-shadow: 0 10px 26px rgba(30,45,84,.09); }.stat-icon-wrap { display: flex; width: 40px; height: 40px; flex-shrink: 0; align-items: center; justify-content: center; border-radius: 12px; }.stat-body { min-width: 0; flex: 1; }.stat-value { margin-top: 2px; color: var(--ink-950); font-family: Georgia, serif; font-size: 23px; font-weight: 650; line-height: 1.05; }.stat-label { color: var(--ink-400); font-size: 10px; }.stat-arrow { color: #ccd2df; font-size: 13px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }.card-title { display: flex; align-items: center; gap: 8px; font-size: 14px; }.task-row { display: flex; gap: 12px; padding: 14px 0; border-bottom: 1px solid #edf0f6; }.task-row:last-child { border: 0; }.task-check { padding-top: 2px; }.task-topic { color: var(--ink-800); font-size: 13px; font-weight: 650; }.task-topic.done { color: var(--ink-400); text-decoration: line-through; }.task-action { margin-top: 4px; color: var(--ink-400); font-size: 11px; }.tips-bar { display: flex; align-items: center; gap: 8px; margin-top: 14px; padding: 11px 14px; border: 1px solid #dce4fb; border-radius: 11px; color: var(--primary); background: #f3f5ff; font-size: 12px; }.task-footer { margin-top: 16px; text-align: center; }.activity-desc { color: var(--ink-600); font-size: 12px; }
@media (max-width: 1240px) { .quick-actions { grid-template-columns: repeat(3,1fr); }.welcome-stats-row { display: none; } }
@media (max-width: 980px) { .stats-grid { grid-template-columns: repeat(2,1fr); } }
@media (max-width: 720px) { .welcome-banner { padding: 25px 22px; border-radius: 19px; }.welcome-title { font-size: 24px; }.welcome-date { display: none; }.section-link { display: none; }.quick-actions { grid-template-columns: repeat(2,1fr); gap: 9px; }.qa-card { padding: 12px; }.stat-card { padding: 13px; }.stat-value { font-size: 22px; } }
@media (max-width: 430px) { .quick-actions, .stats-grid { grid-template-columns: 1fr; } }
</style>
