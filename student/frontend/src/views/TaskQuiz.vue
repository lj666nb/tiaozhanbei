<template>
  <div class="task-quiz-page">
    <!-- Header -->
    <div v-if="currentQuiz" class="quiz-header">
      <PageHero
        eyebrow="FOCUSED PRACTICE"
        :title="currentQuiz.task_context?.topic || '专项练习'"
        :description="`围绕「${currentQuiz.task_context?.knowledge || '当前知识点'}」进行针对性巩固，提交后会同步更新学习数据。`"
        icon="EditPen"
        compact
      >
        <template #meta><el-tag size="small" type="success">Day {{ currentQuiz.task_context?.day }}</el-tag></template>
        <template #actions><el-button @click="goBackToLearningPath">返回学习路径</el-button></template>
      </PageHero>
    </div>

    <!-- 答题中 -->
    <div v-if="currentQuiz && !currentReport" class="quiz-area">
      <el-card shadow="hover">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span><el-icon><List /></el-icon> 答题中 - {{ currentQuiz.task_context?.topic || '' }}</span>
            <div style="display:flex;align-items:center;gap:12px">
              <el-tag>共 {{ currentQuiz.total }} 题</el-tag>
              <el-tag type="info">{{ currentQuiz.task_context?.knowledge }}</el-tag>
            </div>
          </div>
        </template>

        <div v-for="(q, idx) in currentQuiz.questions" :key="q.question_id" class="question-block">
          <div class="q-header">
            <el-tag :type="difficultyTag(q.difficulty)" size="small">{{ q.difficulty }}</el-tag>
            <el-tag type="info" size="small" style="margin-left:8px">{{ q.knowledge_tag }}</el-tag>
            <span style="margin-left:8px;color:#909399;font-size:13px">{{ q.question_type }}</span>
          </div>
          <div class="q-title">{{ idx + 1 }}. {{ q.question }}</div>
          <div v-if="q.options && q.options.length" class="q-options">
            <el-radio-group v-if="q.question_type === '单选'" v-model="answers[q.question_id]" class="option-group">
              <el-radio v-for="(opt, oi) in q.options" :key="oi" :value="opt" class="option-item">{{ opt }}</el-radio>
            </el-radio-group>
            <el-radio-group v-else-if="q.question_type === '判断'" v-model="answers[q.question_id]" class="option-group">
              <el-radio v-for="(opt, oi) in q.options" :key="oi" :value="opt" class="option-item">{{ opt }}</el-radio>
            </el-radio-group>
          </div>
          <div v-else>
            <el-input v-model="answers[q.question_id]" type="textarea" :rows="3" :placeholder="q.question_type === '填空' ? '请填入正确答案...' : '请输入你的答案...'" />
          </div>
        </div>

        <div style="text-align:center;margin-top:24px">
          <el-button type="primary" size="large" @click="submitAnswers" :loading="submitting">
            <el-icon><Finished /></el-icon> 提交答卷
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 练习结果 -->
    <div v-if="currentReport" class="result-area">
      <el-card shadow="hover">
        <template #header><div class="page-title"><el-icon><Trophy /></el-icon> 练习结果</div></template>
        <el-result
          :icon="currentReport.correct_rate >= 60 ? 'success' : 'warning'"
          :title="`${currentReport.score}/${currentReport.total} 正确率 ${currentReport.correct_rate}%`"
          :sub-title="currentReport.report?.overall_assessment"
        >
          <template #extra>
            <el-button type="primary" @click="$router.push(`/diagnosis/report/${currentReport.session_id}`)">查看详细报告</el-button>
            <el-button @click="retryQuiz">重新练习</el-button>
            <el-button @click="goBackToLearningPath">返回学习路径</el-button>
          </template>
        </el-result>
      </el-card>
    </div>

    <!-- 无数据 / 加载 -->
    <el-empty v-if="!currentQuiz && !currentReport" description="练习数据已过期">
      <el-button type="primary" @click="goBackToLearningPath">返回学习路径</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useDiagnosisStore } from '../stores/diagnosis'
import { useStatStore } from '../stores/statStore'
import { ElMessage } from 'element-plus'
import PageHero from '../components/PageHero.vue'

const router = useRouter()
const store = useDiagnosisStore()
const statStore = useStatStore()
const { currentQuiz, currentReport } = storeToRefs(store)

const answers = reactive({})
const submitting = ref(false)

onMounted(() => {
  if (!currentQuiz.value) {
    ElMessage.warning('练习数据已过期，请重新生成')
    router.push('/learning-path')
  }
})

function difficultyTag(difficulty) {
  if (difficulty === 'Lv1入门') return 'success'
  if (difficulty === 'Lv2中等') return 'warning'
  return 'danger'
}

async function submitAnswers() {
  const answerList = []
  for (const [qid, val] of Object.entries(answers)) {
    if (val) {
      answerList.push({ question_id: qid, user_answer: val })
    }
  }

  if (answerList.length === 0) {
    ElMessage.warning('请至少回答一题')
    return
  }

  submitting.value = true
  try {
    console.log('[TaskQuiz] 开始提交答案...')
    const result = await store.submitAnswers(currentQuiz.value.session_id, answerList)
    console.log('[TaskQuiz] 提交结果:', result)
    if (result) {
      const score = result.score || 0
      const total = result.total || answerList.length
      const knowledge = currentQuiz.value?.task_context?.knowledge || '综合'
      console.log('[TaskQuiz] 准备刷新统计:', { score, total, knowledge })
      await statStore.refreshStatData({ score, total, knowledge })
      console.log('[TaskQuiz] 统计刷新完成')
    } else {
      console.log('[TaskQuiz] result 为空，跳过刷新')
    }
  } catch(e) {
    console.error('[TaskQuiz] 提交失败:', e)
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

function goBackToLearningPath() {
  store.resetQuiz()
  router.push('/learning-path')
}

function retryQuiz() {
  store.resetQuiz()
  router.push('/learning-path')
}
</script>

<style scoped>
.page-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: bold; }
.question-block { padding: 20px 0; border-bottom: 1px solid #f0f0f0; }
.q-header { margin-bottom: 10px; }
.q-title { font-size: 15px; font-weight: 500; color: #303133; margin-bottom: 12px; line-height: 1.6; }
.q-options { margin-left: 8px; }
.option-group { display: flex; flex-direction: column; gap: 8px; }
.option-item { padding: 8px 12px; border: 1px solid #e8e8e8; border-radius: 8px; margin-right: 0 !important; }
.quiz-area { max-width: 900px; margin: 0 auto; }
.result-area { max-width: 700px; margin: 0 auto; }
.task-quiz-page { max-width: 960px; margin: 0 auto; }
.quiz-header { max-width: 900px; margin: 0 auto; }
.task-quiz-page { padding: 4px 0 30px; }
</style>
