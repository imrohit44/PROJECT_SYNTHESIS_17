import { UsersRound } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, apiMessage } from "../lib/api";
import type { CurrentUser } from "../types/api";
import { Panel } from "../components/ui/Panel";
import { ErrorState, Loading, Empty } from "../components/ui/Feedback";

export function AdminUsers() { const query = useQuery<CurrentUser[]>({ queryKey: ["admin-users"], queryFn: async () => (await api.get("/users")).data }); if (query.isLoading) return <Loading label="Loading user directory" />; if (query.isError) return <ErrorState message={apiMessage(query.error, "You do not have access to this directory.")} />; return <div><div className="page-heading"><div><span className="eyebrow">Administration</span><h1>User directory</h1><p className="muted">A server-authorized view of PyBank identities.</p></div><span className="transfer-badge"><UsersRound size={16} /> Admin only</span></div><Panel>{query.data?.length ? <div className="user-table">{query.data.map((user) => <div className="user-row" key={user.user_id}><span className="avatar">{user.email.slice(0, 1).toUpperCase()}</span><div><strong>{user.email}</strong><small>{user.customer_id}</small></div><span className="role-pill">{user.role}</span><span className="status"><i />{user.is_active ? "active" : "inactive"}</span></div>)}</div> : <Empty title="No users" detail="The directory is empty." />}</Panel></div>; }
