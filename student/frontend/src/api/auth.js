import request from './request'

export const login = (data) => request.post('/auth/login', data)
export const register = (data) => request.post('/auth/register', data)
export const getProfile = () => request.get('/auth/me')
export const updateProfile = (data) => request.put('/auth/me', data)
export const verifyToken = () => request.get('/auth/verify')
