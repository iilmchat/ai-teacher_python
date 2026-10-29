import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from '@/components/ProtectedRoute';
import { AdminRoute } from '@/components/AdminRoute';
import { TeacherRoute } from '@/components/TeacherRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { Spinner } from '@/components/ui/Spinner';
import { useAuthStore } from '@/store/auth';

// Route-level code splitting (S19-002): страницы грузятся отдельными чанками.
const AdminPage = lazy(() =>
  import('@/pages/AdminPage').then((module) => ({ default: module.AdminPage })),
);
const AssignmentsPage = lazy(() =>
  import('@/pages/AssignmentsPage').then((module) => ({
    default: module.AssignmentsPage,
  })),
);
const ChatPage = lazy(() =>
  import('@/pages/ChatPage').then((module) => ({ default: module.ChatPage })),
);
const ClassroomsPage = lazy(() =>
  import('@/pages/ClassroomsPage').then((module) => ({
    default: module.ClassroomsPage,
  })),
);
const ClassroomDetailPage = lazy(() =>
  import('@/pages/ClassroomDetailPage').then((module) => ({
    default: module.ClassroomDetailPage,
  })),
);
const CodePage = lazy(() =>
  import('@/pages/CodePage').then((module) => ({ default: module.CodePage })),
);
const HomePage = lazy(() =>
  import('@/pages/HomePage').then((module) => ({ default: module.HomePage })),
);
const LoginPage = lazy(() =>
  import('@/pages/LoginPage').then((module) => ({ default: module.LoginPage })),
);
const NotFoundPage = lazy(() =>
  import('@/pages/NotFoundPage').then((module) => ({ default: module.NotFoundPage })),
);
const ProfilePage = lazy(() =>
  import('@/pages/ProfilePage').then((module) => ({ default: module.ProfilePage })),
);
const RegisterPage = lazy(() =>
  import('@/pages/RegisterPage').then((module) => ({ default: module.RegisterPage })),
);
const TaskDetailPage = lazy(() =>
  import('@/pages/TaskDetailPage').then((module) => ({
    default: module.TaskDetailPage,
  })),
);
const TasksPage = lazy(() =>
  import('@/pages/TasksPage').then((module) => ({ default: module.TasksPage })),
);
const TeacherStudentsPage = lazy(() =>
  import('@/pages/TeacherStudentsPage').then((module) => ({
    default: module.TeacherStudentsPage,
  })),
);
const TeacherTasksPage = lazy(() =>
  import('@/pages/TeacherTasksPage').then((module) => ({
    default: module.TeacherTasksPage,
  })),
);

function PageFallback() {
  return (
    <div className="flex justify-center py-16">
      <Spinner />
    </div>
  );
}

export function App() {
  const loadMe = useAuthStore((state) => state.loadMe);

  // После полной перезагрузки страницы восстанавливаем профиль по токену,
  // иначе ProtectedRoute навсегда остаётся в состоянии инициализации.
  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  return (
    <BrowserRouter>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="login" element={<LoginPage />} />
            <Route path="register" element={<RegisterPage />} />

            <Route
              path="chat"
              element={
                <ProtectedRoute>
                  <ChatPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="code"
              element={
                <ProtectedRoute>
                  <CodePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="tasks"
              element={
                <ProtectedRoute>
                  <TasksPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="classrooms"
              element={
                <ProtectedRoute>
                  <ClassroomsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="classrooms/:classroomId"
              element={
                <ProtectedRoute>
                  <ClassroomDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="assignments"
              element={
                <ProtectedRoute>
                  <AssignmentsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="tasks/:taskId"
              element={
                <ProtectedRoute>
                  <TaskDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />

            <Route
              path="admin"
              element={
                <ProtectedRoute>
                  <AdminRoute>
                    <AdminPage />
                  </AdminRoute>
                </ProtectedRoute>
              }
            />

            <Route
              path="teacher/tasks"
              element={
                <ProtectedRoute>
                  <TeacherRoute>
                    <TeacherTasksPage />
                  </TeacherRoute>
                </ProtectedRoute>
              }
            />
            <Route
              path="teacher/students"
              element={
                <ProtectedRoute>
                  <TeacherRoute>
                    <TeacherStudentsPage />
                  </TeacherRoute>
                </ProtectedRoute>
              }
            />

            <Route path="404" element={<NotFoundPage />} />
            <Route path="*" element={<Navigate to="/404" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
