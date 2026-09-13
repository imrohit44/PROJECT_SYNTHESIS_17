import { Plus, WalletCards } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, apiMessage } from "../lib/api";
import { formatMoney } from "../lib/format";
import type { Account } from "../types/api";
import { Panel } from "../components/ui/Panel";
import { Empty, ErrorState, Loading } from "../components/ui/Feedback";

export function Accounts() {
  const query = useQuery<Account[]>({ queryKey: ["accounts"], queryFn: async () => (await api.get("/accounts")).data });
  if (query.isLoading) return <Loading label="Loading accounts" />;
  if (query.isError) return <ErrorState message={apiMessage(query.error, "Unable to load your accounts.")} />;
  const accounts = query.data ?? [];
  return <div><div className="page-heading"><div><span className="eyebrow">Portfolio</span><h1>Accounts</h1><p className="muted">A clear view of every account you own.</p></div><Link className="button button-quiet" to="/accounts/new"><Plus size={17} /> New account</Link></div>{accounts.length === 0 ? <Panel><Empty title="Nothing here yet" detail="Create your first account to get started." /></Panel> : <div className="account-list">{accounts.map((account) => <Link className="account-row" to={`/accounts/${account.account_id}`} key={account.account_id}><span className={`account-icon ${account.account_type}`}><WalletCards size={19} /></span><div><strong>{account.account_type} account</strong><small>•• {account.account_id.slice(-8)}</small></div><span className="account-status"><i />{account.status}</span><strong className="row-balance">{formatMoney(account.balance)}</strong></Link>)}</div>}</div>;
}
