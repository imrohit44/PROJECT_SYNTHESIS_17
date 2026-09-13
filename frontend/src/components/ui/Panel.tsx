import type { ReactNode } from "react";

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) { return <section className={`panel ${className}`}>{children}</section>; }
