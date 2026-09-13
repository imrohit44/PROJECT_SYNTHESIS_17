export function Loading({ label = "Loading" }: { label?: string }) { return <div className="feedback"><span className="spinner" aria-hidden="true" />{label}</div>; }
export function Empty({ title, detail }: { title: string; detail: string }) { return <div className="empty"><span>◌</span><strong>{title}</strong><p>{detail}</p></div>; }
export function ErrorState({ message }: { message: string }) { return <div className="alert alert-error" role="alert">{message}</div>; }
