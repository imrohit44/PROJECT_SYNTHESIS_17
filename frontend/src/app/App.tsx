import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { AdminRoute, ProtectedRoute } from "../components/layout/ProtectedRoute";
import { Dashboard } from "../pages/Dashboard";
import { Login } from "../pages/Login";
import { Register } from "../pages/Register";
import { Accounts } from "../pages/Accounts";
import { CreateAccount } from "../pages/CreateAccount";
import { AccountDetails } from "../pages/AccountDetails";
import { Transactions } from "../pages/Transactions";
import { Transfer } from "../pages/Transfer";
import { AdminUsers } from "../pages/AdminUsers";
import { Profile } from "../pages/Profile";

export function App() {
  return <Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/register" element={<Register />} />
    <Route element={<ProtectedRoute />}>
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/accounts/new" element={<CreateAccount />} />
        <Route path="/accounts/:accountId" element={<AccountDetails />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/transfer" element={<Transfer />} />
        <Route path="/profile" element={<Profile />} />
        <Route element={<AdminRoute />}><Route path="/admin/users" element={<AdminUsers />} /></Route>
      </Route>
    </Route>
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes>;
}
