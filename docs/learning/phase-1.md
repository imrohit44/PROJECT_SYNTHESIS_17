# Learning Guide: Phase 1

## 1. What is a domain model?

A domain model is a software representation of the important concepts and rules in a problem area. PyBank's domain model represents customers, accounts, transactions, and banking operations without knowing how requests arrive or data is stored.

## 2. What is a domain entity?

An entity is an object with identity that remains meaningful across operations. A customer and account have generated identifiers, while their current state can change through valid domain operations.

## 3. Encapsulation

`Account` keeps its balance and status internally. Callers can read the balance, but they cannot assign an arbitrary value such as `-50000`; they must use `deposit`, `withdraw`, or a state operation that enforces invariants.

## 4. Abstraction

The abstract `Account` exposes the common banking vocabulary and requires each concrete account to implement withdrawal validation. Callers can use `withdraw` without knowing how savings and current rules differ.

## 5. Inheritance

`SavingsAccount` and `CurrentAccount` inherit from `Account` because each is genuinely an account and shares account identity, state, balance, and transaction behavior. Inheritance is not used for `Bank`, `Customer`, or `Transaction`; those relationships are composition or association.

## 6. Polymorphism

The base account workflow calls `_validate_withdrawal`. Savings accounts apply a minimum-balance rule, while current accounts apply an overdraft rule. The same public `withdraw` operation therefore has specialized behavior.

## 7. Composition

A customer owns account objects through an internal collection. A bank keeps registries of customers and accounts. These are "has-a" relationships, not reasons for inheritance.

## 8. SOLID in this implementation

- **Single Responsibility:** `Account` owns account invariants, `Transaction` stores an operation record, `Bank` indexes objects, and `TransferService` coordinates a two-account workflow. If all of this lived in `Bank`, changes would become risky and difficult to test.
- **Open/Closed:** New account types can implement the `Account` withdrawal policy without rewriting the shared deposit/state machinery. A large conditional in `Bank` would make every new account type invasive.
- **Liskov Substitution:** Both concrete account types can be used wherever an `Account` is expected because they preserve the base contract: valid active accounts accept permitted deposits and reject invalid withdrawals with domain errors.
- **Interface Segregation:** The model exposes small, focused operations instead of one broad service interface. Phase 1 does not invent interfaces where the problem does not require them.
- **Dependency Inversion:** `Bank` depends on the domain-level `TransferService` abstraction of the workflow rather than embedding transfer rules in HTTP or persistence code. A future adapter can depend on the domain without the domain depending on FastAPI.

## 9. Domain invariants

An invariant is a rule that must remain true after every successful operation. Examples include positive amounts, non-negative savings balances, valid account states, and no same-account transfers. Enforcing these rules at the domain boundary prevents invalid state from spreading to callers.

## 10. Domain exceptions

Specific exceptions such as `InvalidAmountError`, `InsufficientFundsError`, and `AccountNotActiveError` communicate the kind of business failure. Later, an API adapter can map them to appropriate HTTP responses without changing the domain operation.

## 11. Why Decimal is used

Binary floating-point cannot represent many decimal fractions exactly. Repeated operations with `float` can produce values such as `0.30000000000000004`. `Decimal` represents decimal arithmetic intentionally, and PyBank rounds to cents with `ROUND_HALF_EVEN` at its money boundary.

## 12. Why business logic should not live in API routes

Routes are delivery code. If a route decides withdrawal rules, a command-line client or scheduled job would need to duplicate those rules. Keeping decisions in the domain gives every entry point the same behavior and makes unit tests fast.

## 13. Why the domain is independent from FastAPI

FastAPI is a transport framework, not a banking rule engine. Independence lets the domain be tested and reused before HTTP exists, prevents framework details from leaking into entities, and makes a later API layer an adapter rather than the source of truth.

## 14. Why persistence is postponed

A database would introduce schema, migrations, repositories, connection management, and transaction semantics before the rules are understood. Phase 1 first proves the in-memory model. Phase 3 will add durable storage and database-level atomicity when there is a concrete persistence requirement.

## 15. Suggested experiments

- Try assigning to `account.balance` and observe that it has no setter.
- Freeze an account, attempt a deposit, then activate it and retry.
- Change a savings minimum balance and compare its withdrawal behavior with a current account.
- Attempt a failed transfer and inspect both transaction histories.
- Replace a `Decimal` input with a float and observe the deliberate rejection.
