import { Session } from "@inrupt/solid-client-authn-browser";

// Create a Solid session for authentication
export const session = new Session();

// Restore a previous Solid session, if any, and handle redirects coming back
// from the identity provider. This should be awaited before rendering the app
// so that `session.info` is up to date.
export async function restoreSession(): Promise<void> {
  if (typeof window === "undefined") return;
  await session.handleIncomingRedirect({
    url: window.location.href,
    restorePreviousSession: true,
  });
}

// Login with a specific OIDC issuer
export async function solidLogin(issuer: string): Promise<void> {
  await session.login({
    oidcIssuer: issuer,
    redirectUrl: window.location.href,
    clientName: "DINa ESG Reporting",
  });
}

// Logout from the Solid session
export async function solidLogout(): Promise<void> {
  await session.logout();
}

// Check if user is logged in
export function isLoggedIn(): boolean {
  return session.info.isLoggedIn;
}

// Get the user's WebID
export function getWebId(): string | undefined {
  return session.info.webId;
}

// Authenticated fetch for API calls
export const authenticatedFetch = session.fetch.bind(session);

// Get the session ID (can be used for session-based authentication)
export function getSessionId(): string | undefined {
  return session.info.sessionId;
}

// Get the access token for backend API calls
// Note: This accesses internal session properties and may not be officially supported.
// The token is DPoP-bound, so it may only work with Solid servers that accept DPoP tokens.
// For production, consider using server-side authentication or proxying requests.
export async function getAccessToken(): Promise<string | undefined> {
  // The Inrupt library stores the token internally
  // We try to access it through the session's internal token storage
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sessionInternal = session as any;

    // Check if there's an internal token manager
    if (sessionInternal.tokenRequestInProgress) {
      // Wait for any in-progress token request
      await sessionInternal.tokenRequestInProgress;
    }

    // Try to get token from internal storage
    if (sessionInternal.info?.sessionId) {
      // The session ID can be used to identify the session
      // but the actual access token is managed internally
      const sessionId = sessionInternal.info.sessionId;

      // Check browser storage for token (used by Inrupt library)
      const storageKey = `solidClientAuthenticationUser:${sessionId}`;
      const storedSession = localStorage.getItem(storageKey);

      if (storedSession) {
        const sessionData = JSON.parse(storedSession);
        if (sessionData.accessToken) {
          return sessionData.accessToken;
        }
      }
    }
  } catch (error) {
    console.warn('Could not retrieve Solid access token:', error);
  }

  return undefined;
}
