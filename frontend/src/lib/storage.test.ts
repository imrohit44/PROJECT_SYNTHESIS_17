import { describe, expect, it, beforeEach } from "vitest";
import { tokenStorage } from "./storage";

describe("tokenStorage", () => {
  beforeEach(() => tokenStorage.clear());

  it("stores and clears session tokens", () => {
    tokenStorage.set("access", "refresh");
    expect(tokenStorage.accessToken).toBe("access");
    expect(tokenStorage.refreshToken).toBe("refresh");
    tokenStorage.clear();
    expect(tokenStorage.accessToken).toBeNull();
    expect(tokenStorage.refreshToken).toBeNull();
  });
});
