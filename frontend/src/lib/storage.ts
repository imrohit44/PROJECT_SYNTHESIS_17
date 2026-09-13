const ACCESS_KEY = "pybank.access_token";
const REFRESH_KEY = "pybank.refresh_token";

export const tokenStorage = {
  get accessToken() {
    return sessionStorage.getItem(ACCESS_KEY);
  },
  get refreshToken() {
    return sessionStorage.getItem(REFRESH_KEY);
  },
  set(accessToken: string, refreshToken: string) {
    sessionStorage.setItem(ACCESS_KEY, accessToken);
    sessionStorage.setItem(REFRESH_KEY, refreshToken);
  },
  clear() {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
  },
};
