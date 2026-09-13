import { Mail, ShieldCheck } from "lucide-react";
import { useAuth } from "../app/AuthContext";
import { Panel } from "../components/ui/Panel";

export function Profile() { const { user } = useAuth(); return <div className="narrow-page"><div className="page-heading"><div><span className="eyebrow">Your identity</span><h1>Profile</h1><p className="muted">Account access and security details.</p></div></div><Panel><div className="profile-large"><div className="avatar large">{user?.email.slice(0, 1).toUpperCase()}</div><div><h2>{user?.email}</h2><span className="role-pill"><ShieldCheck size={14} />{user?.role}</span></div></div><dl className="details-list profile-details"><div><dt>Email</dt><dd><Mail size={15} />{user?.email}</dd></div><div><dt>Customer ID</dt><dd className="mono">{user?.customer_id}</dd></div><div><dt>Session</dt><dd className="positive">Active and protected</dd></div></dl></Panel></div>; }
