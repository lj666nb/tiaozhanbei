/**
 * 课程 API — 学生端
 * 通过 nginx 代理调用教师端后端 /api/course-mgmt/
 * 注意：教师端返回 { success, data } 格式，不等同于学生端 { code } 格式，
 * 因此使用独立 axios 而非共享 request.js
 */
import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 120000 })

/** 获取全部课程列表 */
export function listCourses(semester = '') {
  return api.get('/course-mgmt/courses', { params: { semester } })
}

/** 获取单门课程详情 */
export function getCourse(courseId) {
  return api.get(`/course-mgmt/courses/${courseId}`)
}

/** 通过班级编号加入课程 */
export function joinByCode(code, studentName) {
  return api.post('/course-mgmt/join-by-code', {
    code,
    student_name: studentName,
  })
}
