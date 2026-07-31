<template>
  <div class="error-book-page">
    <PageHero
      v-if="activeSession === undefined"
      eyebrow="ERROR REVIEW"
      title="错题本"
      description="按测评整理错误原因和复习进度，把每一次失误变成可追踪的知识补强任务。"
      icon="EditPen"
    >
      <template #meta>
        <el-tag type="danger" effect="plain">{{ totalErrors }} 道错题</el-tag>
        <el-tag effect="plain">{{ sessions.length }} 次测评</el-tag>
      </template>
      <template #actions>
        <el-button type="primary" @click="$router.push('/diagnosis')">开始新测评</el-button>
      </template>
    </PageHero>
    <!-- 第一级：测评会话列表 -->
    <el-card v-if="activeSession === undefined" shadow="hover" v-loading="loading" class="error-overview-card">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div class="error-list-heading"><span>REVIEW QUEUE</span><strong>待复习记录</strong></div>
          <div style="display:flex;align-items:center;gap:8px">
            <el-button
              v-if="selectedSessions.size > 0"
              type="danger"
              @click="handleBatchDeleteSessions"
              :loading="batchDeleting"
            >
              <el-icon><Delete /></el-icon> 批量删除 ({{ selectedSessions.size }})
            </el-button>
            <el-tag type="info" effect="plain">按最近测评排序</el-tag>
          </div>
        </div>
      </template>

      <el-empty v-if="sessions.length === 0 && !loading" description="暂无错题，继续保持！">
        <el-button type="primary" @click="$router.push('/diagnosis')">去做测评</el-button>
      </el-empty>

      <!-- 全选工具栏 -->
      <div v-if="sessions.length > 0" class="batch-toolbar">
        <el-checkbox
          v-model="sessionSelectAll"
          :indeterminate="sessionIndeterminate"
          @change="handleSessionSelectAll"
        >
          全选
        </el-checkbox>
        <span class="batch-hint" v-if="selectedSessions.size > 0">已选 {{ selectedSessions.size }} 组</span>
      </div>

      <div
        v-for="s in sessions"
        :key="s.session_id ?? 'orphan'"
        class="session-card"
        :class="{ 'is-selected': selectedSessions.has(deleteKey(s)) }"
      >
        <div class="session-select" @click.stop>
          <el-checkbox
            :model-value="selectedSessions.has(deleteKey(s))"
            @change="(val) => toggleSessionSelect(s, val)"
          />
        </div>
        <div class="session-body" @click="openSession(s)">
          <div class="session-left">
            <div class="session-label">{{ s.label }}</div>
            <div class="session-meta">
              <span v-if="s.quiz_time">{{ s.quiz_time }}</span>
              <span v-if="s.stage && s.stage !== '未知'"> · {{ s.stage }}</span>
              <span v-if="s.total > 0"> · {{ s.score }}/{{ s.total }} 分</span>
            </div>
          </div>
          <div class="session-right">
            <el-tag v-if="s.reviewed_count > 0 && s.reviewed_count >= s.error_count" type="success" size="large">
              已复习 {{ s.reviewed_count }}/{{ s.error_count }}
            </el-tag>
            <el-tag v-else-if="s.reviewed_count > 0" type="warning" size="large">
              已复习 {{ s.reviewed_count }}/{{ s.error_count }}
            </el-tag>
            <el-tag v-else type="danger" size="large">{{ s.error_count }} 道错题</el-tag>
            <el-button type="danger" size="small" plain @click.stop="handleDeleteSession(s)" :loading="deleting === deleteKey(s)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 第二级：某次测评的错题详情 -->
    <el-card v-else shadow="hover" v-loading="loadingDetail">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div style="display:flex;align-items:center;gap:12px">
            <el-button @click="backToSessions" text><el-icon><ArrowLeft /></el-icon> 返回</el-button>
            <span class="page-title">{{ currentSession?.label }}</span>
            <el-tag type="danger">{{ sessionErrors.total }} 道错题</el-tag>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <el-button
              v-if="sessionErrors.items?.some(e => !e.reviewed)"
              type="success"
              @click="handleReviewAll"
              :loading="reviewingAll"
            >
              标记整组已复习 ({{ reviewedInSession }}/{{ sessionErrors.total }})
            </el-button>
            <el-tag v-else-if="sessionErrors.total > 0" type="success" size="large">全部已复习</el-tag>
            <el-button type="danger" plain @click="handleDeleteSession(currentSession)" :loading="deleting === deleteKey(currentSession)">
              <el-icon><Delete /></el-icon> 删除本组全部错题
            </el-button>
          </div>
        </div>
      </template>

      <el-empty v-if="!sessionErrors.items?.length && !loadingDetail" description="该测评没有错题" />

      <div v-for="error in sessionErrors.items" :key="error.id" class="error-card">
        <div class="error-header">
          <div>
            <el-tag :type="getErrorTypeColor(error.error_type)" size="small">{{ error.error_type }}</el-tag>
            <el-tag type="info" size="small" style="margin-left:8px">{{ error.knowledge_tag }}</el-tag>
            <el-tag v-if="getDifficulty(error)" size="small" style="margin-left:8px" effect="plain">{{ getDifficulty(error) }}</el-tag>
            <span style="margin-left:8px;font-size:12px;color:#c0c4cc">{{ error.created_at?.slice(0,16) }}</span>
          </div>
          <el-tag v-if="error.reviewed" type="success" size="small">已复习</el-tag>
        </div>

        <!-- 原题完整复述 -->
        <div class="error-original-question">
          <div class="section-title">原题</div>
          <div class="question-full">
            <div class="q-type-tag">
              <el-tag size="small" effect="dark" type="primary">{{ getQuestionType(error) }}</el-tag>
            </div>
            <div class="q-text">{{ getQuestionText(error) }}</div>
            <div v-if="getOptions(error).length > 0" class="q-options">
              <div v-for="(opt, oi) in getOptions(error)" :key="oi" class="q-option"
                   :class="{ 'is-correct': isCorrectOption(opt, error.correct_answer), 'is-user-pick': isUserPick(opt, error.user_answer) }">
                <span class="opt-label">{{ String.fromCharCode(65 + oi) }}</span>
                <div class="opt-body">
                  <span class="opt-text">{{ opt }}</span>
                </div>
                <div class="opt-tags">
                  <el-tag v-if="isCorrectOption(opt, error.correct_answer)" size="small" type="success" effect="dark">正确</el-tag>
                  <el-tag v-if="isUserPick(opt, error.user_answer) && !isCorrectOption(opt, error.correct_answer)" size="small" type="danger" effect="dark">你的选择</el-tag>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 答案对比 -->
        <div class="error-answer-compare">
          <div class="section-title">答案对比</div>
          <div class="answer-row">
            <div class="answer-box wrong-box">
              <div class="answer-label">你的答案</div>
              <div class="answer-text">{{ error.user_answer || '未作答' }}</div>
            </div>
            <div class="answer-arrow">></div>
            <div class="answer-box correct-box">
              <div class="answer-label">正确答案</div>
              <div class="answer-text">{{ error.correct_answer }}</div>
            </div>
          </div>
        </div>

        <!-- 题目解析 -->
        <div v-if="getAnalysisText(error)" class="error-analysis">
          <div class="section-title">详细解析</div>
          <div class="analysis-text" v-html="getAnalysisText(error)" />
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="sessionErrors.total_pages > 1" style="text-align:center;margin-top:16px">
        <el-pagination
          v-model:current-page="detailPage"
          :page-size="sessionErrors.page_size || 50"
          :total="sessionErrors.total"
          layout="prev, pager, next, total"
          @current-change="handleDetailPageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useLearningStore } from '../stores/learning'
import { deleteSessionErrors, deleteOrphanErrors, recordStudyVisit } from '../api/learning'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import PageHero from '../components/PageHero.vue'

const store = useLearningStore()
const loading = ref(false)
const loadingDetail = ref(false)
const activeSession = ref(undefined)
const detailPage = ref(1)
const deleting = ref(null)
const reviewingAll = ref(false)
const reviewedInSession = computed(() =>
  sessionErrors.value.items?.filter(e => e.reviewed).length || 0
)

// 会话批量选择
const selectedSessions = ref(new Set())
const batchDeleting = ref(false)
const sessionSelectAll = ref(false)
const sessionIndeterminate = computed(() =>
  selectedSessions.value.size > 0 && selectedSessions.value.size < (sessions.value.length || 0)
)

function deleteKey(s) {
  return s?.session_id ?? '__orphan__'
}

onMounted(async () => {
  recordStudyVisit()
  await loadSessions()
})

const sessions = computed(() => store.errorSessions)
const sessionErrors = computed(() => store.sessionErrors)
const currentSession = computed(() => store.errorSessions.find(s => s.session_id === activeSession.value))

const totalErrors = computed(() => store.errorSessions.reduce((sum, s) => sum + s.error_count, 0))

async function loadSessions() {
  loading.value = true
  try {
    await store.fetchErrorSessions()
  } catch(e) {
    console.error('加载错题分组失败:', e)
  } finally {
    loading.value = false
  }
}

async function openSession(session) {
  activeSession.value = session.session_id
  detailPage.value = 1
  await loadSessionErrors()
}

async function loadSessionErrors() {
  loadingDetail.value = true
  try {
    await store.fetchSessionErrors(activeSession.value, detailPage.value)
  } catch(e) {
    console.error('加载错题详情失败:', e)
  } finally {
    loadingDetail.value = false
  }
}

async function backToSessions() {
  activeSession.value = undefined
  detailPage.value = 1
  await loadSessions()
}

async function handleDeleteSession(session) {
  const sid = session.session_id
  const key = deleteKey(session)
  try {
    await ElMessageBox.confirm(
      `确认删除「${session.label}」的全部 ${session.error_count} 道错题？此操作不可恢复。`,
      '删除错题组',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  deleting.value = key
  try {
    await store.removeSession(sid)
    ElMessage.success(`已删除 ${session.error_count} 道错题`)
    if (activeSession.value !== undefined) {
      activeSession.value = undefined
      detailPage.value = 1
    }
    selectedSessions.value = new Set()
    sessionSelectAll.value = false
    await loadSessions()
  } catch(e) {
    ElMessage.error('删除失败')
  } finally {
    deleting.value = null
  }
}

// ===== 批量删除会话 =====

function toggleSessionSelect(session, checked) {
  const key = deleteKey(session)
  if (checked) {
    selectedSessions.value.add(key)
  } else {
    selectedSessions.value.delete(key)
  }
  selectedSessions.value = new Set(selectedSessions.value)
  updateSessionSelectAll()
}

function handleSessionSelectAll(checked) {
  if (checked) {
    selectedSessions.value = new Set(sessions.value.map(s => deleteKey(s)))
  } else {
    selectedSessions.value = new Set()
  }
}

function updateSessionSelectAll() {
  const total = sessions.value.length || 0
  const sel = selectedSessions.value.size
  sessionSelectAll.value = total > 0 && sel === total
}

async function handleBatchDeleteSessions() {
  if (selectedSessions.value.size === 0) return

  const toDelete = sessions.value.filter(s => selectedSessions.value.has(deleteKey(s)))
  const totalErrors = toDelete.reduce((sum, s) => sum + s.error_count, 0)

  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${selectedSessions.value.size} 组错题集（共 ${totalErrors} 道错题）？此操作不可恢复。`,
      '批量删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  batchDeleting.value = true
  let deleted = 0
  try {
    for (const s of toDelete) {
      if (s.session_id != null) {
        await deleteSessionErrors(s.session_id)
      } else {
        await deleteOrphanErrors()
      }
      deleted++
    }
    ElMessage.success(`已删除 ${deleted} 组错题集（共 ${totalErrors} 道错题）`)
    selectedSessions.value = new Set()
    sessionSelectAll.value = false
    await loadSessions()
  } catch(e) {
    ElMessage.error(`已删除 ${deleted} 组，部分删除失败`)
  } finally {
    batchDeleting.value = false
  }
}

async function handleDetailPageChange(page) {
  detailPage.value = page
  await loadSessionErrors()
}

async function handleReviewAll() {
  reviewingAll.value = true
  try {
    const result = await store.reviewSession(activeSession.value)
    ElMessage.success(`已将 ${result.reviewed_count} 道错题标记为已复习`)
    await backToSessions()
  } catch(e) {
    ElMessage.error('操作失败')
  } finally {
    reviewingAll.value = false
  }
}

function getQuestionData(error) {
  if (error.question_data && typeof error.question_data === 'object') return error.question_data
  if (typeof error.question_data === 'string') {
    try { return JSON.parse(error.question_data) } catch { return {} }
  }
  return {}
}

function getQuestionText(error) {
  const qd = getQuestionData(error)
  return qd.question || '题目内容缺失'
}

function getQuestionType(error) {
  const qd = getQuestionData(error)
  return qd.question_type || '简答'
}

function getDifficulty(error) {
  const qd = getQuestionData(error)
  return qd.difficulty || ''
}

function getOptions(error) {
  const qd = getQuestionData(error)
  return qd.options || []
}

function isCorrectOption(opt, correctAnswer) {
  if (!correctAnswer) return false
  return opt === correctAnswer || correctAnswer.includes(opt)
}

function isUserPick(opt, userAnswer) {
  if (!userAnswer) return false
  return opt === userAnswer || userAnswer.includes(opt)
}

function getAnalysisText(error) {
  const qd = getQuestionData(error)
  const raw = qd.analysis || ''
  if (!raw) return ''
  // 将 markdown 解析为 HTML，正确渲染 **加粗**、# 标题 等格式
  return marked.parse(raw, { breaks: true })
}

function getErrorTypeColor(type) {
  const map = {
    '概念认知偏差': 'warning',
    '代码语法失误': 'danger',
    '知识点遗漏': 'info',
    '审题理解偏差': ''
  }
  return map[type] || ''
}
</script>

<style scoped>
.page-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: bold; }

/* 会话选择工具栏 */
.batch-toolbar { display: flex; align-items: center; gap: 12px; padding: 10px 14px; margin-bottom: 12px; background: #f5f7fa; border-radius: 8px; }
.batch-hint { font-size: 13px; color: #F56C6C; font-weight: 500; }

/* 会话卡片 */
.session-card {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px; margin-bottom: 8px;
  background: #fafafa; border-radius: 10px; border: 1px solid #f0f0f0;
  transition: all .2s;
}
.session-card.is-selected { background: #fef0f0; border-color: #fab6b6; }
.session-select { flex-shrink: 0; }
.session-body { flex: 1; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.session-body:hover .session-left { color: #409EFF; }
.session-left { flex: 1; }
.session-label { font-size: 15px; font-weight: 500; color: #303133; margin-bottom: 4px; }
.session-meta { font-size: 12px; color: #909399; }
.session-right { display: flex; align-items: center; gap: 12px; }

/* 错题详情卡片 */
.error-card { padding: 20px; margin-bottom: 16px; background: #fafafa; border-radius: 12px; border: 1px solid #f0f0f0; }
.error-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.section-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 8px; }

/* 原题区域 */
.error-original-question { margin-bottom: 16px; background: #fff; padding: 14px; border-radius: 8px; border: 1px solid #e4e7ed; }
.q-type-tag { margin-bottom: 8px; }
.q-text { font-size: 15px; color: #1a1a2e; line-height: 1.7; font-weight: 500; }
.q-options { margin-top: 10px; }
.q-option { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; margin: 6px 0; border-radius: 6px; background: #f5f7fa; border: 1px solid #e4e7ed; }
.q-option.is-correct { background: #f0f9eb; border-color: #b3e19d; }
.q-option.is-user-pick { background: #fef0f0; border-color: #fab6b6; }
.opt-label { font-weight: 700; font-size: 14px; color: #409EFF; min-width: 20px; padding-top: 1px; }
.opt-body { flex: 1; min-width: 0; }
.opt-text { font-size: 14px; line-height: 1.6; }
.opt-tags { flex-shrink: 0; display: flex; gap: 4px; }

/* 答案对比 */
.error-answer-compare { margin-bottom: 16px; }
.answer-row { display: flex; align-items: center; gap: 12px; }
.answer-box { flex: 1; padding: 12px; border-radius: 8px; min-height: 50px; }
.wrong-box { background: #fef0f0; border: 1px solid #fab6b6; }
.correct-box { background: #f0f9eb; border: 1px solid #b3e19d; }
.answer-label { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.wrong-box .answer-label { color: #F56C6C; }
.correct-box .answer-label { color: #67C23A; }
.answer-text { font-size: 14px; color: #303133; line-height: 1.6; white-space: pre-wrap; }
.answer-arrow { font-size: 20px; color: #c0c4cc; font-weight: bold; }

/* 详细解析 */
.error-analysis { background: #f0f5ff; padding: 12px 14px; border-radius: 8px; border-left: 4px solid #409EFF; }
.analysis-text { font-size: 14px; color: #303133; line-height: 1.8; }
.analysis-text :deep(p) { margin: 4px 0; }
.analysis-text :deep(strong) { color: #1a1a2e; }
.analysis-text :deep(h1), .analysis-text :deep(h2), .analysis-text :deep(h3) { font-size: 15px; margin: 8px 0 4px; color: #303133; }
.error-book-page { padding-bottom: 28px; }
.error-list-heading span,
.error-list-heading strong { display: block; }
.error-list-heading span { color: var(--primary); font-size: 8px; font-weight: 800; letter-spacing: .15em; }
.error-list-heading strong { margin-top: 4px; color: var(--ink-950); font-size: 14px; }
.error-overview-card :deep(.el-empty) { min-height: 300px; }
.session-card { border-color: var(--line); border-radius: 13px; background: #fbfcff; }
.session-card:hover { border-color: #cbd2ef; background: #f7f8ff; transform: translateX(2px); }
@media (max-width: 720px) {
  .session-body { align-items: flex-start; flex-direction: column; gap: 12px; }
  .session-right { width: 100%; justify-content: space-between; }
  .answer-row { flex-direction: column; }
  .answer-arrow { transform: rotate(90deg); }
}
</style>
