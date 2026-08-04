from abc import ABC, abstractmethod
import random

# 1. Abstraction: Base class template that cannot be instantiated directly
class Account(ABC):
    def __init__(self, name, account_type):
        self.name = name
        self.account_type = account_type
        self.account_number = random.randint(10000, 99999)
        # 2. Encapsulation: Private attribute (indicated by __)
        self.__balance = 0.0  

    def deposit(self, amount):
        if amount > 0:
            self.__balance += amount
            print(f" Deposited ${amount:.2f}. New Balance: ${self.__balance:.2f}")
        else:
            print(" Invalid deposit amount.")

    # Abstract method: Forces child classes to implement their own withdrawal logic
    @abstractmethod
    def withdraw(self, amount):
        pass

    # Getter for private attribute
    def get_balance(self):
        return self.__balance

    # Setter (protected for child classes to use)
    def _set_balance(self, amount):
        self.__balance = amount

    def display_details(self):
        print(f"Account: {self.account_number} | Name: {self.name} | Type: {self.account_type} | Balance: ${self.__balance:.2f}")


# 3. Inheritance: SavingsAccount inherits from Account
class SavingsAccount(Account):
    def __init__(self, name):
        super().__init__(name, "Savings")
        self.interest_rate = 0.04  # 4% interest

    # 4. Polymorphism: Overriding the withdraw method for Savings rules
    def withdraw(self, amount):
        if 0 < amount <= self.get_balance():
            self._set_balance(self.get_balance() - amount)
            print(f" Withdrew ${amount:.2f}. New Balance: ${self.get_balance():.2f}")
        else:
            print(" Insufficient funds. Cannot withdraw.")

    def apply_interest(self):
        interest = self.get_balance() * self.interest_rate
        self.deposit(interest)
        print(f"📈 Applied 4% interest.")


# 3. Inheritance: CurrentAccount inherits from Account
class CurrentAccount(Account):
    def __init__(self, name):
        super().__init__(name, "Current")
        self.overdraft_limit = 500.0  # Allows negative balance up to $500

    # 4. Polymorphism: Overriding the withdraw method for Current rules
    def withdraw(self, amount):
        if 0 < amount <= (self.get_balance() + self.overdraft_limit):
            self._set_balance(self.get_balance() - amount)
            print(f" Withdrew ${amount:.2f}. New Balance: ${self.get_balance():.2f}")
        else:
            print(f" Overdraft limit exceeded. Max available to withdraw: ${(self.get_balance() + self.overdraft_limit):.2f}")


# System Manager Class to handle multiple accounts
class BankSystem:
    def __init__(self, bank_name):
        self.bank_name = bank_name
        self.accounts = {}  # Dictionary to store accounts by account_number

    def open_account(self, name, account_type):
        if account_type.lower() == 'savings':
            new_account = SavingsAccount(name)
        elif account_type.lower() == 'current':
            new_account = CurrentAccount(name)
        else:
            print(" Invalid account type. Choose 'Savings' or 'Current'.")
            return None

        self.accounts[new_account.account_number] = new_account
        print(f"\n🎉 Successfully opened a {account_type.capitalize()} account for {name}!")
        new_account.display_details()
        return new_account.account_number

    def get_account(self, account_number):
        return self.accounts.get(account_number, None)

# Testing the Banking System
if __name__ == "__main__":
    bank = BankSystem("Global Tech Bank")

    # 1. Create a Savings Account
    alice_acc_num = bank.open_account("Alice", "Savings")
    alice_account = bank.get_account(alice_acc_num)
    
    alice_account.deposit(1000)
    alice_account.withdraw(200)
    alice_account.apply_interest()
    
    # 2. Create a Current Account
    bob_acc_num = bank.open_account("Bob", "Current")
    bob_account = bank.get_account(bob_acc_num)
    
    bob_account.deposit(200)
    # Testing overdraft feature specific to Current Account
    bob_account.withdraw(600)  # Will work because of $500 overdraft limit
    bob_account.withdraw(200)  # Will fail, exceeds overdraft
    
    print("\n--- Final Bank Overview ---")
    alice_account.display_details()
    bob_account.display_details()
