<template>
  <div class="diagnosis-page">
    <PageHero
      eyebrow="KNOWLEDGE DIAGNOSIS"
      title="智能学情自测"
      description="通过一组分层题目定位知识盲区，完成后会生成掌握度分析和下一步学习建议。"
      icon="DocumentChecked"
    >
      <template #meta>
        <el-tag effect="plain">{{ bankTotal }} 道题库</el-tag>
        <el-tag type="success" effect="plain">约 {{ form.count }} 分钟</el-tag>
      </template>
    </PageHero>
    <el-card v-if="!currentQuiz" shadow="hover" class="start-card">
      <template #header>
        <div class="diagnosis-card-title">
          <div><span>ASSESSMENT SETUP</span><strong>设置本次测评</strong></div>
          <small>选择范围后随机生成试卷</small>
        </div>
      </template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="学习阶段">
          <el-radio-group v-model="form.stage" size="large">
            <el-radio-button value="入门">入门 (70%基础+30%中等)</el-radio-button>
            <el-radio-button value="进阶">进阶 (40%中等+60%高阶)</el-radio-button>
            <el-radio-button value="高阶">高阶 (偏重实操+算法)</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="题目数量">
          <el-input-number v-model="form.count" :min="1" :max="50" :step="1" size="large" />
          <span style="margin-left:12px;color:#909399">共 {{ form.count }} 题（从题库 {{ bankTotal }} 题中随机抽取）</span>
        </el-form-item>
        <el-form-item label="计时设置">
          <el-switch v-model="form.useTimer" active-text="开启计时" inactive-text="不限时" />
          <template v-if="form.useTimer">
            <span style="margin-left:12px;color:#606266">限时</span>
            <el-input-number v-model="form.timerMinutes" :min="1" :max="180" :step="5" size="small" style="width:120px;margin:0 8px" />
            <span style="color:#606266">分钟</span>
          </template>
        </el-form-item>
        <el-form-item label="测评维度">
          <el-checkbox-group v-model="form.selectedCategories">
            <el-checkbox v-for="cat in categories" :key="cat" :label="cat" border style="margin-right:8px;margin-bottom:8px" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" @click="startDiagnosis" :loading="loading" :disabled="loading">
            <el-icon><Cpu /></el-icon> 从题库抽取试卷
          </el-button>
          <el-text type="info" size="small" style="margin-left:12px">基于AI智能体学科题库，随机抽取测评题目</el-text>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 答题中 -->
    <div v-if="currentQuiz && !currentReport" class="quiz-area">
      <el-card shadow="hover">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span><el-icon><List /></el-icon> 测评答题中 - {{ currentQuiz.stage }}测评</span>
            <div style="display:flex;align-items:center;gap:16px">
              <el-tag>共 {{ currentQuiz.total }} 题</el-tag>
              <el-tag v-if="currentQuiz.use_timer" :type="timerWarning ? 'danger' : 'warning'" effect="dark">
                <el-icon><Clock /></el-icon> {{ formatTime(remainingTime) }}
              </el-tag>
            </div>
          </div>
        </template>
        <div v-for="(q, idx) in currentQuiz.questions" :key="q.question_id" class="question-block">
          <div class="q-header">
            <el-tag :type="q.difficulty === 'Lv1入门' ? 'success' : q.difficulty === 'Lv2中等' ? 'warning' : 'danger'" size="small">{{ q.difficulty }}</el-tag>
            <el-tag type="info" size="small" style="margin-left:8px">{{ q.knowledge_tag }}</el-tag>
            <span style="margin-left:8px;color:#909399;font-size:13px">{{ q.question_type }}</span>
          </div>
          <div class="q-title">{{ idx + 1 }}. {{ q.question }}</div>
          <div v-if="q.options && q.options.length" class="q-options">
            <el-radio-group v-if="q.question_type === '单选'" v-model="answers[q.question_id]" class="option-group">
              <el-radio v-for="(opt, oi) in q.options" :key="oi" :value="opt" class="option-item">{{ opt }}</el-radio>
            </el-radio-group>
            <el-checkbox-group v-else-if="q.question_type === '多选'" v-model="multiAnswers[q.question_id]" class="option-group">
              <el-checkbox v-for="(opt, oi) in q.options" :key="oi" :label="opt" :value="opt" class="option-item" />
            </el-checkbox-group>
            <el-radio-group v-else-if="q.question_type === '判断'" v-model="answers[q.question_id]" class="option-group">
              <el-radio v-for="(opt, oi) in q.options" :key="oi" :value="opt" class="option-item">{{ opt }}</el-radio>
            </el-radio-group>
          </div>
          <div v-else>
            <el-input v-model="answers[q.question_id]" type="textarea" :rows="3" :placeholder="q.question_type === '代码实操' ? '请输入你的代码...' : q.question_type === '填空' ? '请填入正确答案...' : '请输入你的答案...'" />
          </div>
        </div>
        <div style="text-align:center;margin-top:24px">
          <el-button type="primary" size="large" @click="submitAnswers" :loading="loading">
            <el-icon><Finished /></el-icon> 提交答卷
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 测评结果 -->
    <div v-if="currentReport" class="result-area">
      <el-card shadow="hover">
        <template #header><div class="page-title"><el-icon><Trophy /></el-icon> 测评结果</div></template>
        <el-result :icon="currentReport.correct_rate >= 60 ? 'success' : 'warning'" :title="`${currentReport.score}/${currentReport.total} 正确率 ${currentReport.correct_rate}%`" :sub-title="currentReport.report?.overall_assessment">
          <template #extra>
            <el-button type="primary" @click="$router.push(`/diagnosis/report/${currentReport.session_id}`)">查看详细报告</el-button>
            <el-button @click="resetQuiz">重新测评</el-button>
            <el-button @click="$router.push('/error-book')">查看错题</el-button>
          </template>
        </el-result>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useDiagnosisStore } from '../stores/diagnosis'
import { ElMessage } from 'element-plus'
import { recordStudyVisit } from '../api/learning'
import PageHero from '../components/PageHero.vue'

const store = useDiagnosisStore()
const { currentQuiz, currentReport } = storeToRefs(store)
const loading = ref(false)
const answers = reactive({})
const multiAnswers = reactive({})
const categories = ref([])
const bankTotal = ref(0)
const form = reactive({
  stage: '入门',
  count: 10,
  useTimer: false,
  timerMinutes: 30,
  selectedCategories: []
})

// 计时器
const remainingTime = ref(0)
const timerWarning = ref(false)
let timerInterval = null

const timerRunning = computed(() => currentQuiz.value?.use_timer && remainingTime.value > 0)

function startTimer(minutes) {
  stopTimer()
  remainingTime.value = minutes * 60
  timerWarning.value = false
  timerInterval = setInterval(() => {
    remainingTime.value--
    if (remainingTime.value <= 60) {
      timerWarning.value = true
    }
    if (remainingTime.value <= 0) {
      stopTimer()
      ElMessage.warning('答题时间已到，系统将自动提交答卷')
      submitAnswers()
    }
  }, 1000)
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

onMounted(async () => {
  recordStudyVisit()
  try {
    const res = await fetch('/api/knowledge/categories').then(r => r.json())
    if (res.data) categories.value = res.data.map(c => c.name)
  } catch(e) {}
  try { await store.fetchProfile() } catch(e) {}
  // 获取题库总量
  try {
    const res = await fetch('/api/diagnosis/bank-stats').then(r => r.json())
    if (res.data) bankTotal.value = res.data.total || 0
  } catch(e) {}
})

onUnmounted(() => {
  stopTimer()
})

async function startDiagnosis() {
  loading.value = true
  try {
    await store.startQuiz(
      form.stage,
      form.count,
      form.useTimer,
      form.timerMinutes,
      form.selectedCategories  // 传递用户选中的测评维度
    )
    // Reset answers
    Object.keys(answers).forEach(k => delete answers[k])
    Object.keys(multiAnswers).forEach(k => delete multiAnswers[k])
    // Start timer if enabled
    if (currentQuiz.value?.use_timer) {
      startTimer(currentQuiz.value.timer_minutes)
    }
  } catch(e) {
    ElMessage.error('生成试卷失败: ' + (e.message || '请重试'))
  }
  finally { loading.value = false }
}

async function submitAnswers() {
  // Merge multi-select answers
  const answerList = []
  for (const [qid, val] of Object.entries(answers)) {
    answerList.push({ question_id: qid, user_answer: Array.isArray(val) ? val.join(',') : val })
  }
  for (const [qid, val] of Object.entries(multiAnswers)) {
    if (Array.isArray(val)) {
      const idx = answerList.findIndex(a => a.question_id === qid)
      if (idx >= 0) answerList[idx].user_answer = val.join(',')
      else answerList.push({ question_id: qid, user_answer: val.join(',') })
    }
  }

  if (answerList.length === 0) {
    ElMessage.warning('请至少回答一题')
    return
  }
  loading.value = true
  stopTimer()
  try {
    await store.submitAnswers(currentQuiz.value.session_id, answerList)
  } catch(e) { ElMessage.error('提交失败') }
  finally { loading.value = false }
}

function resetQuiz() {
  store.resetQuiz()
  Object.keys(answers).forEach(k => delete answers[k])
  Object.keys(multiAnswers).forEach(k => delete multiAnswers[k])
}
</script>

<style scoped>
.page-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: bold; }
.start-card { max-width: 800px; margin: 0 auto; }
.question-block { padding: 20px 0; border-bottom: 1px solid #f0f0f0; }
.q-header { margin-bottom: 10px; }
.q-title { font-size: 15px; font-weight: 500; color: #303133; margin-bottom: 12px; line-height: 1.6; }
.q-options { margin-left: 8px; }
.option-group { display: flex; flex-direction: column; gap: 8px; }
.option-item { padding: 8px 12px; border: 1px solid #e8e8e8; border-radius: 8px; margin-right: 0 !important; }
.quiz-area { max-width: 900px; margin: 0 auto; }
.result-area { max-width: 700px; margin: 0 auto; }
.diagnosis-page { padding-bottom: 28px; }
.diagnosis-card-title { display: flex; align-items: end; justify-content: space-between; }
.diagnosis-card-title div span,
.diagnosis-card-title div strong { display: block; }
.diagnosis-card-title div span { color: var(--primary); font-size: 8px; font-weight: 800; letter-spacing: .15em; }
.diagnosis-card-title div strong { margin-top: 5px; color: var(--ink-950); font-size: 15px; }
.diagnosis-card-title small { color: var(--ink-400); font-size: 10px; }
.start-card { max-width: 980px; }
.start-card :deep(.el-form) { max-width: 860px; padding: 4px 2px; }
.start-card :deep(.el-form-item) { padding: 5px 0; }
.start-card :deep(.el-checkbox.is-bordered) { border-radius: 10px; }
@media (max-width: 720px) {
  .diagnosis-card-title small { display: none; }
  .start-card :deep(.el-form-item) { display: block; }
  .start-card :deep(.el-form-item__label) { width: auto !important; margin-bottom: 7px; }
  .start-card :deep(.el-radio-group) { display: grid; width: 100%; }
  .start-card :deep(.el-radio-button__inner) { width: 100%; }
}
</style>
