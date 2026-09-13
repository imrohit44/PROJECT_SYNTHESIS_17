import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { AuthLayout } from "./AuthLayout";
import { Button } from "../components/ui/Button";
import { Field } from "../components/ui/Field";
import { useAuth } from "../app/AuthContext";
import { apiMessage } from "../lib/api";

export function Register() { const { register } = useAuth(); const navigate = useNavigate(); const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" }); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const update = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: event.target.value });
  async function submit(event: React.FormEvent) { event.preventDefault(); setError(""); if (form.password.length < 8) { setError("Use at least 8 characters for your password."); return; } setBusy(true); try { await register(form); navigate("/login", { state: { registered: true } }); } catch (err) { setError(apiMessage(err, "We could not create that account.")); } finally { setBusy(false); } }
  return <AuthLayout title="Open your account" detail="A simple beginning for better money habits."><form onSubmit={submit} className="stack"><Field id="register-name" label="Full name" value={form.name} onChange={update("name")} autoComplete="name" required /><Field id="register-email" label="Email address" type="email" value={form.email} onChange={update("email")} autoComplete="email" required /><Field id="register-phone" label="Phone (optional)" value={form.phone} onChange={update("phone")} autoComplete="tel" /><Field id="register-password" label="Password" type="password" value={form.password} onChange={update("password")} autoComplete="new-password" hint="At least 8 characters" required />{error && <div className="alert alert-error" role="alert">{error}</div>}<Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create account"}<ArrowRight size={17} /></Button><p className="form-foot">Already registered? <Link to="/login">Sign in</Link></p></form></AuthLayout>; }
