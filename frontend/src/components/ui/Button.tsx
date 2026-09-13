import type { ButtonHTMLAttributes, ReactNode } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> { children: ReactNode; variant?: "primary" | "quiet" | "danger"; }

export function Button({ children, variant = "primary", className = "", ...props }: Props) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>;
}
