import { Navigate } from "react-router-dom";

export default function ProtectedRoute({ isAuthenticated, children, requiredRole, userRole }) {
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  if (requiredRole && userRole !== requiredRole) {
    return <Navigate to="/chat" replace />;
  }
  return children;
}
