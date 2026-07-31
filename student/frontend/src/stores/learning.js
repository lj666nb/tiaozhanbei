import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  generateLearningPath, getLearningPath, deleteLearningPath, generateDiagnosticTest,
  getDailyTasks, completeTask,
  getErrorBook, updatePathProgress, getErrorSessions, getErrorsBySession,
  getOrphanErrors, deleteSessionErrors, deleteOrphanErrors, batchDeleteErrors,
  reviewSessionErrors
} from '../api/learning'

export const useLearningStore = defineStore('learning', () => {
  const currentPath = ref(null)
  const dailyTasks = ref(null)
  const errorBook = ref({ items: [], total: 0 })
  const errorSessions = ref([])
  const sessionErrors = ref({ items: [], total: 0 })
  const loading = ref(false)

  async function createPath(goal = '', timeline = '', learning_depth = '标准', diagnosticSessionId = null, modules = null) {
    loading.value = true
    try {
      currentPath.value = await generateLearningPath({
        goal, timeline, learning_depth,
        diagnostic_session_id: diagnosticSessionId,
        modules: modules
      })
      return currentPath.value
    } finally {
      loading.value = false
    }
  }

  async function removePath() {
    loading.value = true
    try {
      await deleteLearningPath()
      currentPath.value = null
    } finally {
      loading.value = false
    }
  }

  async function createDiagnosticTest(goal = '', count = 10) {
    loading.value = true
    try {
      return await generateDiagnosticTest({ goal, count })
    } finally {
      loading.value = false
    }
  }

  async function fetchPath() {
    const data = await getLearningPath()
    currentPath.value = data
    return data
  }

  async function updateProgress(taskKey, completed = true, subAction = null) {
    const data = { task_key: taskKey, completed }
    if (subAction) data.sub_action = subAction
    await updatePathProgress(data)
    const path = await getLearningPath()
    currentPath.value = path
    return path
  }

  async function fetchTasks(date = null) {
    const data = await getDailyTasks(date)
    dailyTasks.value = data
    return data
  }

  async function finishTask(date = '', completed = 1) {
    await completeTask({ completed }, date)
    return await fetchTasks(date)
  }

  async function fetchErrorBook(page = 1) {
    const data = await getErrorBook(page)
    errorBook.value = data
    return data
  }

  async function fetchErrorSessions() {
    errorSessions.value = await getErrorSessions()
    return errorSessions.value
  }

  async function fetchSessionErrors(sessionId, page = 1) {
    if (sessionId != null) {
      sessionErrors.value = await getErrorsBySession(sessionId, page)
    } else {
      sessionErrors.value = await getOrphanErrors(page)
    }
    return sessionErrors.value
  }

  async function removeSession(sessionId) {
    if (sessionId != null) {
      await deleteSessionErrors(sessionId)
    } else {
      await deleteOrphanErrors()
    }
    return await fetchErrorSessions()
  }

  async function reviewSession(sessionId) {
    const result = await reviewSessionErrors(sessionId)
    return result
  }

  async function deleteErrors(ids) {
    await batchDeleteErrors(ids)
    return await fetchErrorBook()
  }

  return {
    currentPath, dailyTasks, errorBook, errorSessions, sessionErrors, loading,
    createPath, removePath, createDiagnosticTest,
    fetchPath, updateProgress, fetchTasks, finishTask,
    fetchErrorBook, fetchErrorSessions, fetchSessionErrors, removeSession, reviewSession, deleteErrors
  }
})
