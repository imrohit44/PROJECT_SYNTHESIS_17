export type UserRole = "customer" | "admin";
export type AccountStatus = "active" | "frozen" | "closed";
export type TransactionType = "deposit" | "withdrawal" | "transfer" | "interest" | "fee";
export type TransactionStatus = "pending" | "completed" | "failed";

export interface CurrentUser {
  user_id: string;
  customer_id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface Account {
  account_id: string;
  customer_id: string;
  account_type: "savings" | "current";
  balance: string;
  status: AccountStatus;
  available_balance: string | null;
  interest_rate: string | null;
  minimum_balance: string | null;
  overdraft_limit: string | null;
}

export interface Transaction {
  transaction_id: string;
  transaction_type: TransactionType;
  amount: string;
  timestamp: string;
  status: TransactionStatus;
  source_account_id: string | null;
  destination_account_id: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export interface ErrorResponse {
  error: { code: string; message: string };
}

export interface RegisterRequest {
  name: string;
  email: string;
  phone?: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export type ToolCallStatus = "success" | "error" | "failed";

export interface AssistantToolCall {
  tool: string;
  status: ToolCallStatus;
  detail: string | null;
}

export interface AssistantChatResponse {
  response: string;
  conversation_id: string | null;
  tool_calls: AssistantToolCall[];
}
