export const oauthReturnRouteStorageKey = "sezzions.oauthReturnRoute";

export function readCurrentRoute() {
  const pathname = window.location.pathname.replace(/\/+$/, "") || "/";
  return pathname;
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
  if (window.location.pathname !== normalizedRoute) {
    window.history.replaceState(null, "", normalizedRoute);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
}
