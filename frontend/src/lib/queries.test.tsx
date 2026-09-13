import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { useAccount, useMoneyMutation, useTransactions } from "./queries";

vi.mock("./api", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

function wrapper(client: QueryClient) {
  return function TestWrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function testClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

describe("React Query banking hooks", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
  });

  it("loads account details through loading and success states", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        account_id: "account-1",
        customer_id: "customer-1",
        account_type: "savings",
        balance: "25.00",
        status: "active",
      },
    });
    const client = testClient();

    const { result } = renderHook(() => useAccount("account-1"), {
      wrapper: wrapper(client),
    });

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.balance).toBe("25.00");
  });

  it("surfaces transaction query errors for safe page rendering", async () => {
    vi.mocked(api.get).mockRejectedValue(new Error("network unavailable"));
    const client = testClient();

    const { result } = renderHook(() => useTransactions("account-1"), {
      wrapper: wrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("invalidates account and transaction data after deposits", async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        account_id: "account-1",
        customer_id: "customer-1",
        account_type: "savings",
        balance: "35.00",
        status: "active",
      },
    });
    const client = testClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useMoneyMutation("deposit", "account-1"), {
      wrapper: wrapper(client),
    });
    result.current.mutate("10.00");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["account", "account-1"] });
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ["transactions", "account-1"],
    });
  });
});
