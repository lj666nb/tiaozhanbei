<template>
  <div class="task-list-page">
    <div class="top-bar">
      <div>
        <el-breadcrumb separator=">">
          <el-breadcrumb-item :to="{ name: 'ModuleSelect' }">编程实验室</el-breadcrumb-item>
          <el-breadcrumb-item>{{ currentModule?.name || '加载中...' }}</el-breadcrumb-item>
        </el-breadcrumb>
        <p class="top-project">阶段项目 · {{ currentModule?.project }}</p>
      </div>
      <button class="history-btn" @click="$router.push({ name: 'LabHistory' })">
        <el-icon><Clock /></el-icon> 已完成记录
      </button>
    </div>

    <div class="task-body">
      <div class="task-sidebar">
        <div class="sidebar-header">
          <div class="sidebar-heading">
            <span class="sidebar-title">关卡目录</span>
            <span class="sidebar-count">{{ completedCount }}/{{ currentModule?.taskCount || 0 }} 已完成</span>
          </div>
          <div class="sidebar-progress"><i :style="{ width: `${moduleProgress}%` }"></i></div>
        </div>
        <div class="sidebar-list">
          <div
            v-for="(task, index) in currentModule?.tasks || []"
            :key="task.id"
            class="task-item"
            :class="{ active: selectedTaskId === task.id, completed: isCompleted(task.id) }"
            @click="selectTask(task)"
          >
            <div class="task-num">{{ index + 1 }}</div>
            <div class="task-text">
              <div class="task-label">关卡 {{ task.id }}</div>
              <div class="task-name">{{ task.title }}</div>
            </div>
            <span v-if="getScoreBadge(task.id)" :class="['task-score-badge', getScoreBadge(task.id).cls]">
              {{ getScoreBadge(task.id).text }}
            </span>
            <span v-else-if="isCompleted(task.id)" class="task-dot done">✓</span>
            <span v-else class="task-dot pending">○</span>
          </div>
        </div>
      </div>

      <div class="task-main">
        <div v-if="selectedTask" class="task-preview">
          <div class="preview-copy">
            <span class="preview-eyebrow">LEVEL {{ selectedTask.id }}</span>
            <div class="preview-tags">
              <el-tag size="small" type="primary" effect="plain">{{ currentModule?.level }}阶段</el-tag>
              <span><el-icon><Timer /></el-icon>{{ selectedTask.duration }}</span>
            </div>
            <h3>构造能力，而不只是通过测试</h3>
            <h2>{{ selectedTask.title }}</h2>
            <p class="project-name">你正在完成「{{ currentModule?.project }}」的一部分。本关会经过代码测试、原理答辩、故障修复<template v-if="currentModule?.id !== 1">与变式迁移</template>，形成完整能力闭环。</p>
            <div class="capability-flow" aria-label="能力验证流程">
              <span><i>1</i>代码实现</span>
              <b>→</b>
              <span><i>2</i>自动测试</span>
              <b>→</b>
              <span><i>3</i>能力验证</span>
            </div>
            <div class="preview-action">
              <el-button type="primary" size="large" @click="enterTask(selectedTask)">
                {{ getScoreDetail(selectedTask.id) ? '重新进入关卡' : '开始挑战' }}
              </el-button>
              <small>{{ getScoreDetail(selectedTask.id) ? '已有记录会保留，可继续完善' : '将在独立实验工作区中打开' }}</small>
            </div>
          </div>

          <aside class="result-panel">
            <div v-if="getScoreDetail(selectedTask.id)" class="score-detail">
              <div class="result-heading">
                <div>
                  <span>LEARNING RECORD</span>
                  <strong>本关学习记录</strong>
                </div>
                <div :class="['score-circle', getScoreLevel(getScoreDetail(selectedTask.id).score)]">
                  <span class="score-number">{{ getScoreDetail(selectedTask.id).score }}</span>
                  <span class="score-label">综合分</span>
                </div>
              </div>
              <div class="score-breakdown">
                <div class="score-row">
                  <span>自动测试</span>
                  <span :class="getScoreDetail(selectedTask.id).test_score >= 60 ? 'pass' : 'fail'">{{ getScoreDetail(selectedTask.id).test_score || 0 }} 分</span>
                </div>
                <div class="score-row">
                  <span>原理答辩</span>
                  <span>{{ getScoreDetail(selectedTask.id).defense_grading_status === 'completed' ? `${getScoreDetail(selectedTask.id).defense_score || 0} 分` : 'AI 分析中' }}</span>
                </div>
                <div class="score-row"><span>故障修复</span><span>{{ getScoreDetail(selectedTask.id).repair_score || 0 }} 分</span></div>
                <div v-if="currentModule?.id !== 1" class="score-row"><span>变式迁移</span><span>{{ getScoreDetail(selectedTask.id).variant_score || 0 }} 分</span></div>
                <div class="verification-state">
                  <span>{{ getScoreDetail(selectedTask.id).skipped ? '已跳过能力验证' : getScoreDetail(selectedTask.id).verified ? '能力验证已完成' : '能力验证进行中' }}</span>
                  <i :class="{ warn: getScoreDetail(selectedTask.id).skipped }"></i>
                </div>
                <button
                  v-if="getScoreDetail(selectedTask.id).session_id && getScoreDetail(selectedTask.id).defense_feedback.length"
                  class="score-detail-button"
                  @click="openScoreReview(selectedTask.id)"
                >
                  查看 AI 逐题反馈与修复评分
                </button>
              </div>
            </div>
            <div v-else class="empty-result">
              <span>NOT STARTED</span>
              <div class="empty-result-icon"><el-icon><DataAnalysis /></el-icon></div>
              <strong>等待你的首次记录</strong>
              <p>完成测试与能力验证后，评分拆解和 AI 反馈会保存在这里。</p>
            </div>
          </aside>
        </div>
        <el-empty v-else description="请从左侧关卡选择" :image-size="80" />
      </div>
    </div>

    <el-dialog v-model="scoreDialog" width="840px" title="关卡评分详情" class="score-review-dialog">
      <div v-if="scoreLoading" class="score-review-loading">正在读取已保存的评分...</div>
      <div v-else class="score-review-content">
        <div class="score-review-summary">
          <div><small>原理答辩</small><b>{{ scoreReview.defense_grading_status === 'completed' ? `${scoreReview.defense_score || 0}分` : 'AI 评分中' }}</b></div>
          <div><small>故障修复</small><b>{{ scoreReview.repair_score || 0 }}分</b></div>
          <div><small>保存状态</small><b>已写入学习档案</b></div>
        </div>
        <section>
          <h3>原理答辩 · AI 逐题反馈</h3>
          <article v-for="(item, index) in scoreReview.review_items || []" :key="item.question_id" class="saved-review-card">
            <div class="saved-review-title">
              <b>{{ index + 1 }}. {{ item.prompt }}</b>
              <span>{{ item.grading_status === 'completed' ? `${item.user_score || 0}分` : '评分中' }}</span>
            </div>
            <p><strong>你的回答：</strong>{{ item.user_answer || '未作答' }}</p>
            <p class="ai-feedback"><strong>AI 反馈：</strong>{{ item.feedback || '答辩已完成，AI 正在后台分析' }}</p>
            <p v-if="item.missing_points?.length" class="missing-feedback">
              <strong>待补充：</strong>{{ item.missing_points.join(' · ') }}
            </p>
          </article>
        </section>
        <section v-if="scoreReview.repair_review?.explanation || scoreReview.repair_score">
          <h3>故障修复 · 评分拆解</h3>
          <div class="repair-review-summary">
            <div><small>测试恢复</small><b>{{ scoreReview.repair_review?.test_score || 0 }} / 80</b></div>
            <div><small>根因说明</small><b>{{ scoreReview.repair_review?.explanation_score || 0 }} / 20</b></div>
            <div><small>通过用例</small><b>{{ scoreReview.repair_review?.passed_count || 0 }} / {{ scoreReview.repair_review?.total || 0 }}</b></div>
          </div>
          <p v-if="scoreReview.repair_review?.description"><strong>注入故障：</strong>{{ scoreReview.repair_review.description }}</p>
          <p v-if="scoreReview.repair_review?.explanation"><strong>修复说明：</strong>{{ scoreReview.repair_review.explanation }}</p>
        </section>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { MODULES } from '../config/flagshipExercises'
import { getLabProgressOverview } from '../api/workspace'
import { getSessionReview } from '../api/capability'

const router = useRouter()
const route = useRoute()

const moduleId = computed(() => parseInt(route.params.moduleId))
const currentModule = computed(() => MODULES.find(m => m.id === moduleId.value))
const selectedTaskId = ref(currentModule.value?.tasks?.[0]?.id ?? null)
const selectedTask = ref(currentModule.value?.tasks?.[0] ?? null)
const progressData = ref({})
const scoreDialog = ref(false)
const scoreLoading = ref(false)
const scoreReview = ref({})
const completedCount = computed(() => (currentModule.value?.tasks || []).filter(task => isCompleted(task.id)).length)
const moduleProgress = computed(() => currentModule.value?.taskCount
  ? Math.round(completedCount.value / currentModule.value.taskCount * 100)
  : 0)

/**
 * 加载进度数据（含分数）
 */
onMounted(async () => {
  try {
    const data = await getLabProgressOverview()
    progressData.value = data || {}
  } catch (_) {
    progressData.value = {}
  }
})

/**
 * 选择关卡（右侧显示预览，不直接跳转）
 */
function selectTask(task) {
  selectedTaskId.value = task.id
  selectedTask.value = task
}

/**
 * 进入代码编辑页面
 */
function enterTask(task) {
  router.push({
    name: 'CodeLab',
    params: { moduleId: moduleId.value, taskId: task.id }
  })
}

function isCompleted(taskId) {
  return !!getScoreDetail(taskId)
}

/**
 * 获取分数详情（从后端 progress 数据）
 */
function getScoreDetail(taskId) {
  const info = progressData.value[taskId]
  if (!info) return null
  if (info.score == null && !info.verified && !info.skipped) {
    // acceptance passed 但无分数 → 不显示分数
    if (!info.acceptance_passed) return null
  }
  if (info.score == null && !info.verified && !info.skipped) return null
  return {
    score: info.score || 0,
    test_score: info.test_score || 0,
    defense_score: info.defense_score || 0,
    repair_score: info.repair_score || 0,
    variant_score: info.variant_score || 0,
    session_id: info.session_id || null,
    defense_feedback: Array.isArray(info.defense_feedback) ? info.defense_feedback : [],
    verified: info.verified || false,
    skipped: info.skipped || false,
    status: info.status || '',
    defense_grading_status: info.defense_grading_status || 'not_started',
  }
}

async function openScoreReview(taskId) {
  const detail = getScoreDetail(taskId)
  if (!detail?.session_id) return
  scoreDialog.value = true
  scoreLoading.value = true
  scoreReview.value = {}
  try {
    scoreReview.value = await getSessionReview(detail.session_id)
  } finally {
    scoreLoading.value = false
  }
}

/**
 * 获取分数徽标
 */
function getScoreBadge(taskId) {
  const detail = getScoreDetail(taskId)
  if (!detail) return null
  if (detail.verified) {
    const level = getScoreLevel(detail.score)
    return { text: `${detail.score}分`, cls: level }
  }
  if (detail.skipped) {
    return { text: `${detail.score}分`, cls: 'skipped' }
  }
  return null
}

function getScoreLevel(score) {
  if (score >= 90) return 'excellent'
  if (score >= 75) return 'good'
  if (score >= 60) return 'pass'
  return 'low'
}
</script>

<style scoped>
.task-list-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #f5f6f8;
}
.top-bar {
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.history-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border: 1px solid #409eff;
  border-radius: 6px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  cursor: pointer;
  transition: all .2s;
}
.history-btn:hover {
  background: #409eff;
  color: #fff;
}
.task-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ===== 左侧关卡目录 ===== */
.task-sidebar {
  width: 320px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
}
.sidebar-count {
  font-size: 12px;
  color: #909399;
}
.sidebar-list {
  flex: 1;
  overflow-y: auto;
}

/* 关卡条目 */
.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f5f5f5;
  transition: background .15s;
}
.task-item:hover {
  background: #f5f7fa;
}
.task-item.active {
  background: #e6f0ff;
  border-left: 3px solid #409EFF;
}
.task-item.completed .task-num {
  background: #67C23A;
}
.task-num {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  background: #c0c4cc;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.task-item.active .task-num {
  background: #409EFF;
}
.task-text {
  flex: 1;
  min-width: 0;
}
.task-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 2px;
}
.task-name {
  font-size: 13px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-dot {
  font-size: 16px;
  flex-shrink: 0;
}
.task-dot.done {
  color: #67C23A;
}
.task-dot.pending {
  color: #c0c4cc;
}

/* 分数徽标 */
.task-score-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 10px;
  flex-shrink: 0;
  white-space: nowrap;
}
.task-score-badge.excellent {
  background: #e6f7e6;
  color: #2e8b57;
  border: 1px solid #a3d9a3;
}
.task-score-badge.good {
  background: #e6f4ff;
  color: #2979c1;
  border: 1px solid #93c5fd;
}
.task-score-badge.pass {
  background: #fff8e6;
  color: #b8860b;
  border: 1px solid #f0d78c;
}
.task-score-badge.low {
  background: #fff0f0;
  color: #c0392b;
  border: 1px solid #f5a6a6;
}
.task-score-badge.skipped {
  background: #f5f5f5;
  color: #888;
  border: 1px solid #d0d0d0;
}
.task-score-badge.old {
  font-size: 12px;
  color: #67C23A;
  padding: 0;
  background: none;
  border: none;
}

/* ===== 右侧预览区 ===== */
.task-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.task-preview {
  text-align: center;
  max-width: 420px;
}
.task-preview h3 {
  font-size: 18px;
  color: #1a1a2e;
  margin: 0 0 8px;
}
.preview-hint {
  font-size: 14px;
  color: #909399;
  margin: 0 0 20px;
}
.project-name { color: #303133; font-size: 14px; font-weight: 600; margin: 10px 0 4px; }
.task-duration { color: #909399; font-size: 13px; margin: 0 0 14px; }
.completion-info {
  background: #f0f9eb;
  border: 1px solid #c2e7b0;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.completion-info p {
  font-size: 13px;
  color: #606266;
  margin: 4px 0;
}
.old-score-hint {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}

/* 分数详情面板 */
.score-detail {
  background: #fafbff;
  border: 1px solid #e0e4f0;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
.score-ring-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}
.score-circle {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 4px solid #c0c4cc;
}
.score-circle.excellent { border-color: #2e8b57; background: #f0faf4; }
.score-circle.good { border-color: #2979c1; background: #f0f6ff; }
.score-circle.pass { border-color: #e6a817; background: #fffdf5; }
.score-circle.low { border-color: #c0392b; background: #fff5f5; }
.score-number {
  font-size: 22px;
  font-weight: 800;
  color: #1a1a2e;
  line-height: 1;
}
.score-label {
  font-size: 10px;
  color: #909399;
  margin-top: 2px;
}
.score-breakdown {
  text-align: left;
  font-size: 12px;
}
.score-row {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  color: #606266;
}
.score-row span:last-child {
  font-weight: 600;
}
.score-row .pass { color: #2e8b57; }
.score-row .fail { color: #c0392b; }
.score-row .warn { color: #e6a817; }
.score-detail-button {
  width: 100%;
  margin-top: 10px;
  padding: 7px 10px;
  border: 1px solid #9abdf1;
  border-radius: 6px;
  color: #2876c7;
  background: #eef6ff;
  cursor: pointer;
}
.score-detail-button:hover { background: #dceeff; }
.score-review-loading { padding: 48px; text-align: center; color: #909399; }
.score-review-content { display: grid; gap: 20px; color: #303133; }
.score-review-summary,
.repair-review-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.score-review-summary > div,
.repair-review-summary > div {
  padding: 12px;
  border: 1px solid #e1e7f0;
  border-radius: 8px;
  background: #f7f9fc;
}
.score-review-summary small,
.repair-review-summary small,
.score-review-summary b,
.repair-review-summary b { display: block; }
.score-review-summary small,
.repair-review-summary small { color: #909399; }
.score-review-summary b,
.repair-review-summary b { margin-top: 5px; color: #1f2d3d; }
.score-review-content section h3 { margin: 0 0 10px; font-size: 15px; }
.saved-review-card {
  margin-bottom: 10px;
  padding: 13px;
  border: 1px solid #e1e7f0;
  border-radius: 8px;
  background: #fff;
}
.saved-review-title { display: flex; align-items: flex-start; gap: 12px; }
.saved-review-title b { flex: 1; line-height: 1.6; }
.saved-review-title span { color: #6c5ce7; font-weight: 700; white-space: nowrap; }
.saved-review-card p,
.score-review-content section > p { margin: 8px 0 0; color: #606266; line-height: 1.65; }
.saved-review-card strong,
.score-review-content section > p strong { color: #303133; }
.saved-review-card .ai-feedback { padding: 9px; border-radius: 6px; background: #f1efff; }
.saved-review-card .missing-feedback { color: #c45656; }

/* Refined learning workspace */
.task-list-page {
  background:
    radial-gradient(circle at 82% 8%, rgba(86, 183, 220, .08), transparent 26%),
    #f7f8fc;
}
.top-bar {
  min-height: 66px;
  padding: 10px 18px;
  border-bottom-color: var(--line);
  background: rgba(255,255,255,.94);
}
.top-project { margin: 7px 0 0; color: var(--ink-400); font-size: 10px; }
.history-btn {
  padding: 8px 13px;
  border-color: #cbd2f2;
  border-radius: 10px;
  color: var(--primary);
  background: #f5f6ff;
  font-size: 11px;
  font-weight: 700;
}
.history-btn:hover { border-color: var(--primary); background: var(--primary); }
.task-sidebar { width: 300px; border-right-color: var(--line); }
.sidebar-header { display: block; padding: 17px 16px 15px; }
.sidebar-heading { display: flex; align-items: center; justify-content: space-between; }
.sidebar-progress { overflow: hidden; height: 4px; margin-top: 12px; border-radius: 999px; background: #edf0f7; }
.sidebar-progress i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--primary), var(--sky)); transition: width .3s ease; }
.task-item {
  min-height: 62px;
  padding: 11px 14px;
  border-left: 3px solid transparent;
  border-bottom-color: #f1f3f7;
  transition: background .15s, border-color .15s;
}
.task-item.active { border-left-color: var(--primary); background: #eef0fc; }
.task-num { width: 30px; height: 30px; border-radius: 9px; }
.task-main { padding: clamp(24px, 4vw, 56px); }
.task-preview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: clamp(24px, 4vw, 52px);
  align-items: center;
  width: min(100%, 820px);
  max-width: none;
  text-align: left;
}
.preview-eyebrow {
  display: block;
  margin-bottom: 11px;
  color: var(--primary);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .18em;
}
.preview-tags { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
.preview-tags > span { display: flex; align-items: center; gap: 4px; color: var(--ink-400); font-size: 10px; }
.task-preview h3 { margin: 0 0 7px; color: var(--ink-400); font-size: 12px; font-weight: 650; }
.task-preview h2 { margin: 0; color: var(--ink-950); font-size: clamp(24px, 2.7vw, 34px); line-height: 1.2; letter-spacing: -.04em; }
.project-name { max-width: 560px; margin: 16px 0 22px; color: var(--ink-600); font-size: 12px; font-weight: 400; line-height: 1.75; }
.capability-flow { display: flex; align-items: center; gap: 9px; margin-bottom: 25px; }
.capability-flow span { display: flex; align-items: center; gap: 6px; color: var(--ink-600); font-size: 10px; font-weight: 700; white-space: nowrap; }
.capability-flow span i { display: grid; width: 20px; height: 20px; place-items: center; border-radius: 7px; color: var(--primary); background: #eef0fc; font-style: normal; }
.capability-flow b { color: #cbd2e0; font-weight: 400; }
.preview-action { display: flex; align-items: center; gap: 13px; }
.preview-action small { max-width: 150px; color: var(--ink-400); font-size: 9px; line-height: 1.5; }
.result-panel {
  min-height: 330px;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255,255,255,.9);
  box-shadow: 0 16px 38px rgba(30,45,84,.09);
}
.score-detail { height: 100%; margin: 0; padding: 0; border: 0; background: transparent; }
.result-heading { display: flex; align-items: center; justify-content: space-between; padding-bottom: 15px; border-bottom: 1px solid #edf0f6; }
.result-heading > div:first-child span,
.result-heading > div:first-child strong { display: block; }
.result-heading > div:first-child span { color: var(--primary); font-size: 8px; font-weight: 800; letter-spacing: .14em; }
.result-heading > div:first-child strong { margin-top: 5px; color: var(--ink-950); font-size: 13px; }
.score-circle { width: 66px; height: 66px; }
.score-breakdown { padding-top: 12px; }
.score-row { padding: 6px 0; }
.verification-state { display: flex; align-items: center; justify-content: space-between; margin-top: 9px; padding: 10px 11px; border-radius: 10px; color: #237e64; background: #edf9f5; font-size: 10px; font-weight: 700; }
.verification-state i { width: 7px; height: 7px; border-radius: 50%; background: var(--mint); box-shadow: 0 0 0 4px rgba(57,185,145,.13); }
.verification-state i.warn { background: var(--amber); box-shadow: 0 0 0 4px rgba(233,168,58,.13); }
.score-detail-button { margin-top: 11px; padding: 9px 10px; border-color: #cbd2f2; border-radius: 10px; color: var(--primary); background: #f4f5ff; font-size: 10px; font-weight: 700; }
.empty-result { display: flex; min-height: 288px; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.empty-result > span { color: var(--primary); font-size: 8px; font-weight: 800; letter-spacing: .16em; }
.empty-result-icon { display: grid; width: 62px; height: 62px; margin: 25px 0 17px; place-items: center; border-radius: 18px; color: var(--primary); background: #eef0fc; font-size: 26px; }
.empty-result strong { color: var(--ink-950); font-size: 14px; }
.empty-result p { max-width: 220px; margin: 8px 0 0; color: var(--ink-400); font-size: 10px; line-height: 1.7; }
@media (max-width: 1120px) {
  .task-preview { grid-template-columns: 1fr 270px; gap: 24px; }
  .capability-flow { flex-wrap: wrap; }
  .capability-flow b { display: none; }
}
@media (max-width: 760px) {
  .top-project { display: none; }
  .task-preview { grid-template-columns: 1fr; }
  .result-panel { min-height: 0; }
  .preview-action { align-items: flex-start; flex-direction: column; }
  .score-review-summary, .repair-review-summary { grid-template-columns: 1fr; }
}
</style>
