import apiClient from '@/api/client'
import type {
  FaceEnrollment,
  FaceEnrollmentDetail,
  FaceEnrollmentCreatePayload,
} from '@/types/api'

export const faceEnrollmentService = {
  async listEmployeeEnrollments(
    employeeId: number,
    params?: {
      is_template?: boolean
      is_active?: boolean
      model_name?: string
    }
  ): Promise<FaceEnrollment[]> {
    const response = await apiClient.get<FaceEnrollment[]>(
      `/api/v1/employees/${employeeId}/face-enrollments`,
      { params }
    )
    return response.data
  },

  async getEnrollmentById(embeddingId: number): Promise<FaceEnrollmentDetail> {
    const response = await apiClient.get<FaceEnrollmentDetail>(
      `/api/v1/face-enrollments/${embeddingId}`
    )
    return response.data
  },

  async enrollFaceTemplate(
    employeeId: number,
    data: FaceEnrollmentCreatePayload
  ): Promise<FaceEnrollmentDetail> {
    const response = await apiClient.post<FaceEnrollmentDetail>(
      `/api/v1/employees/${employeeId}/face-enrollments`,
      data
    )
    return response.data
  },

  async deactivateEnrollment(embeddingId: number): Promise<FaceEnrollment> {
    const response = await apiClient.delete<FaceEnrollment>(
      `/api/v1/face-enrollments/${embeddingId}`
    )
    return response.data
  },

  async setPrimaryTemplate(embeddingId: number): Promise<FaceEnrollmentDetail> {
    const response = await apiClient.post<FaceEnrollmentDetail>(
      `/api/v1/face-enrollments/${embeddingId}/set-primary`
    )
    return response.data
  },
}
