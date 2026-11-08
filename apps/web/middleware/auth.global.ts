const PUBLIC_ROUTES = new Set(["/login", "/signup"]);

export default defineNuxtRouteMiddleware(async (to) => {
  if (PUBLIC_ROUTES.has(to.path)) return;

  // SSR: forward the request cookies via useFetch. Client navigation: ask the server fresh each time,
  // so a session revoked from another browser is noticed on the next click, not just the next reload.
  const signedIn = import.meta.server
    ? !!(await useAuthSession()).data.value
    : !!(await authClient.getSession()).data;

  if (!signedIn) {
    return navigateTo({ path: "/login", query: { redirect: to.fullPath } });
  }
});
