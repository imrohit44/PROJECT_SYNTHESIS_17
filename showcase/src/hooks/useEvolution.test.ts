import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useEvolution } from "./useEvolution";

describe("useEvolution", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts at phase 0, paused", () => {
    const { result } = renderHook(() => useEvolution());
    expect(result.current.phase).toBe(0);
    expect(result.current.playing).toBe(false);
    expect(result.current.atStart).toBe(true);
  });

  it("steps and clamps with next and prev", () => {
    const { result } = renderHook(() => useEvolution());
    act(() => result.current.prev());
    expect(result.current.phase).toBe(0);
    act(() => result.current.next());
    expect(result.current.phase).toBe(1);
    act(() => result.current.seek(99));
    expect(result.current.phase).toBe(16);
    expect(result.current.atEnd).toBe(true);
  });

  it("seeks from the scrubber and clamps below zero", () => {
    const { result } = renderHook(() => useEvolution());
    act(() => result.current.seek(9));
    expect(result.current.phase).toBe(9);
    act(() => result.current.seek(-4));
    expect(result.current.phase).toBe(0);
  });

  it("advances on a timer while playing and stops at the last phase", () => {
    const { result } = renderHook(() => useEvolution());
    act(() => result.current.seek(15));
    act(() => result.current.play());
    expect(result.current.playing).toBe(true);

    act(() => vi.advanceTimersByTime(5200));
    expect(result.current.phase).toBe(16);
    expect(result.current.playing).toBe(false);
  });

  it("restarts from the first phase when play is pressed at the end", () => {
    const { result } = renderHook(() => useEvolution());
    act(() => result.current.seek(16));
    act(() => result.current.play());
    expect(result.current.phase).toBe(0);
    expect(result.current.playing).toBe(true);
  });
});
