import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "./AuthLayout";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { useAuth } from "../app/AuthContext";
import { apiMessage } from "../lib/api";

export function Login() { const { login } = useAuth(); const navigate = useNavigate(); const location = useLocation(); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) { event.preventDefault(); setError(""); setBusy(true); try { await login({ email, password }); navigate((location.state as { from?: string } | null)?.from ?? "/dashboard", { replace: true }); } catch (err) { setError(apiMessage(err, "Invalid email or password.")); } finally { setBusy(false); } }
  return <AuthLayout title="Sign in" detail="Pick up where you left off."><form onSubmit={submit} className="stack"><Field id="login-email" label="Email address" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required /><Field id="login-password" label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />{error && <div className="alert alert-error" role="alert">{error}</div>}<Button type="submit" disabled={busy}>{busy ? "Signing in…" : "Continue"}<ArrowRight size={17} /></Button><p className="form-foot">New to PyBank? <Link to="/register">Create an account</Link></p></form></AuthLayout>; }
