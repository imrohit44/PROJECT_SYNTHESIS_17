import type { InputHTMLAttributes } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> { label: string; hint?: string; }

export function Field({ label, hint, id, ...props }: Props) {
  return <label className="field" htmlFor={id}><span>{label}</span><input id={id} {...props} />{hint && <small>{hint}</small>}</label>;
}
