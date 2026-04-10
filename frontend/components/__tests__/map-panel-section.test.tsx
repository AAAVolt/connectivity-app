import { describe, expect, it, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { MapPanelSection } from "../map/map-panel-section";

describe("MapPanelSection", () => {
  it("renders the title", () => {
    const { getByText } = render(
      <MapPanelSection title="Test Section" open={false} onToggle={() => {}}>
        <p>Content</p>
      </MapPanelSection>,
    );
    expect(getByText("Test Section")).toBeTruthy();
  });

  it("shows children when open", () => {
    const { getByText } = render(
      <MapPanelSection title="Open Section" open={true} onToggle={() => {}}>
        <p>Visible content</p>
      </MapPanelSection>,
    );
    expect(getByText("Visible content")).toBeTruthy();
  });

  it("hides children when closed", () => {
    const { queryByText } = render(
      <MapPanelSection title="Closed Section" open={false} onToggle={() => {}}>
        <p>Hidden content</p>
      </MapPanelSection>,
    );
    expect(queryByText("Hidden content")).toBeNull();
  });

  it("calls onToggle when trigger is clicked", () => {
    const onToggle = vi.fn();
    const { getByText } = render(
      <MapPanelSection title="Clickable" open={false} onToggle={onToggle}>
        <p>Content</p>
      </MapPanelSection>,
    );
    fireEvent.click(getByText("Clickable"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("renders a chevron icon", () => {
    const { container } = render(
      <MapPanelSection title="With Chevron" open={true} onToggle={() => {}}>
        <p>Content</p>
      </MapPanelSection>,
    );
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
  });

  it("has bottom border for visual separation", () => {
    const { container } = render(
      <MapPanelSection title="Bordered" open={false} onToggle={() => {}}>
        <p>Content</p>
      </MapPanelSection>,
    );
    // The border-b class is on the div wrapping the Collapsible content
    const borderEl = container.querySelector(".border-b");
    expect(borderEl).toBeTruthy();
  });
});
