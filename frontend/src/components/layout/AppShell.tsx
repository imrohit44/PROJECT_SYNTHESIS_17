import { CreditCard, LayoutDashboard, LogOut, ReceiptText, ShieldCheck, Send, Sparkles, UserRound } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../app/AuthContext";

export function AppShell() {
  const { user, logout } = useAuth();
  const links = [
    { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/accounts", label: "Accounts", icon: CreditCard },
    { to: "/transactions", label: "Transactions", icon: ReceiptText },
    { to: "/assistant", label: "Assistant", icon: Sparkles },
    { to: "/transfer", label: "Move money", icon: Send },
  ];
  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">P</span><span>PyBank</span></div><div className="profile"><div className="avatar">{user?.email.slice(0, 1).toUpperCase()}</div><div><strong>{user?.email.split("@")[0]}</strong><small>{user?.role}</small></div></div><nav>{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to}><Icon size={18} />{label}</NavLink>)}{user?.role === "admin" && <NavLink to="/admin/users"><ShieldCheck size={18} />Admin</NavLink>}</nav><button className="logout" onClick={logout}><LogOut size={17} />Sign out</button></aside><main className="main-content"><header className="topbar"><div><span className="eyebrow">Personal banking / 2026</span><span className="secure"><ShieldCheck size={14} /> Secure session</span></div><NavLink className="icon-link" to="/profile" aria-label="View profile"><UserRound size={19} /></NavLink></header><div className="page-content"><Outlet /></div></main></div>;
}
