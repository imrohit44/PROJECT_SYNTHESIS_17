import { describe, expect, it } from "vitest";
import { AxiosError } from "axios";
import { apiMessage } from "./api";

describe("apiMessage", () => {
  it("extracts the backend error envelope", () => {
    const error = new AxiosError("request failed", "409", undefined, undefined, {
      data: { error: { code: "CONFLICT", message: "Account is frozen" } },
      status: 409,
      statusText: "Conflict",
      headers: {},
      config: {} as never,
    });
    expect(apiMessage(error)).toBe("Account is frozen");
  });

  it("falls back without exposing internals", () => {
    expect(apiMessage(new Error("database details"), "Try again")).toBe("Try again");
  });
});
