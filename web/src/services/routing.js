export const oauthReturnRouteStorageKey = "sezzions.oauthReturnRoute";

export function readCurrentRoute() {
  const hashRoute = window.location.hash.replace(/^#/, "").replace(/\/+$/, "") || "";
  const pathRoute = window.location.pathname.replace(/\/+$/, "") || "/";
  return hashRoute || pathRoute;
}

export function rememberOAuthReturnRoute(route) {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  window.sessionStorage.setItem(oauthReturnRouteStorageKey, route);
}

export function consumeOAuthReturnRoute() {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  const route = window.sessionStorage.getItem(oauthReturnRouteStorageKey);
  if (route) {
    window.sessionStorage.removeItem(oauthReturnRouteStorageKey);
  }
  return route;
}

export function applyRoute(route) {
  if (typeof window === "undefined" || !route) {
    return;
  }
  const normalizedRoute = route === "/" ? "/" : route.replace(/\/+$/, "");
  const nextHash = normalizedRoute === "/" ? "#/" : `#${normalizedRoute}`;
  if (window.location.hash !== nextHash) {
    window.location.hash = nextHash;
  }
}
