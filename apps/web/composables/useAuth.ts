import { createAuthClient } from "better-auth/vue";
import { twoFactorClient, multiSessionClient } from "better-auth/client/plugins";

// Same-origin client: requests go to /api/auth on whatever host served the page.
export const authClient = createAuthClient({
  plugins: [twoFactorClient(), multiSessionClient()],
});

// SSR-aware session: passing useFetch forwards the request cookies during SSR.
export const useAuthSession = () => authClient.useSession(useFetch);

// Auth state lives in cookies, so a full reload is the simplest way to make SSR and client agree.
export const reloadTo = (path: string) => {
  window.location.assign(path);
};
