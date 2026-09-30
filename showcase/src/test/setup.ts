/**
 * Vitest setup.
 *
 * Vitest runs without global test APIs, so React Testing Library cannot
 * auto-register its teardown. Unmounting after every test is what keeps the
 * jsdom document clean between renders — without it, a second render in the
 * same file sees the previous test's DOM and duplicate-name queries fail.
 */
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

afterEach(() => cleanup());
