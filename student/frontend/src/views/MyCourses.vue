<template>
  <div class="my-courses" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title">我加入的全部课程</h2>
      <el-button type="primary" size="small" @click="$router.push('/join-class')" :icon="Plus">
        加入新课程
      </el-button>
    </div>

    <el-empty v-if="!loading && courses.length === 0" description="你还没有加入任何课程"
      :image-size="120">
      <el-button type="primary" @click="$router.push('/join-class')">输入班级编号加入</el-button>
    </el-empty>

    <div v-else class="course-grid">
      <div v-for="c in courses" :key="c.id" class="course-card">
        <!-- 课程头部 -->
        <div class="card-top">
          <div class="card-title-row">
            <h3 class="course-name">{{ c.name }}</h3>
            <el-tag :type="statusTagType(c.status)" size="small" effect="light" round>
              {{ c.status || '进行中' }}
            </el-tag>
          </div>
          <div class="course-meta">
            <span class="meta-code">{{ c.code || c.class_code || '未设置编号' }}</span>
            <span class="meta-divider">·</span>
            <span class="meta-teacher">{{ c.teacher }}</span>
          </div>
        </div>

        <!-- 进度条 -->
        <div class="card-progress">
          <div class="progress-label">
            <span>课程进度</span>
            <span class="progress-pct">{{ c.progress || 0 }}%</span>
          </div>
          <el-progress :percentage="c.progress || 0" :stroke-width="8"
            :color="progressColor(c.progress)" :show-text="false" />
          <div class="progress-extra">
            <span>{{ c.students || 0 }} 名同学</span>
            <span>{{ c.sessions || 0 }} 课时</span>
            <span v-if="homeworkCount(c.name) > 0" class="hw-indicator">
              作业 · {{ homeworkCount(c.name) }}
            </span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="card-actions">
          <el-button size="small" type="primary" :icon="Notebook"
            @click="toggleHomework(c)">
            {{ expandedCourse === c.name ? '收起作业' : '查看作业' }}
          </el-button>
          <el-button size="small" :icon="Collection" class="action-btn"
            @click="$router.push({ path: '/resources' })">
            学习资料
          </el-button>
          <el-button size="small" :icon="ChatLineSquare" class="action-btn"
            @click="$router.push({ path: '/messaging', query: { teacher: c.teacher } })">
            联系教师
          </el-button>
          <el-button size="small" :icon="TrendCharts" class="action-btn"
            @click="$router.push({ path: '/analytics' })">
            学习统计
          </el-button>
        </div>

        <!-- 行内作业列表 -->
        <div v-if="expandedCourse === c.name" class="homework-inline" v-loading="hwLoading">
          <el-empty v-if="!hwLoading && courseAssignments.length === 0 && courseSubmissions.length === 0"
            description="暂无作业" :image-size="60" />
          <div v-else class="hw-list">
            <!-- 待提交 -->
            <div v-for="a in courseAssignments" :key="a.id" class="hw-item pending">
              <div class="hw-item-header">
                <el-tag size="small" type="danger" effect="dark" round>待提交</el-tag>
                <span class="hw-title">{{ a.title }}</span>
              </div>
              <div class="hw-item-body" v-if="a.content">
                {{ a.content.slice(0, 120) }}{{ a.content.length > 120 ? '…' : '' }}
              </div>
              <div class="hw-item-foot" v-if="a.deadline">
                <el-icon :size="13"><Clock /></el-icon>
                <span :class="{ urgent: isUrgent(a.deadline) }">截止 {{ a.deadline?.slice(0, 16) }}</span>
                <el-button size="small" type="primary" text @click.stop="openSubmit(a)">提交</el-button>
              </div>
            </div>
            <!-- 已批改 -->
            <div v-for="s in courseSubmissions" :key="s.id" class="hw-item graded">
              <div class="hw-item-header">
                <el-tag size="small" type="success" effect="dark" round>已批改</el-tag>
                <span class="hw-title">{{ s.title || '作业' }}</span>
                <span class="hw-score" :class="scoreClass(s.score)">{{ s.score ?? '-' }}分</span>
              </div>
              <div class="hw-item-body" v-if="s.feedback">
                💬 {{ s.feedback.slice(0, 100) }}
              </div>
            </div>
          </div>
          <el-button v-if="courseAssignments.length > 0" size="small" text type="primary"
            style="margin-top:8px;width:100%"
            @click="$router.push({ path: '/my-homework', query: { course: expandedCourse } })">
            查看全部作业 →
          </el-button>
        </div>
      </div>
    </div>

    <!-- 提交作业弹窗 -->
    <el-dialog v-model="submitOpen" title="提交作业" width="520px" :close-on-click-modal="false">
      <div style="margin-bottom:8px;color:var(--ink-600)">{{ submitting?.title }}</div>
      <el-input v-model="answerText" type="textarea" :rows="5" placeholder="输入你的答案…" />
      <template #footer>
        <el-button @click="submitOpen = false">取消</el-button>
        <el-button type="primary" @click="doSubmit" :loading="submitting2">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Plus, Notebook, Collection, ChatLineSquare, TrendCharts, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { listCourses } from '../api/course'
import { listAssignments, submitHomework, getMySubmissions } from '../api/homework'

const loading = ref(false)
const hwLoading = ref(false)
const courses = ref([])
const expandedCourse = ref(null)
const courseAssignments = ref([])
const courseSubmissions = ref([])
const submitOpen = ref(false)
const submitting = ref(null)
const answerText = ref('')
const submitting2 = ref(false)

function getStudentName() {
  try {
    const raw = localStorage.getItem('user')
    if (raw) {
      const state = JSON.parse(raw)
      const user = state.user || state
      return user.username || user.nickname || '学生'
    }
  } catch { /* */ }
  return '学生'
}

function statusTagType(status) {
  if (status === '已结课') return 'info'
  if (status === '已过半') return 'warning'
  return 'primary'
}

function progressColor(pct) {
  if (pct >= 100) return '#52c41a'
  if (pct >= 50) return '#fa8c16'
  return '#4657d8'
}

function isUrgent(deadline) {
  return deadline ? dayjs(deadline).diff(dayjs(), 'hour') < 24 : false
}

function scoreClass(s) {
  if (s == null) return ''
  if (s >= 80) return 'score-high'
  if (s >= 60) return 'score-mid'
  return 'score-low'
}

// 作业计数（页面上展示用，每门课单独标记）
const _hwCounts = ref({})
function homeworkCount(courseName) {
  return _hwCounts.value[courseName] || 0
}

async function load() {
  loading.value = true
  try {
    const res = await listCourses()
    const all = res.data?.data?.items || []
    const name = getStudentName()
    courses.value = all.filter(c =>
      (c.student_list || []).some(s => s.name === name)
    )
    // 加载作业计数
    try {
      const [aRes, sRes] = await Promise.all([listAssignments(), getMySubmissions()])
      const list = aRes.data?.data?.assignments || aRes.data?.assignments || []
      const subs = sRes.data?.data?.submissions || sRes.data?.submissions || []
      const subIds = new Set(subs.map(s => s.assignment_id))
      const counts = {}
      list.forEach(a => {
        if (subIds.has(a.id) || a.status === 'closed') return
        const cn = a.course_name || ''
        if (cn) counts[cn] = (counts[cn] || 0) + 1
      })
      _hwCounts.value = counts
    } catch { /* */ }
  } catch { courses.value = [] }
  finally { loading.value = false }
}

async function toggleHomework(c) {
  if (expandedCourse.value === c.name) {
    expandedCourse.value = null
    return
  }
  expandedCourse.value = c.name
  hwLoading.value = true
  try {
    const [aRes, sRes] = await Promise.all([
      listAssignments({ course: c.name }),
      getMySubmissions(),
    ])
    const list = aRes.data?.data?.assignments || aRes.data?.assignments || []
    const subs = sRes.data?.data?.submissions || sRes.data?.submissions || []
    const subIds = new Set(subs.map(s => s.assignment_id))
    // 合并已提交的评分信息到 submission 列表
    const gradedSubs = subs.filter(s => s.status === 'graded').map(s => {
      const a = list.find(a => a.id === s.assignment_id)
      return { ...s, title: a?.title || '', course_name: a?.course_name || '' }
    }).filter(s => s.course_name === c.name)
    courseAssignments.value = list.filter(a => !subIds.has(a.id) && a.status !== 'closed')
    courseSubmissions.value = gradedSubs
  } catch {
    courseAssignments.value = []
    courseSubmissions.value = []
  }
  finally { hwLoading.value = false }
}

function openSubmit(a) {
  submitting.value = a
  answerText.value = ''
  submitOpen.value = true
}

async function doSubmit() {
  if (!submitting.value) return
  submitting2.value = true
  try {
    await submitHomework(submitting.value.id, { content: answerText.value })
    ElMessage.success('提交成功！')
    submitOpen.value = false
    // 刷新当前课程的作业列表
    const c = courses.value.find(x => x.name === expandedCourse.value)
    if (c) await toggleHomework(c)
  } catch { ElMessage.error('提交失败') }
  finally { submitting2.value = false }
}

onMounted(() => { load() })
</script>

<style scoped>
.my-courses {
  max-width: 1200px;
  margin: 0 auto;
  padding: 8px 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 750;
  color: var(--ink-950, #10182f);
  margin: 0;
  padding-left: 16px;
  border-left: 4px solid var(--primary, #4657d8);
  line-height: 1.3;
}

.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}

.course-card {
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e5eaf3);
  border-radius: var(--radius-md, 16px);
  padding: 24px;
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(24,35,67,.04), 0 8px 24px rgba(30,45,84,.06));
  transition: transform .2s, box-shadow .2s;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.course-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md, 0 18px 48px rgba(30,45,84,.12));
}

.card-top {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.course-name {
  font-size: 17px;
  font-weight: 720;
  color: var(--ink-950, #10182f);
  margin: 0;
  line-height: 1.3;
}

.course-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-400, #8e99ae);
}

.meta-code {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  background: #f0f2f8;
  padding: 1px 8px;
  border-radius: 6px;
  color: var(--ink-600, #53617d);
}

.meta-teacher {
  color: var(--ink-600, #53617d);
}

.card-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--ink-600, #53617d);
}

.progress-pct {
  font-weight: 700;
  font-family: Georgia, serif;
  color: var(--ink-800, #243252);
}

.progress-extra {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--ink-400, #8e99ae);
}

.hw-indicator {
  color: var(--primary, #4657d8);
  font-weight: 650;
}

.card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: auto;
}

.card-actions .el-button {
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.action-btn {
  color: var(--ink-600, #53617d) !important;
  background: #f2f4f9 !important;
  border: 1px solid var(--line, #e5eaf3) !important;
}

.action-btn:hover {
  color: var(--primary, #4657d8) !important;
  background: #e8ebf6 !important;
  border-color: var(--primary, #4657d8) !important;
}

/* ── 行内作业列表 ── */
.homework-inline {
  border-top: 1px solid var(--line, #e5eaf3);
  padding-top: 12px;
  margin-top: -4px;
}

.hw-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hw-item {
  background: #f8f9fc;
  border-radius: 10px;
  padding: 12px 14px;
  border-left: 3px solid var(--line, #e5eaf3);
}

.hw-item.pending {
  border-left-color: #e63e3e;
}

.hw-item.graded {
  border-left-color: #52c41a;
}

.hw-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hw-title {
  font-size: 13px;
  font-weight: 620;
  color: var(--ink-800, #243252);
  flex: 1;
}

.hw-score {
  font-weight: 700;
  font-family: Georgia, serif;
  font-size: 14px;
}

.score-high { color: #52c41a; }
.score-mid { color: #fa8c16; }
.score-low { color: #e63e3e; }

.hw-item-body {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-400, #8e99ae);
  line-height: 1.5;
}

.hw-item-foot {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--ink-400, #8e99ae);
}

.hw-item-foot .urgent {
  color: #e63e3e;
  font-weight: 600;
}
</style>
