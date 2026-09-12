# Phase 1 Architecture

## Domain model

```text
Bank
 |-- registers --> Customer
 |                 |-- owns --> SavingsAccount
 |                 `-- owns --> CurrentAccount
 |
 `-- finds/co-ordinates --> Account
                              |-- records --> Transaction
                              `-- enforces --> balance and state invariants

TransferService
 `-- validates and co-ordinates --> source Account + destination Account
```

The domain package has no FastAPI imports. It can be used from a Python script, a test, or a future API adapter.

## Entity responsibilities

### Customer

`Customer` stores identity information and composes the accounts owned by that customer. It does not authenticate users, store passwords, or perform banking operations.

### Account

`Account` is the abstract base for shared account behavior: identity, owner association, balance encapsulation, state transitions, deposits, withdrawals, and transaction history. Its balance is exposed read-only and can change only through domain operations.

### SavingsAccount

`SavingsAccount` specializes withdrawal validation with a minimum-balance rule and provides interest calculation/application. The educational rule is deliberately simple and is not a regulatory model.

### CurrentAccount

`CurrentAccount` specializes withdrawal validation with an overdraft limit and exposes available balance as `balance + overdraft_limit`.

### Transaction

`Transaction` is an immutable record of a completed operation. It contains type, amount, account references, status, identifier, and UTC timestamp. A record cannot be edited after creation.

### Bank

`Bank` is a registry and coordination boundary. It registers customers, creates and finds accounts, and delegates transfers. It does not own account withdrawal rules or become the place where every business rule accumulates.

### TransferService

`TransferService` owns the multi-account transfer workflow. It validates source, destination, amount, and source funds before mutating either account. This keeps `Bank` small and gives the cross-account operation a clear home.

## Important invariants

- Amounts must be positive and are rounded to two decimal places using `ROUND_HALF_EVEN`.
- Floats are rejected for money inputs.
- An account must be active to deposit, withdraw, or participate in a transfer.
- Closed accounts cannot be reactivated.
- Savings withdrawals cannot breach the configured minimum balance.
- Current withdrawals cannot exceed balance plus overdraft limit.
- A transfer cannot use the same source and destination.
- A failed transfer changes neither balance nor transaction history.
- Transactions are immutable records of successful operations.

## Why the boundaries matter

Business rules live in the domain objects rather than in HTTP routes. A future API route should translate a request into a domain call and translate domain exceptions into an HTTP response. It should not decide whether an account may withdraw or whether a transfer is valid.

Persistence is intentionally postponed. The in-memory objects demonstrate the rules first. Phase 3 will add database transactions for durable, persistence-level atomicity; that is a different guarantee from the current pre-validation approach.
