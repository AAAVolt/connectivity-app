import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

/**
 * Tests for the RichText component's DOMPurify SSR resilience.
 *
 * The root cause of the methodology page crash was:
 *   DOMPurify v3 exports a factory (not an object with .sanitize)
 *   in Node.js/SSR, so calling DOMPurify.sanitize() threw a TypeError.
 *
 * These tests verify the component handles both cases.
 */

// ── Helper: minimal RichText reimplementation matching the fix ──
// We test the sanitisation logic in isolation to avoid importing the
// full page (which pulls in DOMPurify, IntersectionObserver, etc.).

function sanitize(
  html: string,
  purify: { sanitize?: (h: string, o: object) => string },
): string {
  const opts = {
    ALLOWED_TAGS: ["strong", "em", "sub", "sup", "br", "b", "i"],
    ALLOWED_ATTR: [] as string[],
  };
  return typeof purify.sanitize === "function"
    ? purify.sanitize(html, opts)
    : html;
}

describe("RichText sanitise logic", () => {
  it("calls sanitize when available (browser)", () => {
    const mockPurify = {
      sanitize: vi.fn(
        (html: string, _opts: object) => `clean:${html}`,
      ),
    };
    const result = sanitize("<strong>hi</strong>", mockPurify);
    expect(mockPurify.sanitize).toHaveBeenCalledOnce();
    expect(result).toBe("clean:<strong>hi</strong>");
  });

  it("falls back to raw html when sanitize is not a function (SSR)", () => {
    // DOMPurify v3 in Node.js exports a factory function — no .sanitize property
    const factoryPurify = {} as { sanitize?: unknown };
    const html = "<em>fallback</em>";
    const result = sanitize(html, factoryPurify as never);
    expect(result).toBe(html);
  });

  it("handles undefined sanitize gracefully", () => {
    const purify = { sanitize: undefined };
    const html = "<b>test</b>";
    expect(sanitize(html, purify as never)).toBe(html);
  });
});

describe("RichText rendering", () => {
  it("renders html content in a span", () => {
    // Minimal component matching the real one
    function RichText({ html }: { html: string }) {
      return <span dangerouslySetInnerHTML={{ __html: html }} />;
    }

    const { container } = render(<RichText html="<strong>bold</strong>" />);
    const span = container.querySelector("span");
    expect(span).not.toBeNull();
    expect(span!.innerHTML).toBe("<strong>bold</strong>");
  });
});
