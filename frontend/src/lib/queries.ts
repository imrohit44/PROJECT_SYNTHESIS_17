import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Account, Transaction } from "../types/api";

export const queryKeys = { user: ["current-user"], accounts: ["accounts"] } as const;

export function useAccount(accountId: string | undefined) {
  return useQuery<Account>({ queryKey: ["account", accountId], queryFn: async () => (await api.get(`/accounts/${accountId}`)).data, enabled: Boolean(accountId) });
}

export function useTransactions(accountId: string | undefined) {
  return useQuery<Transaction[]>({ queryKey: ["transactions", accountId], queryFn: async () => (await api.get(`/accounts/${accountId}/transactions`)).data, enabled: Boolean(accountId) });
}

export function useMoneyMutation(path: string, accountId: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: async (amount: string) => (await api.post(`/accounts/${accountId}/${path}`, { amount })).data as Account, onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ["account", accountId] });
    void queryClient.invalidateQueries({ queryKey: ["transactions", accountId] });
  } });
}
