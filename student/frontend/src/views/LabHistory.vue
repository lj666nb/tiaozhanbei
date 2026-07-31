<template>
  <div class="history-page">
    <PageHero
      eyebrow="LAB ARCHIVE"
      title="实验学习档案"
      description="集中查看已完成关卡的综合评分、答辩反馈、故障修复说明和能力验证结论。"
      icon="DocumentChecked"
    >
      <template #meta>
        <el-tag effect="plain">{{ sessions.length }} 条记录</el-tag>
        <el-tag type="success" effect="plain">{{ verifiedCount }} 次完整验证</el-tag>
      </template>
      <template #actions>
        <el-button @click="$router.back()"><el-icon><ArrowLeft /></el-icon>返回</el-button>
        <el-button type="primary" @click="$router.push('/code-lab')">继续实验</el-button>
      </template>
    </PageHero>

    <div v-if="loading" class="loading-wrap" v-loading="true" element-loading-background="transparent"></div>

    <div v-else-if="!sessions.length" class="empty-state">
      <span class="empty-eyebrow">YOUR FIRST RECORD</span>
      <div class="empty-icon"><el-icon><Monitor /></el-icon></div>
      <h3>完成第一关，建立学习档案</h3>
      <p>通过代码测试并提交能力验证后，综合评分与 AI 反馈会自动保存在这里。</p>
      <button class="go-lab-btn" @click="$router.push('/code-lab')">选择第一个关卡 <span>→</span></button>
    </div>

    <div v-else class="history-list">
      <div
        v-for="session in sessions"
        :key="session.session_id"
        :class="['history-card', { verified: session.verified, skipped: session.skipped }]"
      >
        <div class="card-header" @click="toggleExpand(session.session_id)">
          <div class="card-title-area">
            <span :class="['status-badge', session.verified ? 'verified' : 'skipped']">
              {{ session.verified ? '✓ 已验证' : '⏭ 仅测试分' }}
            </span>
            <h3>{{ session.exercise_title || session.exercise_id }}</h3>
            <small>{{ session.knowledge_tag }} · {{ session.exercise_id }}</small>
          </div>
          <div class="card-score-area">
            <div :class="['score-circle', scoreLevel(session.total_score)]">
              <span>{{ session.total_score }}</span>
              <small>综合分</small>
            </div>
            <el-icon :class="{ rotated: expanded.has(session.session_id) }"><ArrowDown /></el-icon>
          </div>
        </div>

        <div v-if="expanded.has(session.session_id)" class="card-detail">
          <!-- 分数维度 -->
          <div class="detail-section">
            <h4>📊 能力维度评分</h4>
            <div class="dimension-bars">
              <div class="dim-bar">
                <span>代码正确性</span>
                <div class="bar-track"><div class="bar-fill code" :style="{ width: (session.code_score || 0) + '%' }"></div></div>
                <b>{{ session.code_score || 0 }}分</b>
              </div>
              <div class="dim-bar">
                <span>原理理解</span>
                <div class="bar-track"><div class="bar-fill defense" :style="{ width: (session.defense_score || 0) + '%' }"></div></div>
                <b>{{ session.defense_score || 0 }}分</b>
              </div>
              <div class="dim-bar">
                <span>故障修复</span>
                <div class="bar-track"><div class="bar-fill repair" :style="{ width: (session.repair_score || 0) + '%' }"></div></div>
                <b>{{ session.repair_score || 0 }}分</b>
              </div>
            </div>
          </div>

          <!-- 答辩回顾 -->
          <div v-if="session.defense_answers?.length" class="detail-section">
            <h4>💬 原理答辩回顾</h4>
            <div v-for="(item, idx) in session.defense_answers" :key="idx" class="defense-review-item">
              <div class="defense-q">
                <span class="q-num">{{ idx + 1 }}</span>
                <div>
                  <b>{{ item.prompt }}</b>
                  <small>得分: {{ item.score }} 分 · {{ item.graded_by === 'ai' ? 'AI 评审' : '关键词评分' }}</small>
                </div>
              </div>
              <div class="defense-a">
                <div class="defense-a-label">你的回答：</div>
                <p>{{ item.answer || '（未作答）' }}</p>
              </div>
              <div v-if="item.feedback" class="defense-feedback">
                <b>{{ item.graded_by === 'ai' ? '🤖 AI' : '⚙️ 系统' }}反馈：</b>{{ item.feedback }}
              </div>
              <div v-if="item.hit_points?.length" class="defense-points hit">
                ✓ {{ item.hit_points.join(' · ') }}
              </div>
              <div v-if="item.missing_points?.length" class="defense-points miss">
                ✗ 遗漏：{{ item.missing_points.join(' · ') }}
              </div>
            </div>
          </div>

          <!-- 故障修复说明 -->
          <div v-if="session.mutation_description" class="detail-section">
            <h4>🔧 故障修复</h4>
            <div class="repair-detail">
              <p><b>注入故障：</b>{{ session.mutation_description }}</p>
              <p v-if="session.repair_explanation"><b>你的修复说明：</b>{{ session.repair_explanation }}</p>
            </div>
          </div>

          <!-- 综合报告 -->
          <div v-if="session.summary" class="detail-section">
            <h4>📝 综合报告</h4>
            <div :class="['report-summary', session.skipped ? 'skipped' : 'verified']">
              <span>{{ session.verdict || (session.skipped ? '仅测试通过' : '能力已验证') }}</span>
              <p>{{ session.summary }}</p>
            </div>
          </div>

          <!-- 时间信息 -->
          <div class="detail-section meta">
            <span>开始：{{ formatTime(session.started_at) }}</span>
            <span>完成：{{ formatTime(session.completed_at) }}</span>
          </div>

          <!-- 操作按钮 -->
          <div class="detail-actions">
            <button class="action-btn primary" @click="redoExercise(session.exercise_id)">
              重做本题
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCapabilityHistory } from '../api/capability'
import PageHero from '../components/PageHero.vue'

const router = useRouter()
const sessions = ref([])
const loading = ref(true)
const expanded = ref(new Set())
const verifiedCount = computed(() => sessions.value.filter(session => session.verified).length)

onMounted(async () => {
  try {
    const res = await getCapabilityHistory()
    sessions.value = res.data || []
  } catch (e) {
    console.warn('获取实验历史失败:', e)
  } finally {
    loading.value = false
  }
})

function toggleExpand(id) {
  if (expanded.value.has(id)) {
    expanded.value.delete(id)
  } else {
    expanded.value.add(id)
  }
  // 触发响应式更新
  expanded.value = new Set(expanded.value)
}

function scoreLevel(score) {
  if (score >= 90) return 'excellent'
  if (score >= 75) return 'good'
  if (score >= 60) return 'pass'
  return 'low'
}

function formatTime(ts) {
  if (!ts) return '—'
  try {
    const d = new Date(ts)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return ts
  }
}

function redoExercise(exerciseId) {
  const moduleId = exerciseId.split('-')[0]
  router.push({ name: 'CodeLab', params: { moduleId, taskId: exerciseId } })
}
</script>

<style scoped>
.history-page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 4px 0 32px;
  color: #303133;
}
.history-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}
.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  cursor: pointer;
  font-size: 13px;
}
.back-btn:hover { color: #409eff; border-color: #409eff; }
.history-header h2 { margin: 0; font-size: 20px; }
.history-count { color: #909399; font-size: 13px; margin-left: auto; }
.loading-wrap { min-height: 300px; }
.empty-state { display: flex; min-height: 390px; flex-direction: column; align-items: center; justify-content: center; padding: 58px 24px; border: 1px solid var(--line); border-radius: 20px; text-align: center; background: rgba(255,255,255,.88); box-shadow: var(--shadow-sm); }
.empty-eyebrow { color: var(--primary); font-size: 8px; font-weight: 800; letter-spacing: .16em; }
.empty-icon { display: grid; width: 72px; height: 72px; margin: 24px 0 18px; place-items: center; border-radius: 21px; color: var(--primary); background: #eef0fc; font-size: 31px; }
.empty-state h3 { font-size: 19px; color: var(--ink-950); margin: 0 0 8px; }
.empty-state p { max-width: 430px; color: var(--ink-400); font-size: 12px; line-height: 1.7; margin: 0 0 22px; }
.go-lab-btn {
  padding: 11px 20px;
  border: 0;
  border-radius: 11px;
  background: var(--primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 9px 20px rgba(70,87,216,.2);
}
.go-lab-btn span { margin-left: 7px; }

.history-list { display: flex; flex-direction: column; gap: 14px; }
.history-card {
  border: 1px solid #e4e7ed;
  border-radius: 15px;
  background: #fff;
  overflow: hidden;
  transition: box-shadow .2s;
}
.history-card:hover { border-color: #cbd2ed; box-shadow: 0 11px 28px rgba(30,45,84,.08); }
.history-card.verified { border-left: 4px solid #2e8b57; }
.history-card.skipped { border-left: 4px solid #e6a817; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
}
.card-title-area { flex: 1; min-width: 0; }
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 6px;
}
.status-badge.verified { color: #2e8b57; background: #f0faf4; border: 1px solid #c6e6d4; }
.status-badge.skipped { color: #b8860b; background: #fffdf5; border: 1px solid #f0d78c; }
.card-title-area h3 { margin: 0 0 4px; font-size: 15px; color: #303133; }
.card-title-area small { color: #909399; font-size: 12px; }
.card-score-area { display: flex; align-items: center; gap: 12px; }
.score-circle {
  width: 56px; height: 56px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  border-radius: 50%; border: 3px solid #dcdfe6;
}
.score-circle span { font-size: 18px; font-weight: 700; }
.score-circle small { font-size: 8px; color: #909399; }
.score-circle.excellent { border-color: #2e8b57; color: #2e8b57; background: #f0faf4; }
.score-circle.good { border-color: #2979c1; color: #2979c1; background: #f0f6ff; }
.score-circle.pass { border-color: #e6a817; color: #b8860b; background: #fffdf5; }
.score-circle.low { border-color: #c0392b; color: #c0392b; background: #fff5f5; }
.rotated { transform: rotate(180deg); }

.card-detail { padding: 0 20px 20px; border-top: 1px solid #f0f0f0; }
.detail-section { margin-top: 16px; }
.detail-section h4 { margin: 0 0 10px; font-size: 13px; color: #606266; }
.dimension-bars { display: flex; flex-direction: column; gap: 8px; }
.dim-bar { display: flex; align-items: center; gap: 10px; font-size: 12px; }
.dim-bar > span { width: 80px; color: #606266; }
.dim-bar > b { width: 40px; text-align: right; color: #303133; }
.bar-track { flex: 1; height: 8px; border-radius: 4px; background: #f0f0f0; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; }
.bar-fill.code { background: #409eff; }
.bar-fill.defense { background: #e6a23c; }
.bar-fill.repair { background: #67c23a; }

.defense-review-item { padding: 10px; margin-bottom: 8px; border: 1px solid #ebeef5; border-radius: 8px; background: #fafafa; }
.defense-q { display: flex; gap: 8px; align-items: flex-start; }
.q-num { width: 20px; height: 20px; display: grid; place-items: center; border-radius: 50%; background: #ecf5ff; color: #409eff; font-size: 10px; font-weight: 700; flex-shrink: 0; }
.defense-q b { font-size: 12px; color: #303133; }
.defense-q small { display: block; margin-top: 2px; color: #909399; font-size: 11px; }
.defense-a { margin-top: 8px; }
.defense-a-label { font-size: 10px; color: #909399; margin-bottom: 3px; }
.defense-a p { margin: 0; padding: 8px; border-radius: 5px; background: #fff; border: 1px solid #ebeef5; font-size: 12px; color: #606266; line-height: 1.6; white-space: pre-wrap; }
.defense-feedback { margin-top: 8px; padding: 8px; border-radius: 5px; background: #f0f6ff; font-size: 11px; color: #606266; line-height: 1.5; }
.defense-feedback b { display: block; color: #409eff; margin-bottom: 2px; }
.defense-points { font-size: 10px; padding: 4px 8px; margin-top: 5px; border-radius: 4px; line-height: 1.5; }
.defense-points.hit { color: #2e8b57; background: #f0faf4; }
.defense-points.miss { color: #c0392b; background: #fff5f5; }

.repair-detail p { margin: 4px 0; font-size: 12px; color: #606266; line-height: 1.6; }
.repair-detail b { color: #303133; }

.report-summary { padding: 10px; border-radius: 7px; }
.report-summary.verified { background: #f0faf4; border: 1px solid #c6e6d4; }
.report-summary.skipped { background: #fffdf5; border: 1px solid #f0d78c; }
.report-summary span { font-size: 11px; font-weight: 600; display: block; margin-bottom: 4px; }
.report-summary.verified span { color: #2e8b57; }
.report-summary.skipped span { color: #b8860b; }
.report-summary p { margin: 0; font-size: 12px; color: #606266; line-height: 1.5; }

.detail-section.meta { display: flex; gap: 24px; font-size: 11px; color: #909399; }
.detail-actions { margin-top: 14px; display: flex; gap: 8px; }
.action-btn {
  padding: 7px 16px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #606266;
}
.action-btn.primary { color: #409eff; border-color: #409eff; }
.action-btn.primary:hover { color: #fff; background: #409eff; }
</style>
