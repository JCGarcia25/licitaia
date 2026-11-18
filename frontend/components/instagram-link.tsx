import { buttonStyles } from "@/lib/button-styles";

export const INSTAGRAM_URL = "https://www.instagram.com/mysecop/";

export function InstagramLink() {
  return (
    <a
      href={INSTAGRAM_URL}
      target="_blank"
      rel="noopener noreferrer"
      className={buttonStyles({ variant: "outline", className: "w-full sm:w-auto" })}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="h-5 w-5 shrink-0" aria-hidden="true" focusable="false">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
      </svg>
      <span>Instagram · @mysecop</span>
      <span aria-hidden="true">↗</span>
      <span className="sr-only">(se abre en una nueva pestaña)</span>
    </a>
  );
}
