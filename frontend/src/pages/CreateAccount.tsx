import { useState, type FormEvent } from "react";
import { ArrowLeft, Plus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, apiMessage } from "../lib/api";
import { useAuth } from "../app/AuthContext";
import { Panel } from "../components/ui/Panel";
import { Field } from "../components/ui/Field";
import { Button } from "../components/ui/Button";

export function CreateAccount() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [type, setType] = useState<"savings" | "current">("savings");
  const [openingBalance, setOpeningBalance] = useState("0.00");
  const [overdraft, setOverdraft] = useState("0.00");
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: async () => (await api.post("/accounts", {
      customer_id: user?.customer_id,
      account_type: type,
      opening_balance: openingBalance,
      overdraft_limit: overdraft,
    })).data,
    onSuccess: (account: { account_id: string }) => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      navigate(`/accounts/${account.account_id}`);
    },
  });
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try { await mutation.mutateAsync(); } catch (err) { setError(apiMessage(err, "The account could not be created.")); }
  }
  return <div className="narrow-page"><Link className="back-link" to="/accounts"><ArrowLeft size={15} /> Back to accounts</Link><div className="page-heading"><div><span className="eyebrow">Portfolio</span><h1>New account</h1><p className="muted">Choose a simple account structure to get started.</p></div></div><Panel><form className="stack" onSubmit={submit}><label className="field"><span>Account type</span><select className="select" value={type} onChange={(event) => setType(event.target.value as "savings" | "current")}><option value="savings">Savings account</option><option value="current">Current account</option></select></label><Field id="opening-balance" label="Opening balance" inputMode="decimal" value={openingBalance} onChange={(event) => setOpeningBalance(event.target.value)} required />{type === "current" && <Field id="overdraft-limit" label="Overdraft limit" inputMode="decimal" value={overdraft} onChange={(event) => setOverdraft(event.target.value)} required />}{error && <div className="alert alert-error">{error}</div>}<Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Creating…" : "Create account"}<Plus size={17} /></Button></form></Panel></div>;
}
