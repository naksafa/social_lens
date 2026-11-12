import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, errorMessage } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("parses structured backend errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "mapping_error", message: "Required field(s) are not mapped.", details: { missing: ["Publish date/time"] } }), {
          status: 422,
        }),
      ),
    );
    const err = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("mapping_error");
    expect(err.status).toBe(422);
    expect(errorMessage(err)).toBe("Required field(s) are not mapped. (Publish date/time)");
  });

  it("reports network failures clearly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const err = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("network_error");
  });

  it("returns JSON on success and undefined on 204", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: 1 }), { status: 200 })));
    expect(await apiFetch("/x")).toEqual({ ok: 1 });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    expect(await apiFetch("/x")).toBeUndefined();
  });
});
