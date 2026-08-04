# Python OOP Banking System

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A lightweight, console-based banking system built entirely in Python. This project serves as a practical demonstration of the four core pillars of Object-Oriented Programming (OOP): **Encapsulation**, **Abstraction**, **Inheritance**, and **Polymorphism**.

##  Features

* **Account Creation**: Open different types of accounts (Savings, Current).
* **Deposits & Withdrawals**: Securely add or remove funds with validation checks.
* **Overdraft Protection**: Current accounts support a customizable overdraft limit.
* **Interest Application**: Savings accounts can accumulate interest on their balance.
* **Secure Ledger**: Account balances are protected from direct external modification.

##  OOP Concepts Demonstrated

This repository is designed to be an educational tool for understanding OOP principles:

1. **Encapsulation**
   * The `__balance` attribute in the `Account` class is private. It cannot be directly modified from outside the class, ensuring financial data integrity. It is securely accessed and modified via `deposit()` and `withdraw()` methods.
2. **Abstraction**
   * The base `Account` class is an Abstract Base Class (`ABC`). It defines a template that cannot be instantiated directly.
   * The `@abstractmethod` decorator enforces that all child classes must implement their own specific `withdraw` logic.
3. **Inheritance**
   * `SavingsAccount` and `CurrentAccount` both inherit core attributes (name, account number) and methods (deposit, display details) from the parent `Account` class, promoting code reusability.
4. **Polymorphism**
   * The `withdraw()` method is shared across account types but behaves differently. A `SavingsAccount` strictly prevents negative balances, whereas a `CurrentAccount` allows withdrawal up to a defined overdraft limit.

##  Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/python-oop-banking-system.git
   cd python-oop-banking-system
   ```

2. **Run the application:**
   No external dependencies are required. Just run the main Python script:
   ```bash
   python main.py
   ```

##  Project Structure

```text
python-oop-banking-system/
│
├── main.py          # Contains the BankSystem, Account classes, and test execution
└── README.md        # Project documentation
```


##  License

This project is open-source and available under the MIT License.
