// Byline: Codex · GPT-5.6-Sol · 2026-08-30
import { useLocation, useRouter } from "@tanstack/react-router";
import { useMemo, type AnchorHTMLAttributes, type MouseEvent } from "react";

export interface AppLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  href: string;
}

export function AppLink({ href, onClick, target, ...props }: AppLinkProps) {
  const router = useRouter();

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (
      event.defaultPrevented
      || event.button !== 0
      || event.metaKey
      || event.ctrlKey
      || event.shiftKey
      || event.altKey
      || target
    ) {
      return;
    }
    event.preventDefault();
    void router.navigate({ href });
  };

  return <a href={href} target={target} onClick={handleClick} {...props} />;
}

export function useCurrentPath() {
  return useLocation({ select: (location) => location.pathname });
}

export function useBrowserSearchParams() {
  const search = useLocation({ select: (location) => location.searchStr });
  return useMemo(() => new URLSearchParams(search), [search]);
}

export function useAppNavigate() {
  const router = useRouter();
  return {
    push: (href: string) => router.navigate({ href }),
    replace: (href: string) => router.navigate({ href, replace: true }),
  };
}
