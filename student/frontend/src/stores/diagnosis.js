import { defineStore } from 'pinia'
import { ref } from 'vue'
import { generateQuiz, submitQuiz, getQuizHistory, getQuizReport, getKnowledgeProfile } from '../api/diagnosis'

export const useDiagnosisStore = defineStore('diagnosis', () => {
  const currentQuiz = ref(null)
  const currentReport = ref(null)
  const history = ref([])
  const knowledgeProfile = ref(null)
  const loading = ref(false)

  async function startQuiz(stage = '入门', count = 10, useTimer = false, timerMinutes = 30, focusKnowledge = []) {
    loading.value = true
    try {
      currentQuiz.value = await generateQuiz({
        stage,
        count,
        use_timer: useTimer,
        timer_minutes: timerMinutes,
        focus_knowledge: focusKnowledge.length > 0 ? focusKnowledge : null
      })
      currentReport.value = null
      return currentQuiz.value
    } finally {
      loading.value = false
    }
  }

  async function submitAnswers(sessionId, answers) {
    loading.value = true
    try {
      currentReport.value = await submitQuiz({ session_id: sessionId, answers })
      return currentReport.value
    } finally {
      loading.value = false
    }
  }

  function resetQuiz() {
    currentQuiz.value = null
    currentReport.value = null
    // 同时清除持久化数据，避免插件恢复旧状态
    try {
      localStorage.removeItem('diagnosis-store')
    } catch(e) {}
  }

  async function fetchHistory() {
    history.value = await getQuizHistory()
  }

  async function fetchReport(id) {
    return await getQuizReport(id)
  }

  async function fetchProfile() {
    knowledgeProfile.value = await getKnowledgeProfile()
  }

  return { currentQuiz, currentReport, history, knowledgeProfile, loading, startQuiz, submitAnswers, resetQuiz, fetchHistory, fetchReport, fetchProfile }
}, {
  persist: {
    key: 'diagnosis-store',
    storage: localStorage,
    pick: ['currentQuiz']  // 只保存进行中的试卷，不保存已完成的结果
  }
})
