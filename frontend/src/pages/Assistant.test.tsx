import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosError } from "axios";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { sendAssistantMessage } from "../lib/api";
import { Assistant } from "./Assistant";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, sendAssistantMessage: vi.fn() };
});

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Assistant />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function ask(question: string) {
  fireEvent.change(screen.getByLabelText(/your question/i), {
    target: { value: question },
  });
  fireEvent.click(screen.getByRole("button", { name: /send/i }));
}

/**
 * Fail exactly like the API layer does (an axios error carrying the backend
 * envelope). The rejection is pre-handled so it can never surface as a
 * process-level unhandled rejection; React Query's consumers still see it.
 */
function assistantFailure(message: string): Promise<never> {
  const failure = new AxiosError("request failed", "503", undefined, undefined, {
    data: { error: { code: "HTTP_ERROR", message } },
    status: 503,
    statusText: "Service Unavailable",
    headers: {},
    config: {} as never,
  });
  const rejected = Promise.reject<never>(failure);
  rejected.catch(() => undefined);
  return rejected;
}

describe("Assistant", () => {
  // NOTE: keep this hook body in braces. `mockReset()` returns the mock
  // function itself, and an expression-bodied hook would return it — the
  // Vitest runner then registers that mock as a per-test cleanup and calls
  // it after every test, re-invoking the mock's current (possibly rejecting)
  // implementation and failing the test with that rejection.
  beforeEach(() => {
    vi.mocked(sendAssistantMessage).mockReset();
  });

  it("starts read-only and empty", () => {
    renderPage();

    expect(screen.getByText("Read-only")).toBeInTheDocument();
    expect(screen.getByText("Ask a question")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("sends a question and shows the answer with the tool calls used", async () => {
    vi.mocked(sendAssistantMessage).mockResolvedValue({
      response: "Your savings balance is 100.00.",
      conversation_id: null,
      tool_calls: [{ tool: "get_account_summary", status: "success", detail: null }],
    });
    renderPage();

    ask("What is my balance?");

    await waitFor(() =>
      expect(sendAssistantMessage).toHaveBeenCalledWith(
        "What is my balance?",
        expect.anything(),
      ),
    );
    expect(screen.getByText("What is my balance?")).toBeInTheDocument();
    expect(await screen.findByText("Your savings balance is 100.00.")).toBeInTheDocument();
    expect(screen.getByText(/get_account_summary/)).toBeInTheDocument();
  });

  it("surfaces rejected tools without leaking internals", async () => {
    vi.mocked(sendAssistantMessage).mockResolvedValue({
      response: "I cannot run that.",
      conversation_id: null,
      tool_calls: [{ tool: "execute_cypher", status: "error", detail: "Unknown tool" }],
    });
    renderPage();

    ask("Run a graph query");

    expect(await screen.findByText("I cannot run that.")).toBeInTheDocument();
    expect(screen.getByText(/execute_cypher/)).toHaveClass("chat-tool", "error");
  });

  it("shows the backend message when the assistant is unavailable", async () => {
    vi.mocked(sendAssistantMessage).mockImplementation(() =>
      assistantFailure("The banking assistant is not configured"),
    );
    renderPage();

    ask("hello");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The banking assistant is not configured",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("LLM_API_KEY");
  });

  it("never sends an empty question", () => {
    renderPage();

    fireEvent.change(screen.getByLabelText(/your question/i), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(sendAssistantMessage).not.toHaveBeenCalled();
    expect(screen.queryByRole("log")).not.toBeInTheDocument();
  });
});
